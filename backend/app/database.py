"""
database.py – SQLAlchemy 2.0 sync engine, session factory, Base, and get_db dependency.

We use the SYNCHRONOUS engine (not AsyncSession) as specified in PROJECT_SPEC.md section 3.
All models must use SQLAlchemy 2.0 style: Mapped, mapped_column, select().
No session.query() calls anywhere in the project.
"""

import sqlite3

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session
from app.config import settings


# ── SQLite: enforce foreign keys ──────────────────────────────────────────────
# SQLite ignores FOREIGN KEY / ON DELETE CASCADE unless this pragma is set on every
# connection.  Without it, deleting a project left its members, tasks and activity
# behind, and because SQLite reuses freed ids, the next new project could inherit
# another user's members and tasks.  PostgreSQL always enforces them, so this makes
# both databases behave the same.  Registered on Engine so the test engine gets it too.
@event.listens_for(Engine, "connect")
def _sqlite_enforce_foreign_keys(dbapi_connection, _record):
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


# ── Engine ────────────────────────────────────────────────────────────────────
# SQLite needs check_same_thread=False (FastAPI uses a thread pool).
# PostgreSQL gets pool_pre_ping so a connection that the host closed while the
# service was idle (Neon / Render free tier do this) is replaced instead of failing.
engine_kwargs = {"echo": False}   # set echo=True to debug SQL
if settings.is_sqlite:
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    engine_kwargs.update(pool_pre_ping=True, pool_recycle=300)

engine = create_engine(settings.database_url, **engine_kwargs)

# ── Session factory ───────────────────────────────────────────────────────────
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)


# ── Declarative base ──────────────────────────────────────────────────────────
# All ORM models inherit from this class to register with the metadata.
class Base(DeclarativeBase):
    pass


# ── Dependency ────────────────────────────────────────────────────────────────
def get_db():
    """
    FastAPI dependency that yields a database session and guarantees close.

    Usage in a router:
        db: Session = Depends(get_db)
    """
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
