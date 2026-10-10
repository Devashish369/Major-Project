"""
tests/test_performance.py – guard against the N+1 query pattern.

In the deployed app every SQL query is a network round trip to the database, so the NUMBER of
queries per request (not the size of the data) decides how fast a screen feels.  These tests fail
if a list endpoint starts issuing more queries as the project / task count grows.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event

from app.main import app
from tests.conftest import engine_test

API = "/api/v1"


@pytest.fixture
def client():
    return TestClient(app)


class QueryCounter:
    def __enter__(self):
        self.n = 0
        event.listen(engine_test, "before_cursor_execute", self._hit)
        return self

    def _hit(self, *args, **kwargs):
        self.n += 1

    def __exit__(self, *exc):
        event.remove(engine_test, "before_cursor_execute", self._hit)


def _user(client, name):
    r = client.post(f"{API}/auth/register", json={"email": f"{name}@perf.com", "username": name,
                                                   "full_name": name, "password": "Secure#2026"})
    return {"Authorization": f"Bearer {r.json()['data']['access_token']}"}


def _project_with_tasks(client, h, title, n_tasks):
    pid = client.post(f"{API}/projects", json={"title": title, "due_date": "2030-01-01"}, headers=h).json()["data"]["id"]
    ids = [client.post(f"{API}/projects/{pid}/tasks", json={"title": f"T{i}", "estimate_hours": 4}, headers=h).json()["data"]["id"]
           for i in range(n_tasks)]
    for a, b in zip(ids[1:], ids[:-1]):                       # a dependency chain
        client.post(f"{API}/tasks/{a}/dependencies", json={"depends_on_id": b}, headers=h)
    return pid


def test_project_list_query_count_does_not_grow_with_projects(client):
    h = _user(client, "perf1")
    _project_with_tasks(client, h, "P0", 4)
    with QueryCounter() as few:
        assert len(client.get(f"{API}/projects", headers=h).json()["data"]) == 1
    for i in range(1, 8):
        _project_with_tasks(client, h, f"P{i}", 4)
    with QueryCounter() as many:
        assert len(client.get(f"{API}/projects", headers=h).json()["data"]) == 8
    assert many.n == few.n, f"1 project: {few.n} queries, 8 projects: {many.n} queries (N+1 is back)"
    assert many.n <= 8


def test_task_list_query_count_does_not_grow_with_tasks(client):
    h = _user(client, "perf2")
    small = _project_with_tasks(client, h, "S", 3)
    big = _project_with_tasks(client, h, "B", 25)
    with QueryCounter() as a:
        assert len(client.get(f"{API}/projects/{small}/tasks", headers=h).json()["data"]) == 3
    with QueryCounter() as b:
        data = client.get(f"{API}/projects/{big}/tasks", headers=h).json()["data"]
    assert len(data) == 25 and b.n == a.n, f"3 tasks: {a.n} queries, 25 tasks: {b.n} queries (N+1 is back)"
    assert sum(len(t["dependencies"]) for t in data) == 24      # bulk-loaded dependencies are still correct


def test_project_pages_need_only_a_few_queries(client):
    h = _user(client, "perf3")
    pid = _project_with_tasks(client, h, "Q", 10)
    for path, limit in [("", 7), ("/members", 4), ("/analytics/health", 8), ("/analytics/forecast", 8),
                        ("/analytics/workload", 6), ("/decisions", 5), ("/sprints", 5)]:
        with QueryCounter() as q:
            assert client.get(f"{API}/projects/{pid}{path}", headers=h).status_code == 200
        assert q.n <= limit, f"{path or '/'} used {q.n} queries (limit {limit})"


def test_non_members_cost_one_membership_query_and_get_404(client):
    owner, other = _user(client, "perf4"), _user(client, "perf5")
    pid = _project_with_tasks(client, owner, "X", 2)
    with QueryCounter() as q:
        assert client.get(f"{API}/projects/{pid}/tasks", headers=other).status_code == 404
        assert client.get(f"{API}/projects/999999/tasks", headers=other).status_code == 404
    assert q.n == 4          # (user lookup + membership lookup) x 2: nothing else is touched


def test_responses_over_1kb_are_gzip_compressed(client):
    h = _user(client, "perf6")
    pid = _project_with_tasks(client, h, "Z", 25)
    r = client.get(f"{API}/projects/{pid}/tasks", headers={**h, "Accept-Encoding": "gzip"})
    assert r.headers.get("content-encoding") == "gzip" and len(r.json()["data"]) == 25
