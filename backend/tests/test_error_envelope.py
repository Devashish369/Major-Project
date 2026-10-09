"""tests/test_error_envelope.py – every error response uses the spec §7 envelope."""
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app

API = "/api/v1"


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


def _is_envelope(body):
    return body["success"] is False and isinstance(body["message"], str) and isinstance(body["errors"], list)


def test_401_is_envelope_and_keeps_detail(client):
    r = client.get(f"{API}/projects")
    assert r.status_code == 401
    body = r.json()
    assert _is_envelope(body) and body["detail"] == body["message"]


def test_404_for_non_member_is_envelope(client):
    tok = client.post(f"{API}/auth/register", json={
        "email": "e@t.com", "username": "enve", "full_name": "E", "password": "password123"}).json()["data"]["access_token"]
    r = client.get(f"{API}/projects/9999", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 404 and _is_envelope(r.json())


def test_422_lists_each_field(client):
    r = client.post(f"{API}/auth/login", json={"email": "x"})
    body = r.json()
    assert r.status_code == 422 and _is_envelope(body)
    assert {e["field"] for e in body["errors"]} == {"email", "password"}
    assert isinstance(body["detail"], list)          # FastAPI-style detail kept for old clients


def test_500_does_not_leak_internals(client):
    def boom():
        raise RuntimeError("secret SQL: SELECT * FROM users")
    app.add_api_route("/api/v1/_boom", boom)
    try:
        r = client.get(f"{API}/_boom")
    finally:
        app.router.routes.pop()
    assert r.status_code == 500 and _is_envelope(r.json())
    assert "secret" not in r.text


def test_bad_username_is_a_readable_422_and_no_account_is_created(client):
    """The exact input from a user report: username 'aditya@'."""
    r = client.post(f"{API}/auth/register", json={
        "email": "aditya@123.com", "username": "aditya@", "full_name": "Aditya Pande", "password": "password123"})
    body = r.json()
    assert r.status_code == 422 and _is_envelope(body)
    assert "letters, digits, and underscores" in body["message"] and "Value error" not in body["message"]
    assert isinstance(body["detail"], list)                     # list shape is kept for old clients ...
    # ... so the frontend must never render `detail` directly (see frontend/src/api/errors.js)
    login = client.post(f"{API}/auth/login", json={"email": "aditya@123.com", "password": "password123"})
    assert login.status_code == 401                             # nothing was stored
