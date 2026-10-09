"""
services/tasks.py – Business logic for tasks and dependencies.

Keeps all non-trivial logic OUT of the router (spec §12 rule 3).

Key functions:
  apply_status_change  – handles completed_at rule (spec §6)
  write_activity       – append-only audit row writer
  has_cycle            – DFS-based cycle detector for task_dependencies
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models import ActivityLog, Task, TaskDependency


# ── completed_at rule (spec §6) ───────────────────────────────────────────────

def apply_status_change(task: Task, new_status: str) -> None:
    """
    Enforce the completed_at rule from spec §6:
      - Setting status → 'done'  sets   completed_at = UTC now
      - Moving away from 'done'  clears completed_at = None

    Mutates the task object in-place; the caller must db.commit().
    """
    if new_status == "done" and task.status != "done":
        task.completed_at = datetime.now(timezone.utc)
    elif new_status != "done" and task.status == "done":
        task.completed_at = None
    task.status = new_status


# ── Activity log ───────────────────────────────────────────────────────────────

def write_activity(
    db: Session,
    *,
    project_id: int,
    user_id: int,
    action: str,
    task_id: Optional[int] = None,
    meta: Optional[dict] = None,
) -> None:
    """
    Append one row to activity_log.

    Called after every create / update / move / assign / delete.
    Never raises – a failed audit write must not fail the main operation,
    so wrap callers in a try/except if you want silent failure.
    (Currently we let it propagate to keep the transaction atomic.)
    """
    db.add(ActivityLog(
        project_id=project_id,
        user_id=user_id,
        task_id=task_id,
        action=action,
        meta=meta or {},
    ))


# ── Cycle detection ───────────────────────────────────────────────────────────

def _get_deps(db: Session, task_id: int) -> list[int]:
    """Return list of task IDs that 'task_id' depends on."""
    return list(db.execute(
        select(TaskDependency.depends_on_id).where(TaskDependency.task_id == task_id)
    ).scalars().all())


def has_cycle(db: Session, task_id: int, depends_on_id: int) -> bool:
    """
    Check whether adding edge task_id → depends_on_id would create a cycle.

    Algorithm: DFS from depends_on_id following existing dependency edges.
    If we ever reach task_id, a cycle exists.

    Example of a cycle:
      A → B → C → A  (if we're trying to add C → A, and A already → B → C)

    Self-reference (task_id == depends_on_id) is handled by the caller
    before this function is invoked.

    Time complexity: O(V + E) where V = tasks, E = dependency edges in project.
    This is fine for typical project sizes (< 500 tasks).
    """
    visited: set[int] = set()
    stack: list[int] = [depends_on_id]

    while stack:
        current = stack.pop()
        if current == task_id:
            return True   # cycle found
        if current in visited:
            continue
        visited.add(current)
        # Follow the edges: what does 'current' depend on?
        stack.extend(_get_deps(db, current))

    return False


def derive_project_status(stored: str, task_statuses: list[str]) -> str:
    """
    Project status follows its tasks, so nobody has to maintain it by hand:
      all tasks done                      -> "completed"
      at least one task started or done   -> "in_progress"
      tasks exist but all are still todo  -> "pending"
    A project with no tasks keeps its stored (manually chosen) status.
    """
    if not task_statuses:
        return stored
    if all(st == "done" for st in task_statuses):
        return "completed"
    if any(st in ("in_progress", "done") for st in task_statuses):
        return "in_progress"
    return "pending"
