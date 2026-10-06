# Where the product differs from PROJECT_SPEC.md

Use this list when you update the deck and report so they describe what was actually built.
Checked against the code and tests on 2026-10-06 (197 tests passing).

## 1. In the spec but NOT built

| Spec | What exists instead |
|---|---|
| §7 Sprints API: `GET/POST /projects/{id}/sprints`, `PATCH/DELETE /sprints/{id}` (and `routers/sprints.py`) | Sprints are created only when an AI plan is applied (`POST /projects/{id}/apply-plan`). There are no sprint endpoints and no sprint screen; the Board does not group by sprint. |
| §7 Realtime `WS /ws/projects/{id}` and `routers/ws.py` (module **M13**, marked stretch) | Not built. A second browser window must refresh to see changes. |
| §3 optional sentence-transformers embeddings (GPU optional) | Not used. The estimator is TF-IDF + Ridge only, as M6 required ("do not install sentence-transformers or PyTorch"). |
| M14 "deployed" | The code, `render.yaml` and the deploy steps are done and the app is verified on PostgreSQL, but the actual Render + Neon deployment is a manual step for you (README → Deployment). |

## 2. Built, but differently from the spec text

| Spec | What was built |
|---|---|
| §4 `services/qa.py` | The Ask logic is `services/ask.py` (+ `routers/decisions.py` holds both the decision log and `/ask`). |
| §4 `backend/app/ml/…` | The ML scripts and artifacts are in `backend/ml/` (a leftover empty `backend/app/ml/` package from an early path bug is harmless and can be deleted). `ai/fallback_plan.json` is at `backend/app/ai/`. |
| §4 routers list | Also has `assignments.py` (recommend/apply/workload). |
| §8.6 `Datasets/*.csv` | The 16 CSVs are read from `Datasets/marked_data/`. |
| §8.6 "Ridge (or RandomForest)" | TF-IDF (20k features, bigrams, sublinear tf) + Ridge, trained on `log1p(story points)`; predictions are back-transformed. |
| §7 error format `{success:false, message, errors}` | Originally only 500-errors used it; fixed in M15: 401/403/404/422/503 now use it too. A `detail` key is kept as well because the frontend reads it. 500 responses no longer expose the raw exception text. |
| §8.4 forecast "days" | Throughput is capacity ÷ 5 × 0.7 per **working** day (as specified), but the simulated duration is added to today as **calendar** days, so forecast dates are somewhat later (more cautious) than a weekday-aware calculation would give. |
| §8.5 health "`done_hours`" | Uses `actual_hours` when a finished task has it, otherwise its estimate. |
| §10 "each project 8–30 tasks" | Yes (9–30). Also each project got a sprint structure and activity history; 28 decisions in total (8 in Event Booking). |
| §6 `decisions` table | Created in M10 (for seeding), CRUD and Ask added in M12. Delete is allowed for the decision's author or a project admin (the spec did not say). |
| §9 Benchmarks page | Exists at `/benchmarks` and is reached from a **Benchmarks** button on the Dashboard header (added in M15; before that it had no link). |

## 3. Added beyond the spec

- `GET /projects/{id}/activity` (activity log feed).
- The Plan tab flags tasks where the model's hours and the LLM's differ by more than 3× (spec M6 asked for this; the LLM value is never overwritten).
- A demo-only account `demo@intellipm.demo` that is an admin of all 16 demo projects (10 h/week capacity, so it appears as an always-"available" member in workload views), and `python -m seed.seed_demo --attach EMAIL`.
- `python -m seed.verify_demo`: prints the designed vs actual health level and delay probability of every demo story (16/16 match).
- Start-up safety check: on PostgreSQL the app refuses to run with the default `SECRET_KEY`.
- `TEST_DATABASE_URL` lets the whole test suite run on PostgreSQL.
- Analytics cards have loading, empty and error (with Retry) states.

## 4. Numbers to quote in the deck (all from the committed metrics files)

| Item | Value | Honest reading |
|---|---|---|
| Estimator (TF-IDF + Ridge), 23,313 Jira issues, held-out test set (4,671) | MAE **3.14** vs median baseline **3.26** story points; MdAE 1.89 vs 2.00 | Small but real improvement; story points are noisy. |
| Risk classifier (gradient boosting), 4,000 **simulated** snapshots | accuracy 93.4 %, precision 92.1 %, recall 91.2 % | Agreement with the simulator, **not** real-world accuracy. One feature (`remaining_ratio`) carries 83 % of the importance. |
| NASA93 effort benchmark (gradient boosting), 93 real projects, 5-fold CV | MAE ≈ 308 person-months, R² **0.27 ± 0.63** | Weak and unstable, as expected with 93 heterogeneous projects. Present it as a benchmark of the method. |
| Forecast | 5,000 Monte Carlo runs, seeded; overrun default log-normal(μ=0.10, σ=0.35), learned from the project if ≥ 10 finished tasks have actual hours | |
| Tests | 197 pytest tests (SQLite in memory; the suite also passes on PostgreSQL) | |
| Demo data | 12 users, 16 projects, 252 tasks, ~55 dependencies, ~900 activity rows, 28 decisions; 16/16 stories verified | |
