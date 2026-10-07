# IntelliPM

**AI-assisted project management** – like Jira/Trello, plus an *explainable* decision-support layer: it plans a project from one sentence, recommends who should do what, forecasts when you will really finish, scores project health, and answers questions about your own project's history.

Every number the AI layer shows can be traced to a formula or a model described in [How the algorithms work](#how-the-algorithms-work).

## Contents

1. [Features](#features) · 2. [Architecture](#architecture) · 3. [Run it locally](#run-it-locally) · 4. [Environment variables](#environment-variables) · 5. [Rebuild the demo data](#rebuild-the-demo-data) · 6. [Tests](#tests) · 7. [Deployment](#deployment-render--neon-no-docker) · 8. [How the algorithms work](#how-the-algorithms-work) · 9. [Data sources and licences](#data-sources-and-licences) · 10. [Known limitations](#known-limitations) · 11. [API](#api)

## Features

| Area | What you can do | Where |
|---|---|---|
| Projects & team | Create projects, add members by e-mail, set roles, weekly capacity and 1–5 skill levels | Dashboard, Team tab, profile |
| Kanban | Drag tasks between To do / In progress / Done, edit in a drawer, add dependencies (cycles rejected), full activity log | Board tab |
| AI planner | One sentence → draft plan (sprints, tasks, estimates, dependencies). Labelled "AI Generated" or "Cached Plan". Admin applies it. | Plan tab |
| Estimate check | A model trained on 23,000 real Jira issues suggests hours next to the LLM's; large disagreements are flagged | Plan tab |
| Assignment | Optimal task → person matching with a plain-English reason for every row | Team tab |
| Workload | Utilisation bars: overloaded / at risk / healthy / available | Team + Analytics tabs |
| Forecast | Monte Carlo P50 / P80 / P90 finish dates and probability of missing the due date | Analytics tab |
| Health score | 0–100 with the four penalties that explain it; Low / Medium / High risk badge on every dashboard card | Analytics tab, Dashboard |
| Delay risk (ML, experimental) | Probability of finishing late with the factors that drive it for this project. Trained on **simulated** data and labelled experimental in the UI; the Monte Carlo forecast is the primary estimate | Analytics tab |
| Burndown | Ideal vs actual remaining hours per day | Analytics tab |
| Dependency graph | One node per task, blocked tasks in red, click to open the task | Graph tab |
| Live updates | When a teammate creates, edits, moves or deletes a task, your Board and Graph update without a refresh (small "Live" badge; falls back to normal REST if the socket is unavailable) | Board / Graph tabs |
| Decision log + Ask | Record decisions with reasons; ask questions and get answers that cite their sources | Decisions tab |
| Project report | One printable report per project: executive summary, key insights and suggested actions written by fixed rules (no LLM) from the health score, forecast, workload, ML risk, overdue and blocked tasks, decisions and activity. "Print / Save as PDF" | Report tab |
| Benchmarks | Metrics of the estimator, the risk model and the NASA93 effort benchmark | `Benchmarks` button on the dashboard |

## Architecture

```
 Browser (React SPA, Vite build)
   │  axios → JSON + JWT bearer token
   ▼
 FastAPI app  (backend/app)
   ├─ routers/   thin HTTP layer: auth, projects, members, tasks, ai, assignments, analytics, decisions
   ├─ services/  all logic: planner, llm, assignment, workload, forecast, health, burndown,
   │             estimator, risk, ask, tasks (status rules, cycle check, audit log),
   │             realtime (WebSocket rooms per project; events published after each commit)
   ├─ models.py  SQLAlchemy 2.0 tables (users, projects, project_members, sprints, tasks,
   │             task_dependencies, activity_log, decisions)
   └─ database.py  one engine; SQLite in development, PostgreSQL in deployment (DATABASE_URL only)
   │
   ├──► LLM providers (Groq primary → Gemini fallback → cached plan JSON)   via the openai SDK
   └──► ml/artifacts/*.joblib   estimator + risk model + NASA93 effort model, loaded lazily
```

* **Thin routers, logic in services** – every algorithm can be unit-tested without HTTP.
* **Response envelope** – success `{"success": true, "data": …, "message": …}`; errors `{"success": false, "message": …, "errors": […]}` (a `detail` key is kept too).
* **Permissions** – non-members always get `404` (project ids cannot be guessed); only project admins can delete projects, remove members, change roles, and apply AI plans or assignments.

```
MajorProject/
  README.md  PROJECT_SPEC.md  PROGRESS.md  DEMO_SCRIPT.md  SPEC_DIFFERENCES.md  render.yaml
  backend/
    requirements.txt  .env.example
    app/      main.py config.py database.py models.py schemas.py deps.py security.py
              routers/  services/  ai/fallback_plan.json
    ml/       generate_synthetic.py  train_estimator.py  train_risk.py  train_effort.py
              artifacts/ (committed models + metrics)
    seed/     demo_projects.py  seed_demo.py  verify_demo.py
    tests/
  frontend/
    src/  api/  components/  pages/  context/
  Datasets/   (not committed: 16 Jira CSVs + NASA93 ARFF files)
```

| Layer | Technology |
|---|---|
| Frontend | React 19, Vite, Tailwind CSS v4, react-router-dom, axios, @tanstack/react-query, @dnd-kit (Kanban), @xyflow/react (graph), recharts, lucide-react |
| Backend | Python 3.13, FastAPI + Uvicorn, Pydantic v2, SQLAlchemy 2.0 (sync), PyJWT, bcrypt |
| Database | SQLite (dev) → PostgreSQL (production, e.g. Neon), switched only by `DATABASE_URL` |
| LLM | Groq (primary) / Gemini (fallback) through the `openai` SDK |
| ML | scikit-learn, pandas, numpy, scipy (`linear_sum_assignment`), joblib |

## Run it locally

Prerequisites: Python 3.13 (3.11+ works for development), Node 20.19+ (22 recommended).

### Quickest: one command for both servers

After the one-time setup below (backend venv + `pip install -r requirements.txt`, and `backend/.env`), run from the repo root:

```bash
python dev.py            # backend http://localhost:8000  +  frontend http://localhost:5173  (Ctrl+C stops both)
python dev.py --seed     # same, but rebuilds the demo data first
```

(`npm install` in `frontend/` is run for you the first time.) The two steps below are the same thing done by hand.

### 1. Backend

```bash
cd backend
python -m venv venv
# Windows: run venv\Scripts\activate    macOS/Linux: run source venv/bin/activate
pip install -r requirements.txt
copy .env.example .env           # macOS/Linux: cp .env.example .env  – then fill in the keys
uvicorn app.main:app --reload --port 8000
```

Tables are created automatically on start-up. Swagger docs: http://localhost:8000/docs

### 2. Frontend

```bash
cd frontend
npm install
copy .env.example .env           # macOS/Linux: cp .env.example .env
npm run dev                      # http://localhost:5173
```

### Running on PostgreSQL locally

Put a PostgreSQL URL in `DATABASE_URL` (and a real `SECRET_KEY`) and start the backend as usual; nothing else changes.
`postgres://…` and `postgresql://…` URLs are accepted as-is (the app selects the psycopg 3 driver).

## Environment variables

`backend/.env` (never committed; copy from `.env.example`):

| Variable | Meaning |
|---|---|
| `DATABASE_URL` | `sqlite:///./intellipm.db` (dev) or a PostgreSQL URL (deployment). **The only change needed to switch databases.** |
| `SECRET_KEY` | JWT signing key. The app refuses to start on PostgreSQL with the placeholder value. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Login lifetime (default 720). |
| `CORS_ORIGINS` | Comma-separated browser origins allowed to call the API. |
| `LLM_API_KEY`, `LLM_MODEL`, `LLM_BASE_URL` | Primary LLM (Groq). |
| `LLM_FALLBACK_*` | Backup LLM (Gemini); used only if its key is set. |
| `USE_CACHED_PLAN_ONLY` | `true` = never call an LLM; the planner loads `app/ai/fallback_plan.json`. (Ask is unavailable in this mode.) |
| `HOURS_PER_STORY_POINT` | Story points → hours for the estimator (default 3). |

Frontend: `VITE_API_BASE_URL` in `frontend/.env`, read at **build** time.

## Rebuild the demo data

16 hand-designed projects with 12 fictional users, each telling one story (healthy, delayed, overloaded developer, blocked chain, nearly finished, just started, …).

```bash
cd backend
python -m seed.seed_demo --verify
```

* Wipes and recreates **only** the demo data (users `@intellipm.demo` and their projects); your own accounts and projects are untouched.
* Fixed random seed, and every date is generated relative to *today*, so the demo is never stale. Each project's due date is derived from its own forecast, so a story such as "delayed" stays true on any day.
* `--verify` prints each project's health level and delay probability next to the level it was designed to show (`16/16 stories show the intended behaviour`).
* Log in as `demo@intellipm.demo` / `Demo@1234` (admin of all 16). Add `--attach you@example.com` to also add your own account to every demo project.

## Tests

```bash
cd backend
python -m pytest tests -q                                                        # SQLite, in memory: 226 pass + 1 expected failure (xfail) that documents a known risk-model defect
TEST_DATABASE_URL=postgresql://USER:PASS@HOST/TESTDB python -m pytest tests -q   # same suite on PostgreSQL (wipes that DB)
```

Covers auth, permissions, tasks and cycle rejection, the planner (LLM always mocked), the assignment optimiser (including a hand-built 3×3 case), workload, forecast, health, burndown, estimator, risk model, decisions/Ask (LLM mocked), the error envelope and the demo-data definitions.

## Deployment (Render + Neon, no Docker)

Architecture: **Neon** (PostgreSQL) ← **Render web service** (FastAPI, `backend/`) ← **Render static site** (React build, `frontend/`).
`render.yaml` in the repo root describes both Render services (Blueprint). The ML models in `backend/ml/artifacts/` are committed, so
they ship with the deploy; the ML libraries are pinned in `requirements.txt` to the versions that created them.

**A. Database (Neon)**

1. neon.tech → sign in → *New project* (any name, nearest region).
2. On the dashboard copy the **connection string** (looks like `postgresql://user:pass@ep-xxx.neon.tech/neondb?sslmode=require`). Keep it secret.

**B. Push the code** – the repo is on GitHub (`Devashish369/Major-Project`, branch `main`). Make sure the latest commit is pushed.

**C. Backend + frontend on Render (Blueprint)**

1. dashboard.render.com → *New +* → **Blueprint** → connect the GitHub repo → it lists `intellipm-api` and `intellipm-web`.
2. Fill the prompted values:
   - `intellipm-api`: `DATABASE_URL` = the Neon string; `LLM_API_KEY` = Groq key; `LLM_FALLBACK_API_KEY` = Gemini key (optional); `CORS_ORIGINS` = `https://intellipm-web.onrender.com` (adjust if Render gives the site another name; no trailing slash). `SECRET_KEY` is generated for you.
   - `intellipm-web`: `VITE_API_BASE_URL` = `https://intellipm-api.onrender.com/api/v1` (use the real API URL shown on the API service page).
3. *Apply*. Wait for both deploys to go green.
4. Open `https://<api-url>/api/v1/health` → `{"status":"ok"}`. Open the web URL → register or log in.

(Without the Blueprint: create a *Web Service* with root dir `backend`, build `pip install -r requirements.txt`, start `uvicorn app.main:app --host 0.0.0.0 --port $PORT`, env var `PYTHON_VERSION=3.13.13`; and a *Static Site* with root dir `frontend`, build `npm install && npm run build`, publish dir `dist`, plus a rewrite rule `/*` → `/index.html`.)

**D. Load the demo data into Neon** (on your own computer, once):

```powershell
cd backend
$env:DATABASE_URL = "postgresql://...your Neon string..."
$env:SECRET_KEY   = "any-non-default-value"      # only needed to satisfy the start-up check
python -m seed.seed_demo --verify
```

**E. Before presenting**: Render's free web service sleeps after ~15 minutes idle and takes 30–60 s to wake. Open the API `/api/v1/health` URL a minute before the demo, and re-run step D on the morning of the demo so dates are fresh.

**Troubleshooting**

- *"Network Error" / CORS error in the browser*: `CORS_ORIGINS` on the API must equal the frontend URL exactly (scheme + host, no trailing slash); redeploy the API after changing it.
- *Frontend calls localhost*: `VITE_API_BASE_URL` was missing at build time; set it and trigger a new frontend deploy.
- *API fails at boot with "SECRET_KEY is still the default"*: set `SECRET_KEY`.
- *Plan/Ask do not work*: check the LLM keys. Plan still works from the cached plan; Ask needs a key.

## How the algorithms work

Plain-language versions of what the code does (the exact definitions are in `PROJECT_SPEC.md` §8).

**AI planner** (`services/planner.py`, `services/llm.py`). The description goes to the LLM with a strict JSON schema. The reply is validated with Pydantic and cleaned: unknown dependency titles are dropped, dependency cycles are broken, estimates are clamped to 1–40 h, skills are lower-cased, at most 40 tasks. If the first answer is invalid JSON it retries once. Provider order: Groq → Gemini (only if its key is set) → a pre-written plan (`app/ai/fallback_plan.json`). The draft is *not saved*; an admin presses Apply.

**Assignment** (`services/assignment.py`). For every unassigned open task and every person we compute
`score = 0.5 × skill match + 0.3 × availability + 0.2 × on-time rate`.
*Skill match* = average of (person's level ÷ 5) over the task's required skills (0.5 if the task needs none). *Availability* = how much of their remaining capacity is free after their open work and this task. Each person gets as many "slots" as their capacity allows, and the **Hungarian algorithm** (`scipy.optimize.linear_sum_assignment`) finds the assignment with the best total score. Every row carries a one-sentence reason built from its three numbers.

**Workload** (`services/workload.py`). `utilisation = open estimated hours assigned ÷ (weekly capacity × weeks until the due date)`. Over 100% = overloaded, 80–100% at risk, 40–80% healthy, under 40% available.

**Forecast** (`services/forecast.py`). A Monte Carlo simulation, 5,000 runs. In each run every open task's real duration is its estimate × a log-normal random overrun (default: typically about 10% over, with realistic spread; if the project has ≥10 finished tasks with actual hours, the overrun is learned from them instead). A run's duration is the larger of (a) total sampled hours ÷ the team's productive hours per day (capacity × 0.7 focus factor) and (b) the longest chain of dependent tasks done one after another by one person. The 50th/80th/90th percentiles of the 5,000 durations are the P50/P80/P90 dates (rounded up to whole days, so a P90 on or before the due date always means at most a 10 % chance of being late), and the share of runs finishing after the due date is the *delay probability*. The random generator is seeded so results are reproducible.

**Health score** (`services/health.py`).
`health = 100 − 30·overdue − 20·blocked − 15·overload − 35·slip`, clipped to 0–100, where *overdue* = share of open tasks past due, *blocked* = share of open tasks with an unfinished dependency, *overload* = how far the busiest person is over 100% (the same utilisation the workload bars show), *slip* = how far real progress (done hours ÷ total hours) lags the elapsed share of the schedule (full penalty at 30 points behind). 75+ Low risk, 50–74 Medium, below 50 High. The four penalties are returned so the UI can show *why*.

**Estimate model** (`ml/train_estimator.py`, `services/estimator.py`). TF-IDF features of a task's title + description feed a Ridge regression trained on ~23,000 real Jira issues with story points (16 open-source projects; the dataset's own train/validation/test split). On the held-out test set it has MAE 3.14 story points vs 3.26 for always predicting the median, i.e. a small but real improvement; story-point text is inherently noisy. Hours = story points × `HOURS_PER_STORY_POINT`. It is shown *next to* the LLM's estimate and never overwrites it.

**Delay-risk classifier – experimental** (`ml/generate_synthetic.py`, `ml/train_risk.py`, `services/risk.py`). The primary forecast is the Monte Carlo simulation; the ML signal is secondary. A `HistGradientBoostingClassifier` with **monotonic constraints** takes 8 project features (team size, average utilisation, overdue and blocked ratios, slip, *remaining_ratio* = remaining hours × (1 + slip) ÷ team hours available until the due date, done ratio, days to due) and outputs the probability of being late. The constraints guarantee the explainable direction: risk can only rise with remaining work, slip, overdue work, blocking and utilisation, and only fall with more days to the due date and more work done. **It is trained on 6,000 simulated project snapshots**, because no public data set of project snapshots exists. Each snapshot's label comes from a small Monte Carlo in which every feature has a documented effect (overload lowers throughput, blocked work adds idle time, overdue work and slip raise the expected overrun, more time and more progress lower the risk), with 6 % of labels flipped as noise. On a held-out test set: accuracy 92.8 %, precision 92.2 %, recall 84.8 %, ROC-AUC 0.93 – agreement with that simulation, not real-world accuracy. Remaining work vs. time still dominates (permutation importance: remaining_ratio 0.51, days_to_due 0.45, the rest ≤ 0.02). The "top factors" are computed per project (each feature is replaced by its typical training value and the probability recomputed). It does not see dependency chains or overruns learned from a project's history, so it can read lower than the Monte Carlo: on the 16 demo projects their Low/Medium/High bands agree on 12.

**Effort benchmark** (`ml/train_effort.py`). A gradient-boosting regressor on the public NASA93 COCOMO data (93 projects, ratings very-low … extra-high mapped to 0–5), reported with 5-fold cross-validated MAE and R². It is a benchmark of the method, not part of day-to-day project scoring. The result is **weak and unstable** (CV R² 0.27 ± 0.63, MAE ≈ 308 person-months on efforts that range from a few to over 8,000), which is expected with only 93 heterogeneous projects, and is reported as is.

**Decision log + Ask** (`services/ask.py`). The question is answered by the LLM from a text built *only* from this project's decisions, tasks and last 50 activity rows (each line tagged `[D3]`, `[T12]`, `[A45]`, truncated to 12,000 characters). The model must cite tags and, if the answer is not there, say so. Cited tags that are not in the context are discarded, so sources are never invented.

## Data sources and licences

| Data | Used for | Source / licence note |
|---|---|---|
| 16 story-point CSVs (`Datasets/marked_data/*.csv`: appceleratorstudio, aptanastudio, bamboo, clover, datamanagement, duracloud, jirasoftware, mesos, moodle, mule, mulestudio, springxd, talenddataquality, talendesb, titanium, usergrid) | Training the estimate model | Public Jira issue titles/descriptions with story points, from the open-source "Deep-SE" story-point research data (Choetkiertikul et al.). The issue text belongs to the respective open-source projects. **Check the dataset repository for its exact licence before redistributing; the CSVs are not in this repo** (gitignored), only the trained model and its metrics are. |
| `nasa93.arff`, `nasa93-dem.arff` | Effort benchmark | NASA COCOMO data from the **PROMISE Software Engineering Repository**. The file header asks users to follow the repository's acknowledgement guidelines (promise.site.uottawa.ca/SERepository) – cite it in the report. |
| Simulated project snapshots (`backend/ml/data/synthetic_risk.csv`) | Training the risk classifier | Generated by `ml/generate_synthetic.py`; no external data, no personal data. |
| Demo users and projects | Demo | Entirely fictional. |
| Groq and Gemini APIs | Plan generation and Ask | Used under their own terms. Only project text (titles, estimates, decisions) is sent in prompts. |
| Inter font | UI | Google Fonts, SIL Open Font Licence. |
| Open-source libraries | Everything else | React, FastAPI, SQLAlchemy, scikit-learn, etc. under their MIT/BSD/Apache licences. |

## Known limitations

* **The risk classifier is experimental and secondary**: trained on simulated data, so its metrics are agreement with the simulation, not evidence of real-world performance; it ignores dependency chains, so on dependency-heavy projects it reads lower than the Monte Carlo forecast (bands agree on 12 of the 16 demo projects). The UI labels it experimental; the primary forecast is the Monte Carlo simulation.
* **The estimate model is a modest improvement over the median** (MAE 3.14 vs 3.26 story points). It is a sanity check for the LLM, not a replacement.
* **The NASA93 effort benchmark is weak** (CV R² 0.27 ± 0.63): 93 projects are too few and too varied for an accurate model. It demonstrates the method on public data; it does not drive any score.
* **Forecast simplifications**: team throughput is capacity × 0.7 spread evenly (no individual calendars, holidays or skills); simulated "days" are converted straight to calendar days, which makes forecasts somewhat conservative (late). Tasks without estimates default to 4 h.
* **Health weights are heuristics** (from the spec), not fitted to data.
* **Assignment** assumes tasks are independent and does not model task order or context switching. Every task always receives a recommendation, even when everybody is already full; that person's availability then shows as 0 % in the reason, and the manager decides.
* **Ask has no offline fallback**: without an LLM key, or with `USE_CACHED_PLAN_ONLY=true`, it returns a clear message instead of an answer. Answers are only as good as what was recorded in the tasks and decisions.
* **No sprint management screens** – sprints are created by applying an AI plan; the API has no sprint endpoints and the Board does not group by sprint.
* **Live updates are basic**: they cover task changes only (not decisions or team changes), only while the Board or Graph tab is open, and rooms live in one server process's memory, so they work with one backend instance (as on Render's free tier) but would need a message broker such as Redis to scale out. The JWT travels in the WebSocket URL (a browser limitation), so it can appear in server access logs.
* **Security scope**: JWT in `localStorage`, no refresh tokens or password reset, no rate limiting; fine for a demo, not for production.
* **Public demo login**: `demo@intellipm.demo` / `Demo@1234` is printed in this README and the seed script and is admin of all demo projects. Anyone who finds a deployed URL can log in and change or delete the demo data. Acceptable for a short-lived demo deployment that holds only fictional data; mitigations: re-seed before presenting (it repairs everything), keep the URL private, change `DEMO_PASSWORD` in `seed/demo_projects.py` before seeding a public deployment, and never put real data in that database.
* **Free hosting**: Render's free tier sleeps when idle (30–60 s wake-up) and Neon's free tier may pause the database.

## API

- Base URL: `http://localhost:8000/api/v1` · Interactive docs: `http://localhost:8000/docs`
- Health check: `GET /api/v1/health`

| Group | Endpoints |
|---|---|
| Auth | `POST /auth/register` · `POST /auth/login` · `GET/PATCH /auth/me` |
| Projects | `GET/POST /projects` · `GET/PATCH/DELETE /projects/{id}` · `GET /projects/{id}/activity` |
| Members | `GET/POST /projects/{id}/members` · `PATCH/DELETE /projects/{id}/members/{user_id}` |
| Tasks | `GET/POST /projects/{id}/tasks` · `GET/PATCH/DELETE /tasks/{id}` · `POST /tasks/{id}/dependencies` · `DELETE /tasks/{id}/dependencies/{dep_id}` |
| AI | `POST /ai/generate-plan` · `POST /projects/{id}/apply-plan` · `POST /ai/estimate` · `POST /projects/{id}/assignments/recommend` · `POST /projects/{id}/assignments/apply` · `POST /projects/{id}/ask` |
| Analytics | `GET /projects/{id}/analytics/health` · `/forecast` · `/workload` · `/burndown` · `GET /ml/effort-benchmark` |
| Decisions | `GET/POST /projects/{id}/decisions` · `DELETE /decisions/{id}` |
| Report | `GET /projects/{id}/report` (rule-based, no LLM) |
| Realtime | `WS /ws/projects/{id}?token=<JWT>` (members only) pushes `{type: task_created \| task_updated \| task_deleted, task}`; send the text `ping` to keep it alive |

See [PROGRESS.md](./PROGRESS.md) for the build log, [DEMO_SCRIPT.md](./DEMO_SCRIPT.md) for the 10-minute demo, and [SPEC_DIFFERENCES.md](./SPEC_DIFFERENCES.md) for where the product differs from `PROJECT_SPEC.md`.
