"""
tests/test_auth.py – Unit/integration tests for M1 auth endpoints.

Uses FastAPI's TestClient with the shared in-memory SQLite DB from conftest.py.

Tests cover the M1 "done when" criteria (section 11):
  ✓ Register a new user
  ✓ Login with correct credentials → token returned
  ✓ Wrong password → 401
  ✓ GET /auth/me with valid token → user returned
  ✓ GET /auth/me without token → 401
  ✓ Duplicate email → 409
  ✓ Duplicate username → 409
  ✓ PATCH /auth/me (update name and skills)
  ✓ Token stays valid across requests (simulate "refresh page")
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


# ── Helpers ───────────────────────────────────────────────────────────────────

def register_user(client, email="test@example.com", username="testuser",
                  full_name="Test User", password="password123"):
    return client.post("/api/v1/auth/register", json={
        "email": email,
        "username": username,
        "full_name": full_name,
        "password": password,
    })


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestRegister:
    def test_register_success(self, client):
        res = register_user(client)
        assert res.status_code == 201
        body = res.json()
        assert body["success"] is True
        assert "access_token" in body["data"]
        assert body["data"]["user"]["email"] == "test@example.com"
        assert "password_hash" not in body["data"]["user"]  # never exposed

    def test_duplicate_email(self, client):
        register_user(client)
        res = register_user(client)   # same email
        assert res.status_code == 409
        assert "Email" in res.json()["detail"]

    def test_duplicate_username(self, client):
        register_user(client, email="a@example.com", username="shared")
        res = register_user(client, email="b@example.com", username="shared")
        assert res.status_code == 409
        assert "Username" in res.json()["detail"]

    def test_short_password_rejected(self, client):
        res = register_user(client, password="short")
        assert res.status_code == 422   # Pydantic validation error

    def test_invalid_email_rejected(self, client):
        res = register_user(client, email="not-an-email")
        assert res.status_code == 422

    def test_username_stored_lowercase(self, client):
        register_user(client, username="TestUser")
        res = register_user(client, email="b@b.com", username="testuser")
        # "TestUser" should have been stored as "testuser" → conflict
        assert res.status_code == 409


class TestLogin:
    def test_login_success(self, client):
        register_user(client)
        res = client.post("/api/v1/auth/login", json={
            "email": "test@example.com",
            "password": "password123",
        })
        assert res.status_code == 200
        body = res.json()
        assert body["success"] is True
        assert "access_token" in body["data"]

    def test_wrong_password_rejected(self, client):
        """M1 done-when: wrong password must return 401."""
        register_user(client)
        res = client.post("/api/v1/auth/login", json={
            "email": "test@example.com",
            "password": "WRONGpassword",
        })
        assert res.status_code == 401

    def test_unknown_email_rejected(self, client):
        res = client.post("/api/v1/auth/login", json={
            "email": "nobody@example.com",
            "password": "password123",
        })
        assert res.status_code == 401

    def test_error_message_does_not_reveal_existence(self, client):
        """Same error message for wrong password and unknown email (no info leak)."""
        register_user(client)
        res_wrong_pw = client.post("/api/v1/auth/login", json={
            "email": "test@example.com",
            "password": "wrong",
        })
        res_unknown = client.post("/api/v1/auth/login", json={
            "email": "nobody@example.com",
            "password": "wrong",
        })
        assert res_wrong_pw.json()["detail"] == res_unknown.json()["detail"]


class TestGetMe:
    def _get_token(self, client):
        res = register_user(client)
        return res.json()["data"]["access_token"]

    def test_me_with_valid_token(self, client):
        """M1 done-when: GET /auth/me returns the current user."""
        token = self._get_token(client)
        res = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200
        assert res.json()["data"]["email"] == "test@example.com"

    def test_me_without_token(self, client):
        """M1 done-when: unauthenticated request must return 401."""
        res = client.get("/api/v1/auth/me")
        assert res.status_code == 401

    def test_me_with_invalid_token(self, client):
        res = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer totally.invalid.token"},
        )
        assert res.status_code == 401

    def test_token_valid_across_requests(self, client):
        """
        Simulate 'refresh page and stay logged in': same token works twice.
        This is the core M1 done-when test.
        """
        token = self._get_token(client)
        headers = {"Authorization": f"Bearer {token}"}

        res1 = client.get("/api/v1/auth/me", headers=headers)
        res2 = client.get("/api/v1/auth/me", headers=headers)

        assert res1.status_code == 200
        assert res2.status_code == 200
        assert res1.json()["data"]["id"] == res2.json()["data"]["id"]


class TestUpdateMe:
    def _auth_headers(self, client):
        res = register_user(client)
        token = res.json()["data"]["access_token"]
        return {"Authorization": f"Bearer {token}"}

    def test_update_full_name(self, client):
        headers = self._auth_headers(client)
        res = client.patch(
            "/api/v1/auth/me",
            json={"full_name": "Updated Name"},
            headers=headers,
        )
        assert res.status_code == 200
        assert res.json()["data"]["full_name"] == "Updated Name"

    def test_update_skills(self, client):
        headers = self._auth_headers(client)
        res = client.patch(
            "/api/v1/auth/me",
            json={"skills": {"python": 5, "react": 3}},
            headers=headers,
        )
        assert res.status_code == 200
        assert res.json()["data"]["skills"]["python"] == 5

    def test_skill_levels_must_be_1_to_5(self, client):
        headers = self._auth_headers(client)
        res = client.patch(
            "/api/v1/auth/me",
            json={"skills": {"python": 9}},
            headers=headers,
        )
        assert res.status_code == 422   # Pydantic validation error

    def test_patch_without_token(self, client):
        res = client.patch("/api/v1/auth/me", json={"full_name": "Hacker"})
        assert res.status_code == 401
