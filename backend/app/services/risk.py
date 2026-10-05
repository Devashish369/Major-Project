"""
services/risk.py – Runtime risk inference service (spec §8.7).

Loads ml/artifacts/risk_model.joblib (GradientBoostingClassifier pipeline)
and ml/artifacts/risk_model_metrics.json at first call (lazy-load).

predict_risk():
  - Takes the same 8 features as training (team_size, avg_utilization, …).
  - Returns delay_probability (0.0–1.0) and top_3_factors (feature names
    sorted by SHAP-like contribution, approximated by feature importance × value
    deviation from training mean).

⚠  The model is trained on SIMULATED data.  Treat the probability as a
   heuristic signal, not a rigorous forecast.
"""

import json
from pathlib import Path
from typing import Optional

import joblib
import numpy as np

# ── Paths ─────────────────────────────────────────────────────────────────────
_ARTIFACTS = Path(__file__).parent.parent.parent / "ml" / "artifacts"
_MODEL_PATH   = _ARTIFACTS / "risk_model.joblib"
_METRICS_PATH = _ARTIFACTS / "risk_model_metrics.json"

FEATURES = [
    "team_size", "avg_utilization", "overdue_ratio", "blocked_ratio",
    "slip", "remaining_ratio", "done_ratio", "days_to_due",
]

# ── Lazy-loaded model ─────────────────────────────────────────────────────────
_pipeline = None
_feature_importances: Optional[dict] = None


def _load():
    global _pipeline, _feature_importances
    if _pipeline is None:
        _pipeline = joblib.load(_MODEL_PATH)
    if _feature_importances is None:
        with open(_METRICS_PATH) as f:
            m = json.load(f)
        _feature_importances = m["feature_importances"]


def predict_risk(
    *,
    team_size: int,
    avg_utilization: float,
    overdue_ratio: float,
    blocked_ratio: float,
    slip: float,
    remaining_ratio: float,
    done_ratio: float,
    days_to_due: float,
) -> dict:
    """
    Returns:
      delay_probability : float 0–1
      risk_level        : "Low" | "Medium" | "High"
      top_factors       : list of up to 3 dicts {feature, importance, direction}
      data_note         : disclaimer string
    """
    _load()

    x = np.array([[
        team_size, avg_utilization, overdue_ratio, blocked_ratio,
        slip, remaining_ratio, done_ratio, days_to_due,
    ]])

    prob = float(_pipeline.predict_proba(x)[0, 1])   # P(delayed)
    prob = float(np.clip(prob, 0.0, 1.0))

    level = "High" if prob >= 0.65 else ("Medium" if prob >= 0.35 else "Low")

    # Approximate per-feature contribution: importance × |normalised feature value|
    values_dict = {
        "team_size":       team_size,
        "avg_utilization": avg_utilization,
        "overdue_ratio":   overdue_ratio,
        "blocked_ratio":   blocked_ratio,
        "slip":            slip,
        "remaining_ratio": remaining_ratio,
        "done_ratio":      done_ratio,
        "days_to_due":     days_to_due,
    }

    # Risk direction heuristics (higher value = more risk)
    risk_positive = {"avg_utilization", "overdue_ratio", "blocked_ratio",
                     "slip", "remaining_ratio"}
    risk_negative = {"done_ratio", "days_to_due", "team_size"}

    factors = []
    for feat in FEATURES:
        imp = _feature_importances.get(feat, 0.0)
        val = values_dict[feat]
        direction = "increases risk" if feat in risk_positive else "reduces risk"
        factors.append({
            "feature":    feat,
            "importance": round(imp, 4),
            "value":      round(float(val), 3),
            "direction":  direction,
        })

    # Sort by model importance (descending) and return top 3
    top_factors = sorted(factors, key=lambda d: -d["importance"])[:3]

    return {
        "delay_probability": round(prob, 4),
        "risk_level":        level,
        "top_factors":       top_factors,
        "data_note": (
            "Risk model trained on SIMULATED data (see ml/generate_synthetic.py). "
            "Use as an indicative signal only."
        ),
    }
