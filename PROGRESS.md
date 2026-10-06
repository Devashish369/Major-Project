# IntelliPM – PROGRESS.md

> Update this file at the END of every coding session, then `git commit`.
> Deadline: **demo on Oct 17, 2026**. Cut line: **end of Oct 11**. Feature freeze: **Oct 14**.

## Current status

- **Current module:** M11 ☑ DONE – next is M12 (Decision log + Ask)
- **Last session:** 2026-10-06 / Claude Code / M11 Dependency graph tab
- **Known bugs:** none
- **Next step:** M12 – decisions CRUD, POST /projects/{id}/ask (mocked-LLM tests), Decisions tab
- **Rebuild demo data (one command, from `backend/`):** `python -m seed.seed_demo --verify`  → login `demo@intellipm.demo` / `Demo@1234` (add `--attach your@email` to also add your own account)

## Module checklist

| Module | Description                               | Priority | Status | Target date |
| ------ | ----------------------------------------- | -------- | ------ | ----------- |
| M0     | Repo, backend skeleton, frontend shell    | MUST     | ☑     | Oct 5       |
| M1     | Auth                                      | MUST     | ☑     | Oct 6       |
| M2     | Projects, members, skills, capacity       | MUST     | ☑     | Oct 6       |
| M3     | Tasks, Kanban, dependencies, activity log | MUST     | ☑     | Oct 7       |
| M4     | AI planner (LLM + fallback)               | MUST     | ☑     | Oct 8       |
| M5     | Assignment optimizer + workload           | MUST     | ☑     | Oct 5       |
| M6     | Estimator model on public data            | MUST     | ☑     | Oct 5       |
| M7     | Forecast + health score                   | MUST     | ☑     | Oct 6       |
| M8     | Risk classifier + NASA93 benchmark        | MUST     | ☑     | Oct 6       |
| M9     | Dashboard + analytics charts              | MUST     | ☑     | Oct 11      |
| M10    | 16 demo projects seeded                   | MUST     | ☑     | Oct 12      |
| M11    | Dependency graph                          | SHOULD   | ☑     | Oct 12      |
| M12    | Decision log + Ask                        | SHOULD   | ☐     | Oct 13      |
| M13    | WebSocket live updates                    | STRETCH  | ☐     | Oct 13      |
| M14    | Postgres switch, deploy, freeze           | FINAL    | ☐     | Oct 14      |
| M15    | Tests, README, report, deck               | FINAL    | ☐     | Oct 15      |
| —     | Rehearsal only, no new features           | —       | ☐     | Oct 16–17  |

Mark ☑ only after the module's **"done when"** test in `PROJECT_SPEC.md` section 11 passes.

## Decisions made (keep short)

- Stack: React+Vite+Tailwind / FastAPI / SQLAlchemy 2.0 (sync) / SQLite→Postgres / Groq LLM with fallback.
- No model training of LLMs. Estimator = TF-IDF+Ridge on 16 public Jira CSVs. Risk classifier = trained on simulated data (disclosed).
- Datasets live in `Datasets/` (gitignored): 16 story-point CSVs and `nasa93.arff`, `nasa93-dem.arff`.
- GPU (RTX 3050 4GB) is optional, used only for sentence embeddings; code must fall back to CPU.

## Session log

| Date       | Account        | Module | What was done                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         | Bugs / notes                                                                                                                                                                                              |
| ---------- | -------------- | ------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 2026-10-05 | Antigravity AI | M0     | Folder structure, backend venv + requirements.txt, config.py (pydantic-settings), database.py (SQLAlchemy 2.0 sync engine), main.py (CORS, response envelope ok()/err(), global error handler, GET /api/v1/health), .gitignore, .env.example, models.py placeholder, ai/fallback_plan.json; Vite+React+Tailwind v4 frontend with react-query, axios, react-router-dom, lucide-react; HealthPage.jsx calls /health and shows live JSON response                                                                                                                                                                                                                                                                        | Tailwind v4 default @theme imported Inter from Google Fonts causing PostCSS ordering error → fixed by using tailwindcss/preflight + tailwindcss/utilities separately and loading Inter via HTML link tag |
| 2026-10-05 | Antigravity AI | M1     | models.py (User, SQLAlchemy 2.0), schemas.py (Pydantic v2 UserCreate/Login/Update/Out, TokenOut), security.py (bcrypt hash/verify, PyJWT create/decode), deps.py (get_current_user), routers/auth.py (register/login/me/patch-me), main.py updated to lifespan pattern + auth router; frontend: AuthContext (localStorage + /me validation on mount), ProtectedRoute, LoginPage, RegisterPage, DashboardPage placeholder; 18/18 pytest tests pass                                                                                                                                                                                                                                                                     | Added email-validator dep for Pydantic EmailStr; replaced deprecated on_event with lifespan context manager                                                                                               |
| 2026-10-05 | Antigravity AI | M2     | models.py: Project + ProjectMember (SQLAlchemy 2.0, cascade, UniqueConstraint); schemas.py: ProjectCreate/Update/Out + MemberAdd/Update/Out; deps.py: get_membership (404 non-members) + require_admin (403); routers/projects.py + routers/members.py (last-admin guard); conftest.py refactored as shared fixture; 40/40 tests; frontend: DashboardPage (project grid + New Project modal), ProjectPage (Overview + Team tabs), CreateProjectModal, AddMemberModal, SkillsEditor slide-out panel, api/projects.js                                                                                                                                                                                                   | none                                                                                                                                                                                                      |
| 2026-10-05 | Antigravity AI | M3     | models.py: Task (completed_at, required_skills JSON, sprint_id nullable) + TaskDependency (UniqueConstraint, cascade) + ActivityLog (append-only audit) + Sprint; schemas.py: TaskCreate/Update/Out + DependencyAdd/Out + ActivityLogOut; services/tasks.py: apply_status_change (completed_at rule), write_activity (audit), has_cycle (DFS O(V+E)); routers/tasks.py: full CRUD + dep add/remove (cycle-checked) + activity endpoint; routers/projects.py updated with real task_count/done_ratio; 59/59 tests; frontend: KanbanBoard (@dnd-kit, 3 columns, drag persists via PATCH), TaskDrawer (inline edit, deps, completed_at), CreateTaskModal, api/tasks.js; Board tab added to ProjectPage (default)         | none                                                                                                                                                                                                      |
| 2026-10-05 | Antigravity AI | M4     | ai/fallback_plan.json (15-task hospital system, 4 sprints); services/llm.py (openai SDK, Groq primary + Gemini fallback, temp=0, 30s timeout); services/planner.py (Plan/TaskPlan/SprintPlan Pydantic schemas, generate_plan with 4-level fallback flow, DFS cycle-break, clamp hours, lowercase skills, cap 40 tasks); routers/ai.py (POST /ai/generate-plan + POST /projects/{id}/apply-plan admin-only atomic transaction); schemas.py M4 additions; config.py env_file tuple fix; 77/77 tests; frontend: PlanTab.jsx (description input, team size, duration, source badge AI/Cached, sprint accordion, apply button); api/ai.js; Plan tab in ProjectPage; Live Groq (openai/gpt-oss-120b) verified with real key | Groq model name in .env.example was incorrect; corrected to openai/gpt-oss-120b |
| 2026-10-05 | Antigravity AI | M5     | services/assignment.py (scipy linear_sum_assignment, skill_match=avg(level/5) or 0.5, availability=clip(1-(open+est)/cap,0,1), score=0.5sm+0.3av+0.2perf, k-slots per member, priority-ordered batching, zero-capacity guard, plain-English reason); services/workload.py (utilization ratio, 4 labels); routers/assignments.py (POST /recommend no-DB-write, POST /apply admin-only atomic, GET /analytics/workload); 105/105 tests; frontend: WorkloadBar (colour-coded labels), RecommendPanel (table + Apply), TeamTab rewritten; api/assignments.js | none |
| 2026-10-05 | Antigravity AI | M6     | ml/train_estimator.py (loads 16 CSVs from Datasets/marked_data/, adds project col, drops null sp, TF-IDF(20k bigrams sublinear)+Ridge on log1p(sp) target, expm1 inverse, clips [0.5,40], beats predict-the-median baseline: test MAE 3.14 < 3.26, MdAE 1.89 < 2.0); ml/artifacts/estimator.joblib + estimator_metrics.json committed; services/estimator.py (lazy-load, clip, hours=sp×HOURS_PER_STORY_POINT); routers/ai.py extended with POST /ai/estimate; schemas EstimateRequest; 117/117 tests; frontend: api/estimator.js; PlanTab shows model estimate alongside LLM, flags >3× divergence with ⚠ review badge; never overwrites LLM value | Path bug: _JOBLIB_PATH was parent.parent (→ app/ml/) not parent.parent.parent (→ ml/); fixed |
| 2026-10-06 | Antigravity AI | M7     | services/forecast.py (5000-run Monte Carlo, seeded RNG seed=42, log-normal overrun mu=0.1 sigma=0.35, critical-path DFS over dependency DAG, effective_per_day=sum(cap)/5×0.7, parallel vs CP duration=max, auto-calibrate mu/sigma from ≥10 completed tasks, 30-bin histogram with zero-range guard); services/health.py (exact spec formula: 100−30×overdue−20×blocked−15×overload−35×slip, 4 penalties returned, 3 levels); routers/analytics.py (GET /analytics/forecast + GET /analytics/health, both member-only 404); projects.py _project_out now calls compute_health (replaces None placeholder); 146/146 tests (29 new M7 tests) | Calibration test used identical ratios → sigma=0 → histogram crash; fixed by zero-range guard and varied test data |
| 2026-10-06 | Antigravity AI | M8     | ml/generate_synthetic.py (4000 snapshots, 8 features, 200-sim MC labelling + 8% noise); ml/train_risk.py (GradientBoostingClassifier n_estimators=200 depth=4 lr=0.05; acc=93.4% prec=92.1% rec=91.2%; saves risk_model.joblib + risk_model_metrics.json; clearly documents SIMULATED data); ml/train_effort.py (NASA93 93 projects, COCOMO ratings vl/l/n/h/vh/xh → 0-5, GBR 5-fold CV MAE + R², saves effort_model.joblib + effort_model_metrics.json); services/risk.py (lazy-load, predict_proba, top_3_factors by importance); health endpoint enriched with risk field; GET /ml/effort-benchmark; BenchmarksPage.jsx (3 sections: NASA93, risk disclaimer, task estimator; feature bars, confusion matrix); App.jsx /benchmarks route; 169/169 tests (23 new M8) | Test path: parent.parent.parent gave MajorProject/ml instead of backend/ml; fixed to parent.parent |
| 2026-10-06 | Claude Code | M9 | services/burndown.py (ideal = straight line total_hours→0 over start..due; actual = total − estimate of tasks with completed_at ≤ day, null after today); GET /projects/{id}/analytics/burndown (member-only, thin router); frontend: api/analytics.js, AnalyticsTab.jsx (recharts: health score + 4 penalty bars, ML delay-risk % + top factors, forecast histogram with P50/P80/P90 + due-date reference lines, burndown line chart, workload bars), every card has loading/empty/error(+Retry) states; Analytics tab in ProjectPage; Dashboard cards show Low/Medium/High risk badge from health_score; 173/173 tests (4 new burndown tests) | Fixed benchmarks.js importing nonexistent './axios' (build was broken). Risk card shows empty state when project has no tasks (model gave 98% for empty project). Cards treat pending/paused queries as loading. |
| 2026-10-06 | Claude Code | M10 | seed/demo_projects.py (12 users with distinct skills/on-time rates, 16 projects of 9-30 tasks each: estimates, dependencies, decisions, per-story tuning knobs); seed/seed_demo.py (idempotent: wipes only @intellipm.demo users + their projects; fixed RNG seed; all dates relative to today; each project's due date = today + slack × its own Monte Carlo P50 and start date set from the intended slip, so stories stay true on any day; actual_hours on ~90% of finished tasks; activity history incl. scope-creep estimate changes; 252 tasks, 58 deps, ~900 activity rows, 28 decisions); seed/verify_demo.py (calls the real health/forecast APIs and prints designed vs actual level + delay band; exit 1 on mismatch); Decision model added to models.py (table only, CRUD is M12); 176 tests (3 new data-definition tests) | Presenter account demo@intellipm.demo is admin of all 16 projects with 10 h/week capacity (it contributes slightly to capacity and shows as 'available'). First run had 12/16 stories right; fixed by raising slip/overdue and by sizing the done set for expected overrun. |
| 2026-10-06 | Claude Code | M11 | components/GraphTab.jsx (@xyflow/react): one node per task, edges prerequisite→dependent, node colour by status, blocked (open task with an unfinished dependency) red with animated red edges, layered layout (column = dependency depth, longest path), legend + blocked count, click node opens the existing TaskDrawer, empty state; Graph tab in ProjectPage; no backend change (task payload already has `dependencies`). Checked on seeded IoT Dashboard: 16 nodes, 14 edges, 7 red nodes = 7 blocked computed from the API; click opens correct task | Fixed a real bug since M0: index.css never imported tailwindcss/theme, so every theme-based class (bg-slate-*, px-*, text-*) generated no CSS and the whole app looked unstyled; added `@import "tailwindcss/theme"`. Nodes given explicit width/height so React Flow renders without waiting for measurement. No frontend test runner is configured, so no automated test for the layout function. |

## Human checklist (do these yourself, not the AI)

- [ ] `git init` in `MajorProject`, `.gitignore` created before the first commit
- [ ] Rotate any key that was ever committed; never commit `.env`
- [ ] After each module: run the app and click through the feature once
- [ ] Commit after every working module (`git commit -m "M3: kanban + dependencies"`)
- [ ] Oct 14: Opus review with the checklist below, then fix only real bugs
- [ ] Update the deck/synopsis to match what was actually built

## Prompt to start / resume ANY session (paste this)

```
You are working on IntelliPM, a FastAPI + React project. First read PROJECT_SPEC.md and
PROGRESS.md in the repo root. Work ONLY on module <Mx> from the spec. Follow the data model,
API, and algorithm definitions exactly (SQLAlchemy 2.0 style, Pydantic v2, no Alembic).
Keep routers thin and logic in services/. Write the tests listed for the module and run them,
then run the app and exercise the feature. Do not add features not in the spec. At the end,
update PROGRESS.md (status, changes, known bugs, next step) and give me the git commit command.
If something in the spec is ambiguous, ask me before inventing.
```

## First prompt (M0) – paste after the generic prompt

```
Module M0. Create the folder structure from section 4 of the spec. Backend: Python 3.11+ venv,
requirements.txt (fastapi, uvicorn[standard], sqlalchemy>=2, pydantic>=2, pydantic-settings,
pyjwt, bcrypt, openai, scikit-learn, pandas, numpy, scipy, joblib, pytest, python-multipart),
config.py reading .env, database.py (sync engine, SessionLocal, get_db, Base), main.py with
CORS, the response envelope helpers, a global error handler, and GET /api/v1/health. Create
.env.example and .gitignore exactly as specified. Frontend: Vite React app with Tailwind,
react-router-dom, axios, @tanstack/react-query, lucide-react, and a page that calls /health
and shows the result. Give exact commands to run both servers.
```

## Final review checklist for Opus (Oct 14)

Review the repo against PROJECT_SPEC.md and report only concrete problems:

1. Does each API in section 7 exist and match the envelope and permissions rules?
2. Do assignment, workload, forecast and health follow section 8 exactly? Show any deviation.
3. Any endpoint missing auth or an admin check? Any SQL/IDOR issue (user reading another project's data)?
4. Any secret committed or hard-coded? Any use of deprecated SQLAlchemy 1.x patterns?
5. Do the unit tests listed per module exist and pass?
6. Does the app still work with `USE_CACHED_PLAN_ONLY=true` and with a missing LLM key?
7. List bugs by severity. Do not suggest new features.
