"""
tests/test_security.py – the attacks a penetration tester would try first, and the defences.

  brute force           → 429 after 5 failures (per email+IP), per-email cap across IPs
  stolen / old tokens   → password change and "sign out everywhere" revoke them (HTTP + WebSocket)
  forged tokens         → wrong key, alg "none", missing expiry, garbage → 401
  long / weak passwords → 422, never a server error
  oversized bodies      → 413;  security headers on every response
  AI quota abuse        → per-user limit → 429;  sign-up spam → 429
"""
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.config import settings
from app.main import app
from app.ratelimit import limit
from app.services import security_events

API = "/api/v1"
PW = "Secure#2026"


@pytest.fixture
def client():
    return TestClient(app)


def _register(client, name, ip="10.0.0.1"):
    r = client.post(f"{API}/auth/register", headers={"X-Forwarded-For": ip},
                    json={"email": f"{name}@sec.org", "username": name, "full_name": name.title(), "password": PW})
    assert r.status_code == 201, r.text
    return r.json()["data"]["access_token"]


def _login(client, name, password, ip="10.0.0.1"):
    return client.post(f"{API}/auth/login", headers={"X-Forwarded-For": ip},
                       json={"email": f"{name}@sec.org", "password": password})


def _h(tok):
    return {"Authorization": f"Bearer {tok}"}


# ── Brute force ───────────────────────────────────────────────────────────────

def test_five_wrong_passwords_block_that_network_for_this_account(client):
    _register(client, "victim")
    for _ in range(5):
        assert _login(client, "victim", "Wrong#1234").status_code == 401
    r = _login(client, "victim", PW)                               # even the right password waits
    assert r.status_code == 429 and int(r.headers["retry-after"]) > 0
    assert "Too many failed sign-in attempts" in r.json()["message"]
    assert _login(client, "victim", PW, ip="10.9.9.9").status_code == 200   # owner elsewhere is not locked out


def test_attack_from_many_addresses_hits_the_per_email_cap(client):
    _register(client, "target")
    for i in range(security_events.MAX_PER_EMAIL):
        _login(client, "target", "Wrong#1234", ip=f"10.1.{i}.1")
    assert _login(client, "target", "Wrong#1234", ip="10.2.0.1").status_code == 429


def test_unknown_emails_get_the_same_answer_as_wrong_passwords(client):
    _register(client, "known")
    a = _login(client, "known", "Wrong#1234")
    b = _login(client, "nobody", "Wrong#1234")
    assert a.status_code == b.status_code == 401 and a.json()["message"] == b.json()["message"]


def test_sign_in_activity_is_recorded_and_private(client):
    tok = _register(client, "alice")
    _login(client, "alice", "Wrong#1234", ip="203.0.113.7")
    _login(client, "alice", PW, ip="203.0.113.7")
    events = client.get(f"{API}/auth/security-events", headers=_h(tok)).json()["data"]
    kinds = [e["event"] for e in events]
    assert kinds[:3] == ["login_success", "login_failed", "register"]
    assert events[0]["ip"] == "203.0.113.7"
    bob = _register(client, "bob")
    assert all(e["event"] == "register" for e in client.get(f"{API}/auth/security-events", headers=_h(bob)).json()["data"])


# ── Revoking sessions ─────────────────────────────────────────────────────────

def test_change_password_revokes_every_older_token(client):
    old = _register(client, "carol")
    other_tab = _login(client, "carol", PW).json()["data"]["access_token"]
    r = client.post(f"{API}/auth/change-password", headers=_h(old),
                    json={"current_password": PW, "new_password": "Brand#New2026"})
    assert r.status_code == 200
    new = r.json()["data"]["access_token"]
    assert client.get(f"{API}/auth/me", headers=_h(old)).status_code == 401
    assert client.get(f"{API}/auth/me", headers=_h(other_tab)).status_code == 401
    assert client.get(f"{API}/auth/me", headers=_h(new)).status_code == 200
    assert _login(client, "carol", PW).status_code == 401 and _login(client, "carol", "Brand#New2026").status_code == 200


def test_change_password_checks_the_current_one_and_the_policy(client):
    tok = _register(client, "dave")
    bad = client.post(f"{API}/auth/change-password", headers=_h(tok),
                      json={"current_password": "Wrong#1234", "new_password": "Brand#New2026"})
    assert bad.status_code == 400
    weak = client.post(f"{API}/auth/change-password", headers=_h(tok),
                       json={"current_password": PW, "new_password": "password123"})
    assert weak.status_code == 422
    assert client.get(f"{API}/auth/me", headers=_h(tok)).status_code == 200      # nothing changed


def test_sign_out_everywhere_also_closes_live_updates(client):
    tok = _register(client, "erin")
    pid = client.post(f"{API}/projects", json={"title": "P"}, headers=_h(tok)).json()["data"]["id"]
    with client.websocket_connect(f"/ws/projects/{pid}?token={tok}") as ws:   # works before
        ws.send_text("ping")
    assert client.post(f"{API}/auth/logout-all", headers=_h(tok)).status_code == 200
    assert client.get(f"{API}/auth/me", headers=_h(tok)).status_code == 401
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"/ws/projects/{pid}?token={tok}") as ws:
            ws.receive_text()


# ── Forged tokens ─────────────────────────────────────────────────────────────

def test_forged_tokens_are_rejected(client):
    _register(client, "frank")
    exp = datetime.now(timezone.utc) + timedelta(hours=1)
    forged = [
        jwt.encode({"sub": "1", "exp": exp}, "not-the-server-key-but-32-bytes-long!", algorithm="HS256"),
        jwt.encode({"sub": "1", "exp": exp}, None, algorithm="none"),
        jwt.encode({"sub": "1"}, settings.SECRET_KEY, algorithm="HS256"),          # no expiry
        jwt.encode({"sub": "1", "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
                   settings.SECRET_KEY, algorithm="HS256"),                          # expired
        "garbage.token.here",
    ]
    for tok in forged:
        assert client.get(f"{API}/auth/me", headers=_h(tok)).status_code == 401


# ── Passwords ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("pw", ["short1", "a" * 73 + "1", "onlyletters", "12345678", "password123", "gracehop12"])
def test_weak_or_too_long_passwords_are_422_not_500(client, pw):
    r = client.post(f"{API}/auth/register", json={"email": "grace@sec.org", "username": "gracehop",
                                                   "full_name": "Grace", "password": pw})
    assert r.status_code == 422, (pw, r.status_code)


def test_a_very_long_login_password_is_401_not_500(client):
    _register(client, "henry")
    assert _login(client, "henry", "x" * 100).status_code == 401
    assert _login(client, "henry", "x" * 200).status_code == 422          # over the 128 limit


# ── Transport / headers ───────────────────────────────────────────────────────

def test_security_headers_and_body_limit(client):
    r = client.get(f"{API}/health")
    for name in ("x-content-type-options", "x-frame-options", "referrer-policy", "strict-transport-security",
                 "content-security-policy", "server-timing"):
        assert name in r.headers, name
    assert r.headers["cache-control"] == "no-store"
    assert "default-src 'none'" not in client.get("/docs").headers.get("content-security-policy", "")
    big = client.post(f"{API}/auth/login", content=b"{" + b" " * 1_100_000 + b"}",
                      headers={"content-type": "application/json"})
    assert big.status_code == 413


def test_cors_allows_the_frontend_only(client):
    pre = {"Access-Control-Request-Method": "GET", "Access-Control-Request-Headers": "authorization"}
    ok = client.options(f"{API}/projects", headers={"Origin": "http://localhost:5173", **pre})
    assert ok.status_code == 200 and ok.headers["access-control-max-age"] == "7200"
    evil = client.options(f"{API}/projects", headers={"Origin": "https://evil.example", **pre})
    assert "access-control-allow-origin" not in evil.headers


# ── Abuse limits ──────────────────────────────────────────────────────────────

def test_per_user_ai_limit():
    mini = FastAPI()

    @mini.get("/x")
    def x(user=Depends(limit("test_limit", 3, 600))):
        return {"ok": True}

    from app.deps import get_current_user

    class U:
        id = 4242
    mini.dependency_overrides[get_current_user] = lambda: U()
    c = TestClient(mini)
    assert [c.get("/x").status_code for _ in range(4)] == [200, 200, 200, 429]


def test_sign_up_spam_is_limited(client, monkeypatch):
    monkeypatch.setattr(security_events, "MAX_REGISTER_PER_IP", 2)
    _register(client, "spam1", ip="10.5.5.5")
    _register(client, "spam2", ip="10.5.5.5")
    r = client.post(f"{API}/auth/register", headers={"X-Forwarded-For": "10.5.5.5"},
                    json={"email": "s3@sec.org", "username": "s3user", "full_name": "S", "password": PW})
    assert r.status_code == 429
    _register(client, "spam4", ip="10.6.6.6")                     # other networks are unaffected
