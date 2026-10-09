"""
services/forecast.py – Monte Carlo completion-date forecast (spec §8.4).

Algorithm (viva-ready):
  1. Collect all open tasks (status != "done") with their estimate_hours.
  2. Collect dependency graph (open tasks only).
  3. Compute team capacity: effective_hours_per_day = sum(cap_per_week)/5 × 0.7
     The 0.7 "focus factor" accounts for meetings, interruptions, context switching.
  4. If ≥10 completed tasks have actual_hours, calibrate mu/sigma from the log-ratios
     of actual vs. estimated (empirical overrun distribution).
  5. Run N_SIMS Monte Carlo simulations (default 5,000, seeded for reproducibility):
     a. Sample actual_i = estimate_i × exp(Normal(mu, sigma)) for each open task.
     b. parallel_days = total_sampled_hours / effective_hours_per_day
     c. critical_path_days = longest_chain_sampled_hours / one_person_hours_per_day
        where longest chain is over the DAG of open task dependencies.
     d. duration_days = max(parallel_days, critical_path_days)
  6. Aggregate P50/P80/P90 of finish_date = today + duration_days.
  7. delay_probability = fraction of simulations finishing after project.due_date.
  8. Return histogram buckets (30 equal-width bins over the simulation range).

Edge cases handled:
  - No open tasks → return assumptions with finish = today.
  - No members (capacity=0) → use 8h/day as a safe default.
  - No due_date → delay_probability = None.
"""

import math
from collections import defaultdict
from datetime import date, timedelta
from typing import Optional

import numpy as np

# ── Constants ─────────────────────────────────────────────────────────────────

N_SIMS     = 5_000     # number of Monte Carlo runs
SEED       = 42        # fixed seed for reproducible unit tests
MU_DEFAULT = 0.10      # log-normal location: slight systematic overrun
SIGMA_DEFAULT = 0.35   # log-normal scale:  realistic uncertainty
FOCUS_FACTOR  = 0.70   # fraction of capacity that is productive work
FALLBACK_CAPACITY_PER_WEEK = 40  # h/week used when no members are present
MIN_COMPLETED_FOR_CALIBRATION = 10  # need at least this many completed tasks


# ── Data classes (plain dicts passed in from the router) ──────────────────────

def _critical_path_hours(
    open_task_ids: set[int],
    sampled: dict[int, float],   # task_id → sampled hours
    dep_graph: dict[int, list[int]],  # task_id → list of tasks it depends on
) -> float:
    """
    Compute the longest sum of sampled hours along any chain in the DAG of
    open tasks using memoised DFS.  'dep_graph[t]' = tasks that t depends on
    (predecessors of t).  Chain length = t's hours + max chain of its deps.
    """
    memo: dict[int, float] = {}

    def dfs(t: int) -> float:
        if t in memo:
            return memo[t]
        preds = [p for p in dep_graph.get(t, []) if p in open_task_ids]
        val = sampled[t] + (max((dfs(p) for p in preds), default=0.0) if preds else 0.0)
        memo[t] = val
        return val

    return max((dfs(t) for t in open_task_ids), default=0.0)


def _simulate_durations(rng, est_array, task_ids, dep_graph, mu, sigma, n_sims, effective_per_day, one_person_per_day):
    """
    Project duration in days for every simulation, computed for ALL simulations at once.

    Same model as spec §8.4 (and the same random numbers, in the same order, as the earlier
    one-simulation-at-a-time loop, so results are unchanged), but numpy works on a
    (n_sims x n_tasks) table instead of 5,000 Python iterations:
      actual hours  = estimate x exp(Normal(mu, sigma))                    (every task, every run)
      parallel days = sum of a run's hours / team hours per day
      chain hours   = for each task in dependency order:  own hours + the largest chain among its
                      open prerequisites;  the longest chain = max over tasks
      duration      = max(parallel days, chain hours / one person's hours per day)
    A dependency cycle (rejected by the API, but never trust data) cannot hang this: tasks that
    are part of a cycle simply do not add their prerequisites' chains.
    """
    n_tasks = len(task_ids)
    actual = est_array * np.exp(rng.normal(mu, sigma, size=(n_sims, n_tasks)))
    parallel_days = actual.sum(axis=1) / effective_per_day

    index = {tid: i for i, tid in enumerate(task_ids)}
    preds = {i: [index[p] for p in dep_graph.get(tid, []) if p in index] for tid, i in index.items()}
    # Kahn topological order: a task is processed after all of its prerequisites
    remaining = {i: len(set(ps)) for i, ps in preds.items()}
    children: dict[int, list[int]] = {i: [] for i in preds}
    for i, ps in preds.items():
        for p in set(ps):
            children[p].append(i)
    order = [i for i, n in remaining.items() if n == 0]
    for i in order:                       # `order` grows while we walk it
        for c in children[i]:
            remaining[c] -= 1
            if remaining[c] == 0:
                order.append(c)

    chain = np.zeros_like(actual)
    for i in order:
        ps = sorted(set(preds[i]))
        chain[:, i] = actual[:, i] + (chain[:, ps].max(axis=1) if ps else 0.0)
    cp_days = chain.max(axis=1) / one_person_per_day if n_tasks else np.zeros(n_sims)
    return np.maximum(parallel_days, cp_days)


def run_forecast(
    *,
    open_tasks: list[dict],       # [{"id": int, "estimate_hours": float}]
    completed_tasks: list[dict],  # [{"estimate_hours": float, "actual_hours": float}]
    dependencies: list[dict],     # [{"task_id": int, "depends_on_id": int}]
    capacity_per_week: list[int], # one entry per member (hours/week)
    due_date: Optional[str],      # ISO "YYYY-MM-DD" or None
    today: Optional[date] = None,
    n_sims: int = N_SIMS,
    seed: int = SEED,
) -> dict:
    """
    Run the Monte Carlo forecast and return the full result dict.
    """
    today = today or date.today()

    # ── 1. Filter tasks with usable estimates ─────────────────────────────────
    usable = [t for t in open_tasks if (t.get("estimate_hours") or 0) > 0]
    open_ids = {t["id"] for t in usable}
    default_estimate = 4.0  # h – for tasks with no estimate

    # Build estimate dict (include tasks with no estimate using default)
    estimates: dict[int, float] = {}
    for t in open_tasks:
        est = t.get("estimate_hours") or default_estimate
        estimates[t["id"]] = float(est)
    open_ids_all = {t["id"] for t in open_tasks}

    # ── 2. Dependency graph (open tasks only) ─────────────────────────────────
    dep_graph: dict[int, list[int]] = defaultdict(list)
    for d in dependencies:
        tid, pred = d["task_id"], d["depends_on_id"]
        if tid in open_ids_all and pred in open_ids_all:
            dep_graph[tid].append(pred)

    # ── 3. Team capacity ──────────────────────────────────────────────────────
    if capacity_per_week:
        total_cap = sum(capacity_per_week)
        avg_cap   = total_cap / len(capacity_per_week)
    else:
        total_cap = FALLBACK_CAPACITY_PER_WEEK
        avg_cap   = FALLBACK_CAPACITY_PER_WEEK

    effective_per_day    = (total_cap / 5) * FOCUS_FACTOR   # team parallel
    one_person_per_day   = (avg_cap / 5) * FOCUS_FACTOR     # single-person critical path
    if effective_per_day <= 0:
        effective_per_day = (FALLBACK_CAPACITY_PER_WEEK / 5) * FOCUS_FACTOR
    if one_person_per_day <= 0:
        one_person_per_day = (FALLBACK_CAPACITY_PER_WEEK / 5) * FOCUS_FACTOR

    # ── 4. Edge case: no open tasks ───────────────────────────────────────────
    if not open_ids_all:
        result = {
            "p50": today.isoformat(),
            "p80": today.isoformat(),
            "p90": today.isoformat(),
            "delay_probability": 0.0 if due_date else None,
            "histogram": [],
            "open_tasks": 0,
            "assumptions": {
                "n_sims": n_sims,
                "mu": MU_DEFAULT,
                "sigma": SIGMA_DEFAULT,
                "focus_factor": FOCUS_FACTOR,
                "effective_hours_per_day": round(effective_per_day, 2),
                "calibrated": False,
                "note": "No open tasks – project is complete or has no tasks.",
            },
        }
        return result

    # ── 5. Calibrate mu/sigma from completed tasks ────────────────────────────
    calibrated = False
    mu, sigma = MU_DEFAULT, SIGMA_DEFAULT

    calibration_pairs = [
        t for t in completed_tasks
        if (t.get("estimate_hours") or 0) > 0 and (t.get("actual_hours") or 0) > 0
    ]
    if len(calibration_pairs) >= MIN_COMPLETED_FOR_CALIBRATION:
        log_ratios = [
            math.log(t["actual_hours"] / t["estimate_hours"])
            for t in calibration_pairs
        ]
        mu    = float(np.mean(log_ratios))
        sigma = float(np.std(log_ratios))
        if sigma <= 0:
            sigma = SIGMA_DEFAULT
        calibrated = True

    # ── 6. Monte Carlo ────────────────────────────────────────────────────────
    rng = np.random.default_rng(seed)
    task_id_list = list(open_ids_all)
    n_tasks = len(task_id_list)
    est_array = np.array([estimates[tid] for tid in task_id_list])

    durations_arr = _simulate_durations(
        rng, est_array, task_id_list, dep_graph, mu, sigma, n_sims, effective_per_day, one_person_per_day
    )

    # ── 7. Percentiles → dates ────────────────────────────────────────────────
    p50_days = float(np.percentile(durations_arr, 50))
    p80_days = float(np.percentile(durations_arr, 80))
    p90_days = float(np.percentile(durations_arr, 90))

    # Round UP to whole days: work that needs 10.3 days is finished on day 11.  This keeps
    # the dates consistent with delay_probability below (late  <=>  duration > days to due),
    # e.g. "P90 on or before the due date" now always means "at most 10 % chance of being late".
    p50_date = (today + timedelta(days=math.ceil(p50_days))).isoformat()
    p80_date = (today + timedelta(days=math.ceil(p80_days))).isoformat()
    p90_date = (today + timedelta(days=math.ceil(p90_days))).isoformat()

    # ── 8. Delay probability ──────────────────────────────────────────────────
    delay_prob: Optional[float] = None
    if due_date:
        try:
            due = date.fromisoformat(due_date)
            days_to_due = (due - today).days
            delay_prob = float((durations_arr > days_to_due).mean())
        except (ValueError, TypeError):
            delay_prob = None

    # ── 9. Histogram (30 buckets) ─────────────────────────────────────────────
    n_bins = 30
    d_min, d_max = float(durations_arr.min()), float(durations_arr.max())
    if d_max - d_min < 1e-6:
        # Degenerate: all simulations gave the same duration (e.g. sigma=0)
        # Collapse to a single bucket so np.histogram doesn't crash.
        histogram = [{
            "start_days": round(d_min, 1),
            "end_days":   round(d_min + 1e-3, 1),
            "start_date": (today + timedelta(days=d_min)).isoformat(),
            "end_date":   (today + timedelta(days=d_min)).isoformat(),
            "count":      n_sims,
        }]
    else:
        counts, edges = np.histogram(durations_arr, bins=n_bins)
        histogram = [
            {
                "start_days": round(float(edges[i]), 1),
                "end_days":   round(float(edges[i + 1]), 1),
                "start_date": (today + timedelta(days=float(edges[i]))).isoformat(),
                "end_date":   (today + timedelta(days=float(edges[i + 1]))).isoformat(),
                "count":      int(counts[i]),
            }
            for i in range(n_bins)
        ]

    return {
        "p50": p50_date,
        "p80": p80_date,
        "p90": p90_date,
        "delay_probability": round(delay_prob, 4) if delay_prob is not None else None,
        "histogram": histogram,
        "open_tasks": len(open_ids_all),
        "assumptions": {
            "n_sims": n_sims,
            "mu": round(mu, 4),
            "sigma": round(sigma, 4),
            "focus_factor": FOCUS_FACTOR,
            "effective_hours_per_day": round(effective_per_day, 2),
            "one_person_hours_per_day": round(one_person_per_day, 2),
            "calibrated": calibrated,
            "calibration_tasks": len(calibration_pairs) if calibrated else 0,
            "note": (
                f"Calibrated from {len(calibration_pairs)} completed tasks."
                if calibrated else
                "Using default lognormal(mu=0.10, sigma=0.35) – no calibration data."
            ),
        },
    }
