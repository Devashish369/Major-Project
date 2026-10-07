"""
routers/report.py – GET /projects/{id}/report (M16): one printable project report.

Member-only (non-members get 404 like every project route).  The numbers come from the
EXISTING endpoints (health, forecast, workload), called as plain functions, so the report
can never disagree with the Analytics and Team tabs.  No LLM is called.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, get_membership
from app.main import ok
from app.models import ActivityLog, Decision, Project, Task, TaskDependency, User
from app.routers.analytics import get_forecast, get_health
from app.routers.assignments import workload as get_workload
from app.services.report import build_report

router = APIRouter(tags=["report"])


@router.get("/projects/{project_id}/report")
def project_report(
    project_id: int,
    current_user=Depends(get_current_user),
    membership=Depends(get_membership),
    db: Session = Depends(get_db),
):
    common = dict(project_id=project_id, current_user=current_user, membership=membership, db=db)
    health = get_health(**common)["data"]
    forecast = get_forecast(**common)["data"]
    workload = get_workload(**common)["data"]

    project = db.get(Project, project_id)
    tasks = db.execute(select(Task).where(Task.project_id == project_id)).scalars().all()
    deps = db.execute(
        select(TaskDependency).where(TaskDependency.task_id.in_([t.id for t in tasks] or [0]))
    ).scalars().all()
    users = {u.id: u.full_name for u in db.execute(select(User)).scalars()}
    decisions = db.execute(
        select(Decision).where(Decision.project_id == project_id)
        .order_by(Decision.created_at.desc(), Decision.id.desc()).limit(10)
    ).scalars().all()
    activity = db.execute(
        select(ActivityLog).where(ActivityLog.project_id == project_id)
        .order_by(ActivityLog.created_at.desc(), ActivityLog.id.desc()).limit(10)
    ).scalars().all()

    report = build_report(
        project={
            "id": project.id, "title": project.title, "description": project.description,
            "status": project.status, "priority": project.priority,
            "start_date": project.start_date, "due_date": project.due_date,
            "member_count": len(workload),
        },
        tasks=[{"id": t.id, "title": t.title, "status": t.status, "estimate_hours": t.estimate_hours,
                "due_date": t.due_date, "assignee_id": t.assignee_id} for t in tasks],
        dependencies=[{"task_id": d.task_id, "depends_on_id": d.depends_on_id} for d in deps],
        health=health, forecast=forecast, workload=workload,
        decisions=[{"id": d.id, "title": d.title, "decision": d.decision, "reason": d.reason,
                    "made_by": users.get(d.made_by), "created_at": d.created_at.isoformat()} for d in decisions],
        activity=[{"id": a.id, "action": a.action, "user": users.get(a.user_id), "task_id": a.task_id,
                   "meta": a.meta or {}, "created_at": a.created_at.isoformat()} for a in activity],
        user_names=users,
    )
    return ok(data=report, message="Project report generated (rule-based, no LLM).")
