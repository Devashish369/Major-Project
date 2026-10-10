"""
numbering.py – per-project numbers for tasks (#1, #2 …) and decisions (D1, D2 …).

Every project counts from 1, independently of the others.  The database `id` stays the internal
key (URLs, dependencies, foreign keys); `number` is what people see.

How a number is handed out (on every insert path – API, AI plan, seed, tests – because it runs in
the session's before_flush hook):
    UPDATE projects SET task_seq = task_seq + <new rows> WHERE id = <project> RETURNING task_seq
The UPDATE is atomic and, on PostgreSQL, locks that project's row until the transaction ends, so
two people creating tasks at the same moment can never get the same number.  The unique index
(project_id, number) is the safety net.  Using a counter (not max()+1) means a deleted task's
number is never given to a new task, so "#7" always means the same task.
"""
from sqlalchemy import event, inspect, update
from sqlalchemy.orm import Session

from app.models import Decision, Project, Task

_COUNTER = {Task: Project.task_seq, Decision: Project.decision_seq}


@event.listens_for(Session, "before_flush")
def _number_new_rows(session: Session, _flush_context, _instances) -> None:
    pending: dict[tuple[type, int], list] = {}
    for obj in session.new:
        cls = type(obj)
        if cls in _COUNTER and obj.number is None and obj.project_id is not None:
            pending.setdefault((cls, obj.project_id), []).append(obj)

    for (cls, project_id), rows in pending.items():
        column = _COUNTER[cls]
        last = session.execute(
            update(Project)
            .where(Project.id == project_id)
            .values({column: column + len(rows)})
            .returning(column)
            .execution_options(synchronize_session=False)
        ).scalar_one_or_none()
        if last is None:          # unknown project: the foreign key will reject the insert anyway
            continue
        rows.sort(key=lambda o: inspect(o).insert_order)   # numbers follow creation order
        first = last - len(rows) + 1
        for offset, obj in enumerate(rows):
            obj.number = first + offset
