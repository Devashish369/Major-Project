"""
routers/decisions.py – Decision log + project Q&A (spec §7, §8.8).

  GET    /projects/{id}/decisions   – list (any member), newest first
  POST   /projects/{id}/decisions   – add (any member)
  DELETE /decisions/{id}            – delete (the author or a project admin)
  POST   /projects/{id}/ask         – answer a question from the project's own data

Non-members always get 404 so project ids cannot be enumerated.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, get_membership
from app.main import ok
from app.models import Decision, ProjectMember, Task, User
from app.schemas import AskRequest, DecisionCreate, DecisionOut
from app.services.ask import AskUnavailable, answer_question
from app.services.tasks import write_activity

router = APIRouter(tags=["decisions"])


def _out(d: Decision, names: dict[int, str]) -> dict:
    out = DecisionOut.model_validate(d)
    out.made_by_name = names.get(d.made_by)
    return out.model_dump(mode="json")


@router.get("/projects/{project_id}/decisions")
def list_decisions(
    project_id: int,
    membership=Depends(get_membership),
    db: Session = Depends(get_db),
):
    rows = db.execute(
        select(Decision).where(Decision.project_id == project_id)
        .order_by(Decision.created_at.desc(), Decision.id.desc())
    ).scalars().all()
    names = {u.id: u.full_name for u in db.execute(
        select(User).where(User.id.in_([d.made_by for d in rows if d.made_by] or [0]))
    ).scalars()}
    return ok(data=[_out(d, names) for d in rows], message="Decisions loaded.")


@router.post("/projects/{project_id}/decisions", status_code=201)
def create_decision(
    project_id: int,
    body: DecisionCreate,
    current_user: User = Depends(get_current_user),
    membership=Depends(get_membership),
    db: Session = Depends(get_db),
):
    if body.related_task_id is not None:
        task = db.get(Task, body.related_task_id)
        if task is None or task.project_id != project_id:
            raise HTTPException(status_code=422, detail="related_task_id must be a task in this project.")
    d = Decision(
        project_id=project_id, title=body.title.strip(), decision=body.decision.strip(),
        reason=(body.reason or "").strip() or None, made_by=current_user.id,
        related_task_id=body.related_task_id,
    )
    db.add(d)
    db.flush()
    write_activity(db, project_id=project_id, user_id=current_user.id, action="decision_added",
                   meta={"decision_id": d.id, "title": d.title})
    db.commit()
    db.refresh(d)
    return ok(data=_out(d, {current_user.id: current_user.full_name}), message="Decision recorded.")


@router.delete("/decisions/{decision_id}")
def delete_decision(
    decision_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    d = db.get(Decision, decision_id)
    member = None
    if d is not None:
        member = db.execute(select(ProjectMember).where(
            ProjectMember.project_id == d.project_id, ProjectMember.user_id == current_user.id
        )).scalar_one_or_none()
    if d is None or member is None:
        raise HTTPException(status_code=404, detail="Decision not found.")
    if member.role != "admin" and d.made_by != current_user.id:
        raise HTTPException(status_code=403, detail="Only the author or a project admin can delete a decision.")
    write_activity(db, project_id=d.project_id, user_id=current_user.id, action="decision_deleted",
                   meta={"title": d.title})
    db.delete(d)
    db.commit()
    return ok(data=None, message="Decision deleted.")


@router.post("/projects/{project_id}/ask")
def ask_project(
    project_id: int,
    body: AskRequest,
    membership=Depends(get_membership),
    db: Session = Depends(get_db),
):
    try:
        result = answer_question(db, project_id, body.question.strip())
    except AskUnavailable as exc:
        # A readable message, not a crash: the UI shows it as-is.
        raise HTTPException(status_code=503, detail=str(exc))
    return ok(data=result, message="Answer generated from project data.")
