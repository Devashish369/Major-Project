"""
models.py – SQLAlchemy 2.0 ORM models for IntelliPM.

M0: This file is intentionally minimal – it defines only the Base import so
    that create_all() works at startup without errors.

All full table definitions are added in M1 (users, projects, etc.) per the
data model in PROJECT_SPEC.md section 6.

Rules (must be followed in every module):
  - Use Mapped[T] and mapped_column() – never Column() at module level.
  - Use select() for queries – never session.query().
  - Every table must have `id` (int PK) and `created_at`.
"""

# Models will be added here in M1+.
# The import in main.py (`import app.models`) is what triggers registration
# with Base.metadata so create_all() picks up new tables automatically.
