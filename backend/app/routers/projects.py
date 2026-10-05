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
from app.models import Project, ProjectMember, User
from app.schemas import ProjectCreate, ProjectOut, ProjectUpdate
from app.main import ok

router = APIRouter(prefix="/projects", tags=["projects"])


# ── Helper: build ProjectOut with computed fields ─────────────────────────────

def _project_out(project: Project, db: Session) -> dict:
    """
    Compute task_count, member_count, done_ratio, health_score for a project.

    health_score is always None until M7 adds the health service.
    task_count / done_ratio are always 0 until M3 adds tasks.
    """
    member_count = db.execute(
        select(func.count(ProjectMember.id)).where(
            ProjectMember.project_id == project.id
        )
    ).scalar_one()

    # M3+ will populate these; keep 0 for now so the schema is stable
    task_count = 0
    done_ratio = 0.0
    health_score = None   # M7

    return ProjectOut(
        id=project.id,
        title=project.title,
        description=project.description,
        status=project.status,
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

    return ok(data=[_project_out(p, db) for p in projects])


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
