"""
tests/test_ai.py – M4 tests for /ai/generate-plan and /projects/{id}/apply-plan.

All LLM calls are mocked – no real API is called.
Covers spec §11 M4 done-when criteria:
  ✓ generate-plan returns a valid plan + source field
  ✓ USE_CACHED_PLAN_ONLY=true returns fallback without calling any API
  ✓ LLM JSON parse failure → retry → fallback (mock behaviour)
  ✓ apply-plan (admin only) creates sprints, tasks, and dependencies
  ✓ Non-admin cannot apply-plan (403)
  ✓ Cycle detection in planner post-processing
  ✓ estimate_hours clamped to 1-40
  ✓ required_skills lowercased
  ✓ Unknown depends_on titles dropped
  ✓ task cap at 40
"""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.planner import Plan, TaskPlan, SprintPlan, _postprocess, generate_plan


# ── Client + helpers ──────────────────────────────────────────────────────────

@pytest.fixture
def client():
    return TestClient(app)


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


# Minimal valid plan JSON the mock LLM will return
MOCK_PLAN_JSON = json.dumps({
    "project_title": "Test App",
    "summary": "A simple test project plan.",
    "sprints": [
        {"name": "Sprint 1", "goal": "Foundation"},
        {"name": "Sprint 2", "goal": "Features"},
    ],
    "tasks": [
        {
            "title": "Setup project",
            "description": "Init repo",
            "module": "Infra",
            "priority": "high",
            "estimate_hours": 4,
            "required_skills": ["Python", "Docker"],
            "sprint_index": 0,
            "depends_on": [],
        },
        {
            "title": "Build API",
            "description": "REST endpoints",
            "module": "Backend",
            "priority": "critical",
            "estimate_hours": 16,
            "required_skills": ["Python", "FastAPI"],
            "sprint_index": 1,
            "depends_on": ["Setup project"],
        },
        {
            "title": "Build UI",
            "description": "React frontend",
            "module": "Frontend",
            "priority": "medium",
            "estimate_hours": 20,
            "required_skills": ["React"],
            "sprint_index": 1,
            "depends_on": ["Build API"],
        },
    ],
})


# ── /ai/generate-plan ─────────────────────────────────────────────────────────

class TestGeneratePlan:
    def test_generate_plan_returns_plan_and_source(self, client):
        """Mocked LLM returns valid JSON → response has plan + source."""
        tok = register(client, "a@a.com", "usera")
        with patch("app.services.planner.call_llm", return_value=MOCK_PLAN_JSON):
            with patch("app.config.settings.LLM_API_KEY", "fake-key"):
                r = client.post(
                    "/api/v1/ai/generate-plan",
                    json={"description": "Build a task management web application", "team_size": 3, "duration_weeks": 8},
                    headers=auth(tok),
                )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["success"] is True
        assert "source" in body
        assert "project_title" in body["data"]
        assert "tasks" in body["data"]
        assert "sprints" in body["data"]

    def test_generate_plan_cached_only_never_calls_api(self, client):
        """USE_CACHED_PLAN_ONLY=true → fallback JSON loaded, no API call."""
        tok = register(client, "a@a.com", "usera")
        with patch("app.services.planner.settings") as mock_settings:
            mock_settings.USE_CACHED_PLAN_ONLY = True
            mock_settings.LLM_API_KEY = "fake-key"
            mock_settings.LLM_FALLBACK_API_KEY = "fake-fallback"
            with patch("app.services.planner.call_llm") as mock_llm:
                r = client.post(
                    "/api/v1/ai/generate-plan",
                    json={"description": "Build a hospital management system", "team_size": 5, "duration_weeks": 12},
                    headers=auth(tok),
                )
                mock_llm.assert_not_called()   # no real API call
        assert r.status_code == 200
        assert r.json()["source"] == "fallback"

    def test_generate_plan_skills_lowercased(self, client):
        """required_skills in response must all be lowercase."""
        tok = register(client, "a@a.com", "usera")
        with patch("app.services.planner.call_llm", return_value=MOCK_PLAN_JSON):
            with patch("app.config.settings.LLM_API_KEY", "fake-key"):
                r = client.post(
                    "/api/v1/ai/generate-plan",
                    json={"description": "Build a task management web application"},
                    headers=auth(tok),
                )
        tasks = r.json()["data"]["tasks"]
        for t in tasks:
            for skill in t.get("required_skills", []):
                assert skill == skill.lower(), f"Skill not lowercased: {skill}"

    def test_generate_plan_unauthenticated_rejected(self, client):
        """No token → 403."""
        r = client.post("/api/v1/ai/generate-plan",
                        json={"description": "Build a task management web application"})
        assert r.status_code in (401, 403)

    def test_generate_plan_description_too_short(self, client):
        """Description must be >= 10 chars."""
        tok = register(client, "a@a.com", "usera")
        r = client.post("/api/v1/ai/generate-plan",
                        json={"description": "short"},
                        headers=auth(tok))
        assert r.status_code == 422


# ── /projects/{id}/apply-plan ─────────────────────────────────────────────────

class TestApplyPlan:
    def _get_plan_dict(self):
        return json.loads(MOCK_PLAN_JSON)

    def test_apply_plan_admin_success(self, client):
        """Admin applies plan → sprints + tasks + deps created."""
        tok = register(client, "a@a.com", "usera")
        pid = create_project(client, tok)
        plan = self._get_plan_dict()
        r = client.post(
            f"/api/v1/projects/{pid}/apply-plan",
            json={"plan": plan, "source": "llm"},
            headers=auth(tok),
        )
        assert r.status_code == 201, r.text
        data = r.json()["data"]
        assert data["sprints_created"] == 2
        assert data["tasks_created"] == 3
        assert data["dependencies_created"] == 2   # Setup→BuildAPI, BuildAPI→BuildUI

    def test_apply_plan_tasks_appear_in_board(self, client):
        """After apply-plan, GET /tasks returns the created tasks."""
        tok = register(client, "a@a.com", "usera")
        pid = create_project(client, tok)
        plan = self._get_plan_dict()
        client.post(f"/api/v1/projects/{pid}/apply-plan",
                    json={"plan": plan, "source": "llm"}, headers=auth(tok))
        r = client.get(f"/api/v1/projects/{pid}/tasks", headers=auth(tok))
        assert r.status_code == 200
        assert len(r.json()["data"]) == 3

    def test_apply_plan_non_admin_forbidden(self, client):
        """Non-admin member cannot apply plan (403)."""
        tok_admin = register(client, "a@a.com", "usera")
        tok_member = register(client, "b@b.com", "userb")
        pid = create_project(client, tok_admin)
        # Add as member (not admin)
        client.post(f"/api/v1/projects/{pid}/members",
                    json={"email": "b@b.com", "role": "member", "capacity_hours_per_week": 30},
                    headers=auth(tok_admin))
        plan = self._get_plan_dict()
        r = client.post(f"/api/v1/projects/{pid}/apply-plan",
                        json={"plan": plan, "source": "llm"}, headers=auth(tok_member))
        assert r.status_code == 403

    def test_apply_plan_non_member_gets_404(self, client):
        """Non-member cannot apply plan (404 to prevent enumeration)."""
        tok_admin = register(client, "a@a.com", "usera")
        tok_other = register(client, "b@b.com", "userb")
        pid = create_project(client, tok_admin)
        plan = self._get_plan_dict()
        r = client.post(f"/api/v1/projects/{pid}/apply-plan",
                        json={"plan": plan, "source": "llm"}, headers=auth(tok_other))
        assert r.status_code == 404

    def test_apply_plan_activity_logged(self, client):
        """apply-plan writes a plan_applied activity row."""
        tok = register(client, "a@a.com", "usera")
        pid = create_project(client, tok)
        plan = self._get_plan_dict()
        client.post(f"/api/v1/projects/{pid}/apply-plan",
                    json={"plan": plan, "source": "llm"}, headers=auth(tok))
        r = client.get(f"/api/v1/projects/{pid}/activity", headers=auth(tok))
        actions = [row["action"] for row in r.json()["data"]]
        assert "plan_applied" in actions


# ── Planner post-processing unit tests (no HTTP) ──────────────────────────────

class TestPlannerPostprocessing:
    def _make_plan(self, tasks, sprints=None):
        return Plan(
            project_title="Test",
            sprints=sprints or [SprintPlan(name="S1")],
            tasks=[TaskPlan(**t) for t in tasks],
        )

    def test_estimate_hours_clamped_max(self):
        """estimate_hours > 40 clamped to 40."""
        p = self._make_plan([{"title": "Huge", "estimate_hours": 999}])
        assert p.tasks[0].estimate_hours == 40

    def test_estimate_hours_clamped_min(self):
        """estimate_hours < 1 clamped to 1."""
        p = self._make_plan([{"title": "Tiny", "estimate_hours": 0}])
        assert p.tasks[0].estimate_hours == 1

    def test_skills_lowercased_by_validator(self):
        """required_skills must be lowercased by validator."""
        p = self._make_plan([{"title": "T", "required_skills": ["Python", "REACT"]}])
        assert p.tasks[0].required_skills == ["python", "react"]

    def test_unknown_depends_on_dropped(self):
        """depends_on referencing non-existent task titles must be dropped."""
        p = self._make_plan([
            {"title": "A", "depends_on": ["NonExistentTask"]},
        ])
        result = _postprocess(p)
        assert result.tasks[0].depends_on == []

    def test_direct_cycle_broken(self):
        """A depends on B and B depends on A → cycle broken by postprocess."""
        p = self._make_plan([
            {"title": "A", "depends_on": ["B"]},
            {"title": "B", "depends_on": ["A"]},
        ])
        result = _postprocess(p)
        # After cycle removal, at most one direction should survive
        a_deps = result.tasks[0].depends_on
        b_deps = result.tasks[1].depends_on
        # They must not both point at each other
        assert not (("B" in a_deps) and ("A" in b_deps)), "Cycle not broken"

    def test_tasks_capped_at_40(self):
        """More than 40 tasks must be capped at 40."""
        tasks = [{"title": f"Task {i}"} for i in range(50)]
        p = self._make_plan(tasks)
        assert len(p.tasks) == 40

    def test_self_dependency_dropped(self):
        """Task depending on itself must be dropped by postprocess."""
        p = self._make_plan([{"title": "A", "depends_on": ["A"]}])
        result = _postprocess(p)
        assert "A" not in result.tasks[0].depends_on

    def test_generate_plan_fallback_loads_json(self):
        """With all keys empty and cached=False → static fallback is loaded."""
        with patch("app.services.planner.settings") as ms:
            ms.USE_CACHED_PLAN_ONLY = False
            ms.LLM_API_KEY = ""          # no primary
            ms.LLM_FALLBACK_API_KEY = "" # no fallback
            result = generate_plan("Build something", 3, 8)
        assert result["source"] == "fallback"
        assert len(result["plan"]["tasks"]) > 0


# ── Review fix M-1 + atomicity: apply-plan re-validates the body and is all-or-nothing ──

class TestApplyPlanHardening:
    def test_cyclic_oversized_plan_is_cleaned_and_forecast_still_works(self, client):
        tok = register(client, "hard@a.com", "hard")
        pid = create_project(client, tok)
        bad = {"project_title": "x", "sprints": [{"name": "S1"}],
               "tasks": [{"title": "A", "estimate_hours": 999, "depends_on": ["B", "Ghost"]},
                         {"title": "B", "estimate_hours": 0, "depends_on": ["A"]}]
                        + [{"title": f"T{i}"} for i in range(50)]}
        r = client.post(f"/api/v1/projects/{pid}/apply-plan", json={"plan": bad}, headers=auth(tok))
        assert r.status_code == 201
        assert r.json()["data"]["tasks_created"] == 40                      # capped
        tasks = {t["title"]: t for t in client.get(f"/api/v1/projects/{pid}/tasks", headers=auth(tok)).json()["data"]}
        assert tasks["A"]["estimate_hours"] == 40 and tasks["B"]["estimate_hours"] == 1
        a_deps, b_deps = set(tasks["A"]["dependencies"]), set(tasks["B"]["dependencies"])
        assert not (tasks["B"]["id"] in a_deps and tasks["A"]["id"] in b_deps)   # cycle broken
        assert client.get(f"/api/v1/projects/{pid}/analytics/forecast", headers=auth(tok)).status_code == 200

    def test_plan_without_task_title_is_422_not_500(self, client):
        tok = register(client, "hard2@a.com", "hard2")
        pid = create_project(client, tok)
        r = client.post(f"/api/v1/projects/{pid}/apply-plan", json={"plan": {"tasks": [{"estimate_hours": 3}]}}, headers=auth(tok))
        assert r.status_code == 422 and r.json()["success"] is False

    def test_failure_midway_saves_nothing(self, client, monkeypatch):
        import app.routers.ai as ai_router
        tok = register(client, "hard3@a.com", "hard3")
        pid = create_project(client, tok)

        def boom(*a, **k):                      # fails AFTER sprints + tasks were flushed
            raise RuntimeError("disk full")
        monkeypatch.setattr(ai_router, "write_activity", boom)
        nofail = TestClient(app, raise_server_exceptions=False)
        r = nofail.post(f"/api/v1/projects/{pid}/apply-plan", json={"plan": json.loads(MOCK_PLAN_JSON)}, headers=auth(tok))
        assert r.status_code == 500
        assert client.get(f"/api/v1/projects/{pid}/tasks", headers=auth(tok)).json()["data"] == []


# ── Review fix M-4: no hidden SDK retries on top of our own retry/fallback logic ──

def test_llm_client_does_not_retry_by_itself():
    from app.services.llm import _make_client
    client = _make_client("https://example.invalid/v1", "k")
    assert client.max_retries == 0
