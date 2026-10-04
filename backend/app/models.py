"""
models.py – SQLAlchemy 2.0 ORM models for IntelliPM.

Rules (enforced everywhere):
  - Mapped[T] + mapped_column() only.  Never Column() at module level.
  - select() for queries.  Never session.query().
  - Every table: id (int PK), created_at (datetime, server default = now).
  - JSON columns: use SQLAlchemy JSON type (works for SQLite and Postgres).

M1 adds: User
M2 will add: Project, ProjectMember, Sprint
M3 will add: Task, TaskDependency, ActivityLog
M12 will add: Decision
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import JSON, DateTime, Float, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


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
        server_default=func.now(),   # DB-side default so it's always set
        nullable=False,
    )

    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    username: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)

    # skills is a JSON dict {"skill_name": level 1-5}; default = empty dict
    skills: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, default=dict)

    # on_time_rate: used by assignment optimizer; default 0.7 means 70% on-time
    on_time_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.7)
