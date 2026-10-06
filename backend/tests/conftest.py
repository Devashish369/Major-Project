"""
conftest.py – Shared pytest fixtures for all IntelliPM backend tests.

Problem solved:
  Each test file previously set up its own in-memory SQLite engine AND
  overrode app.dependency_overrides[get_db]. When pytest collects multiple
  files, the last file's override wins, so the first file's tables aren't
  created in the winning engine.

Solution:
  Use a single session-scoped in-memory engine with StaticPool (same
  connection reused), create tables once per test function (autouse), and
  set the dependency override in conftest so all test files share it.
"""

import sys
import os

# Ensure 'app' package is importable regardless of where pytest is invoked
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from sqlalchemy import create_engine, StaticPool
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database import Base, get_db

# ── Single shared in-memory SQLite engine ─────────────────────────────────────
# Default: private in-memory SQLite.  To run the whole suite on PostgreSQL instead:
#   TEST_DATABASE_URL=postgresql://user:pass@host:5432/testdb pytest      (database is wiped per test!)
import os

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "sqlite:///:memory:")

if TEST_DATABASE_URL.startswith("sqlite"):
    engine_test = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,   # same connection across threads (required for SQLite :memory:)
    )
else:
    for _prefix in ("postgres://", "postgresql://"):
        if TEST_DATABASE_URL.startswith(_prefix):
            TEST_DATABASE_URL = "postgresql+psycopg://" + TEST_DATABASE_URL[len(_prefix):]
    engine_test = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
TestingSessionLocal = sessionmaker(bind=engine_test, autocommit=False, autoflush=False)


def _override_get_db():
    """FastAPI dependency override pointing at the test engine."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


# Register the override immediately so it applies to all collected tests
app.dependency_overrides[get_db] = _override_get_db


@pytest.fixture(autouse=True)
def reset_db():
    """
    Create all tables before every test, drop them after.
    autouse=True means this fixture runs for EVERY test in EVERY file.
    """
    import app.models  # noqa: F401 – register all ORM models
    Base.metadata.create_all(bind=engine_test)
    yield
    Base.metadata.drop_all(bind=engine_test)
