"""
security.py – Password hashing and JWT creation/verification.

Stack (per spec section 3):
  - bcrypt package directly (NOT passlib).
  - PyJWT for tokens (NOT python-jose).

These are pure functions with no FastAPI dependencies so they are easy to unit-test.
"""

import bcrypt
import jwt
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.config import settings


# ── Password hashing ──────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    """
    Hash a plaintext password with bcrypt.

    bcrypt.hashpw requires bytes; we encode and decode around it.
    The salt is generated automatically with bcrypt.gensalt().
    """
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(plain.encode("utf-8"), salt)
    return hashed.decode("utf-8")   # store as string in DB


def verify_password(plain: str, hashed: str) -> bool:
    """
    Return True if the plaintext matches the stored bcrypt hash.

    bcrypt.checkpw is constant-time to prevent timing attacks.
    """
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


# ── JWT ───────────────────────────────────────────────────────────────────────

ALGORITHM = "HS256"   # HMAC-SHA256; symmetric, good for single-server use


def create_access_token(user_id: int) -> str:
    """
    Create a signed JWT containing the user's id as the 'sub' claim.

    Expiry is read from settings.ACCESS_TOKEN_EXPIRE_MINUTES (default 720 = 12h).
    We store id as a string in 'sub' (JWT spec: subject is a string).
    """
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {
        "sub": str(user_id),   # subject = user id
        "exp": expire,         # expiry claim; PyJWT enforces this automatically
        "iat": datetime.now(timezone.utc),  # issued-at (useful for debugging)
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> Optional[int]:
    """
    Decode and verify a JWT. Returns the user_id (int) or None on any error.

    PyJWT raises DecodeError / ExpiredSignatureError; we catch both and
    return None so the caller can raise a clean 401.
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        sub = payload.get("sub")
        if sub is None:
            return None
        return int(sub)
    except (jwt.PyJWTError, ValueError):
        return None
