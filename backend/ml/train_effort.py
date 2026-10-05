"""
ml/train_effort.py – Effort regressor on NASA93 (spec §8.7).

Source: Albrecht & Gaffney (1983) + NASA ground data.
Dataset: Datasets/nasa93.arff – 93 real software projects with COCOMO metrics
         and actual person-month effort.

COCOMO rating scale: vl < l < n < h < vh < xh  (very-low to extra-high)
  → converted to ordered integers 0..5 for regression.

Model: GradientBoostingRegressor (handles non-linear interactions between
  COCOMO cost drivers; LinearRegression is also tried for comparison).

Outputs:
  ml/artifacts/effort_model.joblib       – trained pipeline
  ml/artifacts/effort_model_metrics.json – 5-fold CV MAE, R², feature importances

Endpoint: GET /ml/effort-benchmark  (served from the main API)
UI label: "benchmark on public NASA93 data (93 projects)"

Usage:
    python -m ml.train_effort
"""

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from scipy.io import arff as scipy_arff
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import KFold, cross_val_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

# ── Paths ─────────────────────────────────────────────────────────────────────
THIS_DIR     = Path(__file__).parent
ARFF_PATH    = THIS_DIR.parent.parent / "Datasets" / "nasa93.arff"
ARTIFACTS    = THIS_DIR / "artifacts"
MODEL_PATH   = ARTIFACTS / "effort_model.joblib"
METRICS_PATH = ARTIFACTS / "effort_model_metrics.json"

# ── COCOMO rating → ordinal ────────────────────────────────────────────────────
COCOMO_SCALE = {b"vl": 0, b"l": 1, b"n": 2, b"h": 3, b"vh": 4, b"xh": 5}

# Rating columns (COCOMO cost drivers)
RATING_COLS = ["rely", "data", "cplx", "time", "stor", "virt", "turn",
               "acap", "aexp", "pcap", "vexp", "lexp", "modp", "tool", "sced"]

TARGET = "act_effort"   # actual person-months


def load_nasa93() -> pd.DataFrame:
    data, meta = scipy_arff.loadarff(str(ARFF_PATH))
    df = pd.DataFrame(data)

    # Convert bytes → ordinal for rating columns
    for col in RATING_COLS:
        if col in df.columns:
            df[col] = df[col].map(lambda v: COCOMO_SCALE.get(v, 2))  # default n=2

    # Keep only numeric columns we need
    keep = RATING_COLS + ["equivphyskloc", TARGET]
    df = df[[c for c in keep if c in df.columns]].dropna()
    df = df.astype(float)
    return df


def train():
    ARTIFACTS.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("IntelliPM Effort Benchmark – NASA93 (spec §8.7)")
    print("Dataset: public NASA93 data (93 real projects)")
    print("=" * 60)

    df = load_nasa93()
    print(f"Loaded {len(df)} projects from {ARFF_PATH}")
    print(f"Target range: [{df[TARGET].min():.1f}, {df[TARGET].max():.1f}] person-months")

    feature_cols = [c for c in df.columns if c != TARGET]
    X = df[feature_cols].values
    y = df[TARGET].values

    # ── GradientBoosting ──────────────────────────────────────────────────
    pipe_gb = Pipeline([
        ("scaler", StandardScaler()),
        ("reg", GradientBoostingRegressor(
            n_estimators=200, max_depth=3, learning_rate=0.05,
            subsample=0.8, random_state=42,
        )),
    ])

    # ── Ridge as a baseline ───────────────────────────────────────────────
    pipe_ridge = Pipeline([
        ("scaler", StandardScaler()),
        ("reg", Ridge(alpha=1.0)),
    ])

    kf = KFold(n_splits=5, shuffle=True, random_state=42)

    for label, pipe in [("GradientBoosting", pipe_gb), ("Ridge (baseline)", pipe_ridge)]:
        mae_scores = -cross_val_score(pipe, X, y,
                                      scoring="neg_mean_absolute_error", cv=kf)
        r2_scores  = cross_val_score(pipe, X, y, scoring="r2", cv=kf)
        print(f"\n{label}:")
        print(f"  CV MAE: {mae_scores.mean():.2f} ± {mae_scores.std():.2f} person-months")
        print(f"  CV R²:  {r2_scores.mean():.4f} ± {r2_scores.std():.4f}")

    # ── Final fit on full data (for deployment) ───────────────────────────
    pipe_gb.fit(X, y)

    # In-sample check (leave-one-out would be ideal but data is small)
    y_pred_is = pipe_gb.predict(X)
    mae_is = mean_absolute_error(y, y_pred_is)
    r2_is  = r2_score(y, y_pred_is)
    print(f"\nFinal GB (in-sample): MAE={mae_is:.2f}  R²={r2_is:.4f}")

    # Feature importances
    importances = pipe_gb.named_steps["reg"].feature_importances_
    feat_imp = dict(zip(feature_cols, [round(float(v), 6) for v in importances]))
    sorted_imp = sorted(feat_imp.items(), key=lambda x: -x[1])

    print("\nFeature importances (top 5):")
    for k, v in sorted_imp[:5]:
        print(f"  {k:<20} {v:.4f}")

    # Cross-validated metrics for final report
    mae_cv = -cross_val_score(pipe_gb, X, y,
                              scoring="neg_mean_absolute_error", cv=kf)
    r2_cv  = cross_val_score(pipe_gb, X, y, scoring="r2", cv=kf)

    # Save model
    joblib.dump(pipe_gb, MODEL_PATH)
    print(f"\nModel saved to: {MODEL_PATH}")

    metrics = {
        "dataset":         "NASA93 (public)",
        "source":          "Datasets/nasa93.arff",
        "n_projects":      int(len(df)),
        "note":            "benchmark on public NASA93 data (93 projects)",
        "model":           "GradientBoostingRegressor(n_estimators=200, max_depth=3, lr=0.05)",
        "cv_folds":        5,
        "cv_mae_mean":     round(float(mae_cv.mean()), 2),
        "cv_mae_std":      round(float(mae_cv.std()), 2),
        "cv_r2_mean":      round(float(r2_cv.mean()), 4),
        "cv_r2_std":       round(float(r2_cv.std()), 4),
        "target":          "act_effort (person-months)",
        "features":        feature_cols,
        "feature_importances": feat_imp,
        "feature_importances_sorted": [
            {"feature": k, "importance": v} for k, v in sorted_imp
        ],
        "cocomo_encoding": "vl=0, l=1, n=2, h=3, vh=4, xh=5",
    }
    with open(METRICS_PATH, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"Metrics saved to: {METRICS_PATH}")

    return metrics


if __name__ == "__main__":
    train()
