"""
tests/test_projects.py – Tests for M2: Projects + Members.

Uses the shared in-memory SQLite DB from conftest.py.

Covers the M2 "done when" criteria (spec §11):
  ✓ Create project
  ✓ Creator becomes admin automatically
  ✓ Add member by email with role and capacity
  ✓ Non-member gets 404 (not 403) for project endpoints
  ✓ Non-admin member cannot delete a project (403)
  ✓ Non-admin member cannot remove a member (403)
  ✓ Admin can delete the project
  ✓ Cannot remove last admin
  ✓ PATCH /auth/me skills dict update (levels 1–5)
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


# ── Helpers ───────────────────────────────────────────────────────────────────

def register(client, email, username="user", full_name="User", password="password123"):
    r = client.post("/api/v1/auth/register", json={
        "email": email, "username": username,
        "full_name": full_name, "password": password,
    })
    assert r.status_code == 201
    return r.json()["data"]["access_token"]


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def create_project(client, token, title="Test Project", **kwargs):
    body = {"title": title, **kwargs}
    r = client.post("/api/v1/projects", json=body, headers=auth(token))
    return r


# ── Projects CRUD ─────────────────────────────────────────────────────────────

class TestProjectCRUD:
    def test_create_project_success(self, client):
        tok = register(client, "a@a.com", "useralpha")
        r = create_project(client, tok, title="My Project", priority="high")
        assert r.status_code == 201
        data = r.json()["data"]
        assert data["title"] == "My Project"
        assert data["priority"] == "high"
        assert data["member_count"] == 1   # creator added automatically

    def test_creator_is_admin(self, client):
        tok = register(client, "a@a.com", "useralpha")
        project_id = create_project(client, tok).json()["data"]["id"]
        members = client.get(f"/api/v1/projects/{project_id}/members", headers=auth(tok))
        assert members.status_code == 200
        assert members.json()["data"][0]["role"] == "admin"

    def test_list_projects_only_returns_own(self, client):
        tok1 = register(client, "a@a.com", "useralpha")
        tok2 = register(client, "b@b.com", "userbeta")
        create_project(client, tok1, title="P1")
        create_project(client, tok1, title="P2")
        # User 2 creates no projects
        r = client.get("/api/v1/projects", headers=auth(tok2))
        assert r.status_code == 200
        assert r.json()["data"] == []

    def test_get_project_member_can_see(self, client):
        tok = register(client, "a@a.com", "useralpha")
        pid = create_project(client, tok).json()["data"]["id"]
        r = client.get(f"/api/v1/projects/{pid}", headers=auth(tok))
        assert r.status_code == 200

    def test_get_project_non_member_gets_404(self, client):
        """M2 done-when: non-member must get 404, not 403."""
        tok1 = register(client, "a@a.com", "useralpha")
        tok2 = register(client, "b@b.com", "userbeta")
        pid = create_project(client, tok1).json()["data"]["id"]
        r = client.get(f"/api/v1/projects/{pid}", headers=auth(tok2))
        assert r.status_code == 404

    def test_patch_project_any_member(self, client):
        tok = register(client, "a@a.com", "useralpha")
        pid = create_project(client, tok).json()["data"]["id"]
        r = client.patch(f"/api/v1/projects/{pid}", json={"title": "Renamed"}, headers=auth(tok))
        assert r.status_code == 200
        assert r.json()["data"]["title"] == "Renamed"

    def test_delete_project_admin_succeeds(self, client):
        tok = register(client, "a@a.com", "useralpha")
        pid = create_project(client, tok).json()["data"]["id"]
        r = client.delete(f"/api/v1/projects/{pid}", headers=auth(tok))
        assert r.status_code == 200

    def test_delete_project_non_admin_forbidden(self, client):
        """M2 done-when: non-admin cannot delete."""
        tok1 = register(client, "a@a.com", "useralpha")
        tok2 = register(client, "b@b.com", "userbeta")
        pid = create_project(client, tok1).json()["data"]["id"]
        # Add tok2 user as regular member
        client.post(f"/api/v1/projects/{pid}/members",
                    json={"email": "b@b.com", "role": "member"},
                    headers=auth(tok1))
        r = client.delete(f"/api/v1/projects/{pid}", headers=auth(tok2))
        assert r.status_code == 403

    def test_delete_project_non_member_gets_404(self, client):
        tok1 = register(client, "a@a.com", "useralpha")
        tok2 = register(client, "b@b.com", "userbeta")
        pid = create_project(client, tok1).json()["data"]["id"]
        r = client.delete(f"/api/v1/projects/{pid}", headers=auth(tok2))
        assert r.status_code == 404


# ── Members ───────────────────────────────────────────────────────────────────

class TestMembers:
    def _setup(self, client):
        """Create admin + regular user + project."""
        tok_admin = register(client, "admin@a.com", "adminuser")
        tok_member = register(client, "member@a.com", "memberuser")
        pid = create_project(client, tok_admin).json()["data"]["id"]
        # Add member
        client.post(f"/api/v1/projects/{pid}/members",
                    json={"email": "member@a.com", "role": "member", "capacity_hours_per_week": 20},
                    headers=auth(tok_admin))
        return pid, tok_admin, tok_member

    def test_add_member_by_email(self, client):
        tok_admin = register(client, "admin@a.com", "adminuser")
        register(client, "member@a.com", "memberuser")
        pid = create_project(client, tok_admin).json()["data"]["id"]
        r = client.post(f"/api/v1/projects/{pid}/members",
                        json={"email": "member@a.com", "role": "member", "capacity_hours_per_week": 25},
                        headers=auth(tok_admin))
        assert r.status_code == 201
        assert r.json()["data"]["capacity_hours_per_week"] == 25

    def test_add_duplicate_member_409(self, client):
        tok_admin = register(client, "admin@a.com", "adminuser")
        pid = create_project(client, tok_admin).json()["data"]["id"]
        # Creator is already a member – try adding again
        r = client.post(f"/api/v1/projects/{pid}/members",
                        json={"email": "admin@a.com", "role": "member"},
                        headers=auth(tok_admin))
        assert r.status_code == 409

    def test_add_nonexistent_email_404(self, client):
        tok_admin = register(client, "admin@a.com", "adminuser")
        pid = create_project(client, tok_admin).json()["data"]["id"]
        r = client.post(f"/api/v1/projects/{pid}/members",
                        json={"email": "nobody@nobody.com", "role": "member"},
                        headers=auth(tok_admin))
        assert r.status_code == 404

    def test_list_members(self, client):
        pid, tok_admin, _ = self._setup(client)
        r = client.get(f"/api/v1/projects/{pid}/members", headers=auth(tok_admin))
        assert r.status_code == 200
        assert len(r.json()["data"]) == 2   # admin + member

    def test_non_member_cannot_list_members(self, client):
        tok_admin = register(client, "admin@a.com", "adminuser")
        tok_other = register(client, "other@a.com", "otherusr")
        pid = create_project(client, tok_admin).json()["data"]["id"]
        r = client.get(f"/api/v1/projects/{pid}/members", headers=auth(tok_other))
        assert r.status_code == 404

    def test_admin_can_update_member_capacity(self, client):
        pid, tok_admin, _ = self._setup(client)
        # Get member's user_id
        members = client.get(f"/api/v1/projects/{pid}/members", headers=auth(tok_admin))
        member_uid = next(m["user_id"] for m in members.json()["data"] if m["role"] == "member")
        r = client.patch(f"/api/v1/projects/{pid}/members/{member_uid}",
                         json={"capacity_hours_per_week": 40},
                         headers=auth(tok_admin))
        assert r.status_code == 200
        assert r.json()["data"]["capacity_hours_per_week"] == 40

    def test_non_admin_cannot_update_member(self, client):
        """M2 done-when: non-admin cannot change roles/capacity."""
        pid, tok_admin, tok_member = self._setup(client)
        members = client.get(f"/api/v1/projects/{pid}/members", headers=auth(tok_admin))
        member_uid = next(m["user_id"] for m in members.json()["data"] if m["role"] == "member")
        r = client.patch(f"/api/v1/projects/{pid}/members/{member_uid}",
                         json={"role": "admin"},
                         headers=auth(tok_member))
        assert r.status_code == 403

    def test_admin_can_remove_member(self, client):
        pid, tok_admin, _ = self._setup(client)
        members = client.get(f"/api/v1/projects/{pid}/members", headers=auth(tok_admin))
        member_uid = next(m["user_id"] for m in members.json()["data"] if m["role"] == "member")
        r = client.delete(f"/api/v1/projects/{pid}/members/{member_uid}",
                          headers=auth(tok_admin))
        assert r.status_code == 200

    def test_non_admin_cannot_remove_member(self, client):
        """M2 done-when: non-admin cannot remove members."""
        pid, tok_admin, tok_member = self._setup(client)
        # Get admin's user_id
        members = client.get(f"/api/v1/projects/{pid}/members", headers=auth(tok_admin))
        admin_uid = next(m["user_id"] for m in members.json()["data"] if m["role"] == "admin")
        r = client.delete(f"/api/v1/projects/{pid}/members/{admin_uid}",
                          headers=auth(tok_member))
        assert r.status_code == 403

    def test_cannot_remove_last_admin(self, client):
        tok_admin = register(client, "admin@a.com", "adminuser")
        pid = create_project(client, tok_admin).json()["data"]["id"]
        members = client.get(f"/api/v1/projects/{pid}/members", headers=auth(tok_admin))
        admin_uid = members.json()["data"][0]["user_id"]
        r = client.delete(f"/api/v1/projects/{pid}/members/{admin_uid}",
                          headers=auth(tok_admin))
        assert r.status_code == 409


# ── Skills edit (PATCH /auth/me) ──────────────────────────────────────────────

class TestSkillsEdit:
    def test_set_skills(self, client):
        tok = register(client, "a@a.com", "useralpha")
        r = client.patch("/api/v1/auth/me",
                         json={"skills": {"python": 5, "react": 3}},
                         headers=auth(tok))
        assert r.status_code == 200
        assert r.json()["data"]["skills"]["python"] == 5

    def test_skill_level_out_of_range_422(self, client):
        tok = register(client, "a@a.com", "useralpha")
        r = client.patch("/api/v1/auth/me",
                         json={"skills": {"python": 6}},
                         headers=auth(tok))
        assert r.status_code == 422

    def test_replace_skills(self, client):
        """Sending a new skills dict replaces the old one entirely."""
        tok = register(client, "a@a.com", "useralpha")
        client.patch("/api/v1/auth/me",
                     json={"skills": {"python": 5}},
                     headers=auth(tok))
        r = client.patch("/api/v1/auth/me",
                         json={"skills": {"react": 4}},
                         headers=auth(tok))
        assert r.status_code == 200
        data = r.json()["data"]["skills"]
        assert "react" in data
        # python was replaced
        assert "python" not in data
