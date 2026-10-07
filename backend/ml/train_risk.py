"""
ml/train_risk.py – Train the EXPERIMENTAL delay-risk classifier on simulated data (spec §8.7).

[!]  SIMULATED TRAINING DATA [!]
Trained on ml/data/synthetic_risk.csv from generate_synthetic.py, NOT on real project
history.  In the app the primary forecast is the Monte Carlo simulation; this ML signal
is secondary.

Model: HistGradientBoostingClassifier with MONOTONIC CONSTRAINTS, so the risk can only go
up when remaining_ratio, slip, overdue_ratio, blocked_ratio or avg_utilization go up, and
can only go down when days_to_due or done_ratio go up (team_size is unconstrained).  The
earlier unconstrained model gave erratic answers (utilisation 0.1 -> 86 % but 0.5 -> 32 %);
the constraints make every prediction move in the explainable direction.

Reported on a held-out 20 % test split: accuracy, precision, recall, ROC-AUC, confusion
matrix and permutation importances (drop in test ROC-AUC when one feature is shuffled).

Usage:
    python -m ml.generate_synthetic
    python -m ml.train_risk
"""

import json
from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.inspection import permutation_importance
from sklearn.metrics import (
    accuracy_score, confusion_matrix, precision_score, recall_score, roc_auc_score,
)
from sklearn.model_selection import train_test_split

# ── Paths ─────────────────────────────────────────────────────────────────────
THIS_DIR     = Path(__file__).parent
DATA_CSV     = THIS_DIR / "data" / "synthetic_risk.csv"
ARTIFACTS    = THIS_DIR / "artifacts"
MODEL_PATH   = ARTIFACTS / "risk_model.joblib"
METRICS_PATH = ARTIFACTS / "risk_model_metrics.json"

# Same order as services/risk.py FEATURES (prediction uses this exact order).
FEATURES = [
    "team_size", "avg_utilization", "overdue_ratio", "blocked_ratio",
    "slip", "remaining_ratio", "done_ratio", "days_to_due",
]
# +1 = risk non-decreasing in the feature, -1 = non-increasing, 0 = unconstrained
MONOTONIC = {
    "team_size": 0, "avg_utilization": 1, "overdue_ratio": 1, "blocked_ratio": 1,
    "slip": 1, "remaining_ratio": 1, "done_ratio": -1, "days_to_due": -1,
}
TARGET = "delayed"
TEST_SIZE = 0.20
SEED = 42


def train():
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    if not DATA_CSV.exists():
        from ml.generate_synthetic import main as gen_main
        gen_main()

    print("IntelliPM Risk Classifier – Training (spec 8.7)")
    print("[!] Training data is SIMULATED - not real project history.")
    df = pd.read_csv(DATA_CSV)
    print(f"Loaded {len(df)} rows; class balance {df[TARGET].value_counts().to_dict()}")

    X = df[FEATURES].values
    y = df[TARGET].values
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=TEST_SIZE, random_state=SEED, stratify=y
    )

    model = HistGradientBoostingClassifier(
        max_iter=300,
        learning_rate=0.05,
        max_leaf_nodes=15,
        l2_regularization=1.0,
        monotonic_cst=[MONOTONIC[f] for f in FEATURES],
        random_state=SEED,
    )
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1]

    acc  = accuracy_score(y_test, y_pred)
    prec = precision_score(y_test, y_pred, zero_division=0)
    rec  = recall_score(y_test, y_pred, zero_division=0)
    auc  = roc_auc_score(y_test, y_prob)
    cm   = confusion_matrix(y_test, y_pred).tolist()

    # Permutation importance: drop in test ROC-AUC when one feature is shuffled.
    perm = permutation_importance(model, X_test, y_test, scoring="roc_auc",
                                  n_repeats=10, random_state=SEED)
    raw = {f: max(0.0, float(v)) for f, v in zip(FEATURES, perm.importances_mean)}
    total = sum(raw.values()) or 1.0
    feat_imp = {f: round(v / total, 6) for f, v in raw.items()}      # shares that sum to 1
    sorted_imp = sorted(feat_imp.items(), key=lambda kv: -kv[1])

    print(f"Accuracy {acc:.4f}  Precision {prec:.4f}  Recall {rec:.4f}  ROC-AUC {auc:.4f}")
    print(f"Confusion matrix [[TN FP] [FN TP]] = {cm}")
    for name, val in sorted_imp:
        print(f"  {name:<18} {val:.4f}")

    joblib.dump(model, MODEL_PATH)
    metrics = {
        "model": "HistGradientBoostingClassifier(max_iter=300, lr=0.05, max_leaf_nodes=15, monotonic constraints)",
        "training_data": "SIMULATED (generate_synthetic.py) – NOT real project history",
        "status": "experimental – the primary forecast is the Monte Carlo simulation; the ML signal is secondary",
        "label_noise": 0.06,
        "monotonic_constraints": MONOTONIC,
        "n_train": int(len(X_train)),
        "n_test":  int(len(X_test)),
        "accuracy":  round(acc, 4),
        "precision": round(prec, 4),
        "recall":    round(rec, 4),
        "roc_auc":   round(auc, 4),
        "confusion_matrix": cm,
        "importance_method": "permutation importance (drop in test ROC-AUC), normalised to sum to 1",
        "feature_importances": feat_imp,
        "feature_importances_sorted": [{"feature": k, "importance": v} for k, v in sorted_imp],
        "features": FEATURES,
    }
    with open(METRICS_PATH, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"Saved {MODEL_PATH.name} and {METRICS_PATH.name}")
    return metrics


if __name__ == "__main__":
    train()
