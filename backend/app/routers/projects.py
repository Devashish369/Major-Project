"""
routers/projects.py – Project CRUD endpoints.

Spec §7:
  GET    /projects           – list all projects the caller is a member of
  POST   /projects           – create project; creator becomes admin member
  GET    /projects/{id}      – get project (members only, else 404)
  PATCH  /projects/{id}      – update project (any member)
  DELETE /projects/{id}      – delete project (admin only)

All list responses include computed fields:
  task_count, member_count, done_ratio, health_score (null until M7).
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.database import get_db
from app.deps import get_current_user, get_membership, require_admin
from app.models import Project, ProjectMember, Task, TaskDependency, User
from app.schemas import ProjectCreate, ProjectOut, ProjectUpdate
from app.services.health import compute_health
from app.services.tasks import derive_project_status
from app.main import ok

router = APIRouter(prefix="/projects", tags=["projects"])


# ── Helper: build ProjectOut with computed fields ─────────────────────────────

def _project_out(project: Project, db: Session, members=None, tasks=None, deps=None) -> dict:
    """
    Compute task_count, member_count, done_ratio, status and health_score for a project.

    Callers that already hold the project's members / tasks / dependencies (the dashboard list
    loads them for ALL projects in a few queries) pass them in; otherwise they are loaded here.
    Everything below works on those in-memory lists, so a project costs 0 extra queries when
    the lists are supplied (this used to be ~6 queries per project).
    """
    if tasks is None:
        tasks = db.execute(select(Task).where(Task.project_id == project.id)).scalars().all()
    if members is None:
        members = db.execute(select(ProjectMember).where(ProjectMember.project_id == project.id)).scalars().all()
    if deps is None:
        task_ids = [t.id for t in tasks]
        deps = db.execute(
            select(TaskDependency).where(TaskDependency.task_id.in_(task_ids))
        ).scalars().all() if task_ids else []

    all_tasks_raw, members_raw, deps_raw = tasks, members, deps
    member_count = len(members_raw)
    task_count = len(all_tasks_raw)
    done_count = sum(1 for t in all_tasks_raw if t.status == "done")
    done_ratio = (done_count / task_count) if task_count > 0 else 0.0

    from datetime import date as _date
    today = _date.today()
    # At least 1 week, same as services/workload.py (keeps health and workload bars consistent)
    weeks_remaining = max(1.0, (
        (_date.fromisoformat(project.due_date) - today).days
        if project.due_date else 28
    ) / 7)

    member_utils = []
    for m in members_raw:
        open_h = sum(
            (t.estimate_hours or 0)
            for t in all_tasks_raw
            if t.assignee_id == m.user_id and t.status != "done"
        )
        cap = m.capacity_hours_per_week * weeks_remaining
        member_utils.append(open_h / cap if cap > 0 else 0.0)

    health_result = compute_health(
        start_date=project.start_date,
        due_date=project.due_date,
        all_tasks=[
            {
                "id": t.id,
                "status": t.status,
                "estimate_hours": t.estimate_hours,
                "actual_hours": t.actual_hours,
                "due_date": t.due_date,
            }
            for t in all_tasks_raw
        ],
        dependencies=[
            {"task_id": d.task_id, "depends_on_id": d.depends_on_id}
            for d in deps_raw
        ],
        member_utilizations=member_utils,
        today=today,
    )
    health_score = health_result["health_score"]

    return ProjectOut(
        id=project.id,
        title=project.title,
        description=project.description,
        status=derive_project_status(project.status, [t.status for t in all_tasks_raw]),
        priority=project.priority,
        start_date=project.start_date,
        due_date=project.due_date,
        created_by=project.created_by,
        created_at=project.created_at,
        task_count=task_count,
        member_count=member_count,
        done_ratio=done_ratio,
        health_score=health_score,
    ).model_dump()


# ── GET /projects ─────────────────────────────────────────────────────────────

@router.get("")
def list_projects(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Return all projects the current user is a member of.

    Joins project_members so only the caller's projects are returned –
    no cross-user data leakage possible.
    """
    # Get all project_ids where this user is a member
    member_rows = db.execute(
        select(ProjectMember.project_id).where(
            ProjectMember.user_id == current_user.id
        )
    ).scalars().all()

    if not member_rows:
        return ok(data=[], message="No projects found.")

    projects = db.execute(
        select(Project).where(Project.id.in_(member_rows))
        .order_by(Project.created_at.desc())
    ).scalars().all()

    # Load members, tasks and dependencies of ALL these projects at once (3 queries in total)
    # instead of 3-6 queries per project - each query is a network round trip to the database.
    ids = [p.id for p in projects]
    members_by: dict[int, list] = {i: [] for i in ids}
    tasks_by: dict[int, list] = {i: [] for i in ids}
    deps_by: dict[int, list] = {i: [] for i in ids}
    for m in db.execute(select(ProjectMember).where(ProjectMember.project_id.in_(ids))).scalars():
        members_by[m.project_id].append(m)
    project_of_task = {}
    for t in db.execute(select(Task).where(Task.project_id.in_(ids))).scalars():
        tasks_by[t.project_id].append(t)
        project_of_task[t.id] = t.project_id
    if project_of_task:
        for d in db.execute(
            select(TaskDependency).where(TaskDependency.task_id.in_(list(project_of_task)))
        ).scalars():
            deps_by[project_of_task[d.task_id]].append(d)

    return ok(data=[
        _project_out(p, db, members=members_by[p.id], tasks=tasks_by[p.id], deps=deps_by[p.id])
        for p in projects
    ])


# ── POST /projects ────────────────────────────────────────────────────────────

@router.post("", status_code=status.HTTP_201_CREATED)
def create_project(
    body: ProjectCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create a new project.
    The creator is automatically added as an admin member.
    """
    project = Project(
        title=body.title,
        description=body.description,
        status=body.status,
        priority=body.priority,
        start_date=body.start_date,
        due_date=body.due_date,
        created_by=current_user.id,
    )
    db.add(project)
    db.flush()   # flush so project.id is available before adding member

    # Auto-add creator as admin
    membership = ProjectMember(
        project_id=project.id,
        user_id=current_user.id,
        role="admin",
        capacity_hours_per_week=30,
    )
    db.add(membership)
    db.commit()
    db.refresh(project)

    return ok(data=_project_out(project, db), message="Project created.")


# ── GET /projects/{id} ────────────────────────────────────────────────────────

@router.get("/{project_id}")
def get_project(
    project_id: int,
    membership=Depends(get_membership),   # raises 404 if not a member
    db: Session = Depends(get_db),
):
    """Get a single project. Only members can see it (non-members get 404)."""
    project = db.execute(
        select(Project).where(Project.id == project_id)
    ).scalar_one()
    return ok(data=_project_out(project, db))


# ── PATCH /projects/{id} ──────────────────────────────────────────────────────

@router.patch("/{project_id}")
def update_project(
    project_id: int,
    body: ProjectUpdate,
    membership=Depends(get_membership),   # any member may update
    db: Session = Depends(get_db),
):
    """Update project fields. Any member may call this."""
    project = db.execute(
        select(Project).where(Project.id == project_id)
    ).scalar_one()

    if body.title is not None:
        project.title = body.title
    if body.description is not None:
        project.description = body.description
    if body.status is not None:
        project.status = body.status
    if body.priority is not None:
        project.priority = body.priority
    if body.start_date is not None:
        project.start_date = body.start_date
    if body.due_date is not None:
        project.due_date = body.due_date

    db.commit()
    db.refresh(project)
    return ok(data=_project_out(project, db), message="Project updated.")


# ── DELETE /projects/{id} ─────────────────────────────────────────────────────

@router.delete("/{project_id}", status_code=status.HTTP_200_OK)
def delete_project(
    project_id: int,
    admin_membership=Depends(require_admin),   # only admin may delete
    db: Session = Depends(get_db),
):
    """
    Delete a project and all its members (cascade).
    Admin role required.
    """
    project = db.execute(
        select(Project).where(Project.id == project_id)
    ).scalar_one()

    db.delete(project)
    db.commit()
    return ok(message="Project deleted.")
