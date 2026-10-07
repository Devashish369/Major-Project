"""
ml/generate_synthetic.py – Simulate project snapshots for risk training (spec §8.7).

[!]  IMPORTANT DISCLAIMER [!]
All data produced by this script is SIMULATED / SYNTHETIC.  It is NOT derived from
real project histories.  The classifier trained on it is an EXPERIMENTAL, secondary
signal; the primary forecast in the app is the Monte Carlo simulation.

How a snapshot is made (viva-ready):
  1. Sample the 8 features over their FULL range, including exact zeros
     (e.g. "nothing assigned yet" = utilisation 0, "nothing done yet" = done ratio 0).
  2. Simulate how long the remaining work takes, 300 times, with a Monte Carlo in
     which EVERY feature has a documented effect (assumptions below).
  3. Label the snapshot "delayed" if more than half of the runs finish after the due
     date, then flip 6 % of labels at random (label noise).

Modelling assumptions (each one is a simplification, chosen to be defensible):
  A1 remaining work      remaining_hours = total_hours × (1 − done_ratio)
  A2 team throughput     hours/day = team_size × capacity/week ÷ 5 × 0.7 (same 0.7 focus
                         factor as services/forecast.py)
  A3 overload            if avg_utilization > 1, people are over-committed and lose time
                         to context switching: throughput ÷ (1 + 0.5 × (utilisation − 1)).
                         Below 1 utilisation has no effect (spare capacity does not speed
                         up work that is already planned).
  A4 blocked work        blocked tasks make people wait: duration × (1 + 0.6 × blocked_ratio)
  A5 overrun             each run multiplies the remaining hours by lognormal(mu, 0.35) with
                         mu = 0.10 + 0.40 × overdue_ratio + 0.50 × slip: a project that is
                         already overdue or behind schedule tends to keep overrunning.
  A6 deadline            delayed if duration > max(0, days_to_due); work left on a project
                         whose due date has passed is late by definition.
  More days_to_due and a higher done_ratio therefore lower the risk; more overload, blocking,
  overdue work and slip raise it.  team_size only matters through throughput (A2), which is
  already inside remaining_ratio.

Feature definitions (must match services/risk.py:build_features exactly):
  team_size        number of project members (1–20)
  avg_utilization  mean member utilisation (0–2)
  overdue_ratio    open tasks past due ÷ open tasks (0–1)
  blocked_ratio    open tasks with an unfinished dependency ÷ open tasks (0–1)
  slip             expected progress − actual progress (0–0.6)
  remaining_ratio  remaining_hours × (1 + slip) ÷ (hours/day × max(1, days_to_due)), capped at 10
  done_ratio       done hours ÷ total hours (0–0.98)
  days_to_due      days until the due date (−30 to 120)
"""

from pathlib import Path

import numpy as np
import pandas as pd

# ── Paths ─────────────────────────────────────────────────────────────────────
THIS_DIR = Path(__file__).parent
DATA_DIR = THIS_DIR / "data"
OUT_CSV  = DATA_DIR / "synthetic_risk.csv"

# ── Config ────────────────────────────────────────────────────────────────────
N_SAMPLES     = 6_000    # spec asks for ≥ 3,000
N_MC_SIMS     = 300      # Monte Carlo runs per snapshot (label only)
FLIP_PROB     = 0.06     # label noise
SIGMA         = 0.35     # same spread as services/forecast.py
MU_BASE       = 0.10     # same default overrun as services/forecast.py
MU_PER_OVERDUE = 0.40    # A5
MU_PER_SLIP   = 0.50     # A5
OVERLOAD_LOSS = 0.50     # A3
BLOCKED_IDLE  = 0.60     # A4
FOCUS         = 0.70     # A2
MAX_REMAINING_RATIO = 10.0
SEED          = 0


def _zero_or(rng, p_zero, draw):
    """With probability p_zero return exactly 0, otherwise draw()."""
    return 0.0 if rng.random() < p_zero else float(draw())


def _delay_probability(rng, remaining_hours, per_day, util, blocked, overdue, slip, days_to_due):
    """Share of Monte Carlo runs that finish after the due date (assumptions A3–A6)."""
    if remaining_hours <= 0:
        return 0.0
    throughput = per_day / (1.0 + OVERLOAD_LOSS * max(0.0, util - 1.0))
    mu = MU_BASE + MU_PER_OVERDUE * overdue + MU_PER_SLIP * slip
    sampled = remaining_hours * np.exp(rng.normal(mu, SIGMA, size=N_MC_SIMS))
    duration = sampled / throughput * (1.0 + BLOCKED_IDLE * blocked)
    return float((duration > max(0.0, days_to_due)).mean())


def generate(seed: int = SEED, n: int = N_SAMPLES) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for _ in range(n):
        team_size   = int(rng.integers(1, 21))
        cap_week    = float(rng.uniform(10, 40))
        util        = _zero_or(rng, 0.10, lambda: rng.uniform(0.0, 2.0))
        overdue     = _zero_or(rng, 0.35, lambda: rng.beta(1.5, 4.0))
        blocked     = _zero_or(rng, 0.35, lambda: rng.beta(1.0, 4.0))
        slip        = _zero_or(rng, 0.35, lambda: rng.uniform(0.0, 0.6))
        done_ratio  = _zero_or(rng, 0.10, lambda: rng.uniform(0.0, 0.98))
        days_to_due = float(rng.uniform(-30, 120))
        total_hours = float(np.exp(rng.uniform(np.log(2), np.log(3000))))   # tiny to large projects

        remaining_hours = total_hours * (1.0 - done_ratio)                    # A1
        per_day = team_size * cap_week / 5 * FOCUS                            # A2
        remaining_ratio = min(
            MAX_REMAINING_RATIO,
            remaining_hours * (1.0 + slip) / (per_day * max(1.0, days_to_due)),
        )

        p = _delay_probability(rng, remaining_hours, per_day, util, blocked, overdue, slip, days_to_due)
        delayed = int(p > 0.5)
        if rng.random() < FLIP_PROB:
            delayed = 1 - delayed

        rows.append({
            "team_size":       team_size,
            "avg_utilization": round(util, 4),
            "overdue_ratio":   round(overdue, 4),
            "blocked_ratio":   round(blocked, 4),
            "slip":            round(slip, 4),
            "remaining_ratio": round(remaining_ratio, 4),
            "done_ratio":      round(done_ratio, 4),
            "days_to_due":     round(days_to_due, 1),
            "delayed":         delayed,
        })
    return pd.DataFrame(rows)


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    print("=" * 60)
    print("IntelliPM Synthetic Risk Dataset – Generator (spec §8.7)")
    print("=" * 60)
    print("[!] All data is SIMULATED - not real project history.\n")
    df = generate()
    n_delayed = int(df["delayed"].sum())
    print(f"Generated {len(df)} snapshots: delayed {n_delayed} ({100 * n_delayed / len(df):.1f}%)")
    print(df.describe().T[["mean", "std", "min", "max"]].to_string())
    df.to_csv(OUT_CSV, index=False)
    print(f"Saved to: {OUT_CSV}")
    return df


if __name__ == "__main__":
    main()
