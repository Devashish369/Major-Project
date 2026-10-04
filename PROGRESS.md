# IntelliPM – PROGRESS.md

> Update this file at the END of every coding session, then `git commit`.
> Deadline: **demo on Oct 17, 2026**. Cut line: **end of Oct 11**. Feature freeze: **Oct 14**.

## Current status

- **Current module:** M0 ☑ DONE – next is M1 (Auth)
- **Last session:** 2026-10-05 / Antigravity AI / M0 repo skeleton built end-to-end
- **Known bugs:** none
- **Next step:** M1 – Auth (register/login/me, JWT, password hashing, frontend login/register + protected routes)

## Module checklist

| Module | Description | Priority | Status | Target date |
|---|---|---|---|---|
| M0 | Repo, backend skeleton, frontend shell | MUST | ☑ | Oct 5 |
| M1 | Auth | MUST | ☐ | Oct 6 |
| M2 | Projects, members, skills, capacity | MUST | ☐ | Oct 6 |
| M3 | Tasks, Kanban, dependencies, activity log | MUST | ☐ | Oct 7 |
| M4 | AI planner (LLM + fallback) | MUST | ☐ | Oct 8 |
| M5 | Assignment optimizer + workload | MUST | ☐ | Oct 9 |
| M6 | Estimator model on public data | MUST | ☐ | Oct 9 |
| M7 | Forecast + health score | MUST | ☐ | Oct 10 |
| M8 | Risk classifier + NASA93 benchmark | MUST | ☐ | Oct 11 |
| M9 | Dashboard + analytics charts | MUST | ☐ | Oct 11 |
| M10 | 16 demo projects seeded | MUST | ☐ | Oct 12 |
| M11 | Dependency graph | SHOULD | ☐ | Oct 12 |
| M12 | Decision log + Ask | SHOULD | ☐ | Oct 13 |
| M13 | WebSocket live updates | STRETCH | ☐ | Oct 13 |
| M14 | Postgres switch, deploy, freeze | FINAL | ☐ | Oct 14 |
| M15 | Tests, README, report, deck | FINAL | ☐ | Oct 15 |
| — | Rehearsal only, no new features | — | ☐ | Oct 16–17 |

Mark ☑ only after the module's **"done when"** test in `PROJECT_SPEC.md` section 11 passes.

## Decisions made (keep short)

- Stack: React+Vite+Tailwind / FastAPI / SQLAlchemy 2.0 (sync) / SQLite→Postgres / Groq LLM with fallback.
- No model training of LLMs. Estimator = TF-IDF+Ridge on 16 public Jira CSVs. Risk classifier = trained on simulated data (disclosed).
- Datasets live in `Datasets/` (gitignored): 16 story-point CSVs and `nasa93.arff`, `nasa93-dem.arff`.
- GPU (RTX 3050 4GB) is optional, used only for sentence embeddings; code must fall back to CPU.

## Session log

| Date | Account | Module | What was done | Bugs / notes |
|---|---|---|---|---|
| 2026-10-05 | Antigravity AI | M0 | Folder structure, backend venv + requirements.txt, config.py (pydantic-settings), database.py (SQLAlchemy 2.0 sync engine), main.py (CORS, response envelope ok()/err(), global error handler, GET /api/v1/health), .gitignore, .env.example, models.py placeholder, ai/fallback_plan.json; Vite+React+Tailwind v4 frontend with react-query, axios, react-router-dom, lucide-react; HealthPage.jsx calls /health and shows live JSON response | Tailwind v4 default @theme imported Inter from Google Fonts causing PostCSS ordering error → fixed by using tailwindcss/preflight + tailwindcss/utilities separately and loading Inter via HTML link tag |

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
