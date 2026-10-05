"""
schemas.py – Pydantic v2 request/response schemas for IntelliPM.

Naming convention:
  <Model>Create  – body for POST (creation)
  <Model>Update  – body for PATCH (partial update)
  <Model>Out     – what we send back in the API response (never password_hash)

M1: User schemas + Token schema.
M2: Project, ProjectMember schemas.
"""

from datetime import datetime
from typing import Literal, Optional

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


# ── Project ───────────────────────────────────────────────────────────────────

ProjectStatus   = Literal["pending", "in_progress", "completed"]
ProjectPriority = Literal["low", "medium", "high"]


class ProjectCreate(BaseModel):
    """Body for POST /projects."""
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    status: ProjectStatus = "pending"
    priority: ProjectPriority = "medium"
    start_date: Optional[str] = None   # ISO date string e.g. "2026-10-01"
    due_date: Optional[str] = None


class ProjectUpdate(BaseModel):
    """Body for PATCH /projects/{id} – all fields optional."""
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    status: Optional[ProjectStatus] = None
    priority: Optional[ProjectPriority] = None
    start_date: Optional[str] = None
    due_date: Optional[str] = None


class ProjectOut(BaseModel):
    """
    Project returned by GET /projects and GET /projects/{id}.
    task_count, member_count, done_ratio are computed in the router.
    health_score is null until M7.
    """
    id: int
    title: str
    description: Optional[str]
    status: str
    priority: str
    start_date: Optional[str]
    due_date: Optional[str]
    created_by: Optional[int]
    created_at: datetime
    # Computed fields (populated by the router, not stored in DB)
    task_count: int = 0
    member_count: int = 0
    done_ratio: float = 0.0
    health_score: Optional[float] = None   # null until M7

    model_config = {"from_attributes": True}


# ── Project Member ────────────────────────────────────────────────────────────

MemberRole = Literal["admin", "member"]


class MemberAdd(BaseModel):
    """Body for POST /projects/{id}/members – add by email."""
    email: EmailStr
    role: MemberRole = "member"
    capacity_hours_per_week: int = Field(default=30, ge=1, le=168)


class MemberUpdate(BaseModel):
    """Body for PATCH /projects/{id}/members/{user_id}."""
    role: Optional[MemberRole] = None
    capacity_hours_per_week: Optional[int] = Field(None, ge=1, le=168)


class MemberOut(BaseModel):
    """Member row joined with user info, returned by GET /projects/{id}/members."""
    user_id: int
    email: str
    username: str
    full_name: str
    skills: Optional[dict]
    on_time_rate: float
    role: str
    capacity_hours_per_week: int

    model_config = {"from_attributes": True}
