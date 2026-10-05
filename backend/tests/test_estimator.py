"""
tests/test_estimator.py – M6 tests (spec §11 M6 done-when).

Done-when: "Metrics file shows MAE vs baseline; endpoint returns a number."

Tests:
  ✓ GET /ai/estimate returns story_points (a positive number) and hours
  ✓ hours = story_points × HOURS_PER_STORY_POINT
  ✓ story_points is in [0.5, 40] (the clipped range)
  ✓ Calling with title only (no description) works
  ✓ Calling with title + description works
  ✓ Unauthenticated request → 401
  ✓ metrics JSON exists and model beats baseline on test MAE
  ✓ metrics JSON exists and model beats baseline on test MdAE
  ✓ joblib artefact file exists
"""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings


# ── Helpers ───────────────────────────────────────────────────────────────────

@pytest.fixture
def client():
    return TestClient(app)


def register_and_token(client, email="m6@test.com", username="m6user"):
    r = client.post("/api/v1/auth/register", json={
        "email": email, "username": username,
        "full_name": "M6 Test", "password": "password123",
    })
    assert r.status_code == 201
    return r.json()["data"]["access_token"]


def auth(token):
    return {"Authorization": f"Bearer {token}"}


_METRICS_PATH = Path(__file__).parent.parent / "ml" / "artifacts" / "estimator_metrics.json"
_JOBLIB_PATH  = Path(__file__).parent.parent / "ml" / "artifacts" / "estimator.joblib"


# ── Artefact tests (no HTTP needed) ──────────────────────────────────────────

class TestModelArtefacts:
    def test_joblib_exists(self):
        """The trained model file must exist (produced by ml/train_estimator.py)."""
        assert _JOBLIB_PATH.exists(), f"Model not found at {_JOBLIB_PATH}. Run: python -m ml.train_estimator"

    def test_metrics_json_exists(self):
        assert _METRICS_PATH.exists(), f"Metrics not found at {_METRICS_PATH}."

    def test_metrics_model_beats_baseline_mae(self):
        """Model test MAE must be lower than the predict-the-median baseline MAE."""
        with open(_METRICS_PATH) as f:
            m = json.load(f)
        model_mae    = m["model_tfidf_ridge"]["test"]["MAE"]
        baseline_mae = m["baseline_predict_median"]["test"]["MAE"]
        assert model_mae < baseline_mae, (
            f"Model MAE ({model_mae}) must beat baseline MAE ({baseline_mae}). "
            "Check the training script (log-transform target)."
        )

    def test_metrics_model_beats_baseline_mdae(self):
        """Model test MdAE must be lower than the predict-the-median baseline MdAE."""
        with open(_METRICS_PATH) as f:
            m = json.load(f)
        model_mdae    = m["model_tfidf_ridge"]["test"]["MdAE"]
        baseline_mdae = m["baseline_predict_median"]["test"]["MdAE"]
        assert model_mdae < baseline_mdae, (
            f"Model MdAE ({model_mdae}) must beat baseline MdAE ({baseline_mdae})."
        )

    def test_metrics_has_required_keys(self):
        with open(_METRICS_PATH) as f:
            m = json.load(f)
        assert "train_size" in m
        assert "test_size" in m
        assert "model_tfidf_ridge" in m
        assert "baseline_predict_median" in m
        assert "improvement_vs_baseline_test" in m


# ── Endpoint tests ────────────────────────────────────────────────────────────

class TestEstimateEndpoint:
    def test_returns_story_points_number(self, client):
        """Spec §11 M6: endpoint must return a number."""
        tok = register_and_token(client)
        r = client.post("/api/v1/ai/estimate",
                        json={"title": "Add user authentication with JWT"},
                        headers=auth(tok))
        assert r.status_code == 200, r.text
        data = r.json()["data"]
        assert "story_points" in data
        assert isinstance(data["story_points"], (int, float))
        assert data["story_points"] > 0

    def test_returns_hours(self, client):
        """hours must equal story_points × HOURS_PER_STORY_POINT."""
        tok = register_and_token(client)
        r = client.post("/api/v1/ai/estimate",
                        json={"title": "Implement database schema migration"},
                        headers=auth(tok))
        data = r.json()["data"]
        expected_hours = round(data["story_points"] * settings.HOURS_PER_STORY_POINT, 2)
        assert abs(data["hours"] - expected_hours) < 0.01

    def test_story_points_clipped_to_range(self, client):
        """story_points must always be in [0.5, 40]."""
        tok = register_and_token(client)
        for title in [
            "Fix typo",
            "Build entire distributed machine-learning platform with real-time inference and auto-scaling infrastructure from scratch including all microservices",
        ]:
            r = client.post("/api/v1/ai/estimate",
                            json={"title": title}, headers=auth(tok))
            sp = r.json()["data"]["story_points"]
            assert 0.5 <= sp <= 40.0, f"Out of range: sp={sp} for title={title!r}"

    def test_title_only_works(self, client):
        """description is optional."""
        tok = register_and_token(client)
        r = client.post("/api/v1/ai/estimate",
                        json={"title": "Write unit tests"},
                        headers=auth(tok))
        assert r.status_code == 200

    def test_title_and_description_works(self, client):
        """Full title + description input."""
        tok = register_and_token(client)
        r = client.post("/api/v1/ai/estimate",
                        json={
                            "title": "Implement OAuth2 login",
                            "description": "Support Google and GitHub providers. Store refresh tokens securely.",
                        },
                        headers=auth(tok))
        assert r.status_code == 200
        assert r.json()["data"]["story_points"] > 0

    def test_unauthenticated_rejected(self, client):
        """Must return 401 when no token provided."""
        r = client.post("/api/v1/ai/estimate",
                        json={"title": "Some task"})
        assert r.status_code == 401

    def test_model_identifier_in_response(self, client):
        """Response should include model name for transparency."""
        tok = register_and_token(client)
        r = client.post("/api/v1/ai/estimate",
                        json={"title": "Create REST API endpoint"},
                        headers=auth(tok))
        assert r.json()["data"]["model"] == "tfidf_ridge_v1"
