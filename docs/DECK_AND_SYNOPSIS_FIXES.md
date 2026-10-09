# Deck and synopsis – fixes before the panel (Oct 17)

Source documents: `G33_MajorProjectSynopsis.docx` (repo root, read, **not edited**). The slide deck PDF is **not in the repo**, so the deck rows below come from the list of known issues you gave and could not be checked against the file itself – verify each one on the slides.
"Status" compares the claim with the product as built and tested on 2026-10-08 (see `docs/TESTING_REPORT.md`).

## 1. Synopsis – claim by claim

| Section | Claim (paraphrased) | Status | Replacement wording (where needed) |
|---|---|---|---|
| 1 Background | "AI-powered platform … smart recommendations … reduces manual work" | WORKS | – |
| 1 Background | "automates task allocation" | PARTIAL (by design the AI *recommends*, the manager applies) | "recommends task allocation with an explainable optimiser; the manager approves it with one click" |
| 1 Background | "centralized workspace with real-time project updates and insights" | WORKS | – (live board updates over WebSockets, analytics, report) |
| 2 Problem | "recommend task assignments, predict project risks, optimize workload, provide insights" | WORKS | Say how: "Hungarian-algorithm assignment, Monte Carlo forecast + health score, rule-based report" |
| 3 Objective 1 | Platform for efficient planning and management | WORKS | – |
| 3 Objective 2 | "Automate task assignment and optimize team workload using AI" | PARTIAL | "Recommend task assignments and balance team workload with an explainable optimiser (skills, availability, on-time history); the manager decides." |
| 3 Objective 3 | "Predict potential project risks and provide timely recommendations" | WORKS | "Forecast completion (Monte Carlo P50/P80/P90 and delay probability) and a 0–100 health score with its reasons, plus an experimental ML risk signal trained on simulated data; suggest actions in the project report." |
| 3 Objective 4 | "Improve team collaboration through **real-time communication** and progress tracking" | PARTIAL (no chat/comments) | "Improve team collaboration through **real-time collaboration via live board updates**, a shared decision log and progress tracking." |
| 3 Objective 5 | "Generate intelligent reports and insights" | WORKS (added as M16) | "Generate project reports with rule-based insights and suggested actions (printable / PDF)." |
| 4 Literature | "Very few systems provide PM, AI recommendations, collaboration, analytics and risk prediction in one platform" | MISLEADING if unqualified (Jira, ClickUp, Asana, Monday now ship AI assistants) | "Commercial tools add generative-AI assistants, but they rarely *explain* their recommendations or forecasts; IntelliPM focuses on explainable decision support (every score shows its reason)." |
| 4 Literature table #1 | Nenni et al. **(2024)** | INCONSISTENT with reference [1] (2025) | Use one year in both places. The reference gives *Management Review Quarterly* vol. 75, 2025; the DOI (10.1007/s11301-024-00418-z) shows it was published online in 2024. Recommended: "Nenni et al. (2025)" and, if wanted, "(online 2024)". **Check the publisher page.** |
| 4 Literature table #3 | "**Qureshi** et al. (2023), Artificial Intelligence Enabled Project Management: A Systematic Literature Review" | LIKELY WRONG AUTHOR | To my knowledge that title is by **Taboada et al. (2023)** (as on the deck). Verify on the publisher page and use the same author in synopsis and deck. |
| 4 Literature table #2, #3, #4 | Adamantiadou & Tsironis (2025); Qureshi/Taboada (2023); Bahroun et al. (2023) | MISSING from the reference list | Add full references (authors, title, journal, volume, pages, year, DOI) for every paper in the table; verify each DOI. |
| 10 References | [2] and [5] are the same book (Fowler, *Patterns of Enterprise Application Architecture*) | DUPLICATE | Delete [5]. |
| 10 References | [2] Fowler, [4] Ries *The Lean Startup* | NOT AI-in-PM literature | Keep only if cited in the text; otherwise replace with the review papers above. [3] *Scrum Guide* can stay for the Agile methodology. |
| 5 Methodology | Agile; auth, projects, tasks, team, dashboards, **reporting**; AI for recommendation, workload, risk; tested and deployed | WORKS except deployment (prepared, not yet done) | After deploying: unchanged. Before: "deployment-ready (Render + Neon)". |
| 6 Technology | React, Tailwind, FastAPI, PostgreSQL, scikit-learn, Pandas, JWT, Git/GitHub | WORKS but incomplete | Add: SQLAlchemy 2.0, SQLite for development, LLM via Groq (Gemini fallback, OpenAI-compatible SDK), NumPy/SciPy (Monte Carlo, Hungarian algorithm), Recharts, React Flow, WebSockets, Render + Neon hosting. **No Docker.** |
| 7 Outcomes | "collaborate with team members" | PARTIAL | "share one live board, a decision log and a project report" (no chat) |
| 7 Outcomes | AI module "generate reports" | WORKS | note: rule-based, no LLM in the report |
| 7 Deliverables | web app, source code, **database design**, AI modules, **testing reports**, documentation | WORKS / PARTIAL | Testing report: `docs/TESTING_REPORT.md`. Database design: tables are in `PROJECT_SPEC.md` §6 and `backend/app/models.py` – add an ER diagram to the final report. |
| 8 Scope | students, startups, teams; future mobile, integrations, advanced AI | WORKS | – |
| 9 Timeline | **five** phases (requirements, design, development, testing, documentation) | INCONSISTENT with the deck (four phases) | Pick one. Recommended: keep the synopsis's **five** phases in the deck too. |

## 2. Deck – known required fixes (verify on the slides)

| Slide | Problem | Fix |
|---|---|---|
| Technologies | Lists **Docker** (not used) | Replace with "Render deployment (no Docker); Neon PostgreSQL". Add the missing items from the Technology row above. |
| System Interface | Screenshots of an old app branded **"Drafting"** | Replace with `docs/screenshots/01_login.png` … `10_benchmarks.png` (1600×900). Suggested set: 02 dashboard, 03 board, 06 analytics, 07 graph, 09 report. |
| Objectives / Aim | "real-time communication" | "real-time collaboration through live updates" |
| Proposed Solution / Features | If "reports" are listed | Now true: "printable project report with rule-based insights and suggested actions" |
| Future Scope | Make it contain exactly what is *not* built | what-if simulation; manual sprint management (sprints can now be listed and filtered, not edited); team chat / comments; GitHub integration; real project history for training the risk model; mobile app |
| Timeline | Four phases | Use the same five phases as the synopsis |
| Literature | Taboada et al. 2023 on the deck vs "Qureshi" in the synopsis; Nenni 2025 on the deck vs 2024 in the synopsis | Use one author and one year everywhere (see section 1) |
| Any accuracy claim for the risk model | e.g. "93 % accurate risk prediction" | "Experimental ML signal trained on simulated data: 92.8 % accuracy / ROC-AUC 0.93 against the simulation, not real projects. The primary forecast is the Monte Carlo simulation." |

## 3. Suggested new slide – "Results and Evaluation"

Use only these numbers (all from `README.md` / `docs/TESTING_REPORT.md`):

- **Testing:** 260 automated tests pass on SQLite and PostgreSQL. The demo data reproduces all 16 designed project stories (16/16). Permission matrix: 47/47 checks. The app degrades gracefully in all four AI failure modes (cached-only, bad key, missing fallback, timeout).
- **Explainability, verified by hand:** the health score recomputes exactly from raw data. The assignment optimiser matches an independent integer-program optimum.
- **Effort estimation:** TF-IDF + Ridge trained on 23,313 public Jira issues. Test MAE 3.14 story points vs 3.26 for the median baseline, a small but real improvement.
- **NASA93 benchmark:** 93 public projects, cross-validated R² 0.27 ± 0.63. Weak; shown as a benchmark of the method.
- **Delay risk:** the Monte Carlo forecast (5,000 runs) is the primary estimate. The ML signal is experimental, trained on 6,000 simulated snapshots with monotonic constraints. Its accuracy is 92.8% and ROC-AUC 0.93, measured against the simulation. It agrees with the Monte Carlo band on 12 of the 16 demo projects.
- **Limitations, said aloud:** the risk model has no real-world validation, the capacity model is simple, and there is no chat or sprint editing.

## 4. Things not to claim

- "Automates" assignment: say "recommends; the manager decides".
- "AI predicts delays with 93 % accuracy".
- "Real-time chat / communication".
- Docker, what-if simulation, GitHub integration, or sprint editing as current features.
- Any user study or real-company validation (none was done).
