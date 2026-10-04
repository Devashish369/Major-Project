"""
schemas.py – Pydantic v2 request/response schemas for IntelliPM.

Naming convention:
  <Model>Create  – body for POST (creation)
  <Model>Update  – body for PATCH (partial update)
  <Model>Out     – what we send back in the API response (never password_hash)

M1: User schemas + Token schema.
M2+ will add Project, Member, Sprint schemas.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


# ── Auth / Token ──────────────────────────────────────────────────────────────

class TokenOut(BaseModel):
    """Returned by POST /auth/login."""
    access_token: str
    token_type: str = "bearer"


# ── User ──────────────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    """Body for POST /auth/register."""
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)
    full_name: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=8)

    @field_validator("username")
    @classmethod
    def username_alphanumeric(cls, v: str) -> str:
        """Usernames must be letters, digits, underscores only."""
        if not v.replace("_", "").isalnum():
            raise ValueError("Username may only contain letters, digits, and underscores.")
        return v.lower()


class UserLogin(BaseModel):
    """Body for POST /auth/login."""
    email: EmailStr
    password: str


class UserUpdate(BaseModel):
    """Body for PATCH /auth/me – all fields optional."""
    full_name: Optional[str] = Field(None, min_length=1, max_length=100)
    skills: Optional[dict] = None   # {"react": 4, "python": 5}

    @field_validator("skills")
    @classmethod
    def validate_skill_levels(cls, v: Optional[dict]) -> Optional[dict]:
        """Each skill level must be an integer 1–5."""
        if v is None:
            return v
        for skill, level in v.items():
            if not isinstance(level, int) or not (1 <= level <= 5):
                raise ValueError(
                    f"Skill level for '{skill}' must be an integer 1–5, got {level!r}."
                )
            if not isinstance(skill, str) or not skill.strip():
                raise ValueError("Skill names must be non-empty strings.")
        # Normalise skill names to lowercase
        return {k.lower().strip(): v for k, v in v.items()}


class UserOut(BaseModel):
    """Safe user representation sent to clients; never includes password_hash."""
    id: int
    email: str
    username: str
    full_name: str
    skills: Optional[dict]
    on_time_rate: float
    created_at: datetime

    model_config = {"from_attributes": True}   # Pydantic v2: replaces orm_mode
