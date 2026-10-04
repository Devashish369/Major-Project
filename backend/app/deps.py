"""
deps.py – Reusable FastAPI dependencies for IntelliPM.

M1: get_current_user  – reads the Bearer token from the Authorization header,
                        decodes it, and returns the User ORM object.
                        Raises HTTP 401 if missing or invalid.

Usage in a router:
    current_user: User = Depends(get_current_user)

Later modules will add get_current_admin_member(project_id) etc.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database import get_db
from app.models import User
from app.security import decode_access_token


# HTTPBearer extracts the token from "Authorization: Bearer <token>" header.
# auto_error=False lets us raise a custom 401 instead of FastAPI's default.
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

    Flow:
      1. Extract token string from Authorization: Bearer header.
      2. Call decode_access_token() → user_id or None.
      3. Look up User in DB; raise 401 if not found.

    Raises HTTP 401 for any invalid/expired/missing token.
    """
    if credentials is None:
        raise _CRED_EXCEPTION

    user_id = decode_access_token(credentials.credentials)
    if user_id is None:
        raise _CRED_EXCEPTION

    # SQLAlchemy 2.0: use select() not session.query()
    user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
    if user is None:
        raise _CRED_EXCEPTION

    return user
