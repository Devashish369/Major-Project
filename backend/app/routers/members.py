"""
routers/members.py – Project member management endpoints.

Spec §7:
  GET    /projects/{id}/members              – list members (any member)
  POST   /projects/{id}/members              – add member by email (any member)
  PATCH  /projects/{id}/members/{user_id}    – update role/capacity (admin only)
  DELETE /projects/{id}/members/{user_id}    – remove member (admin only)

Rules (spec §6):
  - Add by email (caller provides email, we look up the user).
  - Cannot remove the last admin.
  - Cannot add a user who is already a member (409).
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database import get_db
from app.deps import get_current_user, get_membership, require_admin
from app.models import ProjectMember, User
from app.schemas import MemberAdd, MemberOut, MemberUpdate
from app.main import ok

router = APIRouter(prefix="/projects", tags=["members"])


def _member_out(pm: ProjectMember, user: User) -> dict:
    """Build a MemberOut dict from a ProjectMember + User pair."""
    return MemberOut(
        user_id=user.id,
        email=user.email,
        username=user.username,
        full_name=user.full_name,
        skills=user.skills,
        on_time_rate=user.on_time_rate,
        role=pm.role,
        capacity_hours_per_week=pm.capacity_hours_per_week,
    ).model_dump()


# ── GET /projects/{project_id}/members ───────────────────────────────────────

@router.get("/{project_id}/members")
def list_members(
    project_id: int,
    _membership=Depends(get_membership),   # any member may list
    db: Session = Depends(get_db),
):
    """List all members of the project with their user info, role, and capacity."""
    rows = db.execute(
        select(ProjectMember, User).join(User, User.id == ProjectMember.user_id)
        .where(ProjectMember.project_id == project_id)
        .order_by(ProjectMember.created_at)
    ).all()

    return ok(data=[_member_out(pm, u) for pm, u in rows])


# ── POST /projects/{project_id}/members ──────────────────────────────────────

@router.post("/{project_id}/members", status_code=status.HTTP_201_CREATED)
def add_member(
    project_id: int,
    body: MemberAdd,
    _membership=Depends(get_membership),   # any member may add regular members
    db: Session = Depends(get_db),
):
    """
    Add a user to the project by their email address.

    Returns 404 if the email doesn't exist (don't reveal whether email is
    registered to an anonymous caller – only members reach this endpoint).
    Returns 409 if already a member.
    Returns 403 if a non-admin tries to add someone as admin.
    """
    # Granting the admin role is admin-only.  Otherwise a plain member could add an
    # account they control as "admin" and then delete the project or remove people.
    if body.role == "admin" and _membership.role != "admin":
        raise HTTPException(status_code=403, detail="Only a project admin can add another admin.")
    # Look up user by email
    user = db.execute(
        select(User).where(User.email == body.email)
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="No user found with that email.")

    # Check not already a member
    existing = db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user.id,
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="User is already a member.")

    pm = ProjectMember(
        project_id=project_id,
        user_id=user.id,
        role=body.role,
        capacity_hours_per_week=body.capacity_hours_per_week,
    )
    db.add(pm)
    db.commit()
    db.refresh(pm)
    return ok(data=_member_out(pm, user), message="Member added.")


# ── PATCH /projects/{project_id}/members/{user_id} ───────────────────────────

@router.patch("/{project_id}/members/{user_id}")
def update_member(
    project_id: int,
    user_id: int,
    body: MemberUpdate,
    _admin=Depends(require_admin),   # admin only
    db: Session = Depends(get_db),
):
    """Update a member's role or capacity. Admin only."""
    pm = db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
        )
    ).scalar_one_or_none()
    if pm is None:
        raise HTTPException(status_code=404, detail="Member not found.")

    # Guard: cannot demote the last admin
    if body.role == "member" and pm.role == "admin":
        admin_count = db.execute(
            select(ProjectMember).where(
                ProjectMember.project_id == project_id,
                ProjectMember.role == "admin",
            )
        ).scalars().all()
        if len(admin_count) <= 1:
            raise HTTPException(
                status_code=409,
                detail="Cannot demote the last admin. Promote another member first.",
            )

    if body.role is not None:
        pm.role = body.role
    if body.capacity_hours_per_week is not None:
        pm.capacity_hours_per_week = body.capacity_hours_per_week

    db.commit()
    db.refresh(pm)

    user = db.execute(select(User).where(User.id == user_id)).scalar_one()
    return ok(data=_member_out(pm, user), message="Member updated.")


# ── DELETE /projects/{project_id}/members/{user_id} ──────────────────────────

@router.delete("/{project_id}/members/{user_id}")
def remove_member(
    project_id: int,
    user_id: int,
    admin_membership=Depends(require_admin),   # admin only
    db: Session = Depends(get_db),
):
    """
    Remove a member from the project. Admin only.
    Cannot remove the last admin.
    """
    pm = db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
        )
    ).scalar_one_or_none()
    if pm is None:
        raise HTTPException(status_code=404, detail="Member not found.")

    # Cannot remove last admin
    if pm.role == "admin":
        admin_count = db.execute(
            select(ProjectMember).where(
                ProjectMember.project_id == project_id,
                ProjectMember.role == "admin",
            )
        ).scalars().all()
        if len(admin_count) <= 1:
            raise HTTPException(
                status_code=409,
                detail="Cannot remove the last admin of a project.",
            )

    db.delete(pm)
    db.commit()
    return ok(message="Member removed.")
