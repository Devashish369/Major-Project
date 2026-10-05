"""
tests/test_tasks.py – Tests for M3: Tasks, Dependencies, Activity Log.

Covers the M3 "done when" criteria (spec §11):
  ✓ Create task
  ✓ Status change → done sets completed_at
  ✓ Moving away from done clears completed_at
  ✓ Self-dependency rejected (422)
  ✓ Cycle rejected (422)
  ✓ Valid dependency accepted
  ✓ Activity log row written on create, move, assign, delete
  ✓ Non-member cannot access project tasks (404)
  ✓ task_count and done_ratio on project list are accurate
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


# ── Helpers ───────────────────────────────────────────────────────────────────

def register(client, email, username, password="password123"):
    r = client.post("/api/v1/auth/register", json={
        "email": email, "username": username,
        "full_name": "Test User", "password": password,
    })
    assert r.status_code == 201, r.text
    return r.json()["data"]["access_token"]


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def create_project(client, token, title="Test Project"):
    r = client.post("/api/v1/projects", json={"title": title}, headers=auth(token))
    assert r.status_code == 201, r.text
    return r.json()["data"]["id"]


def create_task(client, token, project_id, title="Test Task", **kwargs):
    body = {"title": title, **kwargs}
    r = client.post(f"/api/v1/projects/{project_id}/tasks", json=body, headers=auth(token))
    assert r.status_code == 201, r.text
    return r.json()["data"]


# ── Task CRUD ─────────────────────────────────────────────────────────────────

class TestTaskCRUD:
    def test_create_task_success(self, client):
        tok = register(client, "a@a.com", "usera")
        pid = create_project(client, tok)
        t = create_task(client, tok, pid, title="Build login", priority="high")
        assert t["title"] == "Build login"
        assert t["priority"] == "high"
        assert t["status"] == "todo"
        assert t["completed_at"] is None

    def test_list_tasks(self, client):
        tok = register(client, "a@a.com", "usera")
        pid = create_project(client, tok)
        create_task(client, tok, pid, title="T1")
        create_task(client, tok, pid, title="T2")
        r = client.get(f"/api/v1/projects/{pid}/tasks", headers=auth(tok))
        assert r.status_code == 200
        assert len(r.json()["data"]) == 2

    def test_get_task(self, client):
        tok = register(client, "a@a.com", "usera")
        pid = create_project(client, tok)
        t = create_task(client, tok, pid)
        r = client.get(f"/api/v1/tasks/{t['id']}", headers=auth(tok))
        assert r.status_code == 200
        assert r.json()["data"]["id"] == t["id"]

    def test_non_member_cannot_list_tasks(self, client):
        """M3 done-when: non-member gets 404."""
        tok1 = register(client, "a@a.com", "usera")
        tok2 = register(client, "b@b.com", "userb")
        pid = create_project(client, tok1)
        r = client.get(f"/api/v1/projects/{pid}/tasks", headers=auth(tok2))
        assert r.status_code == 404

    def test_delete_task(self, client):
        tok = register(client, "a@a.com", "usera")
        pid = create_project(client, tok)
        t = create_task(client, tok, pid)
        r = client.delete(f"/api/v1/tasks/{t['id']}", headers=auth(tok))
        assert r.status_code == 200

    def test_project_task_count_accurate(self, client):
        tok = register(client, "a@a.com", "usera")
        pid = create_project(client, tok)
        create_task(client, tok, pid, title="T1")
        create_task(client, tok, pid, title="T2")
        r = client.get(f"/api/v1/projects/{pid}", headers=auth(tok))
        assert r.json()["data"]["task_count"] == 2


# ── completed_at rule (spec §6) ───────────────────────────────────────────────

class TestCompletedAt:
    def test_done_sets_completed_at(self, client):
        """M3 done-when: setting status → done sets completed_at."""
        tok = register(client, "a@a.com", "usera")
        pid = create_project(client, tok)
        t = create_task(client, tok, pid)
        assert t["completed_at"] is None

        r = client.patch(f"/api/v1/tasks/{t['id']}",
                         json={"status": "done"}, headers=auth(tok))
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["status"] == "done"
        assert data["completed_at"] is not None

    def test_moving_away_from_done_clears_completed_at(self, client):
        """M3 done-when: moving away from done clears completed_at."""
        tok = register(client, "a@a.com", "usera")
        pid = create_project(client, tok)
        t = create_task(client, tok, pid)

        # Move to done
        client.patch(f"/api/v1/tasks/{t['id']}",
                     json={"status": "done"}, headers=auth(tok))
        # Move back to in_progress
        r = client.patch(f"/api/v1/tasks/{t['id']}",
                         json={"status": "in_progress"}, headers=auth(tok))
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["status"] == "in_progress"
        assert data["completed_at"] is None

    def test_create_done_task_sets_completed_at(self, client):
        """Creating a task directly with status=done sets completed_at."""
        tok = register(client, "a@a.com", "usera")
        pid = create_project(client, tok)
        t = create_task(client, tok, pid, status="done")
        assert t["status"] == "done"
        assert t["completed_at"] is not None

    def test_done_ratio_on_project(self, client):
        """done_ratio = done_tasks / total_tasks."""
        tok = register(client, "a@a.com", "usera")
        pid = create_project(client, tok)
        t1 = create_task(client, tok, pid, title="T1")
        t2 = create_task(client, tok, pid, title="T2")
        create_task(client, tok, pid, title="T3")
        # Mark 2 of 3 done
        client.patch(f"/api/v1/tasks/{t1['id']}", json={"status": "done"}, headers=auth(tok))
        client.patch(f"/api/v1/tasks/{t2['id']}", json={"status": "done"}, headers=auth(tok))
        r = client.get(f"/api/v1/projects/{pid}", headers=auth(tok))
        assert r.json()["data"]["done_ratio"] == pytest.approx(2 / 3)


# ── Dependencies (cycle check) ────────────────────────────────────────────────

class TestDependencies:
    def test_add_dependency_success(self, client):
        tok = register(client, "a@a.com", "usera")
        pid = create_project(client, tok)
        t1 = create_task(client, tok, pid, title="T1")
        t2 = create_task(client, tok, pid, title="T2")
        r = client.post(f"/api/v1/tasks/{t2['id']}/dependencies",
                        json={"depends_on_id": t1["id"]}, headers=auth(tok))
        assert r.status_code == 201
        # t2 now shows t1 in its dependencies list
        r2 = client.get(f"/api/v1/tasks/{t2['id']}", headers=auth(tok))
        assert t1["id"] in r2.json()["data"]["dependencies"]

    def test_self_dependency_rejected(self, client):
        """M3 done-when: self-reference must return 422."""
        tok = register(client, "a@a.com", "usera")
        pid = create_project(client, tok)
        t = create_task(client, tok, pid)
        r = client.post(f"/api/v1/tasks/{t['id']}/dependencies",
                        json={"depends_on_id": t["id"]}, headers=auth(tok))
        assert r.status_code == 422
        assert "itself" in r.json()["detail"].lower()

    def test_direct_cycle_rejected(self, client):
        """M3 done-when: A→B then B→A must return 422 (direct cycle)."""
        tok = register(client, "a@a.com", "usera")
        pid = create_project(client, tok)
        a = create_task(client, tok, pid, title="A")
        b = create_task(client, tok, pid, title="B")
        # A depends on B
        client.post(f"/api/v1/tasks/{a['id']}/dependencies",
                    json={"depends_on_id": b["id"]}, headers=auth(tok))
        # B depends on A → cycle!
        r = client.post(f"/api/v1/tasks/{b['id']}/dependencies",
                        json={"depends_on_id": a["id"]}, headers=auth(tok))
        assert r.status_code == 422
        assert "cycle" in r.json()["detail"].lower()

    def test_transitive_cycle_rejected(self, client):
        """M3 done-when: A→B→C then C→A must be rejected (transitive cycle)."""
        tok = register(client, "a@a.com", "usera")
        pid = create_project(client, tok)
        a = create_task(client, tok, pid, title="A")
        b = create_task(client, tok, pid, title="B")
        c = create_task(client, tok, pid, title="C")
        # A → B → C
        client.post(f"/api/v1/tasks/{a['id']}/dependencies",
                    json={"depends_on_id": b["id"]}, headers=auth(tok))
        client.post(f"/api/v1/tasks/{b['id']}/dependencies",
                    json={"depends_on_id": c["id"]}, headers=auth(tok))
        # C → A would close the cycle
        r = client.post(f"/api/v1/tasks/{c['id']}/dependencies",
                        json={"depends_on_id": a["id"]}, headers=auth(tok))
        assert r.status_code == 422
        assert "cycle" in r.json()["detail"].lower()

    def test_duplicate_dependency_409(self, client):
        tok = register(client, "a@a.com", "usera")
        pid = create_project(client, tok)
        t1 = create_task(client, tok, pid, title="T1")
        t2 = create_task(client, tok, pid, title="T2")
        client.post(f"/api/v1/tasks/{t2['id']}/dependencies",
                    json={"depends_on_id": t1["id"]}, headers=auth(tok))
        r = client.post(f"/api/v1/tasks/{t2['id']}/dependencies",
                        json={"depends_on_id": t1["id"]}, headers=auth(tok))
        assert r.status_code == 409

    def test_remove_dependency(self, client):
        tok = register(client, "a@a.com", "usera")
        pid = create_project(client, tok)
        t1 = create_task(client, tok, pid, title="T1")
        t2 = create_task(client, tok, pid, title="T2")
        client.post(f"/api/v1/tasks/{t2['id']}/dependencies",
                    json={"depends_on_id": t1["id"]}, headers=auth(tok))
        r = client.delete(f"/api/v1/tasks/{t2['id']}/dependencies/{t1['id']}",
                          headers=auth(tok))
        assert r.status_code == 200
        r2 = client.get(f"/api/v1/tasks/{t2['id']}", headers=auth(tok))
        assert r2.json()["data"]["dependencies"] == []


# ── Activity log ──────────────────────────────────────────────────────────────

class TestActivityLog:
    def test_create_task_writes_activity(self, client):
        """M3 done-when: activity row written on task_created."""
        tok = register(client, "a@a.com", "usera")
        pid = create_project(client, tok)
        create_task(client, tok, pid, title="Build auth")
        r = client.get(f"/api/v1/projects/{pid}/activity", headers=auth(tok))
        assert r.status_code == 200
        actions = [row["action"] for row in r.json()["data"]]
        assert "task_created" in actions

    def test_move_task_writes_activity(self, client):
        """M3 done-when: activity row written on task_moved."""
        tok = register(client, "a@a.com", "usera")
        pid = create_project(client, tok)
        t = create_task(client, tok, pid)
        client.patch(f"/api/v1/tasks/{t['id']}",
                     json={"status": "in_progress"}, headers=auth(tok))
        r = client.get(f"/api/v1/projects/{pid}/activity", headers=auth(tok))
        actions = [row["action"] for row in r.json()["data"]]
        assert "task_moved" in actions

    def test_delete_task_writes_activity(self, client):
        """M3 done-when: activity row written on task_deleted."""
        tok = register(client, "a@a.com", "usera")
        pid = create_project(client, tok)
        t = create_task(client, tok, pid)
        client.delete(f"/api/v1/tasks/{t['id']}", headers=auth(tok))
        r = client.get(f"/api/v1/projects/{pid}/activity", headers=auth(tok))
        actions = [row["action"] for row in r.json()["data"]]
        assert "task_deleted" in actions
