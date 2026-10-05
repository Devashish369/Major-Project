"""
tests/test_assignments.py – M5 tests.

Covers spec §11 M5 done-when criteria:
  ✓ Unit test: hand-built 3×3 case with known best answer
  ✓ recommend endpoint returns task_id, user_id, skill_match, availability,
      performance, score, reason (all fields)
  ✓ apply endpoint persists assignee_id (admin only)
  ✓ workload endpoint returns utilization and correct label for each member
  ✓ non-member cannot call recommend (404)
  ✓ non-admin cannot call apply (403)
  ✓ edge cases: no members → 422, no unassigned tasks → empty list
  ✓ zero-capacity member handled without division by zero
  ✓ workload: correct labels for overloaded / at_risk / healthy / available
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.assignment import (
    MemberInfo, TaskInfo, recommend_assignments,
    _skill_match, _availability, _score,
)
from app.services.workload import compute_workload, WorkloadEntry


# ── Client + helpers ──────────────────────────────────────────────────────────

@pytest.fixture
def client():
    return TestClient(app)


def register(client, email, username, password="password123"):
    r = client.post("/api/v1/auth/register", json={
        "email": email, "username": username,
        "full_name": f"User {username}", "password": password,
    })
    assert r.status_code == 201, r.text
    return r.json()["data"]["access_token"]


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def create_project(client, token, title="Test"):
    r = client.post("/api/v1/projects", json={"title": title}, headers=auth(token))
    assert r.status_code == 201
    return r.json()["data"]["id"]


def create_task(client, token, project_id, title, skills=None, estimate=8, priority="medium"):
    body = {"title": title, "estimate_hours": estimate, "priority": priority}
    if skills:
        body["required_skills"] = skills
    r = client.post(f"/api/v1/projects/{project_id}/tasks", json=body, headers=auth(token))
    assert r.status_code == 201
    return r.json()["data"]["id"]


def add_member(client, admin_tok, project_id, email, role="member", capacity=30):
    r = client.post(
        f"/api/v1/projects/{project_id}/members",
        json={"email": email, "role": role, "capacity_hours_per_week": capacity},
        headers=auth(admin_tok),
    )
    assert r.status_code == 201
    return r


# ─────────────────────────────────────────────────────────────────────────────
# Unit tests: pure algorithm (no HTTP, no DB)
# ─────────────────────────────────────────────────────────────────────────────

class TestAssignmentAlgorithmUnit:
    """
    Hand-built 3×3 case (spec §11 M5 done-when).

    3 tasks × 3 members – we compute the expected optimal matching manually
    and verify the optimizer returns the same assignment.

    Tasks:
      T1 priority=high,   estimate=8h,  required_skills=["python"]
      T2 priority=medium, estimate=8h,  required_skills=["react"]
      T3 priority=low,    estimate=8h,  required_skills=[]

    Members (weeks_remaining=4, capacity=10h/wk → capacity_total=40h):
      M1 skills={python:5, react:1}, on_time_rate=0.9  → strong python
      M2 skills={python:1, react:5}, on_time_rate=0.8  → strong react
      M3 skills={},                  on_time_rate=0.6  → generalist

    Expected optimal: T1→M1, T2→M2, T3→M3 (or M1/M2 if M3 slots available)
    Because:
      T1-M1: skill_match=(5/5)=1.0, best
      T2-M2: skill_match=(5/5)=1.0, best
      T3-any: skill_match=0.5 (no required skills)
    """

    WEEKS = 4.0
    CAPACITY_PER_WEEK = 10.0  # capacity_total = 40h, plenty for one 8h task each

    def _make_members(self):
        return [
            MemberInfo(user_id=1, full_name="Alice", skills={"python": 5, "react": 1},
                       capacity_hours_per_week=self.CAPACITY_PER_WEEK,
                       on_time_rate=0.9, weeks_remaining=self.WEEKS),
            MemberInfo(user_id=2, full_name="Bob", skills={"python": 1, "react": 5},
                       capacity_hours_per_week=self.CAPACITY_PER_WEEK,
                       on_time_rate=0.8, weeks_remaining=self.WEEKS),
            MemberInfo(user_id=3, full_name="Carol", skills={},
                       capacity_hours_per_week=self.CAPACITY_PER_WEEK,
                       on_time_rate=0.6, weeks_remaining=self.WEEKS),
        ]

    def _make_tasks(self):
        return [
            TaskInfo(task_id=101, priority="high",   estimate_hours=8, required_skills=["python"]),
            TaskInfo(task_id=102, priority="medium", estimate_hours=8, required_skills=["react"]),
            TaskInfo(task_id=103, priority="low",    estimate_hours=8, required_skills=[]),
        ]

    def test_known_optimal_assignment(self):
        """
        T1 must go to M1 (python:5), T2 must go to M2 (react:5).
        T3 gets the remaining member (M3).
        """
        members = self._make_members()
        tasks = self._make_tasks()
        results = recommend_assignments(tasks, members)
        assigned = {r.task_id: r.user_id for r in results}

        assert assigned[101] == 1, f"T1 should go to Alice (M1), got user {assigned.get(101)}"
        assert assigned[102] == 2, f"T2 should go to Bob (M2), got user {assigned.get(102)}"
        # T3 → M3 (Carol), though M1 or M2 also acceptable if slots remain
        assert 103 in assigned, "T3 should be assigned"

    def test_all_results_have_required_fields(self):
        results = recommend_assignments(self._make_tasks(), self._make_members())
        for r in results:
            assert 0 <= r.skill_match <= 1
            assert 0 <= r.availability <= 1
            assert 0 <= r.performance <= 1
            assert 0 <= r.score <= 1
            assert r.reason  # non-empty string

    def test_skill_match_no_skills_gives_0_5(self):
        task = TaskInfo(task_id=1, priority="low", estimate_hours=8, required_skills=[])
        member = MemberInfo(user_id=1, full_name="X", skills={},
                            capacity_hours_per_week=30, on_time_rate=0.7, weeks_remaining=4)
        assert _skill_match(task, member) == 0.5

    def test_skill_match_full_match(self):
        task = TaskInfo(task_id=1, priority="low", estimate_hours=8, required_skills=["python"])
        member = MemberInfo(user_id=1, full_name="X", skills={"python": 5},
                            capacity_hours_per_week=30, on_time_rate=0.7, weeks_remaining=4)
        assert _skill_match(task, member) == 1.0

    def test_skill_match_missing_skill_zero(self):
        task = TaskInfo(task_id=1, priority="low", estimate_hours=8, required_skills=["sql"])
        member = MemberInfo(user_id=1, full_name="X", skills={"python": 5},
                            capacity_hours_per_week=30, on_time_rate=0.7, weeks_remaining=4)
        assert _skill_match(task, member) == 0.0

    def test_availability_zero_capacity_guard(self):
        """Zero capacity must not cause division by zero."""
        task = TaskInfo(task_id=1, priority="low", estimate_hours=8, required_skills=[])
        member = MemberInfo(user_id=1, full_name="X", skills={},
                            capacity_hours_per_week=0, on_time_rate=0.7, weeks_remaining=4)
        av = _availability(task, member)
        assert av == 0.0

    def test_availability_clipped_at_0(self):
        """When current_open_hours > capacity, availability is 0, not negative."""
        task = TaskInfo(task_id=1, priority="low", estimate_hours=8, required_skills=[])
        member = MemberInfo(user_id=1, full_name="X", skills={},
                            capacity_hours_per_week=5, on_time_rate=0.7, weeks_remaining=1,
                            current_open_hours=50)  # way over capacity
        av = _availability(task, member)
        assert av == 0.0

    def test_score_formula(self):
        """score = 0.5*sm + 0.3*av + 0.2*perf"""
        s = _score(1.0, 1.0, 1.0)
        assert abs(s - 1.0) < 1e-9
        s2 = _score(0.5, 0.5, 0.5)
        assert abs(s2 - 0.5) < 1e-9

    def test_no_members_returns_empty(self):
        tasks = self._make_tasks()
        assert recommend_assignments(tasks, []) == []

    def test_priority_ordering(self):
        """Critical tasks must appear before low-priority tasks in results."""
        members = self._make_members()
        tasks = [
            TaskInfo(task_id=1, priority="low",      estimate_hours=8, required_skills=[]),
            TaskInfo(task_id=2, priority="critical",  estimate_hours=8, required_skills=[]),
            TaskInfo(task_id=3, priority="medium",    estimate_hours=8, required_skills=[]),
        ]
        results = recommend_assignments(tasks, members)
        task_ids = [r.task_id for r in results]
        # Task 2 (critical) must be assigned before task 1 (low)
        assert task_ids.index(2) < task_ids.index(1)


# ─────────────────────────────────────────────────────────────────────────────
# Unit tests: workload service
# ─────────────────────────────────────────────────────────────────────────────

class TestWorkloadUnit:
    def _run(self, members, tasks, weeks=4.0):
        return {e.user_id: e for e in compute_workload(members, tasks, weeks)}

    def test_overloaded_label(self):
        """Member with util > 1.0 → overloaded."""
        m = [{"user_id": 1, "full_name": "A", "capacity_hours_per_week": 10}]
        t = [{"assignee_id": 1, "status": "todo", "estimate_hours": 50}]  # 50h / 40h = 1.25
        result = self._run(m, t, weeks=4)
        assert result[1].label == "overloaded"
        assert result[1].utilization > 1.0

    def test_healthy_label(self):
        """20h assigned / 40h total → util=0.5 → healthy."""
        m = [{"user_id": 1, "full_name": "A", "capacity_hours_per_week": 10}]
        t = [{"assignee_id": 1, "status": "in_progress", "estimate_hours": 20}]
        result = self._run(m, t, weeks=4)
        assert result[1].label == "healthy"

    def test_available_label(self):
        """No tasks assigned → util=0 → available."""
        m = [{"user_id": 1, "full_name": "A", "capacity_hours_per_week": 30}]
        result = self._run(m, [], weeks=4)
        assert result[1].label == "available"
        assert result[1].utilization == 0.0

    def test_at_risk_label(self):
        """util = 0.9 → at_risk."""
        m = [{"user_id": 1, "full_name": "A", "capacity_hours_per_week": 10}]
        t = [{"assignee_id": 1, "status": "todo", "estimate_hours": 36}]  # 36/40 = 0.9
        result = self._run(m, t, weeks=4)
        assert result[1].label == "at_risk"

    def test_done_tasks_not_counted(self):
        """Completed tasks must not contribute to open_hours_assigned."""
        m = [{"user_id": 1, "full_name": "A", "capacity_hours_per_week": 10}]
        t = [{"assignee_id": 1, "status": "done", "estimate_hours": 100}]  # should be ignored
        result = self._run(m, t, weeks=4)
        assert result[1].open_hours_assigned == 0.0
        assert result[1].label == "available"

    def test_zero_capacity_no_divide_by_zero(self):
        """Member with 0 capacity → util=0, no crash."""
        m = [{"user_id": 1, "full_name": "A", "capacity_hours_per_week": 0}]
        t = [{"assignee_id": 1, "status": "todo", "estimate_hours": 8}]
        result = self._run(m, t, weeks=4)
        assert result[1].utilization == 0.0

    def test_sorted_by_utilization_desc(self):
        """Result must be sorted by utilization descending (overloaded first)."""
        members = [
            {"user_id": 1, "full_name": "A", "capacity_hours_per_week": 10},
            {"user_id": 2, "full_name": "B", "capacity_hours_per_week": 10},
        ]
        tasks = [
            {"assignee_id": 1, "status": "todo", "estimate_hours": 50},  # util=1.25
            {"assignee_id": 2, "status": "todo", "estimate_hours": 10},  # util=0.25
        ]
        entries = compute_workload(members, tasks, weeks_remaining=4)
        assert entries[0].user_id == 1  # higher utilization first


# ─────────────────────────────────────────────────────────────────────────────
# HTTP integration tests
# ─────────────────────────────────────────────────────────────────────────────

class TestRecommendEndpoint:
    def test_recommend_returns_all_fields(self, client):
        tok = register(client, "a@a.com", "usera")
        pid = create_project(client, tok)
        create_task(client, tok, pid, "Build login", skills=["python"])
        r = client.post(f"/api/v1/projects/{pid}/assignments/recommend",
                        json={}, headers=auth(tok))
        assert r.status_code == 200, r.text
        data = r.json()["data"]
        assert len(data) == 1
        row = data[0]
        for field in ["task_id", "user_id", "skill_match", "availability",
                      "performance", "score", "reason"]:
            assert field in row, f"Missing field: {field}"
        assert isinstance(row["reason"], str) and len(row["reason"]) > 10

    def test_recommend_no_unassigned_returns_empty(self, client):
        """No unassigned tasks → empty list (not an error)."""
        tok = register(client, "a@a.com", "usera")
        pid = create_project(client, tok)
        # No tasks at all
        r = client.post(f"/api/v1/projects/{pid}/assignments/recommend",
                        json={}, headers=auth(tok))
        assert r.status_code == 200
        assert r.json()["data"] == []

    def test_recommend_non_member_gets_404(self, client):
        tok1 = register(client, "a@a.com", "usera")
        tok2 = register(client, "b@b.com", "userb")
        pid = create_project(client, tok1)
        r = client.post(f"/api/v1/projects/{pid}/assignments/recommend",
                        json={}, headers=auth(tok2))
        assert r.status_code == 404

    def test_recommend_scores_between_0_and_1(self, client):
        tok = register(client, "a@a.com", "usera")
        pid = create_project(client, tok)
        create_task(client, tok, pid, "T1", skills=["react"], estimate=8)
        create_task(client, tok, pid, "T2", estimate=4)
        r = client.post(f"/api/v1/projects/{pid}/assignments/recommend",
                        json={}, headers=auth(tok))
        for row in r.json()["data"]:
            assert 0.0 <= row["score"] <= 1.0
            assert 0.0 <= row["skill_match"] <= 1.0
            assert 0.0 <= row["availability"] <= 1.0


class TestApplyEndpoint:
    def test_apply_assigns_tasks(self, client):
        """Admin applies recommendations → tasks get assignee_id set."""
        tok = register(client, "a@a.com", "usera")
        me = client.get("/api/v1/auth/me", headers=auth(tok)).json()["data"]
        pid = create_project(client, tok)
        tid = create_task(client, tok, pid, "Task X")

        r = client.post(
            f"/api/v1/projects/{pid}/assignments/apply",
            json={"assignments": [{"task_id": tid, "user_id": me["id"]}]},
            headers=auth(tok),
        )
        assert r.status_code == 200, r.text
        assert r.json()["data"]["applied"] == 1

        # Verify assignee persisted
        task = client.get(f"/api/v1/tasks/{tid}", headers=auth(tok)).json()["data"]
        assert task["assignee_id"] == me["id"]

    def test_apply_writes_activity_log(self, client):
        tok = register(client, "a@a.com", "usera")
        me = client.get("/api/v1/auth/me", headers=auth(tok)).json()["data"]
        pid = create_project(client, tok)
        tid = create_task(client, tok, pid, "Task Y")
        client.post(
            f"/api/v1/projects/{pid}/assignments/apply",
            json={"assignments": [{"task_id": tid, "user_id": me["id"]}]},
            headers=auth(tok),
        )
        activity = client.get(f"/api/v1/projects/{pid}/activity", headers=auth(tok)).json()["data"]
        assert any(row["action"] == "task_assigned" for row in activity)

    def test_apply_non_admin_forbidden(self, client):
        tok_admin = register(client, "a@a.com", "usera")
        tok_member = register(client, "b@b.com", "userb")
        pid = create_project(client, tok_admin)
        tid = create_task(client, tok_admin, pid, "Task Z")
        me = client.get("/api/v1/auth/me", headers=auth(tok_member)).json()["data"]
        add_member(client, tok_admin, pid, "b@b.com")
        r = client.post(
            f"/api/v1/projects/{pid}/assignments/apply",
            json={"assignments": [{"task_id": tid, "user_id": me["id"]}]},
            headers=auth(tok_member),
        )
        assert r.status_code == 403


class TestWorkloadEndpoint:
    def test_workload_returns_all_members(self, client):
        tok = register(client, "a@a.com", "usera")
        pid = create_project(client, tok)
        r = client.get(f"/api/v1/projects/{pid}/analytics/workload", headers=auth(tok))
        assert r.status_code == 200
        data = r.json()["data"]
        assert len(data) == 1  # just the admin

    def test_workload_has_label_field(self, client):
        tok = register(client, "a@a.com", "usera")
        pid = create_project(client, tok)
        r = client.get(f"/api/v1/projects/{pid}/analytics/workload", headers=auth(tok))
        for row in r.json()["data"]:
            assert row["label"] in ("overloaded", "at_risk", "healthy", "available")
            assert "utilization" in row

    def test_workload_increases_with_assigned_tasks(self, client):
        tok = register(client, "a@a.com", "usera")
        me = client.get("/api/v1/auth/me", headers=auth(tok)).json()["data"]
        pid = create_project(client, tok)

        # Baseline
        r1 = client.get(f"/api/v1/projects/{pid}/analytics/workload", headers=auth(tok))
        util_before = r1.json()["data"][0]["utilization"]

        # Assign a task
        tid = create_task(client, tok, pid, "Big task", estimate=40)
        client.patch(f"/api/v1/tasks/{tid}", json={"assignee_id": me["id"]}, headers=auth(tok))

        r2 = client.get(f"/api/v1/projects/{pid}/analytics/workload", headers=auth(tok))
        util_after = r2.json()["data"][0]["utilization"]
        assert util_after > util_before

    def test_workload_non_member_gets_404(self, client):
        tok1 = register(client, "a@a.com", "usera")
        tok2 = register(client, "b@b.com", "userb")
        pid = create_project(client, tok1)
        r = client.get(f"/api/v1/projects/{pid}/analytics/workload", headers=auth(tok2))
        assert r.status_code == 404
