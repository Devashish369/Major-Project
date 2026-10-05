"""
models.py – SQLAlchemy 2.0 ORM models for IntelliPM.

Rules (enforced everywhere):
  - Mapped[T] + mapped_column() only.  Never Column() at module level.
  - select() for queries.  Never session.query().
  - Every table: id (int PK), created_at (datetime, server default = now).
  - JSON columns: use SQLAlchemy JSON type (works for SQLite and Postgres).

M1 added: User
M2 added: Project, ProjectMember
M3 will add: Task, TaskDependency, ActivityLog, Sprint
M12 will add: Decision
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON, DateTime, Float, ForeignKey, Integer, String,
    UniqueConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


# ── Users ─────────────────────────────────────────────────────────────────────

class User(Base):
    """
    users table – stores credentials, profile, and skill metadata.

    skills: JSON dict, e.g. {"react": 4, "python": 5}  (levels 1–5)
    on_time_rate: float 0–1; used by the assignment optimizer (section 8.2)
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    username: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)

    # skills is a JSON dict {"skill_name": level 1-5}; default = empty dict
    skills: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, default=dict)

    # on_time_rate: used by assignment optimizer; default 0.7 = 70% on-time history
    on_time_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.7)


# ── Projects ──────────────────────────────────────────────────────────────────

class Project(Base):
    """
    projects table.

    status:   pending | in_progress | completed
    priority: low | medium | high
    created_by → users.id (creator is automatically admin in project_members)
    Deleting a project cascades to project_members (and later tasks, sprints).
    """

    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Enum-like strings – validated by Pydantic in schemas.py
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    priority: Mapped[str] = mapped_column(String, nullable=False, default="medium")

    start_date: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # ISO date string
    due_date: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # FK → users; ON DELETE SET NULL so deleting a user doesn't wipe the project
    created_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class ProjectMember(Base):
    """
    project_members table – join table between projects and users.

    role: admin | member
    capacity_hours_per_week: used by assignment optimizer and workload calc.
    unique(project_id, user_id) – one row per user per project.
    """

    __tablename__ = "project_members"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    project_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # admin can delete/apply AI; member can edit tasks
    role: Mapped[str] = mapped_column(String, nullable=False, default="member")

    # used by workload and assignment algorithms (section 8.2 / 8.3)
    capacity_hours_per_week: Mapped[int] = mapped_column(Integer, nullable=False, default=30)

    __table_args__ = (
        UniqueConstraint("project_id", "user_id", name="uq_project_member"),
    )
