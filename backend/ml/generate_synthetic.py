"""
ml/generate_synthetic.py – Simulate ≥3,000 project snapshots for risk training (spec §8.7).

[!]  IMPORTANT DISCLAIMER [!]
All data produced by this script is SIMULATED / SYNTHETIC.
It is NOT derived from real project histories.
The Monte Carlo model used to label 'delayed' is an approximation;
the risk classifier trained on this data should be used only as an
indicative signal, never as a rigorous prediction.

Algorithm (viva-ready):
  1. Sample random project parameters (team_size, capacity, utilization,
     overdue_ratio, blocked_ratio, slip, remaining_hours/available_hours).
  2. Run a lightweight Monte Carlo (200 sims) to decide whether the project
     finishes before its due_date.
  3. Add Bernoulli noise (flip_prob=0.08) to simulate real-world label noise.
  4. Write the labelled dataset to ml/data/synthetic_risk.csv.

Features (8 total, all numeric):
  team_size           – number of project members (1–20)
  avg_utilization     – mean member utilization ratio (0–2)
  overdue_ratio       – fraction of open tasks past due (0–1)
  blocked_ratio       – fraction of blocked tasks (0–1)
  slip                – schedule slip (expected – actual progress, 0–1)
  remaining_ratio     – remaining_hours / available_hours (>1 means behind)
  done_ratio          – fraction of tasks completed (0–1)
  days_to_due         – calendar days until due date (−60 to 120)
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

# ── Paths ─────────────────────────────────────────────────────────────────────
THIS_DIR  = Path(__file__).parent
DATA_DIR  = THIS_DIR / "data"
OUT_CSV   = DATA_DIR / "synthetic_risk.csv"

# ── Config ────────────────────────────────────────────────────────────────────
N_SAMPLES    = 4_000    # well above the ≥3,000 spec requirement
N_MC_SIMS    = 200      # lightweight MC per snapshot for labelling
FLIP_PROB    = 0.08     # label-noise probability
MU_DEFAULT   = 0.10
SIGMA_DEFAULT = 0.35
FOCUS        = 0.70
SEED         = 0        # reproducible


def _monte_carlo_delayed(
    rng: np.random.Generator,
    remaining_hours: float,
    available_hours_per_day: float,
    days_to_due: float,
    n_sims: int = N_MC_SIMS,
) -> float:
    """
    Return the fraction of simulations that finish after the due date.
    Each simulation samples log-normal overruns on remaining hours.
    """
    if available_hours_per_day <= 0 or days_to_due <= 0:
        return 1.0  # no capacity or already past due → always delayed

    noise = rng.normal(MU_DEFAULT, SIGMA_DEFAULT, size=n_sims)
    sampled_hours = remaining_hours * np.exp(noise)
    finish_days   = sampled_hours / available_hours_per_day
    return float((finish_days > days_to_due).mean())


def generate(seed: int = SEED, n: int = N_SAMPLES) -> pd.DataFrame:
    """Generate n synthetic project snapshots and return as a DataFrame."""
    rng = np.random.default_rng(seed)
    rows = []

    for _ in range(n):
        # ── 1. Sample project parameters ──────────────────────────────────
        team_size       = int(rng.integers(1, 21))           # 1..20
        avg_cap_week    = float(rng.uniform(10, 40))          # hours/week
        avg_util        = float(rng.uniform(0.1, 1.8))        # utilization
        overdue_ratio   = float(rng.beta(1.5, 4.0))           # skewed low
        blocked_ratio   = float(rng.beta(1.0, 5.0))
        slip            = float(np.clip(rng.normal(0.1, 0.15), 0, 1))
        done_ratio      = float(rng.uniform(0.0, 0.95))
        days_to_due     = float(rng.uniform(-30, 120))        # negative = overdue

        # Estimate remaining work
        total_hours     = rng.uniform(50, 2000)
        remaining_hours = total_hours * (1.0 - done_ratio) * (1.0 + slip)

        # Team effective capacity
        avail_per_day   = (team_size * avg_cap_week / 5) * FOCUS
        remaining_ratio = remaining_hours / (avail_per_day * max(1, days_to_due))

        # ── 2. Monte Carlo label ────────────────────────────────────────────
        delay_prob = _monte_carlo_delayed(
            rng, remaining_hours, avail_per_day, days_to_due
        )
        delayed_mc = int(delay_prob >= 0.5)

        # ── 3. Label noise (flip_prob) ──────────────────────────────────────
        if rng.random() < FLIP_PROB:
            delayed_mc = 1 - delayed_mc

        rows.append({
            "team_size":       team_size,
            "avg_utilization": round(avg_util, 4),
            "overdue_ratio":   round(overdue_ratio, 4),
            "blocked_ratio":   round(blocked_ratio, 4),
            "slip":            round(slip, 4),
            "remaining_ratio": round(min(remaining_ratio, 10.0), 4),  # cap outliers
            "done_ratio":      round(done_ratio, 4),
            "days_to_due":     round(days_to_due, 1),
            "delayed":         delayed_mc,
        })

    df = pd.DataFrame(rows)
    return df


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    print("=" * 60)
    print("IntelliPM Synthetic Risk Dataset – Generator (spec §8.7)")
    print("=" * 60)
    print("[!] All data is SIMULATED - not real project history.")
    print()

    df = generate()

    # Stats
    n_delayed  = df["delayed"].sum()
    n_total    = len(df)
    print(f"Generated {n_total} snapshots.")
    print(f"  Delayed: {n_delayed} ({100*n_delayed/n_total:.1f}%)")
    print(f"  On time: {n_total - n_delayed} ({100*(n_total-n_delayed)/n_total:.1f}%)")
    print()
    print("Feature summary:")
    print(df.describe().T[["mean", "std", "min", "max"]].to_string())
    print()

    df.to_csv(OUT_CSV, index=False)
    print(f"Saved to: {OUT_CSV}")
    return df


if __name__ == "__main__":
    main()
