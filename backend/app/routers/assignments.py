"""
routers/assignments.py – Assignment optimizer and workload endpoints (spec §8.2/8.3).

Endpoints:
  POST /projects/{project_id}/assignments/recommend  – compute draft (no DB writes)
  POST /projects/{project_id}/assignments/apply      – admin only, persists assignments
  GET  /projects/{project_id}/analytics/workload     – workload per member

Design decisions (viva-ready):
  - recommend never writes to the DB so callers can preview freely.
  - apply writes in one transaction: PATCH assignee_id on each task + activity row.
  - weeks_remaining: computed from project.due_date (ISO date) relative to today.
    Falls back to 4 weeks if due_date is not set.
  - Only UNASSIGNED open tasks are candidates for the optimizer (assignee_id IS NULL
    AND status != "done"). Admin can pass force=True to re-optimise assigned tasks too.
"""

import logging
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database import get_db
from app.deps import get_current_user, get_membership, require_admin
from app.models import Project, ProjectMember, Task, User
from app.schemas import AssignmentRecommendRequest, AssignmentApplyRequest
from app.services.assignment import MemberInfo, TaskInfo, recommend_assignments
from app.services.workload import compute_workload
from app.services.tasks import write_activity
from app.main import ok

logger = logging.getLogger(__name__)
router = APIRouter(tags=["assignments"])

_DEFAULT_WEEKS = 4.0


def _weeks_remaining(project: Project) -> float:
    """Derive weeks remaining from project.due_date; default to 4."""
    if not project.due_date:
        return _DEFAULT_WEEKS
    try:
        due = date.fromisoformat(project.due_date)
        delta = (due - date.today()).days
        weeks = delta / 7.0
        return max(1.0, weeks)
    except (ValueError, TypeError):
        return _DEFAULT_WEEKS


def _load_members(project_id: int, db: Session) -> list[tuple[ProjectMember, User]]:
    rows = db.execute(
        select(ProjectMember, User)
        .join(User, User.id == ProjectMember.user_id)
        .where(ProjectMember.project_id == project_id)
    ).all()
    return [(pm, u) for pm, u in rows]


def _open_hours_per_member(project_id: int, db: Session) -> dict[int, float]:
    """Sum of estimate_hours for open tasks currently assigned to each user."""
    tasks = db.execute(
        select(Task).where(
            Task.project_id == project_id,
            Task.status.in_(["todo", "in_progress"]),
            Task.assignee_id.isnot(None),
        )
    ).scalars().all()
    totals: dict[int, float] = {}
    for t in tasks:
        h = t.estimate_hours or 0.0
        totals[t.assignee_id] = totals.get(t.assignee_id, 0.0) + h
    return totals


# ── POST /projects/{id}/assignments/recommend ─────────────────────────────────

@router.post("/projects/{project_id}/assignments/recommend")
def recommend(
    project_id: int,
    body: AssignmentRecommendRequest,
    current_user=Depends(get_current_user),
    membership=Depends(get_membership),
    db: Session = Depends(get_db),
):
    """
    Compute recommended assignments for unassigned open tasks.
    Does NOT write to the database – safe to call repeatedly as a preview.

    Set body.force=True to also re-optimise tasks that already have an assignee.
    """
    project = db.execute(select(Project).where(Project.id == project_id)).scalar_one()
    weeks = _weeks_remaining(project)

    # Load all members
    member_rows = _load_members(project_id, db)
    if not member_rows:
        raise HTTPException(status_code=422, detail="Project has no members to assign to.")

    # Current open hours (for availability calculation)
    existing_open_hours = _open_hours_per_member(project_id, db)

    members = [
        MemberInfo(
            user_id=u.id,
            full_name=u.full_name,
            skills=u.skills or {},
            capacity_hours_per_week=pm.capacity_hours_per_week,
            on_time_rate=u.on_time_rate,
            weeks_remaining=weeks,
            current_open_hours=existing_open_hours.get(u.id, 0.0),
        )
        for pm, u in member_rows
    ]

    # Candidate tasks: open + unassigned (or all open if force=True)
    q = select(Task).where(
        Task.project_id == project_id,
        Task.status.in_(["todo", "in_progress"]),
    )
    if not body.force:
        q = q.where(Task.assignee_id.is_(None))
    candidate_tasks_orm = db.execute(q).scalars().all()

    if not candidate_tasks_orm:
        return ok(data=[], message="No unassigned open tasks to recommend for.")

    tasks = [
        TaskInfo(
            task_id=t.id,
            priority=t.priority,
            estimate_hours=t.estimate_hours or 8.0,
            required_skills=[s.lower() for s in (t.required_skills or [])],
        )
        for t in candidate_tasks_orm
    ]

    results = recommend_assignments(tasks, members)

    return ok(
        data=[
            {
                "task_id": r.task_id,
                "user_id": r.user_id,
                "skill_match": r.skill_match,
                "availability": r.availability,
                "performance": r.performance,
                "score": r.score,
                "reason": r.reason,
            }
            for r in results
        ],
        message=f"{len(results)} task(s) assigned (not yet applied).",
    )


# ── POST /projects/{id}/assignments/apply ─────────────────────────────────────

@router.post(
    "/projects/{project_id}/assignments/apply",
    status_code=status.HTTP_200_OK,
)
def apply_assignments(
    project_id: int,
    body: AssignmentApplyRequest,
    current_user=Depends(get_current_user),
    _admin=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Apply a list of {task_id, user_id} assignments to the project (admin only).

    Each assignment sets task.assignee_id and writes an activity log row.
    Runs in one transaction.
    """
    applied = 0
    for assignment in body.assignments:
        task = db.execute(
            select(Task).where(
                Task.id == assignment["task_id"],
                Task.project_id == project_id,
            )
        ).scalar_one_or_none()

        if task is None:
            continue  # skip unknown task IDs silently

        # Verify user is a project member
        member = db.execute(
            select(ProjectMember).where(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == assignment["user_id"],
            )
        ).scalar_one_or_none()

        if member is None:
            continue  # skip non-member assignments silently

        task.assignee_id = assignment["user_id"]
        write_activity(
            db,
            project_id=project_id,
            user_id=current_user.id,
            action="task_assigned",
            task_id=task.id,
            meta={"assignee_id": assignment["user_id"]},
        )
        applied += 1

    db.commit()

    return ok(
        data={"applied": applied},
        message=f"{applied} assignment(s) applied.",
    )


# ── GET /projects/{id}/analytics/workload ─────────────────────────────────────

@router.get("/projects/{project_id}/analytics/workload")
def workload(
    project_id: int,
    current_user=Depends(get_current_user),
    membership=Depends(get_membership),
    db: Session = Depends(get_db),
):
    """
    Return workload stats for all project members.

    utilization = open_estimate_hours_assigned / (capacity_per_week × weeks_remaining)
    Labels: overloaded | at_risk | healthy | available  (spec §8.3)
    """
    project = db.execute(select(Project).where(Project.id == project_id)).scalar_one()
    weeks = _weeks_remaining(project)

    member_rows = _load_members(project_id, db)

    all_tasks = db.execute(
        select(Task).where(Task.project_id == project_id)
    ).scalars().all()

    members_dicts = [
        {
            "user_id": u.id,
            "full_name": u.full_name,
            "capacity_hours_per_week": pm.capacity_hours_per_week,
        }
        for pm, u in member_rows
    ]
    tasks_dicts = [
        {
            "assignee_id": t.assignee_id,
            "status": t.status,
            "estimate_hours": t.estimate_hours or 0.0,
        }
        for t in all_tasks
    ]

    entries = compute_workload(members_dicts, tasks_dicts, weeks)

    return ok(
        data=[
            {
                "user_id": e.user_id,
                "full_name": e.full_name,
                "capacity_hours_per_week": e.capacity_hours_per_week,
                "weeks_remaining": e.weeks_remaining,
                "open_hours_assigned": e.open_hours_assigned,
                "capacity_total": e.capacity_total,
                "utilization": e.utilization,
                "label": e.label,
            }
            for e in entries
        ],
        message="Workload computed.",
    )
