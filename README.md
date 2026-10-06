# IntelliPM

**AI-assisted project management** – like Jira/Trello with an explainable decision-support layer.

## What it does

- Type a one-line project idea → get an AI-generated plan (tasks, estimates, sprints, dependencies)
- Task-assignment recommendations based on skills, workload and past performance
- Forecast completion date, delay probability, and a 0–100 project health score
- Decision log and project Q&A (ask questions about your project)

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | React + Vite + Tailwind CSS v4, react-router-dom, axios, @tanstack/react-query, lucide-react |
| Backend | Python 3.11+, FastAPI + Uvicorn, Pydantic v2, SQLAlchemy 2.0 (sync) |
| Database | SQLite (dev) → PostgreSQL (production, e.g. Neon), switched only by `DATABASE_URL` |
| Auth | PyJWT + bcrypt |
| LLM | Groq (primary) / Gemini (fallback) via openai SDK |
| ML | scikit-learn, pandas, numpy, scipy |

## Run it locally

Prerequisites: Python 3.13 (3.11+ works for development), Node 20.19+ (22 recommended).

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

### 3. Demo data (16 projects, 12 users)
```bash
cd backend
python -m seed.seed_demo --verify
```
Wipes and recreates only the demo data, then prints designed-vs-actual health for each story.
Log in with `demo@intellipm.demo` / `Demo@1234` (admin of all 16 projects).
Add `--attach you@example.com` to also add your own account to every demo project.

### 4. Tests
```bash
cd backend
python -m pytest tests -q                       # SQLite in memory
TEST_DATABASE_URL=postgresql://USER:PASS@HOST/TESTDB python -m pytest tests -q   # same suite on PostgreSQL (wipes that DB)
```

### Environment variables (`backend/.env`, never committed)

| Variable | Meaning |
|---|---|
| `DATABASE_URL` | `sqlite:///./intellipm.db` (dev) or a PostgreSQL URL (deployment). **The only change needed to switch databases.** |
| `SECRET_KEY` | JWT signing key. Required to be non-default when using PostgreSQL. |
| `CORS_ORIGINS` | Comma-separated browser origins allowed to call the API. |
| `LLM_API_KEY`, `LLM_MODEL`, `LLM_BASE_URL` | Primary LLM (Groq). |
| `LLM_FALLBACK_*` | Backup LLM (Gemini); used only if its key is set. |
| `USE_CACHED_PLAN_ONLY` | `true` = never call an LLM; the planner loads `ai/fallback_plan.json` (Ask is unavailable). |
| `HOURS_PER_STORY_POINT` | Story points → hours for the estimator (default 3). |

Frontend: `VITE_API_BASE_URL` (in `frontend/.env`, read at build time).

### Running on PostgreSQL locally
Put a PostgreSQL URL in `DATABASE_URL` (and a real `SECRET_KEY`) and start the backend as usual; nothing else changes.
`postgres://…` and `postgresql://…` URLs are accepted as-is (the app selects the psycopg 3 driver).

## Deployment (Render + Neon, no Docker)

Architecture: **Neon** (PostgreSQL) ← **Render web service** (FastAPI, `backend/`) ← **Render static site** (React build, `frontend/`).
`render.yaml` in the repo root describes both Render services (Blueprint). The ML models in `backend/ml/artifacts/` are committed, so
they ship with the deploy; the ML libraries are pinned in `requirements.txt` to the versions that created them.

### Step by step

**A. Database (Neon)**
1. neon.tech → sign in → *New project* (any name, nearest region).
2. On the dashboard copy the **connection string** (looks like `postgresql://user:pass@ep-xxx.neon.tech/neondb?sslmode=require`). Keep it secret.

**B. Push the code** – the repo is already on GitHub (`Devashish369/Major-Project`, branch `main`). Make sure the latest commit is pushed.

**C. Backend + frontend on Render (Blueprint)**
1. render.yaml-based: dashboard.render.com → *New +* → **Blueprint** → connect the GitHub repo → it lists `intellipm-api` and `intellipm-web`.
2. Fill the prompted values:
   - `intellipm-api`: `DATABASE_URL` = the Neon string; `LLM_API_KEY` = Groq key; `LLM_FALLBACK_API_KEY` = Gemini key (optional); `CORS_ORIGINS` = `https://intellipm-web.onrender.com` (adjust if Render gives the site another name; no trailing slash). `SECRET_KEY` is generated for you.
   - `intellipm-web`: `VITE_API_BASE_URL` = `https://intellipm-api.onrender.com/api/v1` (use the real API URL shown on the API service page).
3. *Apply*. Wait for both deploys to go green.
4. Open `https://<api-url>/api/v1/health` → `{"status":"ok"}`. Open the web URL → register or log in.

(Without the Blueprint: create a *Web Service* with root dir `backend`, build `pip install -r requirements.txt`, start `uvicorn app.main:app --host 0.0.0.0 --port $PORT`, env var `PYTHON_VERSION=3.13.13`; and a *Static Site* with root dir `frontend`, build `npm install && npm run build`, publish dir `dist`, plus a rewrite rule `/*` → `/index.html`.)

**D. Load the demo data into Neon** (run on your own computer, once):
```powershell
cd backend
$env:DATABASE_URL = "postgresql://...your Neon string..."
$env:SECRET_KEY   = "any-non-default-value"      # only needed to satisfy the start-up check
python -m seed.seed_demo --verify
```
It prints the 16/16 verification table. (Run it again any time; it rebuilds the demo data and dates relative to that day.)

**E. Before presenting**: Render's free web service sleeps after ~15 minutes idle and takes 30-60 s to wake. Open the API `/api/v1/health` URL a minute before the demo, and re-run step D on the morning of the demo so dates are fresh.

### Troubleshooting
- *Browser shows "Network Error" / CORS error*: `CORS_ORIGINS` on the API must equal the frontend URL exactly (scheme + host, no trailing slash); redeploy the API after changing it.
- *Frontend calls localhost*: `VITE_API_BASE_URL` was missing at build time; set it and trigger a new frontend deploy.
- *API fails at boot with "SECRET_KEY is still the default"*: set `SECRET_KEY`.
- *Plan/Ask do not work*: check the LLM keys. Plan still works from the cached plan; Ask needs a key.

## API

- Base URL: `http://localhost:8000/api/v1`
- Docs (Swagger): `http://localhost:8000/docs`
- Response envelope: `{"success": true, "data": ..., "message": "..."}`
- Health check: `GET /api/v1/health`

## Module progress

See [PROGRESS.md](./PROGRESS.md) for the current build status.

## Project structure

```
MajorProject/
  PROJECT_SPEC.md   PROGRESS.md   README.md   .gitignore
  backend/
    requirements.txt  .env.example
    app/
      main.py  config.py  database.py  models.py
      routers/   services/   ml/   ai/
    seed/   tests/
  frontend/
    src/
      api/   components/   pages/   context/
```
