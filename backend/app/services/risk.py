"""
services/risk.py – Runtime risk inference service (spec §8.7).

Loads ml/artifacts/risk_model.joblib (GradientBoostingClassifier pipeline)
and ml/artifacts/risk_model_metrics.json at first call (lazy-load).

build_features():
  - Turns a real project's numbers into the 8 features with EXACTLY the definitions
    used in ml/generate_synthetic.py (most importantly remaining_ratio =
    remaining hours ÷ team hours available until the due date).

predict_risk():
  - Returns delay_probability (0.0–1.0) and the top 3 factors FOR THIS PROJECT:
    each feature is replaced by its typical (median) training value and the
    probability is recomputed; the features whose replacement moves the
    probability most are the ones driving this project's risk.

⚠  The model is trained on SIMULATED data whose "delayed" label comes from a
   Monte Carlo on remaining work vs capacity, so it mostly re-learns remaining_ratio.
   Treat the probability as a learned shortcut of that simulation, not as
   independent evidence.
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

_TRAINING_CSV = _ARTIFACTS.parent / "data" / "synthetic_risk.csv"
FOCUS_FACTOR = 0.70          # same focus factor as generate_synthetic.py / forecast
MAX_REMAINING_RATIO = 10.0   # training data caps outliers at 10

# ── Lazy-loaded model ─────────────────────────────────────────────────────────
_pipeline = None
_feature_importances: Optional[dict] = None
_baseline: Optional[dict] = None     # median of each feature in the training data


def _load():
    global _pipeline, _feature_importances, _baseline
    if _pipeline is None:
        _pipeline = joblib.load(_MODEL_PATH)
    if _feature_importances is None:
        with open(_METRICS_PATH) as f:
            m = json.load(f)
        _feature_importances = m["feature_importances"]
    if _baseline is None:
        data = np.genfromtxt(_TRAINING_CSV, delimiter=",", names=True)
        _baseline = {feat: float(np.median(data[feat])) for feat in FEATURES}


def build_features(
    *,
    team_size: int,
    capacities_per_week: list[float],
    member_utilizations: list[float],
    open_estimate_hours: float,
    overdue_ratio: float,
    blocked_ratio: float,
    slip: float,
    done_ratio: float,
    days_to_due: float,
) -> dict:
    """Project numbers -> model features, using the training definitions."""
    # generate_synthetic.py: remaining_hours = open work × (1 + slip),
    # available hours/day = Σ capacity / 5 × focus, ratio over max(1, days to due)
    available_per_day = sum(capacities_per_week) / 5 * FOCUS_FACTOR
    remaining_hours = open_estimate_hours * (1.0 + slip)
    if remaining_hours <= 0:
        remaining_ratio = 0.0
    elif available_per_day <= 0:
        remaining_ratio = MAX_REMAINING_RATIO
    else:
        remaining_ratio = min(MAX_REMAINING_RATIO, remaining_hours / (available_per_day * max(1.0, days_to_due)))
    return {
        "team_size":       max(1, team_size),
        "avg_utilization": float(np.mean(member_utilizations)) if member_utilizations else 0.0,
        "overdue_ratio":   overdue_ratio,
        "blocked_ratio":   blocked_ratio,
        "slip":            slip,
        "remaining_ratio": remaining_ratio,
        "done_ratio":      done_ratio,
        "days_to_due":     days_to_due,
    }


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

    # Per-project contribution: how much the probability changes if this one feature
    # were "typical" (training median) instead of this project's value.
    # contribution > 0  -> this value pushes the risk UP for this project.
    factors = []
    for i, feat in enumerate(FEATURES):
        x_typical = x.copy()
        x_typical[0, i] = _baseline[feat]
        contribution = prob - float(_pipeline.predict_proba(x_typical)[0, 1])
        factors.append({
            "feature":      feat,
            "importance":   round(_feature_importances.get(feat, 0.0), 4),   # global, from training
            "contribution": round(contribution, 4),                           # this project
            "value":        round(float(x[0, i]), 3),
            "direction":    "increases risk" if contribution > 0 else "reduces risk",
        })

    top_factors = sorted(factors, key=lambda d: -abs(d["contribution"]))[:3]

    return {
        "delay_probability": round(prob, 4),
        "risk_level":        level,
        "top_factors":       top_factors,
        "data_note": (
            "Risk model trained on SIMULATED data (see ml/generate_synthetic.py). "
            "Use as an indicative signal only."
        ),
    }
