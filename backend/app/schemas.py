"""
schemas.py – Pydantic v2 request/response schemas for IntelliPM.

Naming convention:
  <Model>Create  – body for POST (creation)
  <Model>Update  – body for PATCH (partial update)
  <Model>Out     – what we send back in the API response (never password_hash)

M1: User schemas + Token schema.
M2: Project, ProjectMember schemas.
M3: Task, TaskDependency, ActivityLog schemas.
"""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator


# ── Auth / Token ──────────────────────────────────────────────────────────────

class TokenOut(BaseModel):
    """Returned by POST /auth/login."""
    access_token: str
    token_type: str = "bearer"


# ── Password policy (cryptography & security protocols) ──────────────────────
# bcrypt only uses the first 72 BYTES of a password (bcrypt 5 refuses longer ones), so longer
# passwords are rejected with a clear message instead of a server error.
COMMON_PASSWORDS = {
    "password", "password1", "password123", "passw0rd", "12345678", "123456789", "1234567890",
    "qwerty123", "qwertyuiop", "iloveyou1", "admin123", "welcome1", "welcome123", "letmein1",
    "abc12345", "abcd1234", "11111111", "00000000", "asdf1234", "india123", "test1234",
}


def check_password_strength(v: str) -> str:
    if len(v) < 8:
        raise ValueError("Password must be at least 8 characters.")
    if len(v.encode("utf-8")) > 72:
        raise ValueError("Password must be at most 72 bytes (about 72 characters).")
    if not any(c.isalpha() for c in v) or not any(c.isdigit() for c in v):
        raise ValueError("Password must contain at least one letter and one number.")
    if v.lower() in COMMON_PASSWORDS:
        raise ValueError("This password is too common. Please choose another one.")
    return v


# ── User ──────────────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    """Body for POST /auth/register."""
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)
    full_name: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def strong_password(cls, v: str) -> str:
        return check_password_strength(v)

    @model_validator(mode="after")
    def password_not_personal(self):
        p = self.password.lower()
        if len(self.username) >= 4 and self.username.lower() in p:
            raise ValueError("Password must not contain your username.")
        local = str(self.email).split("@")[0].lower()
        if len(local) >= 4 and local in p:
            raise ValueError("Password must not contain your email address.")
        return self

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
    password: str = Field(..., max_length=128)


class ChangePasswordRequest(BaseModel):
    """Body for POST /auth/change-password."""
    current_password: str = Field(..., max_length=128)
    new_password: str = Field(..., max_length=128)

    @field_validator("new_password")
    @classmethod
    def strong_password(cls, v: str) -> str:
        return check_password_strength(v)


class SecurityEventOut(BaseModel):
    id: int
    created_at: datetime
    event: str
    ip: Optional[str]
    user_agent: Optional[str]

    model_config = {"from_attributes": True}


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
        if len(v) > 50:
            raise ValueError("At most 50 skills.")
        for skill, level in v.items():
            if isinstance(skill, str) and len(skill.strip()) > 40:
                raise ValueError("Skill names must be at most 40 characters.")
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


# ── Task ──────────────────────────────────────────────────────────────────────

TaskStatus   = Literal["todo", "in_progress", "done"]
TaskPriority = Literal["low", "medium", "high", "critical"]


class TaskCreate(BaseModel):
    """Body for POST /projects/{id}/tasks."""
    title: str = Field(..., min_length=1, max_length=300)
    description: Optional[str] = Field(None, max_length=5000)
    status: TaskStatus = "todo"
    priority: TaskPriority = "medium"
    estimate_hours: Optional[float] = Field(None, ge=0)
    assignee_id: Optional[int] = None
    due_date: Optional[str] = None       # ISO date string
    required_skills: Optional[list[str]] = Field(None, max_length=20)

    @field_validator("required_skills")
    @classmethod
    def short_skill_names(cls, v):
        return _check_required_skills(v)
    module: Optional[str] = None
    sprint_id: Optional[int] = None


class TaskUpdate(BaseModel):
    """Body for PATCH /tasks/{id} – all fields optional."""
    title: Optional[str] = Field(None, min_length=1, max_length=300)
    description: Optional[str] = Field(None, max_length=5000)
    status: Optional[TaskStatus] = None
    priority: Optional[TaskPriority] = None
    estimate_hours: Optional[float] = Field(None, ge=0)
    actual_hours: Optional[float] = Field(None, ge=0)
    assignee_id: Optional[int] = None
    due_date: Optional[str] = None
    required_skills: Optional[list[str]] = Field(None, max_length=20)

    @field_validator("required_skills")
    @classmethod
    def short_skill_names(cls, v):
        return _check_required_skills(v)
    module: Optional[str] = None
    sprint_id: Optional[int] = None


def _check_required_skills(v):
    if v is not None and any(len(str(x)) > 40 for x in v):
        raise ValueError("Skill names must be at most 40 characters.")
    return v


class TaskOut(BaseModel):
    """Task row returned to clients."""
    id: int
    number: Optional[int] = None    # per-project number shown as #1, #2 … (id is the internal key)
    project_id: int
    sprint_id: Optional[int]
    title: str
    description: Optional[str]
    status: str
    priority: str
    estimate_hours: Optional[float]
    actual_hours: Optional[float]
    assignee_id: Optional[int]
    due_date: Optional[str]
    required_skills: Optional[list]
    completed_at: Optional[datetime]
    module: Optional[str]
    created_at: datetime
    # Populated by router: list of depends_on task IDs
    dependencies: list[int] = []

    model_config = {"from_attributes": True}


# ── Task Dependency ───────────────────────────────────────────────────────────

class DependencyAdd(BaseModel):
    """Body for POST /tasks/{id}/dependencies."""
    depends_on_id: int


class DependencyOut(BaseModel):
    """Dependency edge returned to clients."""
    id: int
    task_id: int
    depends_on_id: int
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Activity Log ──────────────────────────────────────────────────────────────

class ActivityLogOut(BaseModel):
    """Activity log entry returned to clients."""
    id: int
    project_id: int
    user_id: int
    task_id: Optional[int]
    action: str
    meta: Optional[dict]
    created_at: datetime

    model_config = {"from_attributes": True}


# ── AI Planner (M4) ───────────────────────────────────────────────────────────

class GeneratePlanRequest(BaseModel):
    """Body for POST /ai/generate-plan."""
    description: str = Field(..., min_length=10, max_length=5000)
    team_size: int = Field(default=3, ge=1, le=50)
    duration_weeks: int = Field(default=8, ge=1, le=104)


class ApplyPlanRequest(BaseModel):
    """Body for POST /projects/{id}/apply-plan (admin only)."""
    plan: dict            # the plan dict from generate-plan
    source: str = "llm"  # "llm" or "fallback" – stored in activity log


# ── Assignment optimizer (M5) ─────────────────────────────────────────────────

class AssignmentRecommendRequest(BaseModel):
    """Body for POST /projects/{id}/assignments/recommend."""
    force: bool = False   # if True, also re-optimise already-assigned tasks


class AssignmentItem(BaseModel):
    task_id: int
    user_id: int
    # who the AI suggested; when it differs from user_id the admin overrode it (kept in the activity log)
    recommended_user_id: Optional[int] = None


class AssignmentApplyRequest(BaseModel):
    """Body for POST /projects/{id}/assignments/apply (admin only)."""
    assignments: list[AssignmentItem] = Field(..., max_length=500)


# ── Estimator (M6) ────────────────────────────────────────────────────────────

class EstimateRequest(BaseModel):
    """Body for POST /ai/estimate (spec §8.6)."""
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = Field(default=None, max_length=10000)


# ── Decisions + Ask (M12) ─────────────────────────────────────────────────────

class DecisionCreate(BaseModel):
    """Body for POST /projects/{id}/decisions."""
    title: str = Field(min_length=1, max_length=200)
    decision: str = Field(min_length=1, max_length=2000)
    reason: Optional[str] = Field(default=None, max_length=2000)
    related_task_id: Optional[int] = None


class DecisionOut(BaseModel):
    """Decision log entry returned to clients."""
    id: int
    number: Optional[int] = None    # per-project number shown as D1, D2 …
    project_id: int
    title: str
    decision: str
    reason: Optional[str]
    made_by: Optional[int]
    made_by_name: Optional[str] = None
    related_task_id: Optional[int]
    created_at: datetime

    model_config = {"from_attributes": True}


class AskRequest(BaseModel):
    """Body for POST /projects/{id}/ask."""
    question: str = Field(min_length=3, max_length=500)
