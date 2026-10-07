# IntelliPM – Testing report

All results below come from real runs on 2026-10-08 (final review and closing session).
Nothing is estimated; where a check was not run, it is listed under "Manual UAT" for a human.

## 1. Test environment

| Item | Version / setting |
|---|---|
| OS | Microsoft Windows 11 Home Single Language |
| Python | 3.13.13 (FastAPI 0.142.2, SQLAlchemy 2.1.3, Pydantic 2.13.5, scikit-learn 1.9.1, numpy 2.5.3, psycopg 3.3.6) |
| Node | v23.6.1 (React 19, Vite 8) |
| Databases | SQLite (in-memory for tests, file for the dev app); PostgreSQL 18.4 (local throwaway server) |
| LLM | Groq free tier (primary); tests always mock the LLM |
| Fresh install | `python -m venv` + `pip install -r requirements.txt` in a clean venv: installs and passes (final review) |

## 2. How to run

```bash
cd backend
python -m pytest tests -q                                                       # SQLite
TEST_DATABASE_URL=postgresql://USER:PASS@HOST/TESTDB python -m pytest tests -q  # PostgreSQL (wipes TESTDB)
python -m seed.seed_demo --verify                                               # demo data + story check
cd ../frontend && npm run build && npm run lint
```

## 3. Automated tests – counts and results

`pytest --collect-only`: **255 tests in 15 files.**

| File | Tests | Covers (module) |
|---|---:|---|
| test_risk.py | 40 | M8 risk model + NASA93 benchmark; monotonic sweeps, edge cases, per-project factors, estimator metrics on the benchmark endpoint |
| test_forecast_health.py | 36 | M7 Monte Carlo forecast + health score; M9 burndown; date/delay consistency; health vs workload consistency |
| test_assignments.py | 28 | M5 assignment optimiser (incl. hand-built 3×3 optimum) + workload |
| test_projects.py | 25 | M2 projects, members, permissions; no admin escalation; delete cascades |
| test_ai.py | 22 | M4 planner with mocked LLM, fallback, apply-plan (validation, atomicity); no hidden SDK retries |
| test_tasks.py | 20 | M3 tasks, dependencies (self / direct / indirect cycles), completed_at, activity, assignee membership |
| test_auth.py | 18 | M1 register, login, me, JWT, bcrypt |
| test_decisions_ask.py | 17 | M12 decision log CRUD + Ask with mocked LLM (sources validated, not-found, provider fallback, offline) |
| test_ws.py | 14 | M13 WebSocket auth, membership, events, isolation, REST unaffected by socket failures |
| test_estimator.py | 12 | M6 estimator model + endpoint |
| test_report.py | 7 | M16 report: structure, outsider 404, empty / completed / no-due-date projects, insights on seeded E-commerce and IoT |
| test_seed_data.py | 5 | M10 demo-data definitions; DEMO_PASSWORD env var; live-LLM script cannot be collected |
| test_error_envelope.py | 4 | §7 error envelope for 401 / 404 / 422 / 500 (no internals leaked) |
| test_config_urls.py | 4 | Neon-style DATABASE_URL normalisation (sslmode, channel_binding, both prefixes) |
| test_sprints.py | 3 | Sprint list with counts, permissions, no write endpoint |

| Database | Result |
|---|---|
| SQLite (in memory) | **255 passed**, 0 failed, 0 skipped |
| PostgreSQL 18.4 | **255 passed**, 0 failed, 0 skipped |

Frontend: `npm run build` succeeds; `npm run lint` **0 warnings, 0 errors** (was 16 warnings before the clean-up). The frontend has no unit-test runner; its behaviour was checked by the browser walk-through (section 8) and the manual UAT table.

## 4. Demo data verification (`python -m seed.seed_demo --verify`)

```
 # Project                    Designed Actual   Score  Delay P Band        MaxUtil Blocked Overdue  OK?
 1 Hospital Management System Low      Low       97.4       2% 0%-25%         0.44     12%      0%  OK
 2 E-commerce Platform        High     High      40.2     100% 65%-100%       1.94      6%     31%  OK
 3 Mobile Banking App         Medium   Medium    67.2      21% 0%-70%         2.08      9%      9%  OK
 4 University Portal          Medium   Medium    66.6      41% 20%-100%       0.98     50%     20%  OK
 5 Food Delivery App          Low      Low      100.0       1% 0%-20%         0.58      0%      0%  OK
 6 Library Management         Low      Low       83.4       2% 0%-30%         0.00     10%      0%  OK
 7 Smart Attendance (ML)      Medium   Medium    64.4      49% 10%-90%        1.11     33%     22%  OK
 8 Online Exam System         Medium   Medium    64.1      52% 30%-95%        0.71     25%     25%  OK
 9 Real-Estate Listing Site   High     High      46.4      71% 50%-100%       0.95     15%     62%  OK
10 Travel Planner             Low      Low       97.8       2% 0%-25%         0.75     11%      0%  OK
11 Inventory Tracker          Low      Low       95.3      10% 0%-30%         0.75     17%      0%  OK
12 Chat Application           Medium   Medium    65.4      57% 50%-100%       1.10     15%     23%  OK
13 Learning Management System Medium   Medium    71.9      25% 10%-90%        0.73     15%     15%  OK
14 Fitness Tracker            Low      Low      100.0       0% 0%-5%          0.00      0%      0%  OK
15 IoT Dashboard              High     High      41.1      72% 50%-100%       0.88     58%     42%  OK
16 Event Booking System       Low      Low       95.1       4% 0%-30%         0.61     12%      0%  OK
16/16 stories show the intended behaviour.
```

Dates are generated relative to the day of seeding, so the numbers move slightly from day to day; the designed levels do not.

## 5. Machine-learning metrics (from the committed metrics files)

| Model | Data | Result | Honest reading |
|---|---|---|---|
| Story-point estimator (TF-IDF + Ridge on log1p) | 23,313 public Jira issues, dataset's own split (13,981 / 4,661 / 4,671) | test MAE **3.14** vs median baseline **3.26**; MdAE **1.89** vs **2.00** | small but real improvement |
| NASA93 effort benchmark (GradientBoostingRegressor) | 93 public projects, 5-fold CV | MAE **308.1 ± 131.4** person-months; R² **0.27 ± 0.63** | weak and unstable; a benchmark of the method only |
| Delay-risk classifier – experimental (HistGradientBoosting, monotonic constraints) | 6,000 **simulated** snapshots, 4,800 train / 1,200 test, 6 % label noise | accuracy **92.8 %**, precision **92.2 %**, recall **84.8 %**, ROC-AUC **0.93**; confusion matrix [[784, 28], [59, 329]] | agreement with the simulation that produced the labels, **not** real-world accuracy |

Risk permutation importances (share of the ROC-AUC drop): remaining_ratio 0.51, days_to_due 0.45, team_size 0.015, done_ratio 0.010, overdue_ratio 0.010, blocked_ratio 0.008, avg_utilization 0.002, slip 0.000.

Agreement between the ML probability and the Monte Carlo delay probability on the 16 demo projects (same Low < 35 % ≤ Medium < 65 % ≤ High band): **12/16** after retraining (was 5/16 before the final review, 9/16 after the input fixes). The four disagreements (University Portal, Smart Attendance, Online Exam, IoT Dashboard) are dependency-heavy projects; the ML features do not include dependency chains.

## 6. Failure-mode matrix (planner and Ask)

Run in-process against the real local database; the LLM is either the real Groq free tier, an invalid key, or a mocked timeout.

| Scenario | Plan generation | Ask | Crash / traceback |
|---|---|---|---|
| (i) `USE_CACHED_PLAN_ONLY=true` | 200, `source=fallback`, 15 tasks (cached plan) | 503 "AI answers are switched off (USE_CACHED_PLAN_ONLY=true)…" | none |
| (ii) invalid primary key, no fallback key | 200, `source=fallback`, 15 tasks | 503 "The AI service could not be reached right now…" | none |
| (iii) fallback key missing, valid primary key | 200, `source=llm`, 12 tasks (≈ 14 s for plan + Ask) | 200, correct answer citing decision D21 | none |
| (iv) every provider times out (mocked) | 200, `source=fallback`, 15 tasks | 503 "could not be reached" | none |

## 7. Security and permission checks

| Check | Result |
|---|---|
| Permission matrix (owner, non-admin member, outsider, helper; plus WebSocket) | **47 / 47 pass**: 26 outsider calls → 404; 7 admin-only actions by a member → 403 (delete project, remove member, change roles ×2, apply plan, apply assignments, add someone as admin); member may still edit tasks and add regular members; cross-project dependency → 404; foreign task ignored by assignment apply; non-member assignee → 422; self / direct / indirect cycles → 422; WebSocket refuses outsider, missing and invalid tokens (403) and accepts members |
| Secrets in the working tree and full git history | no `.env` ever committed; no key-like strings (Groq, Gemini, OpenAI patterns); only placeholders |
| Default `SECRET_KEY` on PostgreSQL | app refuses to start (RuntimeError) |
| CORS | allows the configured origin only; a foreign origin gets no allow-origin header |
| Password storage | all stored hashes are bcrypt (`$2b$`); no plaintext |
| Tokens | JWT with `exp`, 12 h lifetime |
| Endpoint sweep as demo user (33 calls, all API groups) | all 2xx with the standard envelope, no tracebacks |

## 8. Defects found in the final review and how each was fixed

| Id | Severity | Defect | Fix | Commit |
|---|---|---|---|---|
| C-1 | Critical | A non-admin member could add an account as admin, which could then delete the project | only admins may grant the admin role; test | 77f9db8 |
| C-2 | Critical | SQLite did not enforce foreign keys: deleted projects left rows behind and a reused id gave a new project another user's members, or a 500 | `PRAGMA foreign_keys=ON` on every SQLite connection; cascade test (fails without the fix) | 77f9db8 |
| H-1 – H-4 | High | ML risk fed a wrongly defined remaining_ratio and max instead of mean utilisation; same "top factors" for every project; 94 % for a completed project | training-consistent feature builder; per-project contributions; 0 % with no open work | 77f9db8 |
| H-5 | High | Circular simulated labels not disclosed | UI, Benchmarks, README wording | 77f9db8 |
| H-6 | High | Risk model erratic (e.g. utilisation 0.1 → 86 % but 0.5 → 32 %, a 2-hour project due in 60 days → 99 %) | new simulator where every feature has a documented effect; HistGradientBoosting with monotonic constraints; monotonic sweep tests | fc1f0d2 |
| M-1 | Medium | apply-plan stored unvalidated plans (a cycle broke the forecast with a 500) | re-validated with the planner's own rules; 422 on invalid; atomicity test | 77f9db8 |
| M-2 | Medium | Forecast dates floored, so they could contradict the delay probability | rounded up; property test | 77f9db8 |
| M-3 | Medium | Health overload used a different weeks rule than the workload bars | same rule; test | 77f9db8 |
| M-4 | Medium | Hidden SDK retries could stall plan generation for minutes | `max_retries=0`; test | 77f9db8 |
| M-5 | Medium | Tasks could be assigned to non-members | 422; test | 77f9db8 |
| M-6 | Medium | Team tab showed 194 % as 100 % | real percentage, capped bar width | 77f9db8 |
| M-7 | Medium | No sprint API | read-only `GET /projects/{id}/sprints` + Board filter | 5381748 |
| L-1, L-3, L-4, L-6, L-8 | Low | stale docstring; 16 lint warnings; live-LLM script collectable by pytest; estimator numbers missing on Benchmarks; empty package | fixed | 6d61d8a |
| L-2 | Low | a test that could never fail (`… or True`) | replaced by a real assertion | fc1f0d2 |

## 9. Manual UAT (to be filled in by a person)

| # | Feature | Steps | Expected | Result |
|---|---|---|---|---|
| 1 | Login | Open the app, sign in as the demo user | Dashboard with 16 project cards and risk badges | |
| 2 | Kanban | Hospital → Board, drag a card to another column, press F5 | Card stays in the new column | |
| 3 | Sprint filter | Hospital → Board → Sprint: Sprint 1 | Only Sprint 1 cards shown; each card has a sprint badge | |
| 4 | Plan (live LLM) | New project → Plan → type one sentence → Generate Plan | "AI Generated" badge, sprints and tasks, model hours shown; Apply creates tasks | |
| 5 | Plan (fallback) | Set `USE_CACHED_PLAN_ONLY=true`, restart, Generate Plan | Amber "Cached Plan" badge with the hospital example | |
| 6 | Assignment | Library → Team → Recommend assignments → Apply | 10 rows with reasons; Board shows assignees | |
| 7 | Workload | E-commerce → Team | Overloaded members shown above 100 % (e.g. 194 %) | |
| 8 | Analytics | E-commerce → Analytics | Health ≈ 40 with penalties, P50/P80/P90 and due line, burndown, ML card labelled experimental | |
| 9 | Graph | IoT Dashboard → Graph | Blocked tasks red with red edges; click opens the task | |
| 10 | Ask | Event Booking → Decisions → "Why do we hold seats for 10 minutes?" | Answer with a Decision source chip; an off-topic question says it cannot find it | |
| 11 | Report | E-commerce → Report → Print / Save as PDF | Readable A4 document, navigation hidden, sections not split | |
| 12 | Live updates | Same board in two windows, drag in one | The other window updates, "Live" badge green | |
| 13 | Benchmarks | Dashboard → Benchmarks | NASA93 label, estimator MAE vs baseline, risk model marked experimental / simulated | |
| 14 | Permissions | Log in as a non-admin member (e.g. aarav@intellipm.demo on a project he does not lead) | No delete-project button; apply actions refused | |
| 15 | Deployed site | Run DEPLOY_CHECKLIST.md section E | All checks pass on the hosted URL | |
