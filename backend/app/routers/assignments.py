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
from app.services.skill_gaps import GapMember, compute_skill_gaps
from app.services.skills import canonical, canonical_levels
from app.services.workload import compute_workload
from app.services.tasks import write_activity
from app.services.realtime import emit_tasks
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
            skills=canonical_levels(u.skills),   # "ReactJS" and "react" are the same skill
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
            required_skills=[canonical(s) for s in (t.required_skills or []) if canonical(s)],
        )
        for t in candidate_tasks_orm
    ]

    team_skills = {s for m in members for s, lv in m.skills.items() if lv >= 1}
    by_id = {t.id: t for t in candidate_tasks_orm}
    info_by_id = {t.task_id: t for t in tasks}
    results = recommend_assignments(tasks, members)

    return ok(
        data=[
            {
                "task_id": r.task_id,
                "task_number": by_id[r.task_id].number,
                "task_title": by_id[r.task_id].title,
                # required skills nobody has: shown with a link to the Skill gaps card
                "missing_skills": [s for s in info_by_id[r.task_id].required_skills if s not in team_skills],
                "alternatives": r.alternatives,
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


# ── GET /projects/{id}/assignments/skill-gaps ─────────────────────────────────

@router.get("/projects/{project_id}/assignments/skill-gaps")
def skill_gaps(
    project_id: int,
    membership=Depends(get_membership),
    db: Session = Depends(get_db),
):
    """
    Skills that open tasks need but no member has, with who should learn each one:
    the member with the most related existing skill, and the member with the lowest workload.
    Read-only (services/skill_gaps.py explains the scoring).
    """
    project = db.execute(select(Project).where(Project.id == project_id)).scalar_one()
    member_rows = _load_members(project_id, db)
    all_tasks = db.execute(select(Task).where(Task.project_id == project_id)).scalars().all()
    entries = compute_workload(
        [{"user_id": u.id, "full_name": u.full_name, "capacity_hours_per_week": pm.capacity_hours_per_week}
         for pm, u in member_rows],
        [{"assignee_id": t.assignee_id, "status": t.status, "estimate_hours": t.estimate_hours or 0.0}
         for t in all_tasks],
        _weeks_remaining(project),
    )
    util = {e.user_id: e.utilization for e in entries}
    members = [GapMember(user_id=u.id, full_name=u.full_name, skills=u.skills or {},
                         utilization=util.get(u.id, 0.0), on_time_rate=u.on_time_rate)
               for pm, u in member_rows]
    open_tasks = [{"id": t.id, "number": t.number, "title": t.title, "required_skills": t.required_skills or []}
                  for t in all_tasks if t.status != "done"]
    gaps = compute_skill_gaps(open_tasks, members)
    return ok(data=gaps, message=f"{len(gaps)} missing skill(s)." if gaps else "Every required skill is covered.")


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
    overridden = 0
    changed_ids: list[int] = []
    # two queries in total instead of two per assignment
    wanted = {a.task_id for a in body.assignments}
    tasks = {t.id: t for t in db.execute(
        select(Task).where(Task.project_id == project_id, Task.id.in_(wanted or {0}))
    ).scalars()}
    member_ids = set(db.execute(
        select(ProjectMember.user_id).where(ProjectMember.project_id == project_id)
    ).scalars())

    for assignment in body.assignments:
        task = tasks.get(assignment.task_id)
        if task is None or assignment.user_id not in member_ids:
            continue  # unknown task / not a member of this project: skipped, never applied

        task.assignee_id = assignment.user_id
        changed_ids.append(task.id)
        meta = {"assignee_id": assignment.user_id}
        if assignment.recommended_user_id is not None and assignment.recommended_user_id != assignment.user_id:
            meta.update(recommended_user_id=assignment.recommended_user_id, overridden=True)
            overridden += 1
        write_activity(
            db,
            project_id=project_id,
            user_id=current_user.id,
            action="task_assigned",
            task_id=task.id,
            meta=meta,
        )
        applied += 1

    db.commit()
    emit_tasks(db, project_id, "task_updated", changed_ids, current_user.id)

    return ok(
        data={"applied": applied, "overridden": overridden},
        message=f"{applied} assignment(s) applied"
                + (f" ({overridden} changed by the admin)." if overridden else "."),
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
