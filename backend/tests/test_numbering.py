"""
tests/test_numbering.py – tasks and decisions are numbered #1, #2 … separately in every project.
"""
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.main import app
from app.migrations import upgrade
from tests.conftest import engine_test, TestingSessionLocal
from tests.test_ai import MOCK_PLAN_JSON

API = "/api/v1"


@pytest.fixture
def client():
    return TestClient(app)


def _user(client, name):
    r = client.post(f"{API}/auth/register", json={"email": f"{name}@num.org", "username": name,
                                                   "full_name": name.title(), "password": "Secure#2026"})
    return {"Authorization": f"Bearer {r.json()['data']['access_token']}"}


def _project(client, h, title):
    return client.post(f"{API}/projects", json={"title": title}, headers=h).json()["data"]["id"]


def _task(client, h, pid, title):
    return client.post(f"{API}/projects/{pid}/tasks", json={"title": title}, headers=h).json()["data"]


def test_each_project_counts_tasks_from_one(client):
    h = _user(client, "numa")
    p1, p2 = _project(client, h, "One"), _project(client, h, "Two")
    first = [_task(client, h, p1, f"A{i}") for i in range(10)]
    second = [_task(client, h, p2, f"B{i}") for i in range(3)]
    assert [t["number"] for t in first] == list(range(1, 11))
    assert [t["number"] for t in second] == [1, 2, 3]          # not 11, 12, 13
    assert second[0]["id"] != second[0]["number"]               # the internal id is separate
    listed = client.get(f"{API}/projects/{p2}/tasks", headers=h).json()["data"]
    assert sorted(t["number"] for t in listed) == [1, 2, 3]


def test_a_deleted_number_is_never_reused(client):
    h = _user(client, "numb")
    pid = _project(client, h, "P")
    t1, t2, t3 = (_task(client, h, pid, n) for n in ("x", "y", "z"))
    assert client.delete(f"{API}/tasks/{t3['id']}", headers=h).status_code in (200, 204)
    assert _task(client, h, pid, "w")["number"] == 4            # #3 stays retired


def test_decisions_are_numbered_per_project(client):
    h = _user(client, "numc")
    p1, p2 = _project(client, h, "One"), _project(client, h, "Two")
    mk = lambda pid, t: client.post(f"{API}/projects/{pid}/decisions", json={"title": t, "decision": "d"},
                                    headers=h).json()["data"]
    a = [mk(p1, f"a{i}") for i in range(3)]
    b = mk(p2, "b")
    assert [d["number"] for d in a] == [1, 2, 3] and b["number"] == 1
    listed = client.get(f"{API}/projects/{p2}/decisions", headers=h).json()["data"]
    assert [d["number"] for d in listed] == [1]


def test_ai_plan_tasks_continue_the_project_numbering(client):
    h = _user(client, "numd")
    pid = _project(client, h, "Plan")
    _task(client, h, pid, "existing")
    r = client.post(f"{API}/projects/{pid}/apply-plan", json={"plan": json.loads(MOCK_PLAN_JSON), "source": "llm"},
                    headers=h)
    assert r.status_code == 201
    nums = sorted(t["number"] for t in client.get(f"{API}/projects/{pid}/tasks", headers=h).json()["data"])
    assert nums == [1, 2, 3, 4]


def test_report_text_uses_the_project_number(client):
    h = _user(client, "nume")
    other = _project(client, h, "Other")
    for i in range(5):
        _task(client, h, other, f"o{i}")                        # pushes internal ids up
    pid = _project(client, h, "Main")
    blocker, blocked = _task(client, h, pid, "Blocker"), _task(client, h, pid, "Blocked")
    client.post(f"{API}/tasks/{blocked['id']}/dependencies", json={"depends_on_id": blocker["id"]}, headers=h)
    rep = client.get(f"{API}/projects/{pid}/report", headers=h).json()["data"]
    text_all = " ".join(rep["insights"] + rep["suggested_actions"])
    assert "#1 'Blocker'" in text_all and f"#{blocker['id']} " not in text_all
    assert rep["blocked_tasks"][0]["number"] == 2 and rep["blocked_tasks"][0]["blockers"][0]["number"] == 1


def test_ask_context_tags_use_project_numbers(client):
    from app.services.ask import build_context
    h = _user(client, "numf")
    other = _project(client, h, "Other")
    _task(client, h, other, "noise")
    pid = _project(client, h, "Main")
    t = _task(client, h, pid, "Pick a database")
    db = TestingSessionLocal()
    try:
        ctx, sources = build_context(db, pid)
    finally:
        db.close()
    assert "[T1] Pick a database" in ctx
    assert sources["T1"] == {"type": "task", "id": t["id"], "number": 1}


def test_migration_numbers_an_old_database(client):
    """A database created before numbering existed gets numbers 1..n per project, oldest first."""
    h = _user(client, "numg")
    p1, p2 = _project(client, h, "One"), _project(client, h, "Two")
    for i in range(3):
        _task(client, h, p1, f"a{i}")
    _task(client, h, p2, "b0")
    client.post(f"{API}/projects/{p2}/decisions", json={"title": "t", "decision": "d"}, headers=h)

    with engine_test.begin() as conn:             # turn the tables back into the old shape
        conn.execute(text("DROP INDEX uq_task_project_number"))
        conn.execute(text("DROP INDEX uq_decision_project_number"))
        conn.execute(text("ALTER TABLE tasks DROP COLUMN number"))
        conn.execute(text("ALTER TABLE decisions DROP COLUMN number"))
        conn.execute(text("ALTER TABLE projects DROP COLUMN task_seq"))
        conn.execute(text("ALTER TABLE projects DROP COLUMN decision_seq"))
        conn.execute(text("ALTER TABLE users DROP COLUMN token_version"))

    upgrade(engine_test)
    upgrade(engine_test)                          # running it again changes nothing

    with engine_test.connect() as conn:
        rows = conn.execute(text("SELECT project_id, number FROM tasks ORDER BY project_id, id")).all()
        seqs = dict(conn.execute(text("SELECT id, task_seq FROM projects")).all())
        dnum = conn.execute(text("SELECT number FROM decisions")).scalar_one()
    assert [n for pid, n in rows if pid == p1] == [1, 2, 3] and [n for pid, n in rows if pid == p2] == [1]
    assert seqs == {p1: 3, p2: 1} and dnum == 1
    # and new rows continue from there; old tokens (no version) still work
    assert _task(client, h, p1, "new")["number"] == 4
