"""
routers/auth.py – Auth endpoints for IntelliPM.

Spec section 7:
  POST /auth/register  – create account, return token + user
  POST /auth/login     – verify credentials, return token + user
  GET  /auth/me        – return current user (JWT required)
  PATCH /auth/me       – update full_name and/or skills (JWT required)

Router is thin: it only does HTTP plumbing. All business logic is in
services/auth.py so it stays testable without an HTTP client.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database import get_db
from app.deps import get_current_user
from app.models import User
from app.schemas import TokenOut, UserCreate, UserLogin, UserOut, UserUpdate
from app.security import create_access_token, hash_password, verify_password
from app.main import ok, err   # response envelope helpers

router = APIRouter(prefix="/auth", tags=["auth"])


# ── POST /auth/register ───────────────────────────────────────────────────────

@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(body: UserCreate, db: Session = Depends(get_db)):
    """
    Create a new user account.

    Returns the access token plus the user object so the frontend can
    log the user in immediately after registration.
    """
    # 1. Check email uniqueness
    existing_email = db.execute(
        select(User).where(User.email == body.email)
    ).scalar_one_or_none()
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered.",
        )

    # 2. Check username uniqueness
    existing_username = db.execute(
        select(User).where(User.username == body.username)
    ).scalar_one_or_none()
    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already taken.",
        )

    # 3. Create user
    user = User(
        email=body.email,
        username=body.username,   # already lower-cased by Pydantic validator
        full_name=body.full_name,
        password_hash=hash_password(body.password),
        skills={},
        on_time_rate=0.7,
    )
    db.add(user)
    db.commit()
    db.refresh(user)   # load server-generated id, created_at

    # 4. Issue token
    token = create_access_token(user.id)
    return ok(
        data={"access_token": token, "token_type": "bearer", "user": UserOut.model_validate(user)},
        message="Account created successfully.",
    )


# ── POST /auth/login ──────────────────────────────────────────────────────────

@router.post("/login")
def login(body: UserLogin, db: Session = Depends(get_db)):
    """
    Verify credentials and return a JWT.

    We look up by email, verify the bcrypt hash, then issue a new token.
    """
    user = db.execute(
        select(User).where(User.email == body.email)
    ).scalar_one_or_none()

    # Deliberate: same error for "user not found" and "wrong password"
    # to avoid leaking which emails are registered.
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
        )

    token = create_access_token(user.id)
    return ok(
        data={"access_token": token, "token_type": "bearer", "user": UserOut.model_validate(user)},
        message="Login successful.",
    )


# ── GET /auth/me ──────────────────────────────────────────────────────────────

@router.get("/me")
def get_me(current_user: User = Depends(get_current_user)):
    """Return the authenticated user's profile."""
    return ok(data=UserOut.model_validate(current_user))


# ── PATCH /auth/me ────────────────────────────────────────────────────────────

@router.patch("/me")
def update_me(
    body: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Update full_name and/or skills for the current user.

    Only the fields provided (not None) are updated.
    Skill names are lower-cased by the Pydantic validator before reaching here.
    """
    if body.full_name is not None:
        current_user.full_name = body.full_name
    if body.skills is not None:
        current_user.skills = body.skills

    db.commit()
    db.refresh(current_user)
    return ok(data=UserOut.model_validate(current_user), message="Profile updated.")
