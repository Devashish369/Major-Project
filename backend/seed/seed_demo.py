"""
seed/seed_demo.py – Rebuild the 12 demo users and 16 demo projects (spec §10).

Run from the backend folder:

    python -m seed.seed_demo              # wipe + recreate the demo data
    python -m seed.seed_demo --verify     # ... then print designed-vs-actual table
    python -m seed.seed_demo --attach you@example.com   # also add your own account

How it works (viva-ready):
  * Idempotent: it deletes ONLY demo data (users @intellipm.demo and the projects
    they created) and recreates it.  Your own accounts and projects are untouched.
  * Fixed random seed (RNG_SEED) -> same data every run; only the dates move,
    because every date is generated relative to today.
  * Self-calibrating dates: tasks, estimates, assignments and dependencies are
    written first; then the project's own Monte Carlo forecast is run and the
    due date is set to  today + slack x P50  (slack = `f` in demo_projects.py).
    The start date is chosen so that expected progress = actual progress + slip.
    That is why each story keeps its intended health / delay probability.
"""

import argparse
import math
import random
import sys
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import delete, select

from app.database import Base, SessionLocal, engine
from app.models import (
    ActivityLog, Decision, Project, ProjectMember, Sprint, Task, TaskDependency, User,
)
from app.security import hash_password
from app.services.forecast import run_forecast
from seed.demo_projects import (
    DEMO_EMAIL_DOMAIN, DEMO_PASSWORD, PRESENTER, PROJECTS, USERS,
)

RNG_SEED = 20261017
PRESENTER_CAPACITY = 10          # hours/week the presenter account contributes
HOURS_PER_DAY = 6                # productive hours, used to place "started" times


# ── Small helpers ─────────────────────────────────────────────────────────────

def _at(day: date, hour_offset: float = 0.0) -> datetime:
    """Midnight UTC of `day` + 9h + hour_offset, as an aware datetime."""
    return datetime(day.year, day.month, day.day, 9, tzinfo=timezone.utc) + timedelta(hours=hour_offset)


def _parse_tasks(text: str) -> list[dict]:
    rows = []
    for line in text.strip().splitlines():
        module, title, skills, hours = [p.strip() for p in line.split("|")]
        rows.append({
            "module": module, "title": title,
            "skills": [s.strip() for s in skills.split(",") if s.strip()],
            "est": float(hours),
        })
    return rows


def _coverage(task_skills: list[str], user_skills: dict) -> float:
    if not task_skills:
        return 0.5
    return sum(user_skills.get(s, 0) / 5 for s in task_skills) / len(task_skills)


# ── Wipe ──────────────────────────────────────────────────────────────────────

def wipe(db) -> None:
    """Delete demo users, the projects they created, and everything under them."""
    demo_users = db.execute(
        select(User.id).where(User.email.like(f"%{DEMO_EMAIL_DOMAIN}"))
    ).scalars().all()
    if not demo_users:
        return
    pids = db.execute(
        select(Project.id).where(Project.created_by.in_(demo_users))
    ).scalars().all()
    if pids:
        tids = select(Task.id).where(Task.project_id.in_(pids))
        db.execute(delete(ActivityLog).where(ActivityLog.project_id.in_(pids)))
        db.execute(delete(Decision).where(Decision.project_id.in_(pids)))
        db.execute(delete(TaskDependency).where(TaskDependency.task_id.in_(tids)))
        db.execute(delete(Task).where(Task.project_id.in_(pids)))
        db.execute(delete(Sprint).where(Sprint.project_id.in_(pids)))
        db.execute(delete(ProjectMember).where(ProjectMember.project_id.in_(pids)))
        db.execute(delete(Project).where(Project.id.in_(pids)))
    db.execute(delete(ProjectMember).where(ProjectMember.user_id.in_(demo_users)))
    db.execute(delete(User).where(User.id.in_(demo_users)))
    db.commit()


# ── Assignment (simple greedy, only used to create believable data) ───────────

def _pick_assignee(task, team, load, rng, params, open_phase, idle_quota):
    """
    Choose who holds a task.  Lowest (load/capacity - 1.5 x skill coverage) wins,
    so skilled people get matching work and nobody is buried -- unless the story
    asks for a skew (overloaded developer) or an idle member.
    """
    cands = list(team)
    idle = params.get("idle")
    if open_phase and idle:
        if idle_quota["n"] > 0 and task["est"] <= 8 and any(
            m["key"] == idle and _coverage(task["skills"], m["skills"]) >= 0.5 for m in team
        ):
            idle_quota["n"] -= 1
            return next(m for m in team if m["key"] == idle)
        cands = [m for m in cands if m["key"] != idle]
    skew = params.get("skew")
    if open_phase and skew and rng.random() < skew[1]:
        for m in cands:
            if m["key"] == skew[0]:
                return m
    return min(cands, key=lambda m: load[m["key"]] / m["cap"] - 1.5 * _coverage(task["skills"], m["skills"]))


# ── One project ───────────────────────────────────────────────────────────────

def build_project(db, spec, user_rows, presenter, today, rng) -> dict:
    p = spec["params"]
    tasks = _parse_tasks(spec["tasks"])
    n = len(tasks)

    # 1. Optional scope creep: some open estimates grow (logged in activity later)
    creep_log = {}
    # 2. Statuses by order: first tasks done, next `wip` in progress, rest todo
    completed = p.get("completed", False)
    # Finished tasks overrun by exp(growth) on average, so pick fewer of them to
    # land on the intended progress as the health score measures it (actual hours).
    target = p["progress"] * sum(t["est"] for t in tasks) / math.exp(p["growth"])
    done_n, cum = 0, 0.0
    while done_n < n and (completed or cum < target - 1e-9):
        cum += tasks[done_n]["est"]
        done_n += 1
    if not completed:
        done_n = min(done_n, n - 1)
    n_open = n - done_n
    wip = min(n_open, p.get("wip", max(1, round(0.25 * n_open))))
    for i, t in enumerate(tasks):
        t["status"] = "done" if i < done_n else ("in_progress" if i < done_n + wip else "todo")

    if p.get("creep"):
        for i, t in enumerate(tasks):
            if t["status"] != "done" and rng.random() < 0.45:
                new = round(t["est"] * rng.uniform(1.3, 1.8) * 2) / 2
                creep_log[i] = (t["est"], new)
                t["est"] = new

    # 3. Project row + members
    lead_key = next(k for k, role, _ in spec["team"] if role == "admin")
    project = Project(
        title=spec["title"], description=spec["description"], priority=spec["priority"],
        status="pending", start_date=None, due_date=None, created_by=user_rows[lead_key].id,
    )
    db.add(project)
    db.flush()

    team = []
    for key, role, cap in spec["team"]:
        db.add(ProjectMember(project_id=project.id, user_id=user_rows[key].id, role=role,
                             capacity_hours_per_week=cap))
        team.append({"key": key, "id": user_rows[key].id, "cap": cap, "skills": USERS[key][1],
                     "on_time": USERS[key][2]})
    db.add(ProjectMember(project_id=project.id, user_id=presenter.id, role="admin",
                         capacity_hours_per_week=PRESENTER_CAPACITY))

    # 4. Assignment
    hist_load = {m["key"]: 0.0 for m in team}
    open_load = {m["key"]: 0.0 for m in team}
    idle_quota = {"n": 1}
    for t in tasks:
        if t["status"] == "done":
            m = _pick_assignee(t, team, hist_load, rng, p, False, idle_quota)
            hist_load[m["key"]] += t["est"]
            t["assignee"] = m
        elif p.get("unassigned"):
            t["assignee"] = None
        else:
            m = _pick_assignee(t, team, open_load, rng, p, True, idle_quota)
            open_load[m["key"]] += t["est"]
            t["assignee"] = m

    # 5. Actual hours (finished: ~90% have one; in progress: partial)
    creep = p.get("creep", False)
    for t in tasks:
        t["actual"] = None
        if t["status"] == "done" and rng.random() < 0.9:
            t["actual"] = max(0.5, round(t["est"] * math.exp(rng.gauss(p["growth"], 0.22)) * 2) / 2)
        elif t["status"] == "in_progress":
            lo, hi = (0.5, 1.4) if creep else (0.2, 0.9)
            t["actual"] = round(t["est"] * rng.uniform(lo, hi) * 2) / 2

    # 6. Insert tasks (dates are filled in after the forecast)
    n_spr = p.get("sprints", 2)
    sprints = []
    for s in range(n_spr):
        sp = Sprint(project_id=project.id, name=f"Sprint {s + 1}")
        db.add(sp)
        sprints.append(sp)
    db.flush()
    rows = []
    for i, t in enumerate(tasks):
        prio = "high" if i < 3 else rng.choice(["medium", "medium", "low", "high"])
        row = Task(
            project_id=project.id, sprint_id=sprints[min(n_spr - 1, i * n_spr // n)].id,
            title=t["title"], description=f"{t['module']}: {t['title']}.", status=t["status"],
            priority=prio, estimate_hours=t["est"], actual_hours=t["actual"],
            assignee_id=t["assignee"]["id"] if t["assignee"] else None,
            required_skills=t["skills"], module=t["module"],
        )
        db.add(row)
        rows.append(row)
    db.flush()

    # 7. Dependencies (always point to an earlier task -> no cycles)
    deps = set()
    last_in_module = {}
    for i, t in enumerate(tasks):
        j = last_in_module.get(t["module"])
        if j is not None and rng.random() < p["dens"]:
            deps.add((i, j))
        last_in_module[t["module"]] = i
    for mod_a, mod_b in p.get("cross", []):
        a_idx = [i for i, t in enumerate(tasks) if t["module"] == mod_a]
        b_idx = [i for i, t in enumerate(tasks) if t["module"] == mod_b]
        for k, i in enumerate(a_idx):
            j = b_idx[k % len(b_idx)]
            if j < i:
                deps.add((i, j))
    for i, j in sorted(deps):
        db.add(TaskDependency(task_id=rows[i].id, depends_on_id=rows[j].id))
    db.flush()

    # 8. Dates.  Progress exactly as the health score measures it:
    total_est = sum(t["est"] for t in tasks)
    done_hours = sum((t["actual"] or t["est"]) for t in tasks if t["status"] == "done")
    progress = min(1.0, done_hours / total_est)

    capacities = [m["cap"] for m in team] + [PRESENTER_CAPACITY]
    open_idx = [i for i, t in enumerate(tasks) if t["status"] != "done"]
    if completed:
        due = today - timedelta(days=6)
        start = today - timedelta(days=70)
        remaining, elapsed = 0, 70
    else:
        res = run_forecast(
            open_tasks=[{"id": rows[i].id, "estimate_hours": tasks[i]["est"]} for i in open_idx],
            completed_tasks=[{"estimate_hours": t["est"], "actual_hours": t["actual"]}
                             for t in tasks if t["status"] == "done" and t["actual"]],
            dependencies=[{"task_id": rows[i].id, "depends_on_id": rows[j].id} for i, j in deps],
            capacity_per_week=capacities, due_date=None, today=today, n_sims=1500,
        )
        p50_days = max(1, (date.fromisoformat(res["p50"]) - today).days)
        remaining = max(4, round(p["f"] * p50_days))
        e = min(0.97, max(0.0, progress + p["slip"]))
        elapsed = p.get("elapsed") or max(3, round(e / (1 - e) * remaining))
        start, due = today - timedelta(days=elapsed), today + timedelta(days=remaining)

    project.start_date, project.due_date = start.isoformat(), due.isoformat()
    project.status = "completed" if completed else ("pending" if done_n == 0 and wip == 0 else "in_progress")
    span_end = (due - timedelta(days=2)) if completed else today
    window = max(1.0, (span_end - start).days - 2.0)

    # sprint dates (equal slices of the project span)
    span = max(1, (due - start).days)
    for s, sp in enumerate(sprints):
        sp.start_date = (start + timedelta(days=span * s // n_spr)).isoformat()
        sp.end_date = (start + timedelta(days=span * (s + 1) // n_spr - 1)).isoformat()
        mods = list(dict.fromkeys(t["module"] for k, t in enumerate(tasks) if min(n_spr - 1, k * n_spr // n) == s))
        sp.goal = "Deliver: " + ", ".join(mods[:3])

    # Done tasks: completion times spread over the window in proportion to hours
    now = datetime.now(timezone.utc)
    cum_h = 0.0
    done_total = sum((tasks[i]["actual"] or tasks[i]["est"]) for i in range(done_n)) or 1.0
    for i in range(done_n):
        t, row = tasks[i], rows[i]
        h = t["actual"] or t["est"]
        cum_h += h
        offset = 1.0 + (cum_h / done_total) * window + rng.uniform(-0.3, 0.3)
        completed_at = min(_at(start) + timedelta(days=offset), now - timedelta(hours=2))
        created = _at(start) + timedelta(days=rng.uniform(0, 0.12 * max(1, elapsed)))
        started = max(created + timedelta(hours=1), completed_at - timedelta(days=h / HOURS_PER_DAY))
        if started >= completed_at:
            started = completed_at - timedelta(hours=1)
        on_time = rng.random() < (t["assignee"]["on_time"] if t["assignee"] else 0.7)
        slack_days = rng.uniform(0, 4) if on_time else -rng.uniform(1, 3)
        row.completed_at = completed_at
        row.created_at = created
        row.due_date = (completed_at.date() + timedelta(days=round(slack_days))).isoformat()
        t["created"], t["started"], t["done_at"] = created, started, completed_at

    # Open tasks: first `overdue` are already past due, the rest spread to the due date
    n_over = min(p.get("overdue", 0), len(open_idx))
    rest = len(open_idx) - n_over
    for k, i in enumerate(open_idx):
        row, t = rows[i], tasks[i]
        if k < n_over:
            lo = min(14, max(1, (today - start).days))
            row.due_date = (today - timedelta(days=rng.randint(1, lo))).isoformat()
        else:
            m = k - n_over
            row.due_date = (today + timedelta(days=max(1, math.ceil((m + 1) / max(1, rest) * remaining)))).isoformat()
        created = _at(start) + timedelta(days=rng.uniform(0, 0.12 * max(1, elapsed)))
        row.created_at = created
        t["created"] = created
        if t["status"] == "in_progress":
            t["started"] = min(now - timedelta(hours=3), created + timedelta(days=rng.uniform(0.5, max(1, elapsed * 0.5))))

    # 9. Activity history
    n_act = 0
    lead = user_rows[lead_key]
    db.add(ActivityLog(project_id=project.id, user_id=lead.id, action="project_created",
                       meta={"title": project.title}, created_at=_at(start)))
    for m in team:
        db.add(ActivityLog(project_id=project.id, user_id=lead.id, action="member_added",
                           meta={"user_id": m["id"], "name": USERS[m["key"]][0]},
                           created_at=_at(start, 0.2)))
        n_act += 1
    for i, t in enumerate(tasks):
        row = rows[i]
        actor = t["assignee"]["id"] if t["assignee"] else lead.id
        db.add(ActivityLog(project_id=project.id, user_id=lead.id, task_id=row.id, action="task_created",
                           meta={"title": t["title"], "status": "todo"}, created_at=t["created"]))
        n_act += 1
        if t["assignee"]:
            db.add(ActivityLog(project_id=project.id, user_id=lead.id, task_id=row.id, action="task_assigned",
                               meta={"assignee_id": t["assignee"]["id"]}, created_at=t["created"] + timedelta(hours=1)))
            n_act += 1
        if i in creep_log:
            old, new = creep_log[i]
            db.add(ActivityLog(project_id=project.id, user_id=actor, task_id=row.id, action="task_updated",
                               meta={"field": "estimate_hours", "from": old, "to": new},
                               created_at=now - timedelta(days=rng.uniform(1, max(2, elapsed * 0.6)))))
            n_act += 1
        if t["status"] in ("in_progress", "done"):
            db.add(ActivityLog(project_id=project.id, user_id=actor, task_id=row.id, action="task_moved",
                               meta={"from_status": "todo", "to_status": "in_progress"}, created_at=t["started"]))
            n_act += 1
        if t["status"] == "done":
            db.add(ActivityLog(project_id=project.id, user_id=actor, task_id=row.id, action="task_moved",
                               meta={"from_status": "in_progress", "to_status": "done"}, created_at=t["done_at"]))
            n_act += 1
    for i, j in sorted(deps):
        db.add(ActivityLog(project_id=project.id, user_id=lead.id, task_id=rows[i].id, action="dependency_added",
                           meta={"depends_on_id": rows[j].id}, created_at=tasks[i]["created"] + timedelta(hours=2)))
        n_act += 1

    # 10. Decisions
    for title, decision, reason, by, task_idx, days_ago in spec["decisions"]:
        when = now - timedelta(days=min(days_ago, max(1, (today - start).days - 1)))
        d = Decision(project_id=project.id, title=title, decision=decision, reason=reason,
                     made_by=user_rows[by].id,
                     related_task_id=rows[task_idx].id if task_idx is not None else None, created_at=when)
        db.add(d)
        db.add(ActivityLog(project_id=project.id, user_id=user_rows[by].id, action="decision_added",
                           meta={"title": title}, created_at=when))
        n_act += 1

    db.flush()
    return {"title": spec["title"], "tasks": n, "done": done_n, "deps": len(deps),
            "activity": n_act, "decisions": len(spec["decisions"]), "members": len(team) + 1,
            "project_id": project.id}


# ── Main ──────────────────────────────────────────────────────────────────────

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Rebuild the IntelliPM demo data.")
    ap.add_argument("--attach", metavar="EMAIL", help="also add this existing user as admin of every demo project")
    ap.add_argument("--verify", action="store_true", help="run seed.verify_demo afterwards")
    args = ap.parse_args(argv)

    import app.models  # noqa: F401  (register tables)
    Base.metadata.create_all(bind=engine)

    rng = random.Random(RNG_SEED)
    today = date.today()
    pw_hash = hash_password(DEMO_PASSWORD)

    with SessionLocal() as db:
        wipe(db)

        user_rows = {}
        for key, (name, skills, on_time) in USERS.items():
            u = User(email=f"{key}{DEMO_EMAIL_DOMAIN}", username=f"{key}_demo", full_name=name,
                     password_hash=pw_hash, skills=skills, on_time_rate=on_time)
            db.add(u)
            user_rows[key] = u
        email, username, full = PRESENTER
        presenter = User(email=email, username=username, full_name=full, password_hash=pw_hash,
                         skills={}, on_time_rate=0.9)
        db.add(presenter)
        db.flush()

        summaries = []
        for spec in PROJECTS:
            summaries.append(build_project(db, spec, user_rows, presenter, today, rng))

        attached = None
        if args.attach:
            ext = db.execute(select(User).where(User.email == args.attach)).scalar_one_or_none()
            if ext is None:
                print(f"! --attach: no user with email {args.attach}; register first.", file=sys.stderr)
            else:
                for s in summaries:
                    db.add(ProjectMember(project_id=s["project_id"], user_id=ext.id, role="admin",
                                         capacity_hours_per_week=PRESENTER_CAPACITY))
                attached = ext.email
        db.commit()

    print(f"Seeded demo data for {today.isoformat()} (RNG seed {RNG_SEED})")
    print(f"{'#':>2}  {'Project':<30}{'Tasks':>6}{'Done':>6}{'Deps':>6}{'Activity':>9}{'Decisions':>10}{'Members':>8}")
    for i, s in enumerate(summaries, 1):
        print(f"{i:>2}  {s['title']:<30}{s['tasks']:>6}{s['done']:>6}{s['deps']:>6}"
              f"{s['activity']:>9}{s['decisions']:>10}{s['members']:>8}")
    print(f"Totals: {len(USERS) + 1} users, {len(summaries)} projects, "
          f"{sum(s['tasks'] for s in summaries)} tasks, {sum(s['deps'] for s in summaries)} dependencies, "
          f"{sum(s['activity'] for s in summaries)} activity rows, {sum(s['decisions'] for s in summaries)} decisions")
    print(f"Login: {PRESENTER[0]} / {DEMO_PASSWORD}  (admin of all 16 projects)"
          + (f"; also attached {attached}" if attached else ""))

    if args.verify:
        from seed import verify_demo
        print()
        return verify_demo.main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
