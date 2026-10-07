# IntelliPM – Final review report

Reviewed 2026-10-08 against PROJECT_SPEC.md, README.md, PROGRESS.md, SPEC_DIFFERENCES.md and DEMO_SCRIPT.md.
No synopsis or slide deck exists in the repo (`docs/` absent; no .pptx/.pdf/.docx found), so slide promises are listed under HUMAN MUST CHECK.

## 1. Verdict – PARTLY (YES after this review, with one experimental component)

The product does what its aim says. It plans from one sentence, recommends assignments with reasons, shows workload, forecasts P50/P80/P90 with a delay probability, scores health with its penalty breakdown, keeps a decision log with cited Q&A, and offers Kanban, graph, burndown and live updates. The core numbers recompute exactly by hand. Before this review it had two critical defects: a permission bypass, and cross-user data leaking through SQLite id reuse. The ML delay-risk card was also fed wrongly-defined inputs, so it contradicted the forecast (e.g. 94% risk for a finished project). All of these are now fixed and tested. The remaining gap is the ML risk classifier itself: trained on circular, simulated labels, it is still erratic on some inputs. It is now clearly labelled experimental and must not be presented as a real predictor. Sprint management (API and screens) does not exist beyond plan generation.

## 2. Test and run evidence

| Check | Result |
|---|---|
| Fresh venv (`python -m venv`, `pip install -r requirements.txt`, Python 3.13.13) | install OK; **211 passed** (before fixes) |
| Full suite after fixes, SQLite | **226 passed, 1 xfailed** (strict xfail = documented defect H-6) |
| Full suite after fixes, PostgreSQL (`TEST_DATABASE_URL`, throwaway local Postgres) | **226 passed, 1 xfailed** |
| `python -m seed.seed_demo --verify` | **16/16 stories show the intended behaviour** (before and after fixes; Chat seed slack retuned 1.0→0.95 after M-2) |
| Endpoint sweep as demo user (33 calls: all spec §7 + activity + /ml/effort-benchmark + /health) | all 2xx, correct envelope, no tracebacks; only `GET /projects/{id}/sprints` → 404 (endpoint does not exist, see M-7) |
| IDOR / permission matrix (46 checks, 3 users + WebSocket) | 26 outsider calls all 404; 6 admin-only calls by a member all 403; cross-project dependency 404; foreign task skipped in assignment apply; self/direct/indirect cycles 422; WS stranger/missing/garbage token 403, member OPEN. Failed before fixes: C-1, M-5 |
| Frontend `npm install` / `npm run build` / `npm run lint` | 0 vulnerabilities / build OK (single 890 kB chunk warning) / **16 warnings, 0 errors** |
| Browser walk of DEMO_SCRIPT.md (in-app browser, cached-plan mode) | login form → dashboard 16 badges ✔; Hospital board drawer ✔, real pointer drag → In Progress, persists after F5 ✔; Hospital Analytics 97 / Low / P(late) 2 % ✔; E-commerce 40 / High / ML 87 % ✔, Team 194 %/166 %/114 % Overloaded ✔ (after M-6); Library Recommend 10 rows with reasons → Apply → 0 unassigned ✔; IoT Graph 16 nodes / 7 red = API blocked count, click opens drawer ✔; New Project → Plan → "Cached Plan" badge, 15 tasks, model estimates fetched, Apply → board ✔; Ask (cached-only) shows readable "switched off" message ✔; Benchmarks labels + back link ✔ |
| Failure modes – planner / Ask | (i) `USE_CACHED_PLAN_ONLY=true`: plan 200 `source=fallback` 15 tasks / Ask 503 "AI answers are switched off…"; (ii) invalid primary key, no fallback: plan 200 fallback / Ask 503 "could not be reached"; (iii) missing fallback key, valid primary: plan 200 `source=llm` 12 tasks, Ask 200 citing decision D21 (≈10 s total); (iv) mocked timeout on every provider: plan 200 fallback / Ask 503. No crash, no traceback in any case. Real LLM calls used: 5 (3 of them rejected 401s). |
| Secrets (working tree + `git log --all -p`) | no `.env` ever committed; no Groq/Gemini/OpenAI-style key in history or tree; only placeholders (`USER:PASSWORD`, `CHANGE_ME…`, `any-non-default-value`); `backend/test_groq.py` reads the key from the environment |
| Security config | default `SECRET_KEY` on Postgres → RuntimeError at import ✔; CORS preflight allows `http://localhost:5173`, no allow-origin for `https://evil.example` ✔; all 28 stored passwords bcrypt `$2b$`, no plaintext ✔; JWT has `exp`, 12 h ✔ |

## 3. Aim-alignment table

Promises collected from PROJECT_SPEC §1–2 and §9, the README feature table and DEMO_SCRIPT (P#), plus the aim points (A#).

| # | Promise | Where | Verified how | Status |
|---|---|---|---|---|
| A1/P1 | Plan (tasks, estimates, dependencies, sprints) from one line | `services/planner.py`, `POST /ai/generate-plan`, `/apply-plan`, Plan tab | live LLM 12 tasks in ~10 s; cached plan in UI; post-processing unit check (unknown deps dropped, cycle broken, 1–40 h, cap 40, lowercase); apply-plan atomic under injected failure | **WORKS** (sprints only as part of plans – see P12) |
| A2/P2 | Who should do which task, with a reason | `services/assignment.py`, Team tab | independent recompute: 0/10 mismatches; total score 8.0414 = independent MILP optimum 8.0415; reason text matches numbers; zero capacity / no members / no skills / more tasks than slots | **WORKS** |
| A3/P3 | Workload: overloaded / at risk / healthy / available | `services/workload.py`, Team + Analytics | labels per spec §8.3; UI percentage was capped at 100 % (M-6, fixed) | **WORKS** |
| A4a/P4 | Forecast P50/P80/P90 + delay probability | `services/forecast.py`, Analytics | seeded repeatable; more capacity → earlier P50 (10-25 → 10-16); more work → later (→ 11-08); dates now consistent with P(late) (M-2) | **WORKS** |
| A4b/P5 | Health 0–100 with penalty breakdown | `services/health.py`, Analytics, dashboard badge | independent recompute from raw SQLite rows = API for Hospital 96.59, E-commerce 40.21, IoT 40.97, no tasks 100, no due date 70; overload consistency fixed (M-3) | **WORKS** |
| A4c/P6 | ML delay-risk probability with top factors | `services/risk.py`, Analytics card | before: inputs mis-defined, same factors for all 16 projects, completed project 94 %; ML/MC same band 5/16. After fixes: per-project factors (15 distinct), completed 0 %, same band 9/16; model still erratic (H-6) | **PARTIAL** (experimental; disclosed) |
| A5/P7 | Decision log + answers citing sources | `services/ask.py`, Decisions tab | live: correct answer citing D21; off-topic → "can't find"; invented ids dropped (tests); clear 503 offline | **WORKS** |
| A6/P8 | Kanban | Board tab | real drag, persists after reload; cycle rejection | **WORKS** |
| A6/P9 | Dependency graph | Graph tab | 16 nodes, 7 red = API blocked count; drawer on click; edges not visible in hidden pane (seen in earlier visible screenshot) | **WORKS** (edges: HUMAN CHECK) |
| A6/P10 | Burndown | `GET …/burndown`, Analytics | 200 + chart data; unit tests | **WORKS** |
| A6/P11 | Live updates | `routers/ws.py`, `useProjectSocket.js` | 14 WS tests; WS auth matrix; two-tab test in M13 session | **WORKS** (deployed wss: HUMAN CHECK) |
| P12 | Sprint plans (spec §7 sprint endpoints) | only via apply-plan | `GET /projects/{id}/sprints` → 404; no sprint UI | **PARTIAL** (M-7) |
| P13 | "Reports" | – | only dashboards/charts and a decision log; no report export | **MISSING** if a slide promises reports (HUMAN CHECK deck) |
| P14 | Task priorities | `tasks.priority` low…critical; drawer; assignment sorts by priority | code + UI | **WORKS** |
| P15 | What-if simulation | – | not built (deck: Future Scope) | **MISSING – fine only if the slide says Future Scope** |
| P16 | Knowledge/memory of the project | decision log + Ask over tasks/decisions/last 50 activity rows | as A5 | **WORKS** (limited to last 50 activity rows, 12 000 chars) |
| P17 | "The AI recommends, the manager decides; nothing applied without a click" | generate-plan / recommend write nothing; apply endpoints admin-only | sweep + IDOR matrix | **WORKS** |
| P18 | "Every score shows its reason" | health penalties, assignment reasons, risk factors | above | **WORKS** for health/assignment; **PARTIAL** for ML factors (H-6) |
| P19 | Honesty: estimator/effort on public data; risk on simulated data, disclosed wherever shown | Analytics card, Benchmarks page, README | card now "experimental · trained on SIMULATED projects"; Benchmarks explains the accuracy ceiling | **WORKS** (was MISLEADING on circularity, H-5) |
| P20 | Estimate model beats the median baseline | `estimator_metrics.json` | MAE 3.1436 vs 3.2605, MdAE 1.8939 vs 2.0 = README; loads with `-W error` | **WORKS** (small gain) |
| P21 | NASA93 benchmark page | `/ml/effort-benchmark`, Benchmarks | MAE 308.1 ± 131.35, R² 0.2723 ± 0.6318 = README; label present | **WORKS** (weak result, stated) |
| P22 | 16 demo projects tell their stories | `seed/` | 16/16 | **WORKS** |
| P23 | Auth, roles, permissions | deps.py, members.py | IDOR matrix; C-1 fixed | **WORKS** |
| P24 | PostgreSQL by changing only DATABASE_URL; Render deploy without Docker | config.py, render.yaml | full suite on Postgres; deploy not done | **WORKS** locally; deploy HUMAN |

## 4. Findings

| id | severity | what | evidence | status |
|---|---|---|---|---|
| C-1 | CRITICAL | Any non-admin member could add an account as **admin** (`routers/members.py:67` "any member may add"), which could then delete the project | live: member adds `evil` as admin → 201, `evil` deletes project → 200 | **FIXED** (admin role is admin-only; `TestNoAdminEscalation`) |
| C-2 | CRITICAL | SQLite did not enforce foreign keys; `delete_project` (`routers/projects.py:258`) left members/tasks/activity behind and SQLite reuses ids, so the next project could inherit another user's members and tasks, or project creation failed with 500 | 3 orphan member rows + 2 tasks + 2 activity rows; demo user's `POST /projects` → 500 `IntegrityError` | **FIXED** (`app/database.py` `PRAGMA foreign_keys=ON` on every SQLite connection; `TestProjectDeleteCascades` fails without the fix, passes with it); local DB orphans removed |
| H-1 | HIGH | Risk feature `remaining_ratio` meant "1 − progress" at prediction (`routers/analytics.py:193`) but "remaining hours ÷ available hours until due" in training (`ml/generate_synthetic.py:93`) | E-commerce MC 100 % vs ML 41 %; Real-Estate 89 % vs 8 % | **FIXED** (`risk.build_features`, tests) |
| H-2 | HIGH | "Top contributing factors" identical for all 16 projects – sorted by global importance (`services/risk.py:108-109`) despite docstring claiming per-value contributions | 1 distinct factor list across 16 projects | **FIXED** (per-project contribution vs training medians; 15 distinct lists) |
| H-3 | HIGH | `avg_utilization` fed the **max** utilisation (`analytics.py:189`) | code | **FIXED** (mean) |
| H-4 | HIGH | Completed project (Fitness Tracker) shown 94 % likely to be late | risk table | **FIXED** (no open work → 0 %, note shown) |
| H-5 | HIGH | Circularity not disclosed: label = Monte Carlo of `remaining_ratio > ~1` + 8 % flips (`generate_synthetic.py:89-103`), so 93.4 % ≈ the 92 % noise ceiling and the other 7 features never affect the label | code + metrics (remaining_ratio importance 0.828) | **FIXED (wording)**: UI card "experimental", Benchmarks note, README, SPEC_DIFFERENCES, DEMO_SCRIPT |
| H-6 | HIGH | The trained risk model is erratic on in-range and edge inputs: avg_utilization 0.1 → 86 % vs 0.5 → 32 % although labels ignore utilisation; remaining_ratio 0.2 → 38 %; 2 h project due in 60 days → 99 %; Library (healthy) 83 %; Food Delivery (nearly done) 45 %; factor signs like "overdue ratio = 0 increases risk" | probe script + `tests/test_risk.py` strict xfail | **OPEN – needs approval** (see 4a) |
| M-1 | MEDIUM | `apply-plan` stored the client's plan without validation: cyclic dependencies and 999 h tasks were saved, after which that project's forecast returned 500 (`RecursionError`); missing title → 500 | live repro | **FIXED** (re-validated with the planner's schema + post-processing; 422 on invalid; tests incl. atomicity) |
| M-2 | MEDIUM | Forecast dates were floored (`forecast.py:195-197`) while P(late) used exact durations: Inventory P90 = due date but P(late) 23 %; "due today, P50 today, 100 % late" | consistency check over seeded projects | **FIXED** (ceil; property test) |
| M-3 | MEDIUM | Health overload used `max(1 day, days)/7` (`analytics.py:49`, `projects.py:72`) while workload bars use `max(1 week, …)`: due-in-2-days project → penalty on 117 % while Team tab shows 33 % | independent recompute | **FIXED** (same rule; test) |
| M-4 | MEDIUM | OpenAI SDK default `max_retries=2` on top of the planner's own 2 attempts × 2 providers × 30 s timeout → minutes before the cached plan on a bad network | `llm.py:34-42` | **FIXED** (`max_retries=0`; test) |
| M-5 | MEDIUM | A task could be assigned to a non-member user | IDOR matrix: PATCH assignee=outsider → 200 | **FIXED** (422; test) |
| M-6 | MEDIUM | Team-tab workload label capped at 100 % (194 % shown as "100 % Overloaded"), contradicting DEMO_SCRIPT | UI walk | **FIXED** (`ProjectPage.jsx` shows real %, bar width capped) |
| M-7 | MEDIUM | Spec §7 sprint endpoints and any sprint screen are missing | sweep 404 | **OPEN – needs approval** (see 4a) |
| L-1 | LOW | `assignment.py:38` docstring says tasks beyond slots go unassigned, but `slots = max(1, …)` (line 81, per spec) always assigns, at availability 0 | edge-case run: 10/10 assigned, availability 0.0 | open |
| L-2 | LOW | Vacuous test `assert p_high >= p_base or True` | `tests/test_risk.py:169` | open |
| L-3 | LOW | 16 lint warnings (unused imports; missing `key` props `ProjectPage.jsx:392-393`) | lint output | open |
| L-4 | LOW | `backend/test_groq.py` sits outside `tests/`; a bare `pytest` run from `backend/` would collect it and make a real LLM call | file location | open |
| L-5 | LOW | Non-admin members may edit project details and add regular members (spec silent) | IDOR matrix | open (acceptable) |
| L-6 | LOW | Benchmarks page's estimator section shows no MAE numbers (points to the JSON) | UI text | open |
| L-7 | LOW | Single 890 kB JS chunk | build warning | open |
| L-8 | LOW | Leftover empty `backend/app/ml/` package | tree | open |
| L-9 | LOW | Work due *today* with any hours left is 100 % "late" by definition (duration > 0 days) | forecast test | open (definition) |

### 4a. OPEN items that need new code – proposals (not started, waiting for approval)

**H-6 – retrain the risk model (≈ 2 h).**
- **What:** In `ml/generate_synthetic.py`, widen the sampling so avg_utilization and done_ratio can be 0 (≈ 5 lines). In `ml/train_risk.py`, switch to `HistGradientBoostingClassifier` with monotonic constraints: risk rises with remaining_ratio, slip, overdue and blocked, and falls with days_to_due and done_ratio (≈ 15 lines).
- **Then:** regenerate `ml/data` and `ml/artifacts`, remove the xfail, and re-run the seed and the risk table.
- **API impact:** `services/risk.py` keeps its interface.
- **Honest slide wording until then:** "An experimental ML risk signal, trained on simulated project snapshots; the primary forecast is the Monte Carlo simulation."

**M-7 – sprint endpoints and a sprint filter (≈ 3–4 h).**
- **What:** a new `routers/sprints.py` for `GET/POST /projects/{id}/sprints` and `PATCH/DELETE /sprints/{id}` (≈ 80 lines), plus schemas (≈ 20) and tests (≈ 60). On the Board, a sprint dropdown filter (≈ 40 lines).
- **Honest slide wording until then:** "The AI planner groups tasks into sprints and stores them; sprint management screens are future scope."

## 5. Honest-numbers box

**Safe to quote**
- Estimator: TF-IDF + Ridge on 23,313 public Jira issues; test MAE **3.14** vs **3.26** median baseline (MdAE 1.89 vs 2.00), a small improvement.
- NASA93 effort benchmark: 93 projects, 5-fold CV MAE ≈ **308** person-months, R² **0.27 ± 0.63**, which is weak.
- Monte Carlo: **5,000** seeded runs; overrun log-normal(0.10, 0.35), learned from ≥ 10 finished tasks.
- Health formula and its four penalties, recomputed by hand and matching exactly.
- Assignment: Hungarian algorithm, verified optimal against an independent integer program.
- **226** automated tests (plus 1 documented expected failure), passing on SQLite and PostgreSQL.
- 16 demo projects, 16/16 behave as designed.

**Avoid saying**
- "The risk model is 93 % accurate." Say instead: "93 % agreement with the simulation that generated its labels; experimental."
- "The ML predicts delays."
- "Sprint management."
- "Reports" (unless the slide means the analytics dashboards).
- "What-if simulation" as a current feature.
- "Works offline", for Ask.
- Any real-world accuracy claim.

## 6. Demo-day risks

| Risk | Mitigation |
|---|---|
| Render free service sleeps (30–60 s wake) | Open `/api/v1/health` 10 min before; keep it open |
| Neon free DB pauses | First request wakes it; run `seed_demo --verify` against Neon that morning (also refreshes dates) |
| LLM rate limit / outage | Planner falls back to the cached plan (amber badge; it is the hospital example – say so). Ask: read the decision log, or show a screenshot taken the day before |
| Demo credentials are public (README + seed) and admin of all demo projects | Fine for fictional demo data on a short-lived URL. Keep the URL private, re-seed before presenting, change `DEMO_PASSWORD` before seeding a public deployment, never store real data there |
| Experimental ML card disagrees with the forecast on 7/16 projects | Stay on Hospital and E-commerce for Analytics (consistent); call the card experimental (DEMO_SCRIPT warning added) |
| No sprint screens | Don't promise them; describe sprints as part of AI plans |
| Data changed during rehearsal | `python -m seed.seed_demo --verify` (~30 s) |

## 7. HUMAN MUST CHECK

1. **Synopsis and slide deck** (not in the repo). Check every Aim, Proposed Solution, Methodology, Advantages and Future Scope claim against section 3, especially reports, what-if simulation, sprints, and any risk-model accuracy claim.
2. **The live-LLM path in the UI.** I verified the API with the real key (plan source=llm; Ask cited D21), but my browser walk ran in cached-only mode. Click Generate Plan → "AI Generated" badge, and Ask → answer with source chip, once with the real key.
3. **Dependency-graph edges.** The hidden browser pane can't render them. Look at IoT Dashboard → Graph on a visible screen.
4. **Two-window live update on the deployed site** (wss through Render's proxy).
5. **The whole deployment** (Neon + Render Blueprint, env vars, seeding Neon). I didn't do it; it needs your accounts.
6. **A full timed rehearsal** of DEMO_SCRIPT.md on the deployed URL, on a projector.
7. **The licence text of the 16 Jira CSVs** at their source repository.

## 8. Commit commands

The fixes are not committed yet. From `C:\MajorProject`:

```bash
git add -A
git commit -m "Final review fixes: admin-escalation, SQLite FK cascade, risk-model inputs and per-project factors, apply-plan validation, forecast date rounding, health/workload consistency, LLM retries, assignee membership, workload labels; docs and REVIEW_REPORT" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git push origin main
```

`PROGRESS.md` has a session-log row for this review (2026-10-08).

---

## Addendum – closing session (2026-10-08)

### Updated verdict: **YES**
The product now matches its aim:
- Every aim point works and is tested.
- The project report promised by the synopsis exists (M16).
- Sprints can be listed and filtered.
- The ML risk model behaves monotonically and is disclosed as experimental and secondary to the Monte Carlo forecast.

What remains is human work: deploying, live checks on the deployed URL, rehearsal, and editing the deck and synopsis. No known bugs are open.

### Status of the open items

| id | item | status | commit |
|---|---|---|---|
| C-1 … M-6 | review fixes | FIXED | 77f9db8 |
| H-6 | risk model erratic | **FIXED**: every feature drives the simulated label; HistGradientBoosting with monotonic constraints; monotonic sweep tests replace the xfail. Accuracy 92.8 %, ROC-AUC 0.93 (against the simulation); ML/Monte Carlo bands agree on **12/16** demo projects (was 5/16, then 9/16) | fc1f0d2 |
| M-7 | sprint endpoints / screens | **FIXED (minimal, as approved)**: read-only `GET /projects/{id}/sprints` with counts, Board sprint filter and badges; manual sprint editing is future scope | 5381748 |
| P13 | "reports" (synopsis objective 5) | **FIXED**: M16 `GET /projects/{id}/report` + printable Report tab, rule-based, no LLM | 117fa54 |
| L-1 | assignment docstring | FIXED | 6d61d8a |
| L-2 | vacuous `or True` test | FIXED (real assertion) | fc1f0d2 |
| L-3 | lint warnings | FIXED (16 → 0) | 6d61d8a |
| L-4 | live-LLM script collectable by pytest | FIXED (`backend/scripts/check_llm_connection.py`) | 6d61d8a |
| L-5 | non-admins may edit project details / add regular members | OPEN by design – documented in README limitations | 6d61d8a |
| L-6 | estimator numbers missing on Benchmarks | FIXED | 6d61d8a |
| L-7 | single 890 kB bundle | OPEN – documented in README limitations | 6d61d8a |
| L-8 | empty `backend/app/ml/` | FIXED (removed) | 6d61d8a |
| L-9 | work due today counts as late | OPEN by definition – documented | 6d61d8a |
| – | deployment preflight (Neon URL test, prod-build URL check, DEPLOY_CHECKLIST.md) | DONE | dd7d0f3 |
| – | testing report, screenshots, deck/synopsis fixes, viva Q&A | DONE | 7aed470, b5bf180, a11f550 |

### HUMAN MUST CHECK – updated
Done since the review: the **dependency-graph edges** are now visible in `docs/screenshots/07_graph.png`.

Still to do:
1. Deploy.
2. Live-LLM click-through in the UI.
3. Two-window live updates over `wss` on the deployed URL.
4. Print preview of a report on paper/PDF.
5. Timed rehearsal.
6. Licence check of the Jira CSVs.
7. Deck and synopsis edits.
