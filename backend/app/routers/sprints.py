"""
routers/sprints.py – GET /projects/{id}/sprints (read-only, member-only).

Sprints are created when an AI plan is applied (POST /projects/{id}/apply-plan).  This
endpoint lists them with task counts so the Board can filter by sprint.  Creating, editing
or deleting sprints by hand is future scope (no such endpoints on purpose).
"""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_membership
from app.main import ok
from app.models import Sprint, Task

router = APIRouter(tags=["sprints"])


@router.get("/projects/{project_id}/sprints")
def list_sprints(
    project_id: int,
    membership=Depends(get_membership),
    db: Session = Depends(get_db),
):
    sprints = db.execute(
        select(Sprint).where(Sprint.project_id == project_id).order_by(Sprint.id)
    ).scalars().all()
    tasks = db.execute(
        select(Task.sprint_id, Task.status).where(Task.project_id == project_id)
    ).all()
    return ok(data=[
        {
            "id": s.id, "name": s.name, "start_date": s.start_date, "end_date": s.end_date, "goal": s.goal,
            "task_count": sum(1 for sid, _ in tasks if sid == s.id),
            "done_count": sum(1 for sid, st in tasks if sid == s.id and st == "done"),
        }
        for s in sprints
    ], message="Sprints loaded.")
