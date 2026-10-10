"""
services/ask.py – "Ask the project" question answering (spec §8.8).

Flow (viva-ready):
  1. build_context(): turn the project's decisions, tasks and last 50 activity rows
     into plain text where every line starts with an id tag:
        [D3] decision   [T12] task   [A45] activity row
     The text is truncated to MAX_CONTEXT_CHARS (decisions first, then tasks,
     then activity) so the prompt always fits.
  2. answer_question(): ask the LLM to answer ONLY from that text, cite the tags,
     and admit when the answer is not there.  Provider order is the same as the
     planner: primary (Groq) -> fallback (Gemini, only if its key is set).
  3. Citations are validated: any id the model cites that is not in the context
     is dropped, so the UI never shows an invented source.

There is no cached answer.  With USE_CACHED_PLAN_ONLY=true or with no provider
available we raise AskUnavailable and the endpoint returns a clear 503 message.
"""

import json
import logging
import re
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import ActivityLog, Decision, Task, TaskDependency
from app.services.llm import call_llm
from app.services.tasks import names_for

logger = logging.getLogger(__name__)

MAX_CONTEXT_CHARS = 12000
MAX_ACTIVITY_ROWS = 50
NOT_FOUND_ANSWER = "I can't find that in this project's tasks, decisions or recent activity."

SYSTEM_PROMPT = (
    "You answer questions about ONE software project using ONLY the project data given "
    "in the user message. Never use outside knowledge and never guess. Every fact in your "
    "answer must be followed by the id tag(s) it came from, such as [T12] or [D3]. "
    f'If the data does not contain the answer, set the answer to exactly "{NOT_FOUND_ANSWER}" '
    'and use an empty sources list. Reply with JSON only: {"answer": "...", "sources": ["T12", "D3"]}'
)

_TAG = re.compile(r"\b([TDA])(\d+)\b")


class AskUnavailable(Exception):
    """No LLM provider could answer; the message is shown to the user."""


# ── 1. Context ────────────────────────────────────────────────────────────────

def build_context(db: Session, project_id: int) -> tuple[str, dict[str, dict]]:
    """
    Return (context_text, {tag: source}) where tags use the numbers people see:
    T3 = task #3 of THIS project, D2 = decision D2, A123 = activity row 123.
    """
    tasks = db.execute(select(Task).where(Task.project_id == project_id).order_by(Task.id)).scalars().all()
    deps: dict[int, list[int]] = {}
    for d in db.execute(
        select(TaskDependency).where(TaskDependency.task_id.in_([t.id for t in tasks] or [0]))
    ).scalars():
        deps.setdefault(d.task_id, []).append(d.depends_on_id)
    decisions = db.execute(
        select(Decision).where(Decision.project_id == project_id).order_by(Decision.created_at.desc())
    ).scalars().all()
    activity = db.execute(
        select(ActivityLog).where(ActivityLog.project_id == project_id)
        .order_by(ActivityLog.created_at.desc(), ActivityLog.id.desc()).limit(MAX_ACTIVITY_ROWS)
    ).scalars().all()
    # only the people this project's tasks / decisions / activity refer to
    users = names_for(db, [t.assignee_id for t in tasks] + [d.made_by for d in decisions] + [a.user_id for a in activity])

    tnum = {t.id: t.number or t.id for t in tasks}
    dnum = {d.id: d.number or d.id for d in decisions}
    source_of = {f"T{tnum[t.id]}": {"type": "task", "id": t.id, "number": tnum[t.id]} for t in tasks}
    source_of.update({f"D{dnum[d.id]}": {"type": "decision", "id": d.id, "number": dnum[d.id]} for d in decisions})
    source_of.update({f"A{a.id}": {"type": "activity", "id": a.id, "number": a.id} for a in activity})

    def tref(task_id):
        return f"T{tnum[task_id]}" if task_id in tnum else "a deleted task"

    sections: list[tuple[str, list[tuple[str, str]]]] = [
        ("DECISIONS", [(f"D{dnum[d.id]}",
                        f"[D{dnum[d.id]}] {d.title}: {d.decision}"
                        + (f" Reason: {d.reason}" if d.reason else "")
                        + f" (by {users.get(d.made_by, 'unknown')}, {d.created_at:%Y-%m-%d}"
                        + (f", about task {tref(d.related_task_id)}" if d.related_task_id else "") + ")")
                       for d in decisions]),
        ("TASKS", [(f"T{tnum[t.id]}",
                    f"[T{tnum[t.id]}] {t.title} | {t.status} | est {t.estimate_hours}h"
                    + (f" actual {t.actual_hours}h" if t.actual_hours else "")
                    + f" | assignee {users.get(t.assignee_id, 'unassigned')} | due {t.due_date or 'none'}"
                    + (" | depends on " + ", ".join(tref(x) for x in deps[t.id]) if t.id in deps else ""))
                   for t in tasks]),
        ("RECENT ACTIVITY (newest first)", [(f"A{a.id}",
                    f"[A{a.id}] {a.created_at:%Y-%m-%d} {users.get(a.user_id, 'someone')}: {a.action}"
                    + (f" task {tref(a.task_id)}" if a.task_id else "") + f" {json.dumps(a.meta or {})}")
                   for a in activity]),
    ]

    out: list[str] = []
    valid: dict[str, dict] = {}
    used = 0
    for title, items in sections:
        out.append(f"## {title}")
        used += len(title) + 4
        omitted = 0
        for tag, line in items:
            if used + len(line) + 1 > MAX_CONTEXT_CHARS:
                omitted += 1
                continue
            out.append(line)
            valid[tag] = source_of[tag]
            used += len(line) + 1
        if omitted:
            out.append(f"(+{omitted} more omitted to fit the size limit)")
        if not items:
            out.append("(none)")
    return "\n".join(out), valid


# ── 2. LLM call ───────────────────────────────────────────────────────────────

def _parse(raw: str) -> tuple[str, list[str]]:
    """Accept clean JSON, fenced JSON, or plain text containing id tags."""
    text = raw.strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
    try:
        obj = json.loads(text)
        if isinstance(obj, dict) and "answer" in obj:
            return str(obj["answer"]).strip(), [str(s) for s in obj.get("sources") or []]
    except (json.JSONDecodeError, TypeError):
        pass
    return raw.strip(), []


def answer_question(db: Session, project_id: int, question: str) -> dict:
    if settings.USE_CACHED_PLAN_ONLY:
        raise AskUnavailable("AI answers are switched off (USE_CACHED_PLAN_ONLY=true). Turn it off to use Ask.")
    if not settings.LLM_API_KEY and not settings.LLM_FALLBACK_API_KEY:
        raise AskUnavailable("No AI provider is configured. Add LLM_API_KEY (or LLM_FALLBACK_API_KEY) to backend/.env.")

    context, valid = build_context(db, project_id)
    prompt = f"PROJECT DATA\n{context}\n\nQUESTION: {question}"

    attempts = []
    if settings.LLM_API_KEY:
        attempts.append(False)
    if settings.LLM_FALLBACK_API_KEY:
        attempts.append(True)

    raw: Optional[str] = None
    for use_fallback in attempts:
        try:
            raw = call_llm(prompt, use_fallback=use_fallback, system=SYSTEM_PROMPT)
            break
        except Exception as exc:  # network, quota, timeout ... try the next provider
            logger.warning("Ask: %s provider failed: %s", "fallback" if use_fallback else "primary", exc)
    if raw is None:
        raise AskUnavailable("The AI service could not be reached right now. Please try again in a moment.")

    answer, cited = _parse(raw)
    if not answer:
        answer = NOT_FOUND_ANSWER
    # Tags may be cited in the sources list or inline in the answer text
    tags = list(dict.fromkeys(
        [f"{m.group(1)}{m.group(2)}" for s in cited for m in [_TAG.fullmatch(s.strip().strip("[]"))] if m]
        + [f"{m.group(1)}{m.group(2)}" for m in _TAG.finditer(answer)]
    ))
    sources = [valid[t] for t in tags if t in valid]
    return {"answer": answer, "sources": sources}
