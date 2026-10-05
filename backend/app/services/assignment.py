"""
services/assignment.py – Task assignment optimizer (spec §8.2).

Algorithm (viva-ready):
────────────────────────
For each (task, member) pair compute a score in [0, 1]:

  skill_match   = avg over required_skills of (member.skills.get(s, 0) / 5)
                  If task has no required_skills → 0.5 (neutral)

  availability  = clip(1 − (current_open_hours_m + estimate_t) / capacity_total_m, 0, 1)
                  capacity_total_m = capacity_hours_per_week × weeks_remaining  (≥ 1 week)
                  current_open_hours_m = sum of estimate_hours for open tasks already
                  assigned to m (including ones assigned in earlier batches this call).
                  Zero-capacity guard: if capacity_total_m == 0 → availability = 0.

  performance   = member.user.on_time_rate   (default 0.7)

  score = 0.5 * skill_match + 0.3 * availability + 0.2 * performance
  cost  = 1 − score   (linear_sum_assignment minimises cost)

Slots per member:
  k = max(1, floor(remaining_capacity_hours / 8))
  where remaining_capacity_hours = capacity_total_m − current_open_hours_m

Batching (spec §8.2):
  1. Sort unassigned tasks by priority (critical→high→medium→low).
  2. In each batch: total_slots = sum(k_m for each member).
     Take next min(len(remaining_tasks), total_slots) tasks.
  3. Build (n_tasks × total_slots) cost matrix. Each member fills k_m columns.
  4. Run linear_sum_assignment on the cost matrix.
  5. Update each member's current_open_hours after the batch.
  6. Repeat until all tasks placed or no slots remain.

Edge cases:
  - No members → return empty list (caught at router level with 422).
  - Member with zero capacity → k = 0 slots, skipped.
  - More tasks than total slots → tasks beyond total_slots go unassigned.
  - Task with no members who have matching skills → still assigned (lowest cost wins).
"""

import math
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from scipy.optimize import linear_sum_assignment


# ── Priority ordering ─────────────────────────────────────────────────────────

_PRIORITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


# ── Data classes (pure Python, no ORM) ───────────────────────────────────────

@dataclass
class MemberInfo:
    user_id: int
    full_name: str
    skills: dict            # {skill_name: level_1_to_5}
    capacity_hours_per_week: float
    on_time_rate: float     # 0.0–1.0
    weeks_remaining: float  # ≥ 1.0

    # mutable: updated between batches
    current_open_hours: float = field(default=0.0)

    @property
    def capacity_total(self) -> float:
        """Total available hours for the remaining project duration."""
        return self.capacity_hours_per_week * max(1.0, self.weeks_remaining)

    @property
    def remaining_capacity(self) -> float:
        return max(0.0, self.capacity_total - self.current_open_hours)

    @property
    def slots(self) -> int:
        """Number of tasks this member can still absorb (spec §8.2)."""
        return max(1, math.floor(self.remaining_capacity / 8))


@dataclass
class TaskInfo:
    task_id: int
    priority: str
    estimate_hours: float       # default 8 if null
    required_skills: list[str]  # lowercase list


@dataclass
class AssignmentResult:
    task_id: int
    user_id: int
    skill_match: float
    availability: float
    performance: float
    score: float
    reason: str


# ── Score computation ─────────────────────────────────────────────────────────

def _skill_match(task: TaskInfo, member: MemberInfo) -> float:
    """
    Average (level / 5) over required skills.
    Missing skill contributes 0.
    If task has no required skills → 0.5 (neutral per spec §8.2).
    """
    if not task.required_skills:
        return 0.5
    total = sum(member.skills.get(s, 0) / 5.0 for s in task.required_skills)
    return total / len(task.required_skills)


def _availability(task: TaskInfo, member: MemberInfo) -> float:
    """
    clip(1 − (current_open_hours + estimate_t) / capacity_total, 0, 1)
    Guard: if capacity_total == 0 → return 0.
    """
    cap = member.capacity_total
    if cap == 0:
        return 0.0
    raw = 1.0 - (member.current_open_hours + task.estimate_hours) / cap
    return float(np.clip(raw, 0.0, 1.0))


def _score(sm: float, av: float, perf: float) -> float:
    return 0.5 * sm + 0.3 * av + 0.2 * perf


def _reason(sm: float, av: float, perf: float) -> str:
    """Plain-English one-sentence explanation (spec §8.2)."""
    parts = []
    if sm >= 0.8:
        parts.append("strong skill match")
    elif sm >= 0.5:
        parts.append("adequate skill match")
    else:
        parts.append("limited skill overlap")

    if av >= 0.7:
        parts.append("ample availability")
    elif av >= 0.3:
        parts.append("moderate availability")
    else:
        parts.append("low availability")

    if perf >= 0.85:
        parts.append("excellent on-time record")
    elif perf >= 0.6:
        parts.append("acceptable on-time record")
    else:
        parts.append("below-average on-time record")

    return (
        f"Assigned based on {parts[0]}, {parts[1]}, and {parts[2]} "
        f"(skill={sm:.2f}, avail={av:.2f}, perf={perf:.2f})."
    )


# ── Main optimizer ────────────────────────────────────────────────────────────

def recommend_assignments(
    tasks: list[TaskInfo],
    members: list[MemberInfo],
) -> list[AssignmentResult]:
    """
    Run the spec §8.2 optimizer.

    Returns a list of AssignmentResult, one per task that could be assigned.
    Tasks with no available member slots are omitted (logged at router level).
    """
    if not members:
        return []

    # Filter to members with at least some capacity
    active_members = [m for m in members if m.capacity_total > 0]
    if not active_members:
        return []

    # Sort tasks by priority (spec §8.2: process in priority order)
    sorted_tasks = sorted(tasks, key=lambda t: _PRIORITY_ORDER.get(t.priority, 3))

    results: list[AssignmentResult] = []
    remaining = list(sorted_tasks)

    while remaining:
        # Compute per-member slot counts for this batch
        slot_map: list[tuple[MemberInfo, int]] = []
        total_slots = 0
        for m in active_members:
            k = m.slots
            if k > 0:
                slot_map.append((m, k))
                total_slots += k

        if total_slots == 0:
            break  # all members saturated

        # Take at most total_slots tasks this batch
        batch = remaining[:total_slots]
        remaining = remaining[total_slots:]

        n_tasks = len(batch)
        n_cols = total_slots  # one column per slot

        # Build cost matrix: shape (n_tasks, n_cols)
        cost = np.ones((n_tasks, n_cols), dtype=float)
        # Store per-column which member it belongs to
        col_to_member: list[MemberInfo] = []
        for m, k in slot_map:
            col_to_member.extend([m] * k)

        # Fill pre-computed scores into cost matrix
        sm_cache: dict[tuple[int, int], tuple[float, float, float]] = {}
        for ti, task in enumerate(batch):
            for ci, member in enumerate(col_to_member):
                sm = _skill_match(task, member)
                av = _availability(task, member)
                perf = member.on_time_rate
                s = _score(sm, av, perf)
                cost[ti, ci] = 1.0 - s
                sm_cache[(ti, ci)] = (sm, av, perf)

        # Solve assignment (minimises total cost)
        row_ind, col_ind = linear_sum_assignment(cost)

        # Record results and update member loads
        assigned_member_hours: dict[int, float] = {}
        for ri, ci in zip(row_ind, col_ind):
            task = batch[ri]
            member = col_to_member[ci]
            sm, av, perf = sm_cache[(ri, ci)]
            s = _score(sm, av, perf)

            results.append(AssignmentResult(
                task_id=task.task_id,
                user_id=member.user_id,
                skill_match=round(sm, 4),
                availability=round(av, 4),
                performance=round(perf, 4),
                score=round(s, 4),
                reason=_reason(sm, av, perf),
            ))

            # Accumulate load changes for this batch
            assigned_member_hours[member.user_id] = (
                assigned_member_hours.get(member.user_id, 0.0) + task.estimate_hours
            )

        # Update current_open_hours for all members after the batch
        for member in active_members:
            if member.user_id in assigned_member_hours:
                member.current_open_hours += assigned_member_hours[member.user_id]

    return results
