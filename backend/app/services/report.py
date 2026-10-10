"""
services/report.py – Project report (M16): sections + rule-based insights and actions.

Everything here is DETERMINISTIC: plain text templates filled from numbers the app already
computes (health, Monte Carlo forecast, workload, ML risk, tasks, dependencies).  No LLM is
called, so the report is reproducible and every sentence can be traced to a number.

The router (routers/report.py) gathers the inputs by calling the existing analytics
endpoints, so the report always shows the same numbers as the Analytics and Team tabs.
"""

from datetime import date, datetime, timezone
from typing import Optional

PENALTY_NAMES = {
    "overdue": "overdue tasks", "blocked": "blocked tasks",
    "overload": "team overload", "slip": "schedule slip",
}


def _band(p: float) -> str:
    return "High" if p >= 0.65 else ("Medium" if p >= 0.35 else "Low")


def _names(members: list[dict]) -> str:
    return ", ".join(f"{m['full_name']} ({round(m['utilization'] * 100)} %)" for m in members)


def build_report(
    *,
    project: dict,            # id, title, description, status, priority, start_date, due_date
    tasks: list[dict],        # id, title, status, estimate_hours, due_date, assignee_id
    dependencies: list[dict], # task_id, depends_on_id
    health: dict,             # GET /analytics/health data (incl. "risk")
    forecast: dict,           # GET /analytics/forecast data
    workload: list[dict],     # GET /analytics/workload data
    decisions: list[dict],    # newest first
    activity: list[dict],     # newest first
    user_names: dict,         # user_id -> full name
    today: Optional[date] = None,
) -> dict:
    today = today or date.today()
    by_id = {t["id"]: t for t in tasks}
    open_tasks = [t for t in tasks if t["status"] != "done"]
    done_ids = {t["id"] for t in tasks if t["status"] == "done"}

    # ── Task statistics ──────────────────────────────────────────────────────
    overdue = sorted(
        [t for t in open_tasks if t.get("due_date") and date.fromisoformat(t["due_date"]) < today],
        key=lambda t: t["due_date"],
    )
    blockers_of: dict[int, list[int]] = {}
    for d in dependencies:
        if d["task_id"] in by_id and by_id[d["task_id"]]["status"] != "done" and d["depends_on_id"] not in done_ids:
            blockers_of.setdefault(d["task_id"], []).append(d["depends_on_id"])
    blocks_count: dict[int, int] = {}
    for blockers in blockers_of.values():
        for b in blockers:
            blocks_count[b] = blocks_count.get(b, 0) + 1
    blocked = sorted(blockers_of, key=lambda tid: (-len(blockers_of[tid]), tid))

    total_hours = sum(t.get("estimate_hours") or 0 for t in tasks)
    remaining_hours = sum(t.get("estimate_hours") or 0 for t in open_tasks)
    unassigned = [t for t in open_tasks if not t.get("assignee_id")]

    def _task_ref(t):
        return {"id": t["id"], "number": t.get("number") or t["id"], "title": t["title"], "status": t["status"],
                "assignee": user_names.get(t.get("assignee_id")) if t.get("assignee_id") else None}

    task_stats = {
        "total": len(tasks),
        "by_status": {s: sum(1 for t in tasks if t["status"] == s) for s in ("todo", "in_progress", "done")},
        "overdue": len(overdue),
        "blocked": len(blockers_of),
        "unassigned_open": len(unassigned),
        "done_ratio": round(len(done_ids) / len(tasks), 4) if tasks else 0.0,
        "total_hours": round(total_hours, 1),
        "remaining_hours": round(remaining_hours, 1),
    }

    # ── Insights and suggested actions (fixed templates) ─────────────────────
    insights: list[str] = []
    actions: list[str] = []
    overloaded = [m for m in workload if m["label"] == "overloaded"]
    at_risk = [m for m in workload if m["label"] == "at_risk"]
    spare = [m for m in workload if m["label"] == "available" and m.get("capacity_hours_per_week", 0) > 0]

    if not tasks:
        insights.append("This project has no tasks yet.")
        actions.append("Add tasks on the Board, or generate a plan on the Plan tab.")
    elif not open_tasks:
        insights.append(f"All {len(tasks)} tasks are done.")
        actions.append("No action needed: the project is complete.")
    else:
        pen = health.get("penalties") or {}
        worst = max(pen, key=pen.get) if pen else None
        line = f"Health is {round(health['health_score'])}/100 ({health['level']})"
        if worst and pen[worst] > 0:
            line += f"; the largest penalty is {PENALTY_NAMES.get(worst, worst)} (−{pen[worst]:.1f} points)"
        insights.append(line + ".")

        dp = forecast.get("delay_probability")
        if project.get("due_date") and dp is not None:
            insights.append(
                f"Monte Carlo forecast: 50 % chance to finish by {forecast['p50']}, 90 % by {forecast['p90']}; "
                f"{round(dp * 100)} % chance to miss the due date ({project['due_date']})."
            )
        else:
            insights.append(f"No due date is set, so the delay probability cannot be computed (P50 {forecast.get('p50')}).")

        if overloaded:
            insights.append(f"{len(overloaded)} member{'s are' if len(overloaded) > 1 else ' is'} overloaded: {_names(overloaded)}.")
            msg = "Rebalance work: open Team > Recommend assignments, move tasks from overloaded members, or raise capacity."
            if spare:
                msg += f" Spare capacity: {', '.join(m['full_name'] for m in spare)}."
            actions.append(msg)
        if at_risk:
            insights.append(f"{len(at_risk)} member{'s are' if len(at_risk) > 1 else ' is'} close to full capacity: {_names(at_risk)}.")

        if blocks_count:
            top_id = max(blocks_count, key=lambda k: (blocks_count[k], -k))
            top = by_id.get(top_id)
            if top:
                n = blocks_count[top_id]
                num = top.get("number") or top_id
                insights.append(f"Task #{num} '{top['title']}' ({top['status'].replace('_', ' ')}) blocks {n} open task{'s' if n > 1 else ''}.")
                actions.append(f"Prioritise task #{num} '{top['title']}': finishing it unblocks {n} task{'s' if n > 1 else ''}.")
        if overdue:
            first = overdue[0]
            late = (today - date.fromisoformat(first["due_date"])).days
            insights.append(f"{len(overdue)} open task{'s are' if len(overdue) > 1 else ' is'} past the due date.")
            actions.append(f"Re-plan the overdue tasks, starting with #{first.get('number') or first['id']} '{first['title']}' ({late} day{'s' if late != 1 else ''} late).")
        if unassigned:
            actions.append(f"{len(unassigned)} open task{'s have' if len(unassigned) > 1 else ' has'} no assignee: use Team > Recommend assignments.")
        if pen.get("slip", 0) > 0:
            diag = health.get("diagnostics") or {}
            behind = round((diag.get("expected_progress", 0) - diag.get("actual_progress", 0)) * 100)
            if behind > 0:
                insights.append(f"Progress is {behind} percentage points behind the calendar.")

        risk = health.get("risk")
        if risk and dp is not None and _band(risk["delay_probability"]) != _band(dp):
            insights.append(
                f"The experimental ML signal ({round(risk['delay_probability'] * 100)} %) and the Monte Carlo "
                f"({round(dp * 100)} %) disagree; rely on the Monte Carlo forecast (the ML model does not see dependency chains)."
            )
        if not actions:
            actions.append("No urgent action: keep the board up to date and review the forecast weekly.")

    risk = health.get("risk")
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "project": project,
        "tasks": task_stats,
        "health": {k: health.get(k) for k in ("health_score", "level", "penalties")},
        "forecast": {
            "p50": forecast.get("p50"), "p80": forecast.get("p80"), "p90": forecast.get("p90"),
            "delay_probability": forecast.get("delay_probability"),
            "due_date": project.get("due_date"), "open_tasks": forecast.get("open_tasks"),
        },
        "workload": [
            {k: m.get(k) for k in ("user_id", "full_name", "utilization", "label",
                                   "open_hours_assigned", "capacity_hours_per_week")}
            for m in workload
        ],
        "risk": None if risk is None else {
            **risk,
            "experimental": True,
            "training_data": "SIMULATED",
            "note": "Experimental, trained on SIMULATED projects. The primary forecast is the "
                    "Monte Carlo simulation; the ML signal is secondary.",
        },
        "overdue_tasks": [
            {**_task_ref(t), "due_date": t["due_date"], "days_overdue": (today - date.fromisoformat(t["due_date"])).days}
            for t in overdue[:5]
        ],
        "blocked_tasks": [
            {**_task_ref(by_id[tid]),
             "blockers": [_task_ref(by_id[b]) for b in blockers_of[tid] if b in by_id]}
            for tid in blocked[:5]
        ],
        "decisions": decisions[:10],
        "activity": activity[:10],
        "insights": insights,
        "suggested_actions": actions,
    }
