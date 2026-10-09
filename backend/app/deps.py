"""
deps.py – Reusable FastAPI dependencies for IntelliPM.

M1: get_current_user  – decode JWT → User ORM object; raise 401 if invalid.
M2: get_membership    – verify caller is a member of a project; raise 404 if not.
    require_admin     – verify caller is an admin of a project; raise 403 if not.

IMPORTANT security rule (spec §7):
  Non-members must get 404 (not 403) so they cannot enumerate project IDs.
"""

from fastapi import Depends, HTTPException, Path, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database import get_db
from app.models import Project, ProjectMember, User
from app.security import decode_access_token


# ── JWT bearer extraction ─────────────────────────────────────────────────────
bearer_scheme = HTTPBearer(auto_error=False)

_CRED_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    FastAPI dependency: validate JWT and return the authenticated User.

    Raises HTTP 401 for any invalid/expired/missing token.
    """
    if credentials is None:
        raise _CRED_EXCEPTION

    user_id = decode_access_token(credentials.credentials)
    if user_id is None:
        raise _CRED_EXCEPTION

    user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
    if user is None:
        raise _CRED_EXCEPTION

    return user


# ── Project membership checks ─────────────────────────────────────────────────

def get_membership(
    project_id: int = Path(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectMember:
    """
    Verify the calling user is a member of project_id.

    Returns the ProjectMember row (contains role + capacity).
    Raises HTTP 404 for both "project doesn't exist" and "user is not a member"
    so callers cannot enumerate project IDs they don't belong to.
    """
    # ONE query is enough: "project does not exist" and "you are not a member" must look the
    # same to the caller anyway (identical 404), and a membership row implies the project exists.
    # (A separate existence check used to cost an extra database round trip on every request.)
    membership = db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == current_user.id,
        )
    ).scalar_one_or_none()

    if membership is None:
        # Return 404 – do NOT reveal the project exists to non-members
        raise HTTPException(status_code=404, detail="Project not found.")

    return membership


def require_admin(
    membership: ProjectMember = Depends(get_membership),
) -> ProjectMember:
    """
    Verify the calling user is an ADMIN of the project.

    Raises HTTP 403 (not 404) because a non-admin member already knows the
    project exists; hiding it would be confusing UX.
    """
    if membership.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required for this action.",
        )
    return membership
