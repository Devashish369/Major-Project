"""
tests/test_ws.py – M13: WS /ws/projects/{id}?token=  (auth, membership, event broadcast).
"""
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.main import app
from app.services.realtime import manager

API = "/api/v1"


@pytest.fixture
def client():
    with TestClient(app) as c:      # context manager keeps one event loop alive across calls
        yield c
    manager._rooms.clear()


def register(client, name):
    r = client.post(f"{API}/auth/register", json={
        "email": f"{name}@t.com", "username": name, "full_name": name.title(), "password": "password123"})
    return r.json()["data"]["access_token"]


def auth(tok):
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture
def world(client):
    a, b, outsider = register(client, "wsa"), register(client, "wsb"), register(client, "wsout")
    pid = client.post(f"{API}/projects", json={"title": "WS"}, headers=auth(a)).json()["data"]["id"]
    client.post(f"{API}/projects/{pid}/members", json={"email": "wsb@t.com", "role": "member"}, headers=auth(a))
    other = client.post(f"{API}/projects", json={"title": "Other"}, headers=auth(outsider)).json()["data"]["id"]
    return dict(a=a, b=b, out=outsider, pid=pid, other=other)


def url(pid, tok):
    return f"/ws/projects/{pid}?token={tok}"


def hello(ws):
    assert ws.receive_json()["type"] == "connected"


# ── Handshake: auth + membership ──────────────────────────────────────────────

class TestHandshake:
    def test_member_connects_and_gets_hello(self, client, world):
        with client.websocket_connect(url(world["pid"], world["a"])) as ws:
            msg = ws.receive_json()
            assert msg == {"type": "connected", "project_id": world["pid"]}

    @pytest.mark.parametrize("token", ["", "garbage.token.value"])
    def test_missing_or_invalid_token_refused(self, client, world, token):
        with pytest.raises(WebSocketDisconnect) as e:
            with client.websocket_connect(url(world["pid"], token)):
                pass
        assert e.value.code == 1008

    def test_non_member_refused(self, client, world):
        with pytest.raises(WebSocketDisconnect) as e:
            with client.websocket_connect(url(world["pid"], world["out"])):
                pass
        assert e.value.code == 1008

    def test_unknown_project_refused(self, client, world):
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(url(99999, world["a"])):
                pass

    def test_ping_pong(self, client, world):
        with client.websocket_connect(url(world["pid"], world["a"])) as ws:
            hello(ws)
            ws.send_text("ping")
            assert ws.receive_json() == {"type": "pong"}

    def test_disconnect_cleans_up_room(self, client, world):
        with client.websocket_connect(url(world["pid"], world["a"])) as ws:
            hello(ws)
            assert manager.has_listeners(world["pid"])
        # leaving the context closes the socket; the room is emptied once the server notices
        import time
        for _ in range(50):
            if not manager.has_listeners(world["pid"]):
                break
            time.sleep(0.05)
        assert not manager.has_listeners(world["pid"])


# ── Events ────────────────────────────────────────────────────────────────────

class TestEvents:
    def test_create_update_delete_are_broadcast(self, client, world):
        pid = world["pid"]
        with client.websocket_connect(url(pid, world["b"])) as ws:
            hello(ws)
            t = client.post(f"{API}/projects/{pid}/tasks", json={"title": "Live task", "estimate_hours": 3},
                            headers=auth(world["a"])).json()["data"]
            ev = ws.receive_json()
            assert ev["type"] == "task_created" and ev["task"]["id"] == t["id"] and ev["task"]["title"] == "Live task"
            assert ev["task"]["dependencies"] == []

            client.patch(f"{API}/tasks/{t['id']}", json={"status": "done"}, headers=auth(world["a"]))
            ev = ws.receive_json()
            assert ev["type"] == "task_updated" and ev["task"]["status"] == "done"
            assert ev["task"]["completed_at"] is not None          # same shape as the REST payload

            client.delete(f"{API}/tasks/{t['id']}", headers=auth(world["a"]))
            ev = ws.receive_json()
            assert ev["type"] == "task_deleted" and ev["task"]["id"] == t["id"]

    def test_dependency_change_is_broadcast(self, client, world):
        pid = world["pid"]
        t1 = client.post(f"{API}/projects/{pid}/tasks", json={"title": "A"}, headers=auth(world["a"])).json()["data"]["id"]
        t2 = client.post(f"{API}/projects/{pid}/tasks", json={"title": "B"}, headers=auth(world["a"])).json()["data"]["id"]
        with client.websocket_connect(url(pid, world["a"])) as ws:
            hello(ws)
            client.post(f"{API}/tasks/{t2}/dependencies", json={"depends_on_id": t1}, headers=auth(world["a"]))
            ev = ws.receive_json()
            assert ev["type"] == "task_updated" and ev["task"]["id"] == t2 and ev["task"]["dependencies"] == [t1]

    def test_every_watcher_gets_the_event(self, client, world):
        pid = world["pid"]
        with client.websocket_connect(url(pid, world["a"])) as w1, client.websocket_connect(url(pid, world["b"])) as w2:
            hello(w1); hello(w2)
            client.post(f"{API}/projects/{pid}/tasks", json={"title": "Both"}, headers=auth(world["a"]))
            assert w1.receive_json()["task"]["title"] == "Both"
            assert w2.receive_json()["task"]["title"] == "Both"

    def test_other_projects_events_are_not_delivered(self, client, world):
        with client.websocket_connect(url(world["pid"], world["a"])) as ws:
            hello(ws)
            # activity in a different project, then in ours; ours must be the first thing received
            client.post(f"{API}/projects/{world['other']}/tasks", json={"title": "Elsewhere"}, headers=auth(world["out"]))
            client.post(f"{API}/projects/{world['pid']}/tasks", json={"title": "Ours"}, headers=auth(world["a"]))
            assert ws.receive_json()["task"]["title"] == "Ours"

    def test_assignment_apply_broadcasts_updates(self, client, world):
        pid = world["pid"]
        tid = client.post(f"{API}/projects/{pid}/tasks", json={"title": "Assign me"}, headers=auth(world["a"])).json()["data"]["id"]
        uid = client.get(f"{API}/auth/me", headers=auth(world["b"])).json()["data"]["id"]
        with client.websocket_connect(url(pid, world["b"])) as ws:
            hello(ws)
            r = client.post(f"{API}/projects/{pid}/assignments/apply",
                            json={"assignments": [{"task_id": tid, "user_id": uid}]}, headers=auth(world["a"]))
            assert r.status_code == 200
            ev = ws.receive_json()
            assert ev["type"] == "task_updated" and ev["task"]["assignee_id"] == uid

    def test_rest_still_works_when_nobody_is_listening(self, client, world):
        r = client.post(f"{API}/projects/{world['pid']}/tasks", json={"title": "Quiet"}, headers=auth(world["a"]))
        assert r.status_code == 201

    def test_broken_socket_layer_never_breaks_rest(self, client, world, monkeypatch):
        def boom(*a, **k):
            raise RuntimeError("socket layer down")
        with client.websocket_connect(url(world["pid"], world["a"])) as ws:
            hello(ws)
            monkeypatch.setattr(manager, "_send_all", boom)
            r = client.post(f"{API}/projects/{world['pid']}/tasks", json={"title": "Still saved"}, headers=auth(world["a"]))
            assert r.status_code == 201
