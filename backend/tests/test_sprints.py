"""tests/test_sprints.py – GET /projects/{id}/sprints (read-only list with task counts)."""

import pytest
from fastapi.testclient import TestClient

from app.main import app

API = "/api/v1"


@pytest.fixture
def client():
    return TestClient(app)


def reg(client, name):
    r = client.post(f"{API}/auth/register", json={"email": f"{name}@spr.com", "username": name,
                                                   "full_name": name, "password": "password123"})
    return {"Authorization": f"Bearer {r.json()['data']['access_token']}"}


PLAN = {"project_title": "P", "sprints": [{"name": "Sprint 1", "goal": "Base"}, {"name": "Sprint 2", "goal": "UI"}],
        "tasks": [{"title": "A", "sprint_index": 0}, {"title": "B", "sprint_index": 0},
                  {"title": "C", "sprint_index": 1}]}


def test_lists_sprints_with_counts(client):
    h = reg(client, "spr1")
    pid = client.post(f"{API}/projects", json={"title": "S"}, headers=h).json()["data"]["id"]
    assert client.post(f"{API}/projects/{pid}/apply-plan", json={"plan": PLAN}, headers=h).status_code == 201
    a = [t for t in client.get(f"{API}/projects/{pid}/tasks", headers=h).json()["data"] if t["title"] == "A"][0]
    client.patch(f"{API}/tasks/{a['id']}", json={"status": "done"}, headers=h)
    r = client.get(f"{API}/projects/{pid}/sprints", headers=h)
    assert r.status_code == 200 and r.json()["success"] is True
    s1, s2 = r.json()["data"]
    assert (s1["name"], s1["goal"], s1["task_count"], s1["done_count"]) == ("Sprint 1", "Base", 2, 1)
    assert (s2["name"], s2["task_count"], s2["done_count"]) == ("Sprint 2", 1, 0)
    assert {"id", "start_date", "end_date"} <= set(s1)


def test_empty_project_has_no_sprints(client):
    h = reg(client, "spr2")
    pid = client.post(f"{API}/projects", json={"title": "S"}, headers=h).json()["data"]["id"]
    assert client.get(f"{API}/projects/{pid}/sprints", headers=h).json()["data"] == []


def test_outsider_gets_404_and_there_is_no_write_endpoint(client):
    owner, outsider = reg(client, "spr3"), reg(client, "spr4")
    pid = client.post(f"{API}/projects", json={"title": "S"}, headers=owner).json()["data"]["id"]
    assert client.get(f"{API}/projects/{pid}/sprints", headers=outsider).status_code == 404
    assert client.post(f"{API}/projects/{pid}/sprints", json={"name": "x"}, headers=owner).status_code == 405
