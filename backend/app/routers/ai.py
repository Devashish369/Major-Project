"""
routers/ai.py – AI planner and estimator endpoints (spec §7, §8.6).

Spec §7:
  POST /ai/generate-plan         – draft plan (returns JSON, saves nothing)
  POST /projects/{id}/apply-plan – create sprints+tasks from plan (admin only)

Spec §8.6:
  POST /ai/estimate              – predict story_points + hours for a task title

Both planner endpoints include source: "llm" | "fallback" in the response.
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database import get_db
from app.deps import get_current_user, require_admin
from app.models import ActivityLog, Project, ProjectMember, Sprint, Task, TaskDependency
from app.schemas import GeneratePlanRequest, ApplyPlanRequest, EstimateRequest
from app.services.planner import generate_plan
from app.services.tasks import write_activity
from app.services.realtime import emit_tasks
from app.services.estimator import estimate as _estimate_sp
from app.main import ok

logger = logging.getLogger(__name__)
router = APIRouter(tags=["ai"])


# ── POST /ai/generate-plan ────────────────────────────────────────────────────

@router.post("/ai/generate-plan")
def api_generate_plan(
    body: GeneratePlanRequest,
    current_user=Depends(get_current_user),
):
    """
    Generate a project plan draft. Does NOT save anything to the database.
    Returns the plan JSON and source: "llm" | "fallback".

    Auth: any authenticated user (no project membership required).
    """
    result = generate_plan(
        description=body.description,
        team_size=body.team_size,
        duration_weeks=body.duration_weeks,
    )
    resp = ok(
        data=result["plan"],
        message=f"Plan generated (source: {result['source']})",
    )
    resp["source"] = result["source"]   # add source at top level per spec
    return resp


# ── POST /projects/{project_id}/apply-plan ────────────────────────────────────

@router.post("/projects/{project_id}/apply-plan", status_code=status.HTTP_201_CREATED)
def apply_plan(
    project_id: int,
    body: ApplyPlanRequest,
    current_user=Depends(get_current_user),
    _admin=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Apply a generated plan to a project (admin only, spec §7).

    Creates sprints, tasks, and dependency edges in ONE transaction so a
    partial failure rolls back everything (atomicity).

    The plan dict is the same shape returned by /ai/generate-plan.
    """
    # Verify project exists (membership already checked by require_admin)
    project = db.execute(select(Project).where(Project.id == project_id)).scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")

    plan = body.plan

    # ── 1. Create sprints ─────────────────────────────────────────────────────
    sprint_ids: list[int] = []
    for s in plan.get("sprints", []):
        sprint = Sprint(
            project_id=project_id,
            name=s.get("name", "Sprint"),
            goal=s.get("goal"),
        )
        db.add(sprint)
        db.flush()   # get sprint.id
        sprint_ids.append(sprint.id)

    # ── 2. Create tasks ───────────────────────────────────────────────────────
    task_title_to_id: dict[str, int] = {}
    tasks_data = plan.get("tasks", [])[:40]   # safety cap

    for t in tasks_data:
        sprint_idx = t.get("sprint_index", 0)
        sprint_id = sprint_ids[sprint_idx] if sprint_idx < len(sprint_ids) else None

        # Handle completed_at if task is created as done (edge case)
        completed_at = None
        if t.get("status") == "done":
            completed_at = datetime.now(timezone.utc)

        task = Task(
            project_id=project_id,
            sprint_id=sprint_id,
            title=t["title"],
            description=t.get("description"),
            module=t.get("module"),
            priority=t.get("priority", "medium"),
            estimate_hours=t.get("estimate_hours", 8),
            required_skills=[s.lower() for s in (t.get("required_skills") or [])],
            status=t.get("status", "todo"),
            completed_at=completed_at,
        )
        db.add(task)
        db.flush()
        task_title_to_id[task.title] = task.id

    # ── 3. Create dependency edges ────────────────────────────────────────────
    dep_count = 0
    for t in tasks_data:
        task_id = task_title_to_id.get(t["title"])
        if task_id is None:
            continue
        for dep_title in (t.get("depends_on") or []):
            dep_id = task_title_to_id.get(dep_title)
            if dep_id and dep_id != task_id:
                # Skip if duplicate (plan post-processing should prevent this)
                existing = db.execute(
                    select(TaskDependency).where(
                        TaskDependency.task_id == task_id,
                        TaskDependency.depends_on_id == dep_id,
                    )
                ).scalar_one_or_none()
                if not existing:
                    db.add(TaskDependency(task_id=task_id, depends_on_id=dep_id))
                    dep_count += 1

    # ── 4. Write activity log ──────────────────────────────────────────────────
    write_activity(
        db,
        project_id=project_id,
        user_id=current_user.id,
        action="plan_applied",
        meta={
            "sprints": len(sprint_ids),
            "tasks": len(task_title_to_id),
            "dependencies": dep_count,
            "source": body.source,
        },
    )

    db.commit()
    emit_tasks(db, project_id, "task_created", list(task_title_to_id.values()), current_user.id)

    return ok(
        data={
            "sprints_created": len(sprint_ids),
            "tasks_created": len(task_title_to_id),
            "dependencies_created": dep_count,
        },
        message=f"Plan applied: {len(sprint_ids)} sprints, {len(task_title_to_id)} tasks, {dep_count} dependencies created.",
    )


# ── POST /ai/estimate ────────────────────────────────────────────────────────────

@router.post("/ai/estimate")
def estimate(
    body: EstimateRequest,
    current_user=Depends(get_current_user),
):
    """
    Predict story_points and hours for a given task title + description.

    Uses the offline-trained TF-IDF + Ridge model (spec §8.6).
    hours = story_points × HOURS_PER_STORY_POINT (from settings).

    Never overwrites LLM or user values – always returns a suggestion only.
    """
    try:
        result = _estimate_sp(body.title, body.description)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    return ok(
        data=result,
        message="Estimate generated by TF-IDF + Ridge model (spec §8.6).",
    )
