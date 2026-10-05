"""
services/health.py – Project health score (spec §8.5).

Formula (viva-ready):
  expected = clip(elapsed_days / total_days, 0, 1)
  actual   = done_hours / total_hours            (0 if no tasks)
  slip     = max(0, expected − actual)

  health = 100
         − 30 × overdue_ratio
         − 20 × blocked_ratio
         − 15 × min(1, max(0, max_utilization − 1))
         − 35 × min(1, slip / 0.30)

  Clipped to [0, 100].

Where:
  overdue_ratio    = open tasks past their due_date ÷ open tasks
                     (0 if no open tasks)
  blocked_ratio    = open tasks with ≥1 unfinished dependency ÷ open tasks
                     (0 if no open tasks)
  max_utilization  = highest member utilization across the team
                     (from services/workload.compute_workload)
  slip             = schedule slip: how far behind plan we are in % complete

Levels:
  ≥ 75 → Low risk (green)
  50–74 → Medium risk (amber)
  < 50 → High risk (red)

Penalties returned explicitly so the UI can display WHY the score is what it is.
"""

from datetime import date
from typing import Optional


# ── Levels ────────────────────────────────────────────────────────────────────

def _level(score: float) -> str:
    if score >= 75:
        return "Low risk"
    if score >= 50:
        return "Medium risk"
    return "High risk"


# ── Public API ────────────────────────────────────────────────────────────────

def compute_health(
    *,
    # Project timeline
    start_date: Optional[str],   # ISO "YYYY-MM-DD" or None
    due_date: Optional[str],     # ISO "YYYY-MM-DD" or None

    # All tasks (open + done)
    all_tasks: list[dict],
    # [{"status": str, "estimate_hours": float|None,
    #   "due_date": str|None, "actual_hours": float|None}]

    # Dependencies (raw rows)
    dependencies: list[dict],    # [{"task_id": int, "depends_on_id": int}]

    # Member utilizations (from compute_workload)
    member_utilizations: list[float],  # [] if no members

    today: Optional[date] = None,
) -> dict:
    """
    Compute the project health score and return the score, level, and penalties.

    Edge cases:
      - No tasks at all → health = 100 (no evidence of problems).
      - No open tasks (all done) → overdue/blocked = 0; slip = 0 → high score.
      - No start/due date → slip penalty = 0 (can't compute schedule progress).
      - No members → max_utilization penalty = 0.
    """
    today = today or date.today()

    open_tasks = [t for t in all_tasks if t.get("status") != "done"]
    done_tasks  = [t for t in all_tasks if t.get("status") == "done"]
    n_open = len(open_tasks)
    n_all  = len(all_tasks)

    # ── 1. Overdue ratio ──────────────────────────────────────────────────────
    if n_open == 0:
        overdue_ratio = 0.0
    else:
        n_overdue = sum(
            1 for t in open_tasks
            if t.get("due_date") and date.fromisoformat(t["due_date"]) < today
        )
        overdue_ratio = n_overdue / n_open

    # ── 2. Blocked ratio ──────────────────────────────────────────────────────
    if n_open == 0:
        blocked_ratio = 0.0
    else:
        done_ids = {t["id"] for t in done_tasks}
        open_ids = {t["id"] for t in open_tasks}

        # Build set of open tasks that have ≥1 predecessor that is NOT done
        blocked_ids: set[int] = set()
        for dep in dependencies:
            tid  = dep["task_id"]
            pred = dep["depends_on_id"]
            if tid in open_ids and pred not in done_ids:
                blocked_ids.add(tid)

        blocked_ratio = len(blocked_ids) / n_open

    # ── 3. Schedule slip ──────────────────────────────────────────────────────
    slip = 0.0
    expected = 0.0
    actual_progress = 0.0

    if start_date and due_date and n_all > 0:
        try:
            start = date.fromisoformat(start_date)
            due   = date.fromisoformat(due_date)
            total_days   = max(1, (due - start).days)
            elapsed_days = max(0, (today - start).days)
            expected = min(1.0, elapsed_days / total_days)

            # Compute actual progress from hours
            total_hours = sum(
                (t.get("estimate_hours") or 0) for t in all_tasks
            )
            done_hours = sum(
                (t.get("actual_hours") or t.get("estimate_hours") or 0)
                for t in done_tasks
            )
            if total_hours > 0:
                actual_progress = min(1.0, done_hours / total_hours)
            else:
                actual_progress = len(done_tasks) / n_all if n_all > 0 else 0.0

            slip = max(0.0, expected - actual_progress)
        except (ValueError, TypeError):
            slip = 0.0

    # ── 4. Max utilization ────────────────────────────────────────────────────
    max_util = max(member_utilizations) if member_utilizations else 0.0

    # ── 5. Compute penalties ──────────────────────────────────────────────────
    p_overdue  = 30.0 * overdue_ratio
    p_blocked  = 20.0 * blocked_ratio
    p_util     = 15.0 * min(1.0, max(0.0, max_util - 1.0))
    p_slip     = 35.0 * min(1.0, slip / 0.30)

    raw_score = 100.0 - p_overdue - p_blocked - p_util - p_slip
    score     = round(max(0.0, min(100.0, raw_score)), 2)

    return {
        "health_score": score,
        "level": _level(score),
        "penalties": {
            "overdue":  round(p_overdue, 2),
            "blocked":  round(p_blocked, 2),
            "overload": round(p_util, 2),
            "slip":     round(p_slip, 2),
        },
        "diagnostics": {
            "overdue_ratio":   round(overdue_ratio, 4),
            "blocked_ratio":   round(blocked_ratio, 4),
            "max_utilization": round(max_util, 4),
            "expected_progress": round(expected, 4),
            "actual_progress":   round(actual_progress, 4),
            "slip":              round(slip, 4),
            "open_tasks":        n_open,
            "done_tasks":        len(done_tasks),
        },
    }
