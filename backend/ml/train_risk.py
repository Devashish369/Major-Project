"""
ml/train_risk.py – Train a risk classifier on synthetic data (spec §8.7).

[!]  SIMULATED TRAINING DATA [!]
The model is trained on data from generate_synthetic.py, which simulates
project snapshots using a Monte Carlo model.  This is NOT trained on
real project histories.  Use the probability as an indicative signal only.

Model: GradientBoostingClassifier (chosen over LogisticRegression because
  it handles non-linear interactions between features like overdue_ratio
  and days_to_due without manual feature engineering, and naturally provides
  feature importances via the impurity-based method).

Outputs:
  ml/artifacts/risk_model.joblib        – trained pipeline
  ml/artifacts/risk_model_metrics.json  – accuracy, precision, recall,
                                          confusion matrix, feature importances

Usage:
    python -m ml.train_risk
"""

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score, classification_report,
    confusion_matrix, precision_score, recall_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

# ── Paths ─────────────────────────────────────────────────────────────────────
THIS_DIR     = Path(__file__).parent
DATA_CSV     = THIS_DIR / "data" / "synthetic_risk.csv"
ARTIFACTS    = THIS_DIR / "artifacts"
MODEL_PATH   = ARTIFACTS / "risk_model.joblib"
METRICS_PATH = ARTIFACTS / "risk_model_metrics.json"

FEATURES = [
    "team_size", "avg_utilization", "overdue_ratio", "blocked_ratio",
    "slip", "remaining_ratio", "done_ratio", "days_to_due",
]
TARGET = "delayed"
TEST_SIZE = 0.20
SEED = 42


def train():
    ARTIFACTS.mkdir(parents=True, exist_ok=True)

    if not DATA_CSV.exists():
        print(f"CSV not found at {DATA_CSV}. Running generate_synthetic.py first…")
        from ml.generate_synthetic import main as gen_main
        gen_main()

    print("=" * 60)
    print("IntelliPM Risk Classifier – Training (spec §8.7)")
    print("[!] Training data is SIMULATED - not real project history.")
    print("=" * 60)

    df = pd.read_csv(DATA_CSV)
    print(f"Loaded {len(df)} rows from {DATA_CSV}")
    print(f"Class balance: {df[TARGET].value_counts().to_dict()}")

    X = df[FEATURES].values
    y = df[TARGET].values

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=TEST_SIZE, random_state=SEED, stratify=y
    )
    print(f"Train: {len(X_train)}, Test: {len(X_test)}")

    # GradientBoosting handles mixed scales natively, but we wrap in a pipeline
    # with StandardScaler for consistency with the inference path.
    pipe = Pipeline([
        ("scaler", StandardScaler()),
        ("clf", GradientBoostingClassifier(
            n_estimators=200,
            max_depth=4,
            learning_rate=0.05,
            subsample=0.8,
            random_state=SEED,
        )),
    ])

    pipe.fit(X_train, y_train)
    y_pred = pipe.predict(X_test)

    acc  = accuracy_score(y_test, y_pred)
    prec = precision_score(y_test, y_pred, zero_division=0)
    rec  = recall_score(y_test, y_pred, zero_division=0)
    cm   = confusion_matrix(y_test, y_pred).tolist()

    print(f"\nAccuracy:  {acc:.4f}")
    print(f"Precision: {prec:.4f}   Recall: {rec:.4f}")
    print("\nConfusion matrix (rows=actual, cols=predicted):")
    print(f"  [[TN={cm[0][0]}  FP={cm[0][1]}]")
    print(f"   [FN={cm[1][0]}  TP={cm[1][1]}]]")

    # Feature importances (from the GBM estimator, post-scaling irrelevant)
    importances = pipe.named_steps["clf"].feature_importances_
    feat_imp = dict(zip(FEATURES, [round(float(v), 6) for v in importances]))
    sorted_imp = sorted(feat_imp.items(), key=lambda x: -x[1])

    print("\nFeature importances (descending):")
    for name, val in sorted_imp:
        print(f"  {name:<22} {val:.4f}")

    # Save model
    joblib.dump(pipe, MODEL_PATH)
    print(f"\nModel saved to: {MODEL_PATH}")

    metrics = {
        "model": "GradientBoostingClassifier(n_estimators=200, max_depth=4, lr=0.05)",
        "training_data": "SIMULATED (generate_synthetic.py) – NOT real project history",
        "n_train": int(len(X_train)),
        "n_test":  int(len(X_test)),
        "accuracy":  round(acc, 4),
        "precision": round(prec, 4),
        "recall":    round(rec, 4),
        "confusion_matrix": cm,
        "feature_importances": feat_imp,
        "feature_importances_sorted": [
            {"feature": k, "importance": v} for k, v in sorted_imp
        ],
        "features": FEATURES,
    }
    with open(METRICS_PATH, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"Metrics saved to: {METRICS_PATH}")

    return metrics


if __name__ == "__main__":
    train()
