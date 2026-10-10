"""
models.py – SQLAlchemy 2.0 ORM models for IntelliPM.

Rules (enforced everywhere):
  - Mapped[T] + mapped_column() only.  Never Column() at module level.
  - select() for queries.  Never session.query().
  - Every table: id (int PK), created_at (datetime, server default = now).
  - JSON columns: use SQLAlchemy JSON type (works for SQLite and Postgres).

M1 added: User
M2 added: Project, ProjectMember
M3 added: Task, TaskDependency, ActivityLog
M12 will add: Decision
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON, DateTime, Float, ForeignKey, Index, Integer, String,
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

    skills: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, default=dict)
    on_time_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.7)
    # Bumped on password change / "sign out everywhere": every token carries the version it was
    # issued with, so older tokens stop working at once (see deps.get_current_user).
    token_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")


# ── Projects ──────────────────────────────────────────────────────────────────

class Project(Base):
    """
    projects table.
    status:   pending | in_progress | completed
    priority: low | medium | high
    """

    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    priority: Mapped[str] = mapped_column(String, nullable=False, default="medium")
    start_date: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    due_date: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    created_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Last task / decision number handed out in THIS project (tasks are #1, #2 … per project).
    # Counters, not max()+1, so a deleted task's number is never reused.  See app/numbering.py.
    task_seq: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    decision_seq: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")


class ProjectMember(Base):
    """
    project_members table – join table between projects and users.
    role: admin | member
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
    role: Mapped[str] = mapped_column(String, nullable=False, default="member")
    capacity_hours_per_week: Mapped[int] = mapped_column(Integer, nullable=False, default=30)

    __table_args__ = (
        UniqueConstraint("project_id", "user_id", name="uq_project_member"),
    )


# ── Tasks ─────────────────────────────────────────────────────────────────────

class Task(Base):
    """
    tasks table.

    status:   todo | in_progress | done
    priority: low | medium | high | critical

    completed_at rule (spec §6):
      - Setting status → 'done' sets completed_at = now (UTC).
      - Moving away from 'done' clears completed_at = None.
    This logic lives in services/tasks.py so it's always applied consistently.

    required_skills: JSON list of skill names, e.g. ["python", "react"]
    """

    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    project_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # sprint_id nullable – tasks can exist outside sprints until M3/M4
    sprint_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("sprints.id", ondelete="SET NULL"), nullable=True
    )

    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    status: Mapped[str] = mapped_column(String, nullable=False, default="todo")
    priority: Mapped[str] = mapped_column(String, nullable=False, default="medium")

    estimate_hours: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    actual_hours: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Assignee is a project member; nullable = unassigned
    assignee_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    due_date: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # ISO date

    # JSON list of skill names e.g. ["python", "react"]
    required_skills: Mapped[Optional[list]] = mapped_column(JSON, nullable=True, default=list)

    # Set when status becomes 'done'; cleared when moving out of 'done' (spec §6)
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Optional module label for AI planner grouping (spec §6)
    module: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Number shown to people (#1, #2 …), counted per project.  `id` stays the internal key
    # used in URLs and dependencies.  Filled automatically on insert (app/numbering.py).
    number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    __table_args__ = (Index("uq_task_project_number", "project_id", "number", unique=True),)


class TaskDependency(Base):
    """
    task_dependencies table – directed edge: task_id depends on depends_on_id.

    Constraints enforced in services/tasks.py:
      1. No self-reference (task_id == depends_on_id).
      2. No cycles – DFS from depends_on_id must not reach task_id.
    unique(task_id, depends_on_id) prevents duplicate edges.
    """

    __tablename__ = "task_dependencies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    task_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    depends_on_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )

    __table_args__ = (
        UniqueConstraint("task_id", "depends_on_id", name="uq_task_dep"),
    )


# ── Activity log ──────────────────────────────────────────────────────────────

class ActivityLog(Base):
    """
    activity_log table – append-only audit trail.

    action: human-readable string, e.g. "task_created", "task_moved",
            "task_assigned", "task_deleted".
    meta:   JSON dict with context, e.g. {"from": "todo", "to": "in_progress"}.
    task_id is nullable (project-level actions like member changes don't have a task).
    """

    __tablename__ = "activity_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    project_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    task_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True
    )
    action: Mapped[str] = mapped_column(String, nullable=False)
    meta: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, default=dict)


# ── Sprints ───────────────────────────────────────────────────────────────────

class Sprint(Base):
    """
    sprints table – added in M3, used heavily from M4 onward.

    Tasks reference sprint_id (nullable) so they can exist outside sprints.
    """

    __tablename__ = "sprints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    project_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    start_date: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    end_date: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    goal: Mapped[Optional[str]] = mapped_column(String, nullable=True)


# ── Decisions (table added in M10 so the demo seed can fill it; CRUD is M12) ──
class Decision(Base):
    """
    decisions table – a project's decision log (spec §6).
    related_task_id is optional; made_by is the user who recorded it.
    """
    __tablename__ = "decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    project_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    decision: Mapped[str] = mapped_column(String, nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    made_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    related_task_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True
    )
    # Shown as D1, D2 … per project (filled automatically on insert, app/numbering.py)
    number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    __table_args__ = (Index("uq_decision_project_number", "project_id", "number", unique=True),)


# ── Security events (sign-in audit trail, brute-force protection) ────────────
class SecurityEvent(Base):
    """
    security_events table – who tried to sign in, from where, and what happened.

    event: login_success | login_failed | login_blocked | register | password_changed |
           sessions_revoked
    Used for (1) brute-force protection: recent failures are counted here, so limits survive a
    restart, and (2) the user's own "Recent sign-in activity" list (digital forensics).
    """
    __tablename__ = "security_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    email: Mapped[Optional[str]] = mapped_column(String(320), nullable=True, index=True)
    event: Mapped[str] = mapped_column(String(32), nullable=False)
    ip: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)


# Per-project numbering of tasks and decisions (registers a before_flush hook)
import app.numbering  # noqa: E402,F401
