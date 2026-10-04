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
# connect_args is SQLite-specific: allows the same connection to be used
# across threads (needed because FastAPI runs in a thread pool).
connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=False,   # set True to debug SQL; keep False in production
)

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
