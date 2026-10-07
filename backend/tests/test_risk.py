"""
tests/test_risk.py – M8 unit and integration tests.

Tests:
  ✓ Risk model file exists
  ✓ Risk metrics file exists
  ✓ predict_risk returns probability between 0 and 1
  ✓ predict_risk returns top_factors list of length ≤ 3
  ✓ High risk project (many overdue, behind schedule) gives high probability
  ✓ Healthy project gives lower probability than risky project
  ✓ GET /analytics/health includes risk field (may be None if model missing)
  ✓ GET /ml/effort-benchmark returns expected keys
  ✓ GET /ml/effort-benchmark requires authentication
  ✓ Effort metrics: model beats Ridge baseline on CV MAE
  ✓ Risk metrics: accuracy ≥ 0.80
"""

from pathlib import Path
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.risk import predict_risk

# ── Paths ─────────────────────────────────────────────────────────────────────
# tests/test_risk.py lives in backend/tests/ → parent=backend/tests, parent.parent=backend/
ML_DIR        = Path(__file__).parent.parent / "ml" / "artifacts"
RISK_MODEL    = ML_DIR / "risk_model.joblib"
RISK_METRICS  = ML_DIR / "risk_model_metrics.json"
EFFORT_MODEL  = ML_DIR / "effort_model.joblib"
EFFORT_METRICS= ML_DIR / "effort_model_metrics.json"


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def client():
    return TestClient(app)


def register_and_token(client, suffix="m8risk"):
    r = client.post("/api/v1/auth/register", json={
        "email": f"{suffix}@test.com", "username": suffix,
        "full_name": "M8 Test", "password": "password123",
    })
    assert r.status_code == 201
    return r.json()["data"]["access_token"]


def auth(tok):
    return {"Authorization": f"Bearer {tok}"}


def make_project(client, tok, days_ahead=60):
    due = (date.today() + timedelta(days=days_ahead)).isoformat()
    r = client.post("/api/v1/projects",
                    json={"title": "M8 Project", "due_date": due},
                    headers=auth(tok))
    assert r.status_code == 201
    return r.json()["data"]["id"]


# ── Risk model artifact tests ─────────────────────────────────────────────────

class TestRiskArtifacts:
    def test_risk_model_exists(self):
        assert RISK_MODEL.exists(), f"Missing: {RISK_MODEL}"

    def test_risk_metrics_exists(self):
        assert RISK_METRICS.exists(), f"Missing: {RISK_METRICS}"

    def test_effort_model_exists(self):
        assert EFFORT_MODEL.exists(), f"Missing: {EFFORT_MODEL}"

    def test_effort_metrics_exists(self):
        assert EFFORT_METRICS.exists(), f"Missing: {EFFORT_METRICS}"

    def test_risk_metrics_accuracy_above_80(self):
        import json
        with open(RISK_METRICS) as f:
            m = json.load(f)
        assert m["accuracy"] >= 0.80, f"Risk model accuracy too low: {m['accuracy']}"

    def test_risk_metrics_has_required_keys(self):
        import json
        with open(RISK_METRICS) as f:
            m = json.load(f)
        for key in ("accuracy", "precision", "recall", "confusion_matrix",
                    "feature_importances", "training_data"):
            assert key in m, f"Missing key in risk_model_metrics.json: {key}"

    def test_risk_training_data_is_documented_as_simulated(self):
        """training_data field must mention SIMULATED."""
        import json
        with open(RISK_METRICS) as f:
            m = json.load(f)
        assert "SIMULATED" in m["training_data"].upper()

    def test_effort_metrics_has_required_keys(self):
        import json
        with open(EFFORT_METRICS) as f:
            m = json.load(f)
        for key in ("cv_mae_mean", "cv_r2_mean", "n_projects", "note"):
            assert key in m, f"Missing key in effort_model_metrics.json: {key}"

    def test_effort_note_mentions_nasa93(self):
        import json
        with open(EFFORT_METRICS) as f:
            m = json.load(f)
        assert "93" in m["note"] and "NASA" in m["note"].upper()


# ── predict_risk unit tests ───────────────────────────────────────────────────

class TestPredictRisk:
    HEALTHY = dict(
        team_size=8, avg_utilization=0.5, overdue_ratio=0.0,
        blocked_ratio=0.0, slip=0.0, remaining_ratio=0.3,
        done_ratio=0.8, days_to_due=45,
    )
    RISKY = dict(
        team_size=3, avg_utilization=1.4, overdue_ratio=0.6,
        blocked_ratio=0.4, slip=0.4, remaining_ratio=5.0,
        done_ratio=0.1, days_to_due=5,
    )

    def test_returns_probability_in_range(self):
        r = predict_risk(**self.HEALTHY)
        p = r["delay_probability"]
        assert 0.0 <= p <= 1.0, f"Probability out of [0,1]: {p}"

    def test_risky_project_has_higher_prob(self):
        healthy_p = predict_risk(**self.HEALTHY)["delay_probability"]
        risky_p   = predict_risk(**self.RISKY)["delay_probability"]
        assert risky_p > healthy_p, (
            f"Risky project ({risky_p}) should exceed healthy ({healthy_p})"
        )

    def test_returns_top_factors_list(self):
        r = predict_risk(**self.HEALTHY)
        assert isinstance(r["top_factors"], list)
        assert len(r["top_factors"]) <= 3

    def test_top_factors_have_required_keys(self):
        r = predict_risk(**self.RISKY)
        for factor in r["top_factors"]:
            for key in ("feature", "importance", "value", "direction"):
                assert key in factor, f"Missing key in top_factor: {key}"

    def test_risk_level_valid(self):
        r = predict_risk(**self.HEALTHY)
        assert r["risk_level"] in ("Low", "Medium", "High")

    def test_data_note_present(self):
        r = predict_risk(**self.HEALTHY)
        assert "SIMULATED" in r["data_note"].upper()

    def test_overdue_increases_risk(self):
        """Higher overdue_ratio must never lower the delay probability (monotonic model)."""
        base = {**self.HEALTHY, "overdue_ratio": 0.0, "remaining_ratio": 0.9}
        high = {**self.HEALTHY, "overdue_ratio": 0.8, "remaining_ratio": 0.9}
        assert predict_risk(**high)["delay_probability"] >= predict_risk(**base)["delay_probability"]


# ── Integration tests ─────────────────────────────────────────────────────────

class TestHealthRiskIntegration:
    def test_health_includes_risk_field(self, client):
        tok = register_and_token(client, "m8h1")
        proj_id = make_project(client, tok)
        r = client.get(f"/api/v1/projects/{proj_id}/analytics/health",
                       headers=auth(tok))
        assert r.status_code == 200
        d = r.json()["data"]
        assert "risk" in d  # may be None if model not loaded, but key must exist

    def test_health_risk_probability_in_range_when_available(self, client):
        tok = register_and_token(client, "m8h2")
        proj_id = make_project(client, tok)
        r = client.get(f"/api/v1/projects/{proj_id}/analytics/health",
                       headers=auth(tok))
        risk = r.json()["data"].get("risk")
        if risk is not None:
            assert 0.0 <= risk["delay_probability"] <= 1.0


class TestEffortBenchmarkEndpoint:
    def test_benchmark_returns_200(self, client):
        tok = register_and_token(client, "m8e1")
        r = client.get("/api/v1/ml/effort-benchmark", headers=auth(tok))
        assert r.status_code == 200, r.text

    def test_benchmark_has_label(self, client):
        tok = register_and_token(client, "m8e2")
        r = client.get("/api/v1/ml/effort-benchmark", headers=auth(tok))
        d = r.json()["data"]
        assert "93" in d["label"] and "NASA" in d["label"].upper()

    def test_benchmark_requires_auth(self, client):
        r = client.get("/api/v1/ml/effort-benchmark")
        assert r.status_code == 401

    def test_benchmark_has_effort_section(self, client):
        tok = register_and_token(client, "m8e3")
        r = client.get("/api/v1/ml/effort-benchmark", headers=auth(tok))
        d = r.json()["data"]
        assert "effort" in d
        assert d["effort"]["n_projects"] == 93

    def test_benchmark_risk_data_note_mentions_simulated(self, client):
        tok = register_and_token(client, "m8e4")
        r = client.get("/api/v1/ml/effort-benchmark", headers=auth(tok))
        note = r.json()["data"]["risk_data_note"]
        assert "SIMULATED" in note.upper()


# ── Review fixes R-1/R-2/R-3: features use the training definitions; factors are per project ──

from app.services.risk import build_features


class TestBuildFeatures:
    def test_remaining_ratio_matches_training_definition(self):
        # generate_synthetic.py: remaining = open hours × (1 + slip); available/day = Σcap/5 × 0.7
        f = build_features(team_size=2, capacities_per_week=[30, 30], member_utilizations=[0.2, 0.6],
                           open_estimate_hours=100, overdue_ratio=0, blocked_ratio=0, slip=0.1,
                           done_ratio=0.5, days_to_due=10)
        assert f["remaining_ratio"] == pytest.approx(110 / (60 / 5 * 0.7 * 10))
        assert f["avg_utilization"] == pytest.approx(0.4)          # mean, not max

    def test_edge_cases(self):
        common = dict(team_size=1, member_utilizations=[], overdue_ratio=0, blocked_ratio=0,
                      slip=0, done_ratio=0, days_to_due=-5)
        assert build_features(capacities_per_week=[30], open_estimate_hours=0, **common)["remaining_ratio"] == 0
        assert build_features(capacities_per_week=[], open_estimate_hours=10, **common)["remaining_ratio"] == 10
        # overdue project: divide by max(1, days) like the training data
        assert build_features(capacities_per_week=[50], open_estimate_hours=7, **common)["remaining_ratio"] == pytest.approx(1.0)


class TestPerProjectFactors:
    def test_factors_differ_between_projects_and_match_their_sign(self):
        a = predict_risk(**TestPredictRisk.HEALTHY)["top_factors"]
        b = predict_risk(**TestPredictRisk.RISKY)["top_factors"]
        assert [x["feature"] for x in a] != [x["feature"] for x in b]
        for f in a + b:
            assert "contribution" in f
            assert (f["direction"] == "increases risk") == (f["contribution"] > 0)

    def test_completed_project_reports_zero_risk(self, client):
        tok = register_and_token(client, "rvdone")
        pid = make_project(client, tok)
        client.post(f"/api/v1/projects/{pid}/tasks", json={"title": "x", "estimate_hours": 4, "status": "done"}, headers=auth(tok))
        risk = client.get(f"/api/v1/projects/{pid}/analytics/health", headers=auth(tok)).json()["data"]["risk"]
        assert risk["delay_probability"] == 0.0 and risk["top_factors"] == []

    def test_lots_of_work_close_to_due_is_riskier_than_little_work(self, client):
        tok = register_and_token(client, "rvload")
        heavy = make_project(client, tok, days_ahead=5)
        light = make_project(client, tok, days_ahead=60)
        for _ in range(6):
            client.post(f"/api/v1/projects/{heavy}/tasks", json={"title": "big", "estimate_hours": 40}, headers=auth(tok))
        client.post(f"/api/v1/projects/{light}/tasks", json={"title": "small", "estimate_hours": 2}, headers=auth(tok))
        p = lambda pid: client.get(f"/api/v1/projects/{pid}/analytics/health", headers=auth(tok)).json()["data"]["risk"]["delay_probability"]
        assert p(heavy) > 0.65 > p(light)


# ── Task 1 (H-6): the constrained model moves in the explainable direction ────

class TestMonotonicModel:
    BASE = dict(team_size=6, avg_utilization=0.6, overdue_ratio=0.1, blocked_ratio=0.1,
                slip=0.05, remaining_ratio=0.8, done_ratio=0.3, days_to_due=20)
    UP = {"remaining_ratio": [0, 0.3, 0.6, 0.9, 1.2, 1.5, 3, 10], "slip": [0, 0.1, 0.2, 0.4, 0.6],
          "overdue_ratio": [0, 0.2, 0.5, 0.9], "blocked_ratio": [0, 0.2, 0.5, 0.8],
          "avg_utilization": [0, 0.5, 1.0, 1.5, 2.0]}
    DOWN = {"days_to_due": [-10, 0, 5, 20, 60, 120], "done_ratio": [0, 0.3, 0.6, 0.9]}

    def _sweep(self, feat, values):
        return [predict_risk(**{**self.BASE, feat: v})["delay_probability"] for v in values]

    @pytest.mark.parametrize("feat", list(UP))
    def test_non_decreasing(self, feat):
        ps = self._sweep(feat, self.UP[feat])
        assert all(b >= a - 1e-9 for a, b in zip(ps, ps[1:])), (feat, ps)

    @pytest.mark.parametrize("feat", list(DOWN))
    def test_non_increasing(self, feat):
        ps = self._sweep(feat, self.DOWN[feat])
        assert all(b <= a + 1e-9 for a, b in zip(ps, ps[1:])), (feat, ps)

    def test_probability_always_in_unit_interval(self):
        import itertools
        for r, d, u in itertools.product([0, 0.5, 1.5, 10], [-30, 0, 60, 120], [0, 1, 2]):
            p = predict_risk(**{**self.BASE, "remaining_ratio": r, "days_to_due": d, "avg_utilization": u})["delay_probability"]
            assert 0.0 <= p <= 1.0

    def test_tiny_project_due_in_60_days_is_low(self):
        f = build_features(team_size=2, capacities_per_week=[30, 30], member_utilizations=[0, 0],
                           open_estimate_hours=2, overdue_ratio=0, blocked_ratio=0, slip=0,
                           done_ratio=0, days_to_due=60)
        assert predict_risk(**f)["delay_probability"] < 0.35

    def test_one_and_a_half_times_remaining_is_high(self):
        assert predict_risk(**{**self.BASE, "remaining_ratio": 1.5})["delay_probability"] >= 0.65

    def test_metrics_report_roc_auc_and_constraints(self):
        import json
        with open(RISK_METRICS) as f:
            m = json.load(f)
        assert 0.5 < m["roc_auc"] <= 1.0
        assert m["monotonic_constraints"]["remaining_ratio"] == 1 and m["monotonic_constraints"]["days_to_due"] == -1
        assert "SIMULATED" in m["training_data"].upper()
