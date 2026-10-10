"""
database.py – SQLAlchemy 2.0 sync engine, session factory, Base, and get_db dependency.

We use the SYNCHRONOUS engine (not AsyncSession) as specified in PROJECT_SPEC.md section 3.
All models must use SQLAlchemy 2.0 style: Mapped, mapped_column, select().
No session.query() calls anywhere in the project.
"""

import contextvars
import sqlite3
import time

from sqlalchemy import create_engine, event, exc
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


# ── Per-request query statistics (Server-Timing header, app/middleware.py) ─────
# The middleware puts a [count, seconds] list in this context variable; FastAPI runs sync
# endpoints in a worker thread with a COPY of the context, which still points at the same list.
query_stats: contextvars.ContextVar = contextvars.ContextVar("query_stats", default=None)


@event.listens_for(Engine, "before_cursor_execute")
def _query_start(conn, cursor, statement, parameters, context, executemany):
    conn.info.setdefault("_qstart", []).append(time.perf_counter())


@event.listens_for(Engine, "after_cursor_execute")
def _query_end(conn, cursor, statement, parameters, context, executemany):
    started = conn.info.get("_qstart")
    stats = query_stats.get()
    if started:
        t0 = started.pop()
        if stats is not None:
            stats[0] += 1
            stats[1] += time.perf_counter() - t0


# ── Engine ────────────────────────────────────────────────────────────────────
# SQLite needs check_same_thread=False (FastAPI uses a thread pool).
# PostgreSQL: Neon closes connections when it suspends after 5 idle minutes, so a pooled
# connection may be dead.  `pool_pre_ping` would test EVERY checkout with "SELECT 1" – one extra
# database round trip on every request.  Instead we only test a connection that has been idle
# for more than 30 s (see _ping_if_idle); one used a moment ago is known to be alive.
# pool_recycle=240 s (< Neon's 5 min) replaces old connections before Neon can drop them.
engine_kwargs = {"echo": False}   # set echo=True to debug SQL
if settings.is_sqlite:
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    engine_kwargs.update(pool_recycle=240, pool_size=5, max_overflow=5)

engine = create_engine(settings.database_url, **engine_kwargs)

IDLE_PING_SECONDS = 30

if not settings.is_sqlite:
    @event.listens_for(engine, "checkin")
    def _mark_used(dbapi_connection, record):
        record.info["last_used"] = time.monotonic()

    @event.listens_for(engine, "checkout")
    def _ping_if_idle(dbapi_connection, record, proxy):
        last = record.info.get("last_used")
        if last is None or time.monotonic() - last < IDLE_PING_SECONDS:
            return                      # brand-new or recently used: alive
        try:
            cur = dbapi_connection.cursor()
            cur.execute("SELECT 1")
            cur.close()
            dbapi_connection.rollback()
        except Exception as e:          # dead: the pool discards it and connects again
            raise exc.DisconnectionError() from e

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
