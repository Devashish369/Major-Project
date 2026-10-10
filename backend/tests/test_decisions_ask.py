"""
tests/test_decisions_ask.py – M12: decisions CRUD + POST /projects/{id}/ask.

The LLM is ALWAYS mocked (patching app.services.ask.call_llm); no real API call is made.
"""
import json

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import ask as ask_mod

API = "/api/v1"


@pytest.fixture
def client():
    return TestClient(app)


def auth(tok):
    return {"Authorization": f"Bearer {tok}"}


def register(client, name):
    r = client.post(f"{API}/auth/register", json={
        "email": f"{name}@t.com", "username": name, "full_name": name.title(), "password": "Secure#2026"})
    assert r.status_code == 201
    return r.json()["data"]["access_token"]


@pytest.fixture
def world(client):
    """admin owns project P with one task and one decision; 'mem' is a member; 'out' is not."""
    admin, mem, out = register(client, "admin1"), register(client, "mem1"), register(client, "out1")
    pid = client.post(f"{API}/projects", json={"title": "P"}, headers=auth(admin)).json()["data"]["id"]
    client.post(f"{API}/projects/{pid}/members", json={"email": "mem1@t.com", "role": "member"}, headers=auth(admin))
    tid = client.post(f"{API}/projects/{pid}/tasks", json={"title": "Build login", "estimate_hours": 5},
                      headers=auth(admin)).json()["data"]["id"]
    d = client.post(f"{API}/projects/{pid}/decisions", headers=auth(admin), json={
        "title": "Use PostgreSQL", "decision": "We store data in PostgreSQL.",
        "reason": "Team knows it.", "related_task_id": tid}).json()["data"]
    return dict(admin=admin, mem=mem, out=out, pid=pid, tid=tid, did=d["id"])


@pytest.fixture
def llm(monkeypatch):
    """Configure a primary key and capture prompts; tests set .reply."""
    monkeypatch.setattr(ask_mod.settings, "LLM_API_KEY", "k")
    monkeypatch.setattr(ask_mod.settings, "LLM_FALLBACK_API_KEY", "")
    monkeypatch.setattr(ask_mod.settings, "USE_CACHED_PLAN_ONLY", False)

    class Fake:
        reply = ""
        calls = []

    def fake(prompt, *, use_fallback=False, system=None):
        Fake.calls.append({"prompt": prompt, "fallback": use_fallback, "system": system})
        if isinstance(Fake.reply, Exception):
            raise Fake.reply
        return Fake.reply

    Fake.calls = []
    monkeypatch.setattr(ask_mod, "call_llm", fake)
    return Fake


# ── Decisions CRUD ────────────────────────────────────────────────────────────

class TestDecisions:
    def test_create_list_shows_author(self, client, world):
        r = client.get(f"{API}/projects/{world['pid']}/decisions", headers=auth(world["mem"]))
        assert r.status_code == 200
        rows = r.json()["data"]
        assert len(rows) == 1 and rows[0]["title"] == "Use PostgreSQL"
        assert rows[0]["made_by_name"] == "Admin1" and rows[0]["related_task_id"] == world["tid"]

    def test_create_writes_activity(self, client, world):
        acts = client.get(f"{API}/projects/{world['pid']}/activity", headers=auth(world["admin"])).json()["data"]
        assert any(a["action"] == "decision_added" for a in acts)

    def test_non_member_gets_404_everywhere(self, client, world):
        h = auth(world["out"])
        assert client.get(f"{API}/projects/{world['pid']}/decisions", headers=h).status_code == 404
        assert client.post(f"{API}/projects/{world['pid']}/decisions", headers=h,
                           json={"title": "x", "decision": "y"}).status_code == 404
        assert client.delete(f"{API}/decisions/{world['did']}", headers=h).status_code == 404
        assert client.post(f"{API}/projects/{world['pid']}/ask", headers=h,
                           json={"question": "anything?"}).status_code == 404

    def test_related_task_must_belong_to_project(self, client, world):
        other = client.post(f"{API}/projects", json={"title": "Q"}, headers=auth(world["admin"])).json()["data"]["id"]
        t2 = client.post(f"{API}/projects/{other}/tasks", json={"title": "Other"}, headers=auth(world["admin"])).json()["data"]["id"]
        r = client.post(f"{API}/projects/{world['pid']}/decisions", headers=auth(world["admin"]),
                        json={"title": "x", "decision": "y", "related_task_id": t2})
        assert r.status_code == 422

    def test_validation(self, client, world):
        r = client.post(f"{API}/projects/{world['pid']}/decisions", headers=auth(world["admin"]),
                        json={"title": "", "decision": "y"})
        assert r.status_code == 422

    def test_delete_rules(self, client, world):
        # a member who is not the author cannot delete; the author's own decision can be deleted
        d2 = client.post(f"{API}/projects/{world['pid']}/decisions", headers=auth(world["mem"]),
                         json={"title": "Mine", "decision": "mine"}).json()["data"]["id"]
        assert client.delete(f"{API}/decisions/{world['did']}", headers=auth(world["mem"])).status_code == 403
        assert client.delete(f"{API}/decisions/{d2}", headers=auth(world["mem"])).status_code == 200
        assert client.delete(f"{API}/decisions/{world['did']}", headers=auth(world["admin"])).status_code == 200
        assert client.get(f"{API}/projects/{world['pid']}/decisions", headers=auth(world["admin"])).json()["data"] == []


# ── Ask ───────────────────────────────────────────────────────────────────────

def ask(client, world, q="Why PostgreSQL?", who="mem"):
    return client.post(f"{API}/projects/{world['pid']}/ask", json={"question": q}, headers=auth(world[who]))


class TestAsk:
    def test_answer_with_validated_sources(self, client, world, llm):
        did, tid = world["did"], world["tid"]
        llm.reply = json.dumps({"answer": f"PostgreSQL was chosen because the team knows it [D{did}].",
                                "sources": [f"D{did}", f"T{tid}", "D9999"]})   # D9999 is invented
        r = ask(client, world)
        assert r.status_code == 200
        data = r.json()["data"]
        assert "PostgreSQL" in data["answer"]
        assert ("decision", did) in [(x["type"], x["id"]) for x in data["sources"]]
        assert ("task", tid) in [(x["type"], x["id"]) for x in data["sources"]]
        assert all(s["id"] != 9999 for s in data["sources"])        # invented id dropped

    def test_prompt_contains_project_data_and_strict_system_prompt(self, client, world, llm):
        llm.reply = json.dumps({"answer": "x", "sources": []})
        ask(client, world)
        call = llm.calls[0]
        assert "Use PostgreSQL" in call["prompt"] and "Build login" in call["prompt"]
        assert f"[D{world['did']}]" in call["prompt"] and f"[T{world['tid']}]" in call["prompt"]
        assert "ONLY" in call["system"] and "Why PostgreSQL?" in call["prompt"]

    def test_other_projects_data_never_in_context(self, client, world, llm):
        other = client.post(f"{API}/projects", json={"title": "Secret"}, headers=auth(world["admin"])).json()["data"]["id"]
        client.post(f"{API}/projects/{other}/decisions", headers=auth(world["admin"]),
                    json={"title": "TOPSECRET plan", "decision": "launch on mars"})
        llm.reply = json.dumps({"answer": "x", "sources": []})
        ask(client, world)
        assert "TOPSECRET" not in llm.calls[0]["prompt"]

    def test_not_in_context_is_passed_through(self, client, world, llm):
        llm.reply = json.dumps({"answer": ask_mod.NOT_FOUND_ANSWER, "sources": []})
        data = ask(client, world, "What is the CEO's birthday?").json()["data"]
        assert data["answer"] == ask_mod.NOT_FOUND_ANSWER and data["sources"] == []

    def test_fenced_json_and_plain_text_are_handled(self, client, world, llm):
        did = world["did"]
        llm.reply = "```json\n" + json.dumps({"answer": f"See [D{did}]", "sources": []}) + "\n```"
        assert ask(client, world).json()["data"]["sources"] == [{"type": "decision", "id": did, "number": 1}]
        llm.reply = f"Plain text answer citing D{did}."
        assert ask(client, world).json()["data"]["sources"] == [{"type": "decision", "id": did, "number": 1}]

    def test_fallback_provider_used_when_primary_fails(self, client, world, llm, monkeypatch):
        monkeypatch.setattr(ask_mod.settings, "LLM_FALLBACK_API_KEY", "k2")
        results = [RuntimeError("primary down"), json.dumps({"answer": "ok", "sources": []})]

        def flaky(prompt, *, use_fallback=False, system=None):
            r = results.pop(0)
            if isinstance(r, Exception):
                raise r
            assert use_fallback is True
            return r

        monkeypatch.setattr(ask_mod, "call_llm", flaky)
        assert ask(client, world).json()["data"]["answer"] == "ok"

    def test_all_providers_failing_gives_clear_503(self, client, world, llm):
        llm.reply = RuntimeError("boom")
        r = ask(client, world)
        assert r.status_code == 503 and "could not be reached" in r.json()["detail"]

    def test_no_provider_configured_gives_clear_503(self, client, world, llm, monkeypatch):
        monkeypatch.setattr(ask_mod.settings, "LLM_API_KEY", "")
        r = ask(client, world)
        assert r.status_code == 503 and "No AI provider" in r.json()["detail"]
        assert llm.calls == []

    def test_cached_only_mode_never_calls_llm(self, client, world, llm, monkeypatch):
        monkeypatch.setattr(ask_mod.settings, "USE_CACHED_PLAN_ONLY", True)
        r = ask(client, world)
        assert r.status_code == 503 and "USE_CACHED_PLAN_ONLY" in r.json()["detail"]
        assert llm.calls == []

    def test_question_validation(self, client, world, llm):
        assert ask(client, world, "?").status_code == 422


class TestContext:
    def test_truncated_to_safe_size_and_activity_capped(self, client, world, db_session=None):
        from tests.conftest import TestingSessionLocal
        for i in range(400):
            client.post(f"{API}/projects/{world['pid']}/tasks",
                        json={"title": f"Task number {i} with a fairly long descriptive title", "estimate_hours": 2},
                        headers=auth(world["admin"]))
        db = TestingSessionLocal()
        try:
            text, valid = ask_mod.build_context(db, world["pid"])
        finally:
            db.close()
        assert len(text) <= ask_mod.MAX_CONTEXT_CHARS + 200
        assert "more omitted" in text
        assert any(s["type"] == "decision" and s["id"] == world["did"] for s in valid.values())                              # decisions are kept first
        assert sum(1 for t in valid if t.startswith("A")) <= ask_mod.MAX_ACTIVITY_ROWS
