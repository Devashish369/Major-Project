"""
database.py – SQLAlchemy 2.0 sync engine, session factory, Base, and get_db dependency.

We use the SYNCHRONOUS engine (not AsyncSession) as specified in PROJECT_SPEC.md section 3.
All models must use SQLAlchemy 2.0 style: Mapped, mapped_column, select().
No session.query() calls anywhere in the project.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session
from app.config import settings


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
