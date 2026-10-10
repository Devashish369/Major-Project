"""
tests/test_skill_gaps.py – skill synonyms, skill relatedness, "who should learn it", and the admin
changing an AI assignment suggestion.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.models import ActivityLog
from app.services.skill_gaps import GapMember, compute_skill_gaps
from app.services.skills import canonical, canonical_levels, relatedness
from tests.conftest import TestingSessionLocal

API = "/api/v1"


@pytest.fixture
def client():
    return TestClient(app)


# ── Pure functions ────────────────────────────────────────────────────────────

def test_synonyms_collapse_to_one_name():
    assert canonical(" ReactJS ") == canonical("react.js") == "react"
    assert canonical("ML") == "machine learning" and canonical("Gen AI") == canonical("GenAI") == "generative ai"
    assert canonical_levels({"React": 2, "reactjs": 4, "ML": 3}) == {"react": 4, "machine learning": 3}


def test_rag_is_much_closer_to_generative_ai_than_react_is():
    assert relatedness("generative ai", "rag") >= 0.9
    assert relatedness("generative ai", "react") < 0.3
    assert relatedness("penetration testing", "ethical hacking") >= 0.9
    assert relatedness("css", "react") == pytest.approx(0.6)               # same family
    assert relatedness("x", "x") == 1.0 and relatedness("", "react") == 0.0
    assert relatedness("rag", "llm") == relatedness("llm", "rag")          # symmetric


def _m(uid, name, skills, util, ontime=0.7):
    return GapMember(user_id=uid, full_name=name, skills=skills, utilization=util, on_time_rate=ontime)


def test_closest_and_least_loaded_are_both_suggested():
    members = [_m(1, "Riya", {"rag": 4, "python": 3}, 0.9), _m(2, "Arjun", {"react": 5}, 0.2)]
    tasks = [{"id": 10, "number": 3, "title": "Chatbot", "required_skills": ["Gen AI", "python"]}]
    [gap] = compute_skill_gaps(tasks, members)
    assert gap["canonical"] == "generative ai" and gap["skill"] == "Gen AI"
    assert gap["tasks"] == [{"id": 10, "number": 3, "title": "Chatbot"}]
    assert gap["closest"]["full_name"] == "Riya" and gap["closest"]["via_skill"] == "rag"
    assert gap["least_loaded"]["full_name"] == "Arjun"
    assert "Riya" in gap["advice"] and "Arjun" in gap["advice"]


def test_one_person_can_be_both():
    members = [_m(1, "Riya", {"rag": 4}, 0.1), _m(2, "Arjun", {"react": 5}, 0.8)]
    [gap] = compute_skill_gaps([{"id": 1, "number": 1, "title": "t", "required_skills": ["llm"]}], members)
    assert gap["closest"]["user_id"] == gap["least_loaded"]["user_id"] == 1
    assert "lowest workload" in gap["advice"]


def test_no_related_skill_falls_back_to_lowest_workload():
    members = [_m(1, "A", {"figma": 5}, 0.5), _m(2, "B", {"excel": 2}, 0.1)]
    [gap] = compute_skill_gaps([{"id": 1, "number": 1, "title": "t", "required_skills": ["kubernetes"]}], members)
    assert gap["closest"] is None and gap["least_loaded"]["full_name"] == "B"
    assert gap["advice"].startswith("No one has a related skill")


def test_covered_skills_are_not_gaps_and_higher_level_wins():
    members = [_m(1, "A", {"node": 1}, 0.0), _m(2, "B", {"rag": 2}, 0.0), _m(3, "C", {"llm": 5}, 0.5)]
    tasks = [{"id": 1, "number": 1, "title": "t", "required_skills": ["Node.js", "generative ai"]}]
    [gap] = compute_skill_gaps(tasks, members)              # node.js is covered via the synonym
    assert gap["canonical"] == "generative ai"
    assert gap["closest"]["full_name"] == "C"               # llm L5 (0.95×1.0) beats rag L2 (0.9×0.7)


# ── API ───────────────────────────────────────────────────────────────────────

def _user(client, name, skills):
    r = client.post(f"{API}/auth/register", json={"email": f"{name}@gap.org", "username": name,
                                                   "full_name": name.title(), "password": "Secure#2026"})
    h = {"Authorization": f"Bearer {r.json()['data']['access_token']}"}
    client.patch(f"{API}/auth/me", json={"skills": skills}, headers=h)
    return h, r.json()["data"]["user"]["id"]


@pytest.fixture
def team(client):
    admin, admin_id = _user(client, "admin", {"rag": 4, "python": 4})
    member, member_id = _user(client, "riya", {"react": 5})
    pid = client.post(f"{API}/projects", json={"title": "AI app", "due_date": "2030-01-01"}, headers=admin).json()["data"]["id"]
    client.post(f"{API}/projects/{pid}/members", json={"email": "riya@gap.org", "role": "member"}, headers=admin)
    tasks = [client.post(f"{API}/projects/{pid}/tasks", headers=admin, json={
        "title": title, "estimate_hours": 8, "required_skills": skills}).json()["data"]
        for title, skills in [("Chatbot", ["GenAI"]), ("UI", ["ReactJS"]), ("Infra", ["kubernetes"])]]
    return {"pid": pid, "admin": admin, "admin_id": admin_id, "member": member, "member_id": member_id, "tasks": tasks}


def test_skill_gaps_endpoint(client, team):
    r = client.get(f"{API}/projects/{team['pid']}/assignments/skill-gaps", headers=team["member"])
    assert r.status_code == 200
    gaps = {g["canonical"]: g for g in r.json()["data"]}
    assert set(gaps) == {"generative ai", "kubernetes"}            # react is covered via "ReactJS"
    assert gaps["generative ai"]["closest"]["user_id"] == team["admin_id"]
    assert gaps["generative ai"]["tasks"][0]["number"] == 1


def test_skill_gaps_are_members_only(client, team):
    outsider, _ = _user(client, "outsider", {})
    assert client.get(f"{API}/projects/{team['pid']}/assignments/skill-gaps", headers=outsider).status_code == 404


def test_recommendation_rows_have_numbers_alternatives_and_missing_skills(client, team):
    rows = client.post(f"{API}/projects/{team['pid']}/assignments/recommend", json={}, headers=team["admin"]).json()["data"]
    by_title = {r["task_title"]: r for r in rows}
    ui = by_title["UI"]
    assert ui["task_number"] == 2 and ui["user_id"] == team["member_id"]    # synonym match: ReactJS = react
    assert ui["skill_match"] == 1.0
    assert {a["user_id"] for a in ui["alternatives"]} == {team["admin_id"], team["member_id"]}
    assert ui["alternatives"][0]["score"] >= ui["alternatives"][-1]["score"]
    assert by_title["Chatbot"]["missing_skills"] == ["generative ai"] and ui["missing_skills"] == []


def test_admin_can_change_the_suggested_person(client, team):
    rows = client.post(f"{API}/projects/{team['pid']}/assignments/recommend", json={}, headers=team["admin"]).json()["data"]
    ui = next(r for r in rows if r["task_title"] == "UI")
    other = next(a["user_id"] for a in ui["alternatives"] if a["user_id"] != ui["user_id"])
    r = client.post(f"{API}/projects/{team['pid']}/assignments/apply", headers=team["admin"], json={"assignments": [
        {"task_id": ui["task_id"], "user_id": other, "recommended_user_id": ui["user_id"]}]})
    assert r.status_code == 200 and r.json()["data"] == {"applied": 1, "overridden": 1}
    task = next(t for t in client.get(f"{API}/projects/{team['pid']}/tasks", headers=team["admin"]).json()["data"]
                if t["id"] == ui["task_id"])
    assert task["assignee_id"] == other
    db = TestingSessionLocal()
    try:
        meta = db.execute(select(ActivityLog.meta).where(ActivityLog.action == "task_assigned")).scalar_one()
    finally:
        db.close()
    assert meta == {"assignee_id": other, "recommended_user_id": ui["user_id"], "overridden": True}


def test_only_admins_apply_and_bad_bodies_are_422(client, team):
    t = team["tasks"][0]["id"]
    body = {"assignments": [{"task_id": t, "user_id": team["member_id"]}]}
    assert client.post(f"{API}/projects/{team['pid']}/assignments/apply", json=body, headers=team["member"]).status_code == 403
    for bad in ({"assignments": [{"task_id": t}]}, {"assignments": [{"task_id": "x", "user_id": 1}]}, {"assignments": "no"}):
        assert client.post(f"{API}/projects/{team['pid']}/assignments/apply", json=bad, headers=team["admin"]).status_code == 422
    outsider, outsider_id = _user(client, "stranger", {})
    r = client.post(f"{API}/projects/{team['pid']}/assignments/apply", headers=team["admin"],
                    json={"assignments": [{"task_id": t, "user_id": outsider_id}]})
    assert r.json()["data"]["applied"] == 0                          # non-members are never assigned
