# Viva preparation – 20 likely questions with honest answers

Answers are grounded in the code and in `docs/TESTING_REPORT.md`. Keep them short; offer to show the code or the screen.

**1. What is new compared with Jira, ClickUp or Asana AI?**
Those tools add generative assistants (summaries, writing help). IntelliPM focuses on *explainable decision support*: each recommendation and score shows its reason. Examples: the assignment table gives skill / availability / on-time numbers per row, the health score shows its four penalties, and the forecast shows P50/P80/P90 with the assumptions. The AI recommends; nothing is applied without the manager's click. We don't claim to be better than those products in general; this is a prototype built around one idea.

**2. Why FastAPI?**
Python is where the ML lives (scikit-learn, NumPy, SciPy), so one language runs the API and the models. FastAPI gives typed request/response models (Pydantic v2), automatic API docs at `/docs`, WebSocket support and good performance with little code.

**3. Why didn't you train your own LLM?**
It's not feasible or necessary. Training even a small LLM needs data and compute far beyond a student project. We use a hosted model (Groq, with Gemini as fallback) only where language is needed: turning a sentence into a plan, and answering questions from the project's own data. Everything numeric is deterministic code or classical ML we trained ourselves.

**4. What data did you use?**
- **Estimator:** 16 public Jira story-point datasets (23,313 issues).
- **Effort benchmark:** the public NASA93 COCOMO data from the PROMISE repository.
- **Risk classifier:** 6,000 *simulated* project snapshots; no public dataset of project snapshots exists.
- **Demo:** 16 fictional projects with fictional users.

No personal or company data is used.

**5. How does the plan generator work, and what if the LLM is wrong?**
- The prompt asks for strict JSON matching a schema.
- The reply is validated, with one retry on invalid JSON.
- The plan is then cleaned: unknown dependencies dropped, cycles broken, hours clamped to 1–40, at most 40 tasks.
- The same validation now runs again when a plan is applied.
- If both providers fail, a cached plan is used and labelled "Cached Plan".
- The draft is never saved until an admin clicks Apply.

**6. How does the assignment work?**
For every task and person, `score = 0.5·skill match + 0.3·availability + 0.2·on-time rate`. Skill match is the average of skill level ÷ 5 over the required skills. Availability is the share of remaining capacity left after this task. The Hungarian algorithm (`scipy.optimize.linear_sum_assignment`) picks the assignment with the best total score, with each person given capacity-based "slots". We checked it against an independent integer-program solver: same optimum. Every row carries a sentence built from its three numbers.

**7. How does the forecast work?**
It's a Monte Carlo simulation with 5,000 runs:
- Each open task takes its estimate × a random log-normal overrun (about 10% over by default). The overrun is learned from the project's own finished tasks when at least 10 have actual hours.
- Each run takes the longer of two times: all the work spread over the team's productive hours (capacity × 0.7), or the longest dependency chain done by one person.
- The 50th/80th/90th percentiles are P50/P80/P90, and the share of runs after the due date is the delay probability.
- It's seeded, so results are reproducible.

**8. How is the health score computed?**
`100 − 30·overdue − 20·blocked − 15·overload − 35·slip`, clipped to 0–100. Overdue is the share of open tasks past due, blocked the share with an unfinished dependency, overload how far the busiest person is over 100%, and slip how far progress lags the calendar. The weights are our heuristic, not fitted. We recomputed it by hand from raw database rows and it matches exactly.

**9. Why is the ML risk model "experimental"?**
It's trained on simulated data, so we can't claim it predicts real projects. The Monte Carlo forecast is the primary estimate and the ML signal is secondary. We kept it to show the ML pipeline: feature engineering, training, monotonic constraints, evaluation, and per-project explanations.

**10. Isn't that circular – training on labels from your own simulation?**
Yes, partly, and we say so. The labels come from a Monte Carlo over the same quantities the features describe. So the 92.8% accuracy / 0.93 ROC-AUC measures agreement with that simulation, not real-world accuracy. We made it as defensible as we could:
- Every feature has a documented effect in the simulator: overload lowers throughput, blocking adds idle time, overdue work and slip raise overruns.
- Monotonic constraints guarantee the risk moves in the explainable direction.

Real project history is the first item in our future work.

**11. Your NASA93 result is weak (R² 0.27) – why show it?**
It's honest benchmarking of the method on 93 heterogeneous real projects: too few samples for a stable model, which is why the ± 0.63 across folds is so large. It doesn't drive any score in the app. Hiding a weak result would be worse.

**12. Is the estimator any good?**
It's a modest improvement: test MAE 3.14 story points vs 3.26 for always predicting the median. Story points from text are noisy. It's shown *next to* the LLM's estimate as a second opinion, it flags 3× disagreements, and it never overwrites.

**13. How do you stop the Q&A from making things up?**
Ask only sees this project's tasks, decisions and last 50 activity rows, each line tagged with an id. The model must cite tags and say when the answer isn't there. Cited ids that aren't in the context are discarded, so the UI never shows an invented source. Tests cover this with a mocked LLM.

**14. How is the app secured?**
- Passwords are bcrypt-hashed, and logins use JWTs that expire after 12 hours.
- Every project route checks membership: outsiders get 404, so ids can't be probed. Admin-only actions return 403.
- We ran a 47-check permission matrix.
- The final review found and fixed a privilege-escalation bug (a member could add an admin) and an SQLite cascade bug.
- Secrets live only in environment variables. The app refuses to start on PostgreSQL with the default secret key.
- Limits: no rate limiting, no refresh tokens, and the demo login is public.

**15. Does it scale?**
For a classroom or a small team, yes. Beyond that there are three limits:
- The forecast runs 5,000 simulations per request (fine for tens of tasks; it would need caching for thousands).
- Live updates keep connections in one server's memory, so several servers would need a message broker such as Redis.
- The free hosting sleeps when idle.

The database layer already runs on PostgreSQL with only `DATABASE_URL` changed.

**16. How did you test it?**
- 257 automated tests, passing on both SQLite and PostgreSQL.
- A seed script that rebuilds 16 demo projects and checks each tells its designed story (16/16).
- Failure-mode runs without the LLM.
- An endpoint sweep, the permission matrix, and a click-through of the demo script.

Details are in `docs/TESTING_REPORT.md`.

**17. What happens if the AI service is down during the demo?**
The planner falls back to a cached plan and says "Cached Plan". Ask shows a clear "AI service could not be reached" message instead of crashing. Everything else (board, assignment, forecast, health, report) needs no LLM at all.

**18. What would you do next?**
1. Real project histories to train and validate the risk model.
2. What-if simulation (e.g. "add one developer").
3. Manual sprint management.
4. Team chat / comments.
5. GitHub integration.
6. Per-person calendars in the forecast.

**19. Which parts did you write, which were generated, and how did you verify them?**
*Answer truthfully for your own team; template:*
- "We wrote the specification (`PROJECT_SPEC.md`): the data model, the API and the exact formulas.
- We planned the modules and reviewed every one.
- Much of the code was produced with AI coding assistants working from that specification, one module at a time.
- We verified it: each module has tests, and a final review recomputed the health score and assignments by hand.
- We fixed what the review found (listed in the testing report), and we can explain every formula and file."

Each member should be ready to explain the module they reviewed most closely.

**20. Why should we trust your demo numbers?**
- The demo data is generated relative to today with a fixed random seed.
- A verify script prints each project's designed vs actual health and delay band; all 16 match.
- The same numbers appear in the Analytics tab, the Team tab and the Report, because the report calls the same code.
- Anything uncertain is labelled: the ML card says experimental and simulated.
