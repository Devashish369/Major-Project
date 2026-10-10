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

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database import get_db
from app.deps import get_current_user
from app.models import User
from app.schemas import (
    ChangePasswordRequest, SecurityEventOut, TokenOut, UserCreate, UserLogin, UserOut, UserUpdate,
)
from app.security import DUMMY_HASH, create_access_token, hash_password, verify_password
from app.services import security_events as sec
from app.main import ok, err   # response envelope helpers

router = APIRouter(prefix="/auth", tags=["auth"])


# ── POST /auth/register ───────────────────────────────────────────────────────

@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(body: UserCreate, request: Request, db: Session = Depends(get_db)):
    """
    Create a new user account.

    Returns the access token plus the user object so the frontend can
    log the user in immediately after registration.
    """
    # 0. Sign-up spam protection: at most REGISTER_LIMIT_PER_HOUR (30) new accounts per IP per hour
    if sec.register_blocked(db, sec.client_ip(request)):
        raise HTTPException(status_code=429, detail="Too many new accounts from this network. Try again later.",
                            headers={"Retry-After": "3600"})

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
    db.flush()
    sec.record(db, request, "register", user_id=user.id, email=user.email)
    db.commit()
    db.refresh(user)   # load server-generated id, created_at

    # 4. Issue token
    token = create_access_token(user.id, user.token_version)
    return ok(
        data={"access_token": token, "token_type": "bearer", "user": UserOut.model_validate(user)},
        message="Account created successfully.",
    )


# ── POST /auth/login ──────────────────────────────────────────────────────────

@router.post("/login")
def login(body: UserLogin, request: Request, db: Session = Depends(get_db)):
    """
    Verify credentials and return a JWT.

    Brute-force protection (services/security_events.py): too many recent failures → 429.
    Every attempt is recorded for the user's "Recent sign-in activity".
    """
    email = str(body.email).lower()
    ip = sec.client_ip(request)
    wait = sec.login_block_seconds(db, email, ip)
    user = db.execute(
        select(User).where(User.email == body.email)
    ).scalar_one_or_none()
    if wait:
        sec.record(db, request, "login_blocked", user_id=user.id if user else None, email=email)
        db.commit()
        minutes = max(1, round(wait / 60))
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many failed sign-in attempts. Try again in about {minutes} minute{'s' if minutes > 1 else ''}.",
            headers={"Retry-After": str(wait)},
        )

    # Deliberate: same error, and the same bcrypt work, for "user not found" and "wrong password"
    # so neither the message nor the response time reveals which emails are registered.
    ok_password = verify_password(body.password, user.password_hash if user else DUMMY_HASH)
    if user is None or not ok_password:
        sec.record(db, request, "login_failed", user_id=user.id if user else None, email=email)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
        )

    sec.record(db, request, "login_success", user_id=user.id, email=email)
    db.commit()
    token = create_access_token(user.id, user.token_version)
    return ok(
        data={"access_token": token, "token_type": "bearer", "user": UserOut.model_validate(user)},
        message="Login successful.",
    )


# ── Account security ──────────────────────────────────────────────────────────

@router.post("/change-password")
def change_password(
    body: ChangePasswordRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Change the password. Every other session is signed out; this tab gets a fresh token."""
    if not verify_password(body.current_password, current_user.password_hash):
        sec.record(db, request, "password_change_failed", user_id=current_user.id, email=current_user.email)
        db.commit()
        raise HTTPException(status_code=400, detail="Your current password is not correct.")
    if body.new_password == body.current_password:
        raise HTTPException(status_code=422, detail="The new password must be different from the current one.")
    current_user.password_hash = hash_password(body.new_password)
    current_user.token_version += 1          # revokes every token issued before now
    sec.record(db, request, "password_changed", user_id=current_user.id, email=current_user.email)
    db.commit()
    return ok(
        data={"access_token": create_access_token(current_user.id, current_user.token_version), "token_type": "bearer"},
        message="Password changed. You were signed out on every other device and tab.",
    )


@router.post("/logout-all")
def logout_all(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Sign out everywhere (all tabs and devices), e.g. after using a shared computer."""
    current_user.token_version += 1
    sec.record(db, request, "sessions_revoked", user_id=current_user.id, email=current_user.email)
    db.commit()
    return ok(data=None, message="Signed out on every device and tab.")


@router.get("/security-events")
def my_security_events(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """The current user's recent sign-ins, failed attempts and security changes (newest first)."""
    rows = sec.recent_for_user(db, current_user.id, current_user.email)
    return ok(data=[SecurityEventOut.model_validate(r).model_dump(mode="json") for r in rows])


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
