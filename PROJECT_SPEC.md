# IntelliPM – PROJECT_SPEC.md

> **Every coding session: read this file and `PROGRESS.md` first. Build ONE module per session. Do not change the schema, API or formulas without updating this file in the same commit.**

## 1. What we are building

**IntelliPM** is a project-management web app (like Jira/Trello) with an **explainable decision-support layer**. A manager can:
1. Type a one-line project idea and get an AI-generated plan (modules, tasks, estimates, dependencies, sprints).
2. Get task-assignment recommendations based on skills, workload and past performance.
3. See a forecast completion date, delay probability, and a 0–100 project health score.
4. (Should-have) Keep a decision log and ask questions about the project.

**Principles**
- **The AI recommends, the manager decides.** Nothing is applied without a user click.
- **Every score shows its reason** (which factors, which numbers). No black boxes.
- **Honest about data:** estimation models are trained on public Jira data; risk scoring uses rules plus a classifier trained on *simulated* project histories (prototype).

## 2. Scope

| Priority | Feature | Module |
|---|---|---|
| MUST | Auth, projects, members (skills + capacity), tasks, Kanban, dependencies | M1–M3 |
| MUST | AI project generator (LLM) | M4 |
| MUST | Assignment optimizer + workload | M5 |
| MUST | Task-estimate model (public data) | M6 |
| MUST | Forecast (Monte Carlo) + health score | M7 |
| MUST | Risk classifier + effort benchmark page | M8 |
| MUST | Dashboard / analytics | M9 |
| MUST | 16 demo projects seeded | M10 |
| SHOULD | Dependency graph view | M11 |
| SHOULD | Decision log + project Q&A | M12 |
| STRETCH | WebSocket live board updates | M13 |
| FINAL | Postgres switch, deploy, freeze, tests, report, deck | M14–M15 |

**Cut line: end of Oct 11.** Anything in MUST not working by then is fixed first; SHOULD/STRETCH not started by then moves to "Future Scope" and the deck/synopsis are edited to match.

## 3. Final tech stack

- **Frontend:** React + Vite + Tailwind CSS, react-router-dom, axios, @tanstack/react-query, @dnd-kit (Kanban), @xyflow/react (dependency graph), recharts, lucide-react. JavaScript (no TypeScript).
- **Backend:** Python 3.11+, FastAPI + Uvicorn, Pydantic v2 (+ pydantic-settings), SQLAlchemy 2.0 (**sync**, `Mapped`/`mapped_column`/`select()` style), PyJWT, `bcrypt` package directly (not passlib).
- **Database:** SQLite for development, PostgreSQL for deployment. Switch only via `DATABASE_URL`. No Postgres-only features. `Base.metadata.create_all` + seed script; **no Alembic**.
- **LLM:** Groq (primary) via the `openai` SDK with `base_url`; Gemini free tier (backup); cached fallback JSON. All behind `services/llm.py`.
- **ML/Algorithms:** scikit-learn, pandas, numpy, scipy (`linear_sum_assignment`), joblib. Optional: sentence-transformers `all-MiniLM-L6-v2` (CPU fallback required).
- **Real-time (stretch):** FastAPI WebSockets.
- **Tests:** pytest (optimizer, forecast, health, estimator, auth).
- **Deploy:** Render (backend + static frontend) + Neon/Supabase/Render Postgres. No Docker required.

## 4. Repo structure

```
MajorProject/
  PROJECT_SPEC.md   PROGRESS.md   README.md   .gitignore
  Datasets/                      # gitignored: 16 story-point CSVs + nasa93*.arff
  backend/
    requirements.txt  .env.example
    app/
      main.py  config.py  database.py  models.py  schemas.py  security.py  deps.py
      routers/   auth.py projects.py members.py tasks.py sprints.py ai.py analytics.py decisions.py ws.py
      services/  llm.py planner.py assignment.py workload.py forecast.py health.py risk.py estimator.py qa.py
      ml/        train_estimator.py train_effort.py generate_synthetic.py train_risk.py artifacts/
      ai/        fallback_plan.json
    seed/        seed_demo.py demo_projects.py
    tests/
  frontend/
    src/ api/ components/ pages/ context/
```

`.gitignore` must contain: `.env`, `venv/`, `node_modules/`, `Datasets/`, `*.db`, `__pycache__/`, `dist/`.

## 5. Environment variables (`backend/.env`, never committed)

```
DATABASE_URL=sqlite:///./intellipm.db
SECRET_KEY=<generate-with-openssl-rand-hex-32>
ACCESS_TOKEN_EXPIRE_MINUTES=720
CORS_ORIGINS=http://localhost:5173
LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_API_KEY=<your-groq-api-key>
LLM_MODEL=openai/gpt-oss-120b
LLM_FALLBACK_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
LLM_FALLBACK_API_KEY=<your-gemini-api-key>
LLM_FALLBACK_MODEL=gemini-flash-latest
USE_CACHED_PLAN_ONLY=false
HOURS_PER_STORY_POINT=3
```
Provide `.env.example` with the same keys and empty values. Frontend: `VITE_API_BASE_URL=http://localhost:8000/api/v1`.

## 6. Data model (SQLAlchemy 2.0)

All tables have `id` (int PK) and `created_at`.

| Table | Columns |
|---|---|
| **users** | email (unique), username (unique), full_name, password_hash, skills (JSON dict `{"react":4,"python":5}`, levels 1–5), on_time_rate (float 0–1, default 0.7) |
| **projects** | title, description, status (`pending`/`in_progress`/`completed`), priority (`low`/`medium`/`high`), start_date, due_date, created_by → users |
| **project_members** | project_id, user_id, role (`admin`/`member`), capacity_hours_per_week (default 30); unique(project_id, user_id) |
| **sprints** | project_id, name, start_date, end_date, goal |
| **tasks** | project_id, sprint_id (nullable), title, description, status (`todo`/`in_progress`/`done`), priority (`low`/`medium`/`high`/`critical`), estimate_hours, actual_hours (nullable), assignee_id → users (nullable), due_date (nullable), required_skills (JSON list), completed_at (nullable), module (str, nullable) |
| **task_dependencies** | task_id, depends_on_id; unique pair; reject cycles and self-reference |
| **decisions** | project_id, title, decision, reason, made_by → users, related_task_id (nullable) |
| **activity_log** | project_id, user_id, task_id (nullable), action (str), meta (JSON) |

Rules: every create/update/move/assign writes an `activity_log` row. Setting status to `done` sets `completed_at`; moving away clears it. Deleting a project cascades to its children. Only a project `admin` can delete a project, remove members, or apply AI plans/assignments; any member can edit tasks.

## 7. API (prefix `/api/v1`, JSON, JWT bearer auth except register/login)

Response envelope: `{ "success": true, "data": ..., "message": "..." }`. Errors: `{ "success": false, "message": "...", "errors": [] }` with proper status codes.

**Auth:** `POST /auth/register` (email, username, full_name, password) · `POST /auth/login` · `GET /auth/me` · `PATCH /auth/me` (full_name, skills)
**Projects:** `GET/POST /projects` · `GET/PATCH/DELETE /projects/{id}` (list returns task_count, member_count, done_ratio, health_score)
**Members:** `GET/POST /projects/{id}/members` (by email, role, capacity) · `PATCH/DELETE /projects/{id}/members/{user_id}`
**Tasks:** `GET/POST /projects/{id}/tasks` · `GET/PATCH/DELETE /tasks/{id}` · `POST /tasks/{id}/dependencies` · `DELETE /tasks/{id}/dependencies/{dep_id}`
**Sprints:** `GET/POST /projects/{id}/sprints` · `PATCH/DELETE /sprints/{id}`
**AI:**
- `POST /ai/generate-plan` `{description, team_size?, duration_weeks?}` → **draft plan JSON, not saved**
- `POST /projects/{id}/apply-plan` `{plan}` → creates sprints, tasks, dependencies (admin only)
- `POST /projects/{id}/assignments/recommend` → recommendations with reasons (not applied)
- `POST /projects/{id}/assignments/apply` `{assignments:[{task_id,user_id}]}` (admin only)
- `POST /ai/estimate` `{title, description}` → `{story_points, hours, model}`
- `POST /projects/{id}/ask` `{question}` → `{answer, sources:[{type,id}]}` (M12)
**Analytics:** `GET /projects/{id}/analytics/health` · `/forecast` · `/workload` · `/burndown` · `GET /ml/effort-benchmark`
**Decisions:** `GET/POST /projects/{id}/decisions` · `DELETE /decisions/{id}`
**Realtime (M13):** `WS /ws/projects/{id}?token=...` broadcasts `{type:"task_updated"|"task_created"|"task_deleted", task}`.
`GET /health` returns `{status:"ok"}`.

## 8. Algorithms (exact definitions, so we can explain them in the viva)

### 8.1 LLM planner (`services/planner.py`, `services/llm.py`)
- One function `generate_plan(description, team_size, duration_weeks)`.
- Ask for **JSON only** matching this Pydantic schema (validate; on failure retry once; then try fallback provider; then `ai/fallback_plan.json`):
```
Plan { project_title, summary,
       sprints: [ { name, goal } ],
       tasks: [ { title, description, module, priority(low|medium|high|critical),
                  estimate_hours(int 1-40), required_skills[str], sprint_index(int),
                  depends_on[str titles] } ] }
```
- Post-process: drop unknown dependency titles, break any cycle, clamp estimates to 1–40h, lowercase skills, cap to 40 tasks.
- Response includes `source: "llm" | "fallback"` so the UI can show it.

### 8.2 Assignment optimizer (`services/assignment.py`)
For each unassigned task *t* and member *m* (from project_members):
- `skill_match` = average over required skills of `level/5` (0 if member lacks it); if the task has no required skills, 0.5.
- `availability` = `clip(1 − (current_open_hours_m + estimate_t) / capacity_total_m, 0, 1)` where `capacity_total_m = capacity_hours_per_week × weeks_remaining` (min 1 week).
- `performance` = `user.on_time_rate`.
- `score = 0.5·skill_match + 0.3·availability + 0.2·performance`; `cost = 1 − score`.
- Solve with `scipy.optimize.linear_sum_assignment`. To let a member take several tasks, give each member `k` slots, `k = max(1, floor(remaining_capacity_hours / 8))`, process tasks in priority order in batches of (total slots), and update each member's load between batches.
- Output per task: `{task_id, user_id, score, skill_match, availability, performance, reason}` where `reason` is a one-sentence plain-English explanation built from the three numbers.

### 8.3 Workload (`services/workload.py`)
`utilization_m = open_estimate_hours_assigned_m / (capacity_hours_per_week × weeks_remaining)`.
Labels: `> 1.0` overloaded · `0.8–1.0` at risk · `0.4–0.8` healthy · `< 0.4` available.

### 8.4 Forecast (`services/forecast.py`) – Monte Carlo
- Inputs: open tasks, their estimates, dependencies, members' capacities.
- Each simulation (default 5,000): for every open task sample `actual = estimate × lognormal(mu, sigma)` with defaults `mu=0.1, sigma=0.35` (overrun is typical). If the project has ≥10 completed tasks with `actual_hours`, calibrate `mu, sigma` from `ln(actual/estimate)` instead.
- `effective_hours_per_day = sum(capacity_hours_per_week)/5 × 0.7` (focus factor 0.7).
- `one_person_hours_per_day = (average capacity_hours_per_week / 5) × 0.7`.
- `duration_days = max( total_sampled_hours / effective_hours_per_day , critical_path_sampled_hours / one_person_hours_per_day )`, i.e. the larger of (a) the time to do all the work in parallel across the team and (b) the time to do the longest dependency chain one task after another. `critical_path_sampled_hours` is the largest sum of sampled hours along any chain of dependent open tasks.
- Output: P50/P80/P90 completion dates, `delay_probability = share of simulations finishing after project.due_date`, histogram buckets for a chart, plus the assumptions used.

### 8.5 Health score (`services/health.py`)
```
expected = elapsed_days / total_days            (clip 0..1)
actual   = done_hours / total_hours             (0 if no tasks)
slip     = max(0, expected − actual)
health = 100 − 30·overdue_ratio − 20·blocked_ratio
             − 15·min(1, max(0, max_utilization − 1))
             − 35·min(1, slip / 0.30)
```
`overdue_ratio` = open tasks past due ÷ open tasks; `blocked_ratio` = open tasks whose dependency is not done ÷ open tasks. Clip to 0–100. Levels: ≥75 **Low risk**, 50–74 **Medium**, <50 **High**. Return the four penalty values so the UI can show *why*.

### 8.6 Task-estimate model (`ml/train_estimator.py`, `services/estimator.py`)
- Data: the 16 CSVs in `Datasets/` (columns `issuekey,title,description,storypoint,split_mark`). Add a `project` column from the file name. Use `split_mark` for train/validation/test.
- Model v1: TF-IDF on `title + " " + description` → Ridge (or RandomForest). Report MAE and MdAE on test **vs. a predict-the-median baseline**. Save with joblib to `ml/artifacts/estimator.joblib`.
- Model v2 (optional, only after v1 works): MiniLM embeddings + Ridge; keep whichever is better *and* explainable. Code must run on CPU if CUDA is absent.
- Runtime: `hours = story_points × HOURS_PER_STORY_POINT` (assumption, documented).

### 8.7 Risk classifier and effort benchmark (`ml/…`)
- `generate_synthetic.py` simulates ≥3,000 project snapshots (team size, utilization, overdue_ratio, blocked_ratio, slip, remaining_hours / available_hours, etc.) and labels `delayed` using the Monte Carlo outcome plus noise. **Document that this is simulated data.**
- `train_risk.py` trains a scikit-learn classifier (LogisticRegression or GradientBoosting); report accuracy, precision/recall, confusion matrix, and feature importances. UI shows the probability next to the rule-based health score, with the top 3 contributing factors.
- `train_effort.py`: load `Datasets/nasa93.arff` with `scipy.io.arff`, convert COCOMO rating labels (`vl,l,n,h,vh,xh`) to ordered numbers, train a regressor for person-months, report cross-validated MAE/R². Exposed at `GET /ml/effort-benchmark` and shown on a page labelled **"benchmark on public NASA93 data (93 projects)"**.

### 8.8 Decision log and Q&A (M12)
Decisions are stored with reasons. `POST /ask` builds a context string from the project's tasks, decisions and last 50 activity rows (truncate to a safe size), asks the LLM to answer **only from that context** and to cite item ids, and returns `answer + sources`. If the context lacks the answer, the reply says so.

## 9. Frontend pages

Login · Register · **Dashboard** (project cards with status, progress, health badge) · **Project** with tabs: **Board** (Kanban, drag and drop, task drawer showing details, assignee and dependencies) · **Plan** (AI generator: input → draft preview → Apply) · **Team** (members, skills, capacity, workload bars, "Recommend assignments" with reasons → Apply) · **Analytics** (health score with penalty breakdown, forecast histogram with P50/P80/P90, burndown, risk probability) · **Graph** (dependencies, M11) · **Decisions** (log + Ask box, M12) · **Benchmarks** (NASA93 and estimator metrics).
Show loading and error states. Show a small "AI: LLM" / "AI: cached fallback" label on generated plans.

## 10. Demo data (16 hand-designed projects, `seed/demo_projects.py`)

A pool of **12 fictional users** with distinct skills (frontend, backend, ML, QA, DevOps, design) and on-time rates. Seed with `python -m seed.seed_demo` (idempotent: wipes and recreates). Each project has 8–30 tasks with realistic titles, estimates, some `actual_hours`, dependencies and activity history.

| # | Project | Story it demonstrates |
|---|---|---|
| 1 | Hospital Management System | Healthy, on track |
| 2 | E-commerce Platform | Delayed, high delay probability |
| 3 | Mobile Banking App | One developer severely overloaded |
| 4 | University Portal | Blocked dependency chain |
| 5 | Food Delivery App | Nearly finished |
| 6 | Library Management | Just started (all tasks unassigned → assignment demo) |
| 7 | Smart Attendance (ML) | ML-skilled work, few matching members |
| 8 | Online Exam System | Medium risk, deadline close |
| 9 | Real-Estate Listing Site | Overdue tasks pile up |
| 10 | Travel Planner | Well balanced team |
| 11 | Inventory Tracker | Underused member available |
| 12 | Chat Application | Scope creep (estimates growing) |
| 13 | Learning Management System | Large project, multiple sprints |
| 14 | Fitness Tracker | Completed project (history for calibration) |
| 15 | IoT Dashboard | Dependencies on a late backend |
| 16 | Event Booking System | Decision log heavy (M12 demo) |

Add 2–4 spares if time allows. Dates are generated **relative to today** so the demo is never stale.

## 11. Module list and "done when" tests

| Module | Build | Done when |
|---|---|---|
| **M0** | Repo, venv, `.gitignore`, FastAPI skeleton with `/health`, CORS, config, DB session; Vite + Tailwind shell | `GET /health` returns ok; frontend loads and calls it |
| **M1** | Auth (register/login/me), password hashing, JWT, frontend login/register + protected routes | Can register, log in, refresh page and stay logged in; wrong password rejected |
| **M2** | Projects + members + user skills + capacity | Create project, add member by email, set skills/capacity; non-admin cannot delete |
| **M3** | Tasks, Kanban drag/drop, dependencies (cycle check), activity log | Move a card; refresh; state persists; cycle rejected; activity rows written |
| **M4** | LLM wrapper, `generate-plan`, `apply-plan`, fallback | A one-line idea gives a valid plan in the UI; with `USE_CACHED_PLAN_ONLY=true` the fallback loads |
| **M5** | Assignment optimizer + workload API + Team tab | Recommend → Apply works; every row shows a reason; unit test passes on a hand-built 3×3 case |
| **M6** | Train estimator; `/ai/estimate`; planner uses it to sanity-check estimates | Metrics file shows MAE vs baseline; endpoint returns a number |
| **M7** | Forecast + health APIs | Unit tests: more overdue → lower health; more capacity → earlier P50 |
| **M8** | Synthetic data, risk classifier, NASA93 benchmark | Metrics saved; both shown in UI |
| **M9** | Dashboard + Analytics tab with charts | Seeded project shows health, forecast histogram, burndown, workload |
| **M10** | `seed_demo.py` with all 16 projects | One command rebuilds all demos; each tells its intended story |
| **M11** | Dependency graph (React Flow) | Blocked tasks highlighted |
| **M12** | Decisions + Ask | Question about a seeded decision returns an answer with sources |
| **M13** | WebSocket live updates | Two browsers see a card move |
| **M14** | Postgres switch, deploy, feature freeze | App runs on Postgres locally and deployed; demo script rehearsed |
| **M15** | Tests, README, report, updated deck | `pytest` green; docs match the real product |

## 12. Rules for AI coding sessions

1. Read `PROJECT_SPEC.md` and `PROGRESS.md` first. Work on **one module**.
2. Use SQLAlchemy **2.0** style and Pydantic **v2**. Do not use `session.query()`.
3. Keep routers thin; put logic in `services/`. Algorithms must follow section 8 exactly; if you want to change one, say so and update this file.
4. No secrets in code. Read config from environment.
5. Write the unit tests listed for the module and run them. Run the app and exercise the feature once before declaring it done.
6. At the end of the session: update `PROGRESS.md` (status, what changed, known bugs, next step) and make a git commit.
7. Explain anything non-obvious in a short comment: the author must be able to defend the code in a viva.
8. Do not add features that are not in this spec.
