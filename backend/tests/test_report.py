"""
tests/test_report.py – M16: GET /projects/{id}/report (structure, permissions, edge cases,
rule-based insights on the seeded E-commerce and IoT demo projects).  No LLM is involved.
"""
import random
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.main import app

API = "/api/v1"
SECTIONS = {"generated_at", "project", "tasks", "health", "forecast", "workload", "risk",
            "overdue_tasks", "blocked_tasks", "decisions", "activity", "insights", "suggested_actions"}


@pytest.fixture
def client():
    return TestClient(app)


def reg(client, name):
    r = client.post(f"{API}/auth/register", json={"email": f"{name}@rep.com", "username": name,
                                                   "full_name": name.title(), "password": "password123"})
    return {"Authorization": f"Bearer {r.json()['data']['access_token']}"}


def project(client, h, **kw):
    return client.post(f"{API}/projects", json={"title": "R", **kw}, headers=h).json()["data"]["id"]


class TestReportBasics:
    def test_structure_and_envelope(self, client):
        h = reg(client, "rep1")
        pid = project(client, h, due_date=(date.today() + timedelta(days=30)).isoformat())
        a = client.post(f"{API}/projects/{pid}/tasks", json={"title": "A", "estimate_hours": 5}, headers=h).json()["data"]["id"]
        b = client.post(f"{API}/projects/{pid}/tasks", json={"title": "B", "estimate_hours": 5}, headers=h).json()["data"]["id"]
        client.post(f"{API}/tasks/{b}/dependencies", json={"depends_on_id": a}, headers=h)
        client.post(f"{API}/projects/{pid}/decisions", json={"title": "D", "decision": "x"}, headers=h)
        r = client.get(f"{API}/projects/{pid}/report", headers=h)
        body = r.json()
        assert r.status_code == 200 and body["success"] is True
        d = body["data"]
        assert SECTIONS <= set(d)
        assert d["tasks"]["total"] == 2 and d["tasks"]["blocked"] == 1 and d["tasks"]["remaining_hours"] == 10
        assert d["blocked_tasks"][0]["id"] == b and d["blocked_tasks"][0]["blockers"][0]["id"] == a
        assert d["risk"]["experimental"] is True and d["risk"]["training_data"] == "SIMULATED"
        assert d["decisions"][0]["title"] == "D" and len(d["activity"]) <= 10
        # same numbers as the Analytics tab
        health = client.get(f"{API}/projects/{pid}/analytics/health", headers=h).json()["data"]
        assert d["health"]["health_score"] == health["health_score"]
        assert any("blocks 1 open task" in s for s in d["insights"])

    def test_outsider_gets_404(self, client):
        owner, outsider = reg(client, "rep2"), reg(client, "rep3")
        pid = project(client, owner)
        assert client.get(f"{API}/projects/{pid}/report", headers=outsider).status_code == 404

    def test_empty_project(self, client):
        h = reg(client, "rep4")
        d = client.get(f"{API}/projects/{project(client, h)}/report", headers=h).json()["data"]
        assert d["tasks"]["total"] == 0
        assert d["insights"] == ["This project has no tasks yet."]

    def test_completed_project(self, client):
        h = reg(client, "rep5")
        pid = project(client, h)
        client.post(f"{API}/projects/{pid}/tasks", json={"title": "x", "estimate_hours": 3, "status": "done"}, headers=h)
        d = client.get(f"{API}/projects/{pid}/report", headers=h).json()["data"]
        assert d["insights"] == ["All 1 tasks are done."]
        assert d["risk"]["delay_probability"] == 0.0

    def test_no_due_date(self, client):
        h = reg(client, "rep6")
        pid = project(client, h)
        client.post(f"{API}/projects/{pid}/tasks", json={"title": "x", "estimate_hours": 3}, headers=h)
        d = client.get(f"{API}/projects/{pid}/report", headers=h).json()["data"]
        assert d["forecast"]["delay_probability"] is None and d["forecast"]["due_date"] is None
        assert any("No due date is set" in s for s in d["insights"])


class TestReportOnSeededStories:
    @pytest.fixture
    def seeded(self, client):
        """Seed the E-commerce and IoT demo projects into the test DB with the real seed code."""
        from app.models import User
        from app.security import hash_password
        from seed import seed_demo
        from seed.demo_projects import DEMO_PASSWORD, PRESENTER, PROJECTS, USERS
        from tests.conftest import TestingSessionLocal

        pw = hash_password(DEMO_PASSWORD)
        with TestingSessionLocal() as db:
            users = {}
            for key, (name, skills, on_time) in USERS.items():
                users[key] = User(email=f"{key}@intellipm.demo", username=f"{key}_demo", full_name=name,
                                  password_hash=pw, skills=skills, on_time_rate=on_time)
                db.add(users[key])
            presenter = User(email=PRESENTER[0], username=PRESENTER[1], full_name=PRESENTER[2],
                             password_hash=pw, skills={}, on_time_rate=0.9)
            db.add(presenter)
            db.flush()
            rng = random.Random(seed_demo.RNG_SEED)
            for spec in PROJECTS:
                if spec["title"] in ("E-commerce Platform", "IoT Dashboard"):
                    seed_demo.build_project(db, spec, users, presenter, date.today(), rng)
            db.commit()
        tok = client.post(f"{API}/auth/login", json={"email": PRESENTER[0], "password": DEMO_PASSWORD}).json()["data"]["access_token"]
        h = {"Authorization": f"Bearer {tok}"}
        ids = {p["title"]: p["id"] for p in client.get(f"{API}/projects", headers=h).json()["data"]}
        return h, ids

    def test_ecommerce_mentions_overloaded_members(self, client, seeded):
        h, ids = seeded
        d = client.get(f"{API}/projects/{ids['E-commerce Platform']}/report", headers=h).json()["data"]
        assert any("overloaded" in s for s in d["insights"])
        assert any("Recommend assignments" in s for s in d["suggested_actions"])
        assert d["overdue_tasks"] and d["overdue_tasks"][0]["days_overdue"] > 0

    def test_iot_mentions_blocked_tasks(self, client, seeded):
        h, ids = seeded
        d = client.get(f"{API}/projects/{ids['IoT Dashboard']}/report", headers=h).json()["data"]
        assert any("blocks" in s for s in d["insights"])
        assert any(s.startswith("Prioritise task") for s in d["suggested_actions"])
        assert d["blocked_tasks"] and d["blocked_tasks"][0]["blockers"]
