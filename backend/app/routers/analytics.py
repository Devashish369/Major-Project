"""
routers/analytics.py – Forecast and health score endpoints (spec §8.4/8.5).

Endpoints:
  GET /projects/{project_id}/analytics/forecast
  GET /projects/{project_id}/analytics/health

Design decisions (viva-ready):
  - Both endpoints are GET (read-only; no DB writes).
  - All heavy computation is in the service layer; the router only queries
    the DB and formats the response.
  - Workload is computed inline (reusing services/workload.compute_workload)
    to get member utilizations for the health score.
  - health_score is computed on-the-fly; it is NOT stored in the DB because
    it changes continuously as tasks move.  The project-list endpoint returns
    it via a separate quick call.
"""

import logging
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database import get_db
from app.deps import get_current_user, get_membership
from app.models import Project, ProjectMember, Task, TaskDependency, User
from app.services.forecast import run_forecast
from app.services.health import compute_health
from app.main import ok
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

router = APIRouter(tags=["analytics"])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _weeks_remaining(due_date_str) -> float:
    if not due_date_str:
        return 4.0
    try:
        due = date.fromisoformat(due_date_str)
        delta = (due - date.today()).days
        return max(1, delta) / 7
    except (ValueError, TypeError):
        return 4.0


def _task_to_dict(t: Task) -> dict:
    return {
        "id": t.id,
        "status": t.status,
        "estimate_hours": t.estimate_hours,
        "actual_hours": t.actual_hours,
        "due_date": t.due_date,
        "assignee_id": t.assignee_id,
        "required_skills": t.required_skills or [],
    }


# ── GET /projects/{project_id}/analytics/forecast ────────────────────────────

@router.get("/projects/{project_id}/analytics/forecast")
def get_forecast(
    project_id: int,
    current_user=Depends(get_current_user),
    membership=Depends(get_membership),
    db: Session = Depends(get_db),
):
    """
    Run a 5,000-run Monte Carlo forecast for the project.

    Returns P50/P80/P90 completion dates, delay_probability (fraction of
    simulations finishing after project.due_date), a histogram, and the
    assumptions used (including whether mu/sigma were calibrated from data).
    """
    project: Project = db.get(Project, project_id)

    # Fetch tasks
    tasks = db.execute(
        select(Task).where(Task.project_id == project_id)
    ).scalars().all()

    open_tasks = [_task_to_dict(t) for t in tasks if t.status != "done"]
    completed  = [
        {"estimate_hours": t.estimate_hours, "actual_hours": t.actual_hours}
        for t in tasks
        if t.status == "done" and t.estimate_hours and t.actual_hours
    ]

    # Fetch dependencies (open task pairs only)
    deps = db.execute(
        select(TaskDependency).where(TaskDependency.task_id.in_(
            [t["id"] for t in open_tasks]
        ))
    ).scalars().all()
    dep_dicts = [{"task_id": d.task_id, "depends_on_id": d.depends_on_id} for d in deps]

    # Fetch member capacities
    members = db.execute(
        select(ProjectMember).where(ProjectMember.project_id == project_id)
    ).scalars().all()
    capacity = [m.capacity_hours_per_week for m in members]

    result = run_forecast(
        open_tasks=open_tasks,
        completed_tasks=completed,
        dependencies=dep_dicts,
        capacity_per_week=capacity,
        due_date=project.due_date,
    )

    return ok(data=result, message="Monte Carlo forecast complete.")


# ── GET /projects/{project_id}/analytics/health ──────────────────────────────

@router.get("/projects/{project_id}/analytics/health")
def get_health(
    project_id: int,
    current_user=Depends(get_current_user),
    membership=Depends(get_membership),
    db: Session = Depends(get_db),
):
    """
    Compute and return the project health score.

    Returns the score (0–100), the risk level, the four penalty values
    (overdue, blocked, overload, slip), and diagnostics so the UI can
    explain *why* the score is what it is.
    """
    project: Project = db.get(Project, project_id)

    # Fetch tasks
    tasks = db.execute(
        select(Task).where(Task.project_id == project_id)
    ).scalars().all()
    task_dicts = [_task_to_dict(t) for t in tasks]

    # Add task IDs to dict (needed for blocked ratio computation)
    for t, td in zip(tasks, task_dicts):
        td["id"] = t.id

    # Fetch dependencies
    deps = db.execute(
        select(TaskDependency).where(TaskDependency.task_id.in_(
            [t.id for t in tasks]
        ))
    ).scalars().all()
    dep_dicts = [{"task_id": d.task_id, "depends_on_id": d.depends_on_id} for d in deps]

    # Fetch member workload for utilization
    members = db.execute(
        select(ProjectMember).where(ProjectMember.project_id == project_id)
    ).scalars().all()

    weeks = _weeks_remaining(project.due_date)
    member_utilizations = []
    if members:
        for m in members:
            open_assigned = sum(
                (t.estimate_hours or 0)
                for t in tasks
                if t.assignee_id == m.user_id and t.status != "done"
            )
            cap = m.capacity_hours_per_week * weeks
            util = open_assigned / cap if cap > 0 else 0.0
            member_utilizations.append(util)

    result = compute_health(
        start_date=project.start_date,
        due_date=project.due_date,
        all_tasks=task_dicts,
        dependencies=dep_dicts,
        member_utilizations=member_utilizations,
    )

    # M8: enrich with ML risk probability + top 3 factors
    try:
        from app.services.risk import predict_risk
        diag = result["diagnostics"]
        risk_result = predict_risk(
            team_size=max(1, len(members)),
            avg_utilization=diag["max_utilization"],
            overdue_ratio=diag["overdue_ratio"],
            blocked_ratio=diag["blocked_ratio"],
            slip=diag["slip"],
            remaining_ratio=max(0.0, 1.0 - diag["actual_progress"]),
            done_ratio=diag["actual_progress"],
            days_to_due=(
                (date.fromisoformat(project.due_date) - date.today()).days
                if project.due_date else 30
            ),
        )
        result["risk"] = risk_result
    except Exception as e:
        logger.warning("Risk model not available: %s", e)
        result["risk"] = None

    return ok(data=result, message="Health score computed.")


# ── GET /projects/{project_id}/analytics/burndown ────────────────────────────

@router.get("/projects/{project_id}/analytics/burndown")
def get_burndown(
    project_id: int,
    current_user=Depends(get_current_user),
    membership=Depends(get_membership),
    db: Session = Depends(get_db),
):
    """Ideal vs actual remaining hours per day (uses tasks' completed_at)."""
    from app.services.burndown import compute_burndown

    project: Project = db.get(Project, project_id)
    tasks = db.execute(
        select(Task).where(Task.project_id == project_id)
    ).scalars().all()
    result = compute_burndown(
        project.start_date,
        project.due_date,
        [
            {
                "estimate_hours": t.estimate_hours,
                "completed_at": t.completed_at if t.status == "done" else None,
                "created_at": t.created_at,
            }
            for t in tasks
        ],
    )
    return ok(data=result, message="Burndown computed.")


# ── GET /ml/effort-benchmark ─────────────────────────────────────────────────

@router.get("/ml/effort-benchmark")
def get_effort_benchmark(
    current_user=Depends(get_current_user),
):
    """
    Return NASA93 effort model benchmark metrics.

    Labelled: "benchmark on public NASA93 data (93 projects)"
    The model is a GradientBoostingRegressor trained on COCOMO features.
    """
    metrics_path = (
        Path(__file__).parent.parent.parent / "ml" / "artifacts" / "effort_model_metrics.json"
    )
    if not metrics_path.exists():
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Effort model not trained yet. Run ml/train_effort.py.")

    with open(metrics_path) as f:
        metrics = json.load(f)

    # Also attach risk model metrics if available
    risk_metrics_path = (
        Path(__file__).parent.parent.parent / "ml" / "artifacts" / "risk_model_metrics.json"
    )
    risk_metrics = None
    if risk_metrics_path.exists():
        with open(risk_metrics_path) as f:
            risk_metrics = json.load(f)

    return ok(
        data={
            "effort": metrics,
            "risk":   risk_metrics,
            "label":  "benchmark on public NASA93 data (93 projects)",
            "risk_data_note": "Risk model trained on SIMULATED data (not real project history).",
        },
        message="Benchmark metrics loaded.",
    )
