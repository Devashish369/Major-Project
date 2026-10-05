"""
services/workload.py – Member workload computation (spec §8.3).

Formula (viva-ready):
    utilization_m = open_estimate_hours_assigned_m
                    ─────────────────────────────────────────────────
                    capacity_hours_per_week × max(1, weeks_remaining)

Labels (spec §8.3):
    > 1.0       → overloaded
    0.8 – 1.0   → at_risk
    0.4 – 0.8   → healthy
    < 0.4       → available

"open" means status in (todo, in_progress) AND assignee_id = user.id.
Completed tasks do not count (they're no longer consuming capacity).
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class WorkloadEntry:
    user_id: int
    full_name: str
    capacity_hours_per_week: float
    weeks_remaining: float
    open_hours_assigned: float    # numerator: open tasks' estimate_hours
    utilization: float            # ratio (can exceed 1.0 if overloaded)
    label: str                    # overloaded | at_risk | healthy | available
    capacity_total: float         # denominator (for display)


def _label(utilization: float) -> str:
    """Map a utilization ratio to a display label (spec §8.3)."""
    if utilization > 1.0:
        return "overloaded"
    if utilization >= 0.8:
        return "at_risk"
    if utilization >= 0.4:
        return "healthy"
    return "available"


def compute_workload(
    members: list[dict],   # [{user_id, full_name, capacity_hours_per_week}]
    tasks: list[dict],     # [{assignee_id, status, estimate_hours}]
    weeks_remaining: float,
) -> list[WorkloadEntry]:
    """
    Compute workload for all members.

    Args:
        members: list of member dicts (from ProjectMember + User join)
        tasks:   list of task dicts (all tasks in the project)
        weeks_remaining: derived from project.due_date or defaulted to 4.0

    Returns:
        One WorkloadEntry per member, sorted by utilization descending
        (overloaded members first).
    """
    weeks = max(1.0, weeks_remaining)

    # Accumulate open hours per user
    open_hours: dict[int, float] = {}
    for task in tasks:
        if task.get("status") in ("todo", "in_progress") and task.get("assignee_id"):
            uid = task["assignee_id"]
            open_hours[uid] = open_hours.get(uid, 0.0) + (task.get("estimate_hours") or 0.0)

    entries: list[WorkloadEntry] = []
    for m in members:
        uid = m["user_id"]
        cap_week = float(m.get("capacity_hours_per_week") or 0)
        cap_total = cap_week * weeks
        assigned = open_hours.get(uid, 0.0)

        # Guard: zero capacity → utilization = 0 (they can't work, not a ratio error)
        util = (assigned / cap_total) if cap_total > 0 else 0.0

        entries.append(WorkloadEntry(
            user_id=uid,
            full_name=m.get("full_name", ""),
            capacity_hours_per_week=cap_week,
            weeks_remaining=weeks,
            open_hours_assigned=round(assigned, 2),
            utilization=round(util, 4),
            label=_label(util),
            capacity_total=round(cap_total, 2),
        ))

    return sorted(entries, key=lambda e: e.utilization, reverse=True)
