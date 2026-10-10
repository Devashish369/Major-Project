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

def register(client, email, username="user", full_name="User", password="Secure#2026"):
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


# ── Review fix C-1: no privilege escalation through "add member" ─────────────

class TestNoAdminEscalation:
    def test_member_cannot_add_someone_as_admin(self, client):
        owner = register(client, "own@esc.com", "ownesc")
        member = register(client, "mem@esc.com", "memesc")
        register(client, "evil@esc.com", "evilesc")
        pid = create_project(client, owner).json()["data"]["id"]
        client.post(f"/api/v1/projects/{pid}/members", json={"email": "mem@esc.com", "role": "member"}, headers=auth(owner))
        r = client.post(f"/api/v1/projects/{pid}/members", json={"email": "evil@esc.com", "role": "admin"}, headers=auth(member))
        assert r.status_code == 403
        roles = {m["email"]: m["role"] for m in client.get(f"/api/v1/projects/{pid}/members", headers=auth(owner)).json()["data"]}
        assert "evil@esc.com" not in roles

    def test_member_can_still_add_a_regular_member_and_admin_can_add_admin(self, client):
        owner = register(client, "own2@esc.com", "own2esc")
        member = register(client, "mem2@esc.com", "mem2esc")
        register(client, "new2@esc.com", "new2esc")
        register(client, "adm2@esc.com", "adm2esc")
        pid = create_project(client, owner).json()["data"]["id"]
        client.post(f"/api/v1/projects/{pid}/members", json={"email": "mem2@esc.com", "role": "member"}, headers=auth(owner))
        assert client.post(f"/api/v1/projects/{pid}/members", json={"email": "new2@esc.com", "role": "member"},
                           headers=auth(member)).status_code == 201
        assert client.post(f"/api/v1/projects/{pid}/members", json={"email": "adm2@esc.com", "role": "admin"},
                           headers=auth(owner)).status_code == 201


# ── Review fix C-2: deleting a project removes its children (SQLite too) ─────

class TestProjectDeleteCascades:
    def test_children_removed_and_recycled_id_starts_clean(self, client):
        from sqlalchemy import select, func
        from tests.conftest import TestingSessionLocal
        from app.models import ActivityLog, Decision, ProjectMember, Task, TaskDependency

        a = register(client, "casc_a@x.com", "casca")
        register(client, "casc_b@x.com", "cascb")
        c = register(client, "casc_c@x.com", "cascc")
        pid = create_project(client, a).json()["data"]["id"]
        client.post(f"/api/v1/projects/{pid}/members", json={"email": "casc_b@x.com"}, headers=auth(a))
        t1 = client.post(f"/api/v1/projects/{pid}/tasks", json={"title": "T1"}, headers=auth(a)).json()["data"]["id"]
        t2 = client.post(f"/api/v1/projects/{pid}/tasks", json={"title": "T2"}, headers=auth(a)).json()["data"]["id"]
        client.post(f"/api/v1/tasks/{t2}/dependencies", json={"depends_on_id": t1}, headers=auth(a))
        client.post(f"/api/v1/projects/{pid}/decisions", json={"title": "D", "decision": "d"}, headers=auth(a))

        assert client.delete(f"/api/v1/projects/{pid}", headers=auth(a)).status_code == 200
        db = TestingSessionLocal()
        try:
            for model in (ProjectMember, Task, ActivityLog, Decision):
                n = db.execute(select(func.count()).select_from(model).where(model.project_id == pid)).scalar_one()
                assert n == 0, model.__name__
            assert db.execute(select(func.count()).select_from(TaskDependency)).scalar_one() == 0
        finally:
            db.close()

        # A different user's new project (SQLite may reuse the id) must not inherit anything
        new = create_project(client, c, title="Fresh")
        assert new.status_code == 201
        nid = new.json()["data"]["id"]
        members = client.get(f"/api/v1/projects/{nid}/members", headers=auth(c)).json()["data"]
        assert [m["email"] for m in members] == ["casc_c@x.com"]
        assert client.get(f"/api/v1/projects/{nid}/tasks", headers=auth(c)).json()["data"] == []


# ── Project status follows the tasks (dynamic, not a stale stored field) ──────

class TestProjectStatusIsDerived:
    def test_pure_rules(self):
        from app.services.tasks import derive_project_status as d
        assert d("pending", []) == "pending" and d("in_progress", []) == "in_progress"   # no tasks: keep stored
        assert d("in_progress", ["todo", "todo"]) == "pending"
        assert d("pending", ["todo", "in_progress"]) == "in_progress"
        assert d("pending", ["todo", "done"]) == "in_progress"
        assert d("in_progress", ["done", "done"]) == "completed"

    def test_status_follows_board_moves(self, client):
        tok = register(client, "dyn@s.com", "dynuser")
        pid = create_project(client, tok).json()["data"]["id"]
        status = lambda: client.get(f"/api/v1/projects/{pid}", headers=auth(tok)).json()["data"]["status"]
        a = client.post(f"/api/v1/projects/{pid}/tasks", json={"title": "A"}, headers=auth(tok)).json()["data"]["id"]
        b = client.post(f"/api/v1/projects/{pid}/tasks", json={"title": "B"}, headers=auth(tok)).json()["data"]["id"]
        assert status() == "pending"
        client.patch(f"/api/v1/tasks/{a}", json={"status": "in_progress"}, headers=auth(tok))
        assert status() == "in_progress"
        client.patch(f"/api/v1/tasks/{a}", json={"status": "done"}, headers=auth(tok))
        client.patch(f"/api/v1/tasks/{b}", json={"status": "done"}, headers=auth(tok))
        assert status() == "completed"
        listed = [p for p in client.get("/api/v1/projects", headers=auth(tok)).json()["data"] if p["id"] == pid][0]
        assert listed["status"] == "completed"                 # the dashboard card uses the same value
        client.patch(f"/api/v1/tasks/{b}", json={"status": "todo"}, headers=auth(tok))
        assert status() == "in_progress"                       # reopening a task reopens the project


# ── Account isolation: a user sees ONLY the projects they belong to ───────────

class TestOnlyMyProjects:
    def test_added_to_one_project_sees_only_that_project(self, client):
        owner = register(client, "iso_owner@x.com", "isoowner")
        aditya = register(client, "iso_aditya@x.com", "isoaditya")
        ids = [create_project(client, owner, title=t).json()["data"]["id"]
               for t in ("Hospital", "Something Management", "E-commerce")]
        mine = lambda: [p["title"] for p in client.get("/api/v1/projects", headers=auth(aditya)).json()["data"]]

        assert mine() == []                                            # new account: nothing
        client.post(f"/api/v1/projects/{ids[1]}/members", json={"email": "iso_aditya@x.com", "role": "member"}, headers=auth(owner))
        assert mine() == ["Something Management"]                      # exactly the one project he was added to

        for other in (ids[0], ids[2]):                                 # everything else is invisible, not just hidden in the list
            for path in ("", "/tasks", "/members", "/report", "/analytics/health", "/decisions", "/sprints", "/activity"):
                assert client.get(f"/api/v1/projects/{other}{path}", headers=auth(aditya)).status_code == 404, path

        client.delete(f"/api/v1/projects/{ids[1]}/members/"
                      f"{client.get('/api/v1/auth/me', headers=auth(aditya)).json()['data']['id']}", headers=auth(owner))
        assert mine() == []                                            # removing him removes the project from his list

    def test_name_lookup_only_returns_requested_people(self, client):
        from tests.conftest import TestingSessionLocal
        from app.services.tasks import names_for
        a = register(client, "nm_a@x.com", "nma"); register(client, "nm_b@x.com", "nmb")
        uid = client.get("/api/v1/auth/me", headers=auth(a)).json()["data"]["id"]
        db = TestingSessionLocal()
        try:
            assert names_for(db, [uid, None]) == {uid: "User"}
            assert names_for(db, []) == {} and names_for(db, [None]) == {}
        finally:
            db.close()
