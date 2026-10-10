"""
migrations.py – tiny, idempotent schema upgrades run at start-up.

`Base.metadata.create_all` creates missing TABLES but never adds COLUMNS to tables that already
exist, so a database created by an older version (e.g. the deployed Neon database) needs these
steps.  Every step checks first and is safe to run on every start, on SQLite and PostgreSQL.

1. users.token_version, projects.task_seq / decision_seq, tasks.number, decisions.number
2. Backfill numbers 1..n per project in creation order for rows that have none, and set each
   project's counters to the highest number used.
3. Unique indexes (project_id, number).
"""
import logging

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

_COLUMNS = [
    ("users", "token_version", "INTEGER NOT NULL DEFAULT 0"),
    ("projects", "task_seq", "INTEGER NOT NULL DEFAULT 0"),
    ("projects", "decision_seq", "INTEGER NOT NULL DEFAULT 0"),
    ("tasks", "number", "INTEGER"),
    ("decisions", "number", "INTEGER"),
]


def _backfill(conn, table: str, counter: str) -> int:
    """Give un-numbered rows the next numbers of their project, oldest first."""
    rows = conn.execute(text(
        f"SELECT id, project_id FROM {table} WHERE number IS NULL ORDER BY project_id, created_at, id"
    )).all()
    if not rows:
        return 0
    highest = dict(conn.execute(text(
        f"SELECT project_id, COALESCE(MAX(number), 0) FROM {table} GROUP BY project_id"
    )).all())
    params = []
    for row_id, project_id in rows:
        highest[project_id] = highest.get(project_id, 0) + 1
        params.append({"n": highest[project_id], "id": row_id})
    # one executemany (pipelined by the driver) instead of one round trip per row
    conn.execute(text(f"UPDATE {table} SET number = :n WHERE id = :id"), params)
    for project_id, n in highest.items():
        conn.execute(text(f"UPDATE projects SET {counter} = :n WHERE id = :pid AND {counter} < :n"),
                     {"n": n, "pid": project_id})
    return len(rows)


def upgrade(engine: Engine) -> None:
    with engine.begin() as conn:
        insp = inspect(conn)
        tables = set(insp.get_table_names())
        for table, column, ddl in _COLUMNS:
            if table in tables and column not in {c["name"] for c in insp.get_columns(table)}:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))
                logger.info("migration: added %s.%s", table, column)

        if {"tasks", "decisions", "projects"} <= tables:
            n_tasks = _backfill(conn, "tasks", "task_seq")
            n_decisions = _backfill(conn, "decisions", "decision_seq")
            if n_tasks or n_decisions:
                logger.info("migration: numbered %d tasks and %d decisions", n_tasks, n_decisions)
            conn.execute(text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_task_project_number ON tasks (project_id, number)"))
            conn.execute(text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_decision_project_number ON decisions (project_id, number)"))
