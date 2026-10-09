"""
routers/tasks.py – Task CRUD and dependency endpoints.

Spec §7:
  GET    /projects/{id}/tasks               – list all tasks for a project
  POST   /projects/{id}/tasks               – create task (any member)
  GET    /tasks/{id}                        – get single task
  PATCH  /tasks/{id}                        – update task (any member)
  DELETE /tasks/{id}                        – delete task (any member)
  POST   /tasks/{id}/dependencies           – add dependency (cycle check)
  DELETE /tasks/{id}/dependencies/{dep_id} – remove dependency

All writes emit an activity_log row via services.tasks.write_activity.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.database import get_db
from app.deps import get_current_user, get_membership
from app.models import ActivityLog, Project, ProjectMember, Task, TaskDependency, User
from app.schemas import (
    DependencyAdd, DependencyOut, TaskCreate, TaskOut, TaskUpdate,
)
from app.services.tasks import apply_status_change, has_cycle, write_activity
from app.main import ok
from app.services.realtime import emit_task_deleted, emit_tasks

router = APIRouter(tags=["tasks"])


def _check_assignee(db: Session, project_id: int, assignee_id) -> None:
    """An assignee must be a member of the task's project (else 422)."""
    if assignee_id is None:
        return
    member = db.execute(
        select(ProjectMember.id).where(
            ProjectMember.project_id == project_id, ProjectMember.user_id == assignee_id
        )
    ).first()
    if member is None:
        raise HTTPException(status_code=422, detail="The assignee must be a member of this project.")


# ── Helper: build TaskOut dict with dependency list ───────────────────────────

def _task_out(task: Task, db: Session, dep_ids=None) -> dict:
    # `dep_ids` is passed by the list endpoint, which loads every dependency in ONE query;
    # single-task callers leave it None and it is looked up here.
    if dep_ids is None:
        dep_ids = list(db.execute(
            select(TaskDependency.depends_on_id).where(TaskDependency.task_id == task.id)
        ).scalars().all())

    return TaskOut(
        id=task.id,
        project_id=task.project_id,
        sprint_id=task.sprint_id,
        title=task.title,
        description=task.description,
        status=task.status,
        priority=task.priority,
        estimate_hours=task.estimate_hours,
        actual_hours=task.actual_hours,
        assignee_id=task.assignee_id,
        due_date=task.due_date,
        required_skills=task.required_skills or [],
        completed_at=task.completed_at,
        module=task.module,
        created_at=task.created_at,
        dependencies=dep_ids,
    ).model_dump()


def _get_project_membership(project_id: int, user: User, db: Session) -> ProjectMember:
    """Return membership row or raise 404 (non-members cannot discover project)."""
    pm = db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user.id,
        )
    ).scalar_one_or_none()
    if pm is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    return pm


# ── GET /projects/{project_id}/tasks ─────────────────────────────────────────

@router.get("/projects/{project_id}/tasks")
def list_tasks(
    project_id: int,
    _membership=Depends(get_membership),
    db: Session = Depends(get_db),
):
    """Return all tasks for the project. Members only."""
    tasks = db.execute(
        select(Task).where(Task.project_id == project_id)
        .order_by(Task.created_at)
    ).scalars().all()
    deps_by_task: dict[int, list[int]] = {t.id: [] for t in tasks}
    if tasks:
        for task_id, dep_id in db.execute(
            select(TaskDependency.task_id, TaskDependency.depends_on_id)
            .where(TaskDependency.task_id.in_(list(deps_by_task)))
        ).all():
            deps_by_task[task_id].append(dep_id)
    return ok(data=[_task_out(t, db, deps_by_task[t.id]) for t in tasks])


# ── POST /projects/{project_id}/tasks ────────────────────────────────────────

@router.post("/projects/{project_id}/tasks", status_code=status.HTTP_201_CREATED)
def create_task(
    project_id: int,
    body: TaskCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a task. Any project member may create tasks."""
    _get_project_membership(project_id, current_user, db)
    _check_assignee(db, project_id, body.assignee_id)

    task = Task(
        project_id=project_id,
        sprint_id=body.sprint_id,
        title=body.title,
        description=body.description,
        status=body.status,
        priority=body.priority,
        estimate_hours=body.estimate_hours,
        assignee_id=body.assignee_id,
        due_date=body.due_date,
        required_skills=body.required_skills or [],
        module=body.module,
    )
    # Handle completed_at if task is created directly as 'done'
    if body.status == "done":
        task.completed_at = datetime.now(timezone.utc)

    db.add(task)
    db.flush()   # get task.id before writing activity

    write_activity(
        db,
        project_id=project_id,
        user_id=current_user.id,
        task_id=task.id,
        action="task_created",
        meta={"title": task.title, "status": task.status},
    )
    db.commit()
    db.refresh(task)
    emit_tasks(db, project_id, "task_created", [task.id], current_user.id)
    return ok(data=_task_out(task, db), message="Task created.")


# ── GET /tasks/{task_id} ──────────────────────────────────────────────────────

@router.get("/tasks/{task_id}")
def get_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a single task. Caller must be a project member."""
    task = db.execute(select(Task).where(Task.id == task_id)).scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found.")
    _get_project_membership(task.project_id, current_user, db)
    return ok(data=_task_out(task, db))


# ── PATCH /tasks/{task_id} ────────────────────────────────────────────────────

@router.patch("/tasks/{task_id}")
def update_task(
    task_id: int,
    body: TaskUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Update a task. Any project member may update.

    Handles:
      - completed_at rule when status changes (via apply_status_change)
      - activity_log rows for status moves and assignee changes
    """
    task = db.execute(select(Task).where(Task.id == task_id)).scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found.")
    _get_project_membership(task.project_id, current_user, db)

    meta: dict = {}

    # Status change – must go through service so completed_at is handled
    if body.status is not None and body.status != task.status:
        meta["from_status"] = task.status
        meta["to_status"] = body.status
        apply_status_change(task, body.status)

    # Assignee change
    if body.assignee_id is not None and body.assignee_id != task.assignee_id:
        _check_assignee(db, task.project_id, body.assignee_id)
        meta["assignee_id"] = body.assignee_id
        task.assignee_id = body.assignee_id
    elif "assignee_id" in body.model_fields_set and body.assignee_id is None:
        meta["assignee_id"] = None
        task.assignee_id = None

    # Remaining scalar fields
    if body.title is not None:
        task.title = body.title
    if body.description is not None:
        task.description = body.description
    if body.priority is not None:
        task.priority = body.priority
    if body.estimate_hours is not None:
        task.estimate_hours = body.estimate_hours
    if body.actual_hours is not None:
        task.actual_hours = body.actual_hours
    if body.due_date is not None:
        task.due_date = body.due_date
    if body.required_skills is not None:
        task.required_skills = body.required_skills
    if body.module is not None:
        task.module = body.module
    if body.sprint_id is not None:
        task.sprint_id = body.sprint_id

    action = "task_moved" if "from_status" in meta else "task_updated"
    write_activity(
        db,
        project_id=task.project_id,
        user_id=current_user.id,
        task_id=task.id,
        action=action,
        meta=meta,
    )
    db.commit()
    db.refresh(task)
    emit_tasks(db, task.project_id, "task_updated", [task.id], current_user.id)
    return ok(data=_task_out(task, db), message="Task updated.")


# ── DELETE /tasks/{task_id} ───────────────────────────────────────────────────

@router.delete("/tasks/{task_id}")
def delete_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a task. Any project member may delete tasks."""
    task = db.execute(select(Task).where(Task.id == task_id)).scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found.")
    _get_project_membership(task.project_id, current_user, db)

    project_id = task.project_id
    write_activity(
        db,
        project_id=project_id,
        user_id=current_user.id,
        task_id=None,   # task is about to be deleted; set null to avoid FK error
        action="task_deleted",
        meta={"title": task.title},
    )
    db.flush()   # flush activity log first, then delete (FK task_id = None)
    db.delete(task)
    db.commit()
    emit_task_deleted(project_id, task_id, current_user.id)
    return ok(message="Task deleted.")


# ── POST /tasks/{task_id}/dependencies ───────────────────────────────────────

@router.post("/tasks/{task_id}/dependencies", status_code=status.HTTP_201_CREATED)
def add_dependency(
    task_id: int,
    body: DependencyAdd,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Add a dependency: task_id depends on body.depends_on_id.

    Rejects:
      - Self-reference (task_id == depends_on_id)
      - Cycles (DFS from depends_on_id reaches task_id)
      - Both tasks must belong to the same project
      - Duplicates (unique constraint)
    """
    task = db.execute(select(Task).where(Task.id == task_id)).scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found.")
    _get_project_membership(task.project_id, current_user, db)

    # Self-reference check
    if body.depends_on_id == task_id:
        raise HTTPException(status_code=422, detail="A task cannot depend on itself.")

    # Target task must exist and belong to the same project
    dep_task = db.execute(select(Task).where(Task.id == body.depends_on_id)).scalar_one_or_none()
    if dep_task is None or dep_task.project_id != task.project_id:
        raise HTTPException(status_code=404, detail="Dependency target task not found in this project.")

    # Cycle check (DFS)
    if has_cycle(db, task_id, body.depends_on_id):
        raise HTTPException(
            status_code=422,
            detail="Adding this dependency would create a cycle.",
        )

    # Duplicate check
    existing = db.execute(
        select(TaskDependency).where(
            TaskDependency.task_id == task_id,
            TaskDependency.depends_on_id == body.depends_on_id,
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Dependency already exists.")

    dep = TaskDependency(task_id=task_id, depends_on_id=body.depends_on_id)
    db.add(dep)
    write_activity(
        db,
        project_id=task.project_id,
        user_id=current_user.id,
        task_id=task_id,
        action="dependency_added",
        meta={"depends_on_id": body.depends_on_id},
    )
    db.commit()
    db.refresh(dep)
    emit_tasks(db, task.project_id, "task_updated", [task_id], current_user.id)   # its dependency list changed
    return ok(data=DependencyOut.model_validate(dep).model_dump(), message="Dependency added.")


# ── DELETE /tasks/{task_id}/dependencies/{dep_id} ────────────────────────────

@router.delete("/tasks/{task_id}/dependencies/{dep_id}")
def remove_dependency(
    task_id: int,
    dep_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Remove a dependency edge. dep_id is the depends_on_id (target task id)."""
    task = db.execute(select(Task).where(Task.id == task_id)).scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found.")
    _get_project_membership(task.project_id, current_user, db)

    dep = db.execute(
        select(TaskDependency).where(
            TaskDependency.task_id == task_id,
            TaskDependency.depends_on_id == dep_id,
        )
    ).scalar_one_or_none()
    if dep is None:
        raise HTTPException(status_code=404, detail="Dependency not found.")

    db.delete(dep)
    write_activity(
        db,
        project_id=task.project_id,
        user_id=current_user.id,
        task_id=task_id,
        action="dependency_removed",
        meta={"removed_dep_id": dep_id},
    )
    db.commit()
    emit_tasks(db, task.project_id, "task_updated", [task_id], current_user.id)
    return ok(message="Dependency removed.")


# ── GET /projects/{project_id}/activity ──────────────────────────────────────

@router.get("/projects/{project_id}/activity")
def list_activity(
    project_id: int,
    _membership=Depends(get_membership),
    db: Session = Depends(get_db),
):
    """Return recent activity log for the project (last 100 rows, newest first)."""
    rows = db.execute(
        select(ActivityLog).where(ActivityLog.project_id == project_id)
        .order_by(ActivityLog.created_at.desc())
        .limit(100)
    ).scalars().all()
    from app.schemas import ActivityLogOut
    return ok(data=[ActivityLogOut.model_validate(r).model_dump() for r in rows])
