# IntelliPM – 10-minute demo script

Login for the whole demo: **`demo@intellipm.demo` / `Demo@1234`** (admin of all 16 demo projects).
Numbers below are what the seeded data shows *today*; because dates are relative they can move by a few points, so say "about".

## Before you present

**The day before**
- [ ] `git pull`, deployed site works: open `https://<api-url>/api/v1/health` then the web URL.
- [ ] Rehearse once end to end with a stopwatch (target 9½ min so you have buffer).
- [ ] Record the backup video / take screenshots of: Analytics tab of *E-commerce Platform*, Graph tab of *IoT Dashboard*, an Ask answer on *Event Booking System*, the Plan tab with an "AI Generated" plan.

**The morning of the demo** (so dates are fresh)
```powershell
cd backend
$env:DATABASE_URL = "<your Neon string>"      # skip this line to reseed the local SQLite instead
$env:SECRET_KEY   = "any-non-default-value"
python -m seed.seed_demo --verify             # must print 16/16 stories show the intended behaviour
```

**10 minutes before**
- [ ] Open the API health URL (wakes the free Render service, 30–60 s).
- [ ] Log in, open the Dashboard, zoom the browser to ~110 %, close other tabs.
- [ ] Optional backup: local copy running (`uvicorn app.main:app --port 8000` and `npm run dev`) on the SQLite demo data.

> The demo **changes data** in two places (Apply assignments in step 4, Apply to Project in step 7). Re-run the seed command afterwards to reset.

---

## The flow

| Time | Where | Click | Say |
|---|---|---|---|
| **0:00–0:45** | Login → **Dashboard** | Log in. Point at the 16 cards. | "IntelliPM is a project-management tool like Jira, with a decision-support layer. This is a demo account with 16 fictional projects, each designed to show one situation. Every card has a risk badge computed from the project's data, not typed in by hand." |
| **0:45–1:15** | Dashboard | Hover Hospital (Low risk), E-commerce (High risk), University Portal (Medium). | "Low, Medium, High risk comes from a 0–100 health score: 75 and up is Low, below 50 is High. I'll show why two of them differ so much." |
| **1:15–2:45** | **Hospital Management System** → **Board** | Open a card (drawer: assignee, estimate, due date, dependencies). Drag one card to another column, press F5, show it stayed. | "A normal Kanban board: drag and drop persists, dependencies can't form cycles, and every change is written to an activity log." |
| | *(optional, 30 s)* | Open the same project in a **second browser window** next to the first, both on **Board** (green "Live" badge). Drag a card in window 2; window 1 updates by itself. | "Changes appear for everyone instantly over a WebSocket. If the socket ever drops the badge turns amber, the app keeps working through the normal API, and it reconnects by itself." |
| | → **Analytics** | Point to: Health ≈ 97 with tiny penalties; forecast histogram with P50/P80/P90 lines *left of* the white Due line; burndown close to the dashed ideal line; delay risk low. | "This project is healthy. The forecast is a Monte Carlo simulation: 5,000 runs where each task takes its estimate times a random overrun. P50 means half the runs finish by that date; P90 is the cautious date. All three are before the due date, so the chance of being late is about 7 %." |
| **2:45–4:00** | **E-commerce Platform** → **Analytics** | Health ≈ 40, High risk. Penalty bars (overdue, schedule slip). Forecast: bars sit *right of* the Due line; "P(late) = 100 %". Burndown: Actual above Ideal. | "Same screens, opposite story. The health score is `100 − 30·overdue − 20·blocked − 15·overload − 35·slip`, and the bars show which term hurts: a third of open tasks are overdue and progress is far behind the calendar. The simulation says it is essentially certain to miss the due date. The ML card also gives a delay probability and the top factors." |
| | → **Team** | Show workload bars: Karan ≈ 190 %, Ananya ≈ 165 %, two at ≈ 115 % – all "Overloaded". | "The cause is visible: four people are loaded well past 100 % of their capacity." |
| **4:00–5:15** | **Library Management** → **Team** | Click **Recommend assignments**. Read one row's reason aloud. Click **Apply assignments**, then open **Board** to show tasks now have assignees. | "This project just started and nothing is assigned. The optimiser scores every person–task pair on skill match, availability and on-time history, then solves the best overall matching with the Hungarian algorithm. Every row has a plain-English reason, and nothing changes until an admin clicks Apply." |
| **5:15–6:15** | **IoT Dashboard** → **Graph** | Show red nodes and red animated edges; click a red node to open its drawer (what it waits on). Optionally open **Decisions** and show "Mock the API so the UI can move". | "Each node is a task, coloured by status. Red means blocked: it is open but something it depends on isn't finished. Most of the dashboard work is waiting on the late cloud API – that is why this project is High risk, and why the team logged a decision to mock the API." |
| **6:15–8:00** | Dashboard → **New Project** → title "Campus Bus Tracker" → open it → **Plan** | Type: *"Build a campus bus tracking app with live map, driver app and notifications"*, team size 4, 8 weeks → **Generate Plan** (≈ 10 s). Show the **AI Generated** badge, sprints, tasks, the model-suggested hours and any ⚠ review flags. Click **Apply to Project**, then **Board**. | "One sentence becomes a plan: sprints, tasks, estimates and dependencies. The LLM's output is validated – cycles broken, estimates clamped. Next to the LLM's hours you see a second opinion from a model I trained on 23,000 real Jira issues; where they disagree by 3× it flags the task but never overwrites. Nothing is saved until the admin applies it." |
| **8:00–9:00** | **Event Booking System** → **Decisions** | In the Ask box type *"Why do we hold seats for 10 minutes?"* → answer with a source chip (Decision). Then ask *"What is the capital of France?"* → "can't find". | "Teams forget why they decided things. Eight decisions are logged here. Ask answers only from this project's tasks, decisions and recent activity, cites its sources, and says so when the answer isn't there, so it can't invent facts." |
| **9:00–9:40** | Dashboard → **Benchmarks** | Show the "benchmark on public NASA93 data (93 projects)" label, the estimator vs baseline numbers, and the *simulated data* notice on the risk model. | "Honesty slide: the estimator beats the median baseline by a modest margin. The NASA93 effort model is only a benchmark of the method on 93 real projects – its cross-validated R² is about 0.27, which is weak, and I report it as is. And the risk classifier is trained on simulated projects – its 93 % measures agreement with the simulator, not real-world accuracy." |
| **9:40–10:00** | Dashboard | Back to the 16 cards. | "To summarise: it plans, assigns, forecasts and explains, and every number is traceable to a formula or a model. Limits: simulated risk data, simple capacity model, no live sync yet. Questions?" |

---

## Backup plans

| If this fails | Do this |
|---|---|
| **Plan generation is slow or errors** (Groq down, rate limit) | The app already falls back **Groq → Gemini → cached plan**; you will see an amber **Cached Plan** badge. Say: "That is the safety net – the app never leaves you without a plan." To force it on purpose: set `USE_CACHED_PLAN_ONLY=true` in the Render env vars (service restarts) or in `backend/.env` locally. |
| **Ask shows "No AI provider…" / "could not be reached"** | Ask has no cached answer by design. Read the **decision log** on the same page instead ("the answer is in these entries, Ask just finds it faster"), or show the screenshot you took the day before. Do not retry more than once. |
| **Site is slow to respond** (Render free service waking) | Wait 30–60 s; talk through the Dashboard badges meanwhile. Next time open the `/api/v1/health` URL 10 minutes earlier. |
| **"Network Error" in the browser** | Almost always `CORS_ORIGINS` or `VITE_API_BASE_URL` (see README → Deployment → Troubleshooting). Switch to the local copy of the app. |
| **No internet at all** | Local copy: `uvicorn app.main:app --port 8000` + `npm run dev`, `USE_CACHED_PLAN_ONLY=true`. Everything except Ask works offline. |
| **Data got messy during rehearsal** | `python -m seed.seed_demo --verify` (30 s). |
| **Live badge stays amber / says Offline** | Skip the optional live-update beat. Everything else is unaffected (the socket is a bonus); a refresh shows the latest data. |
| **A screen is blank** | F5. If still blank, use the screenshots / backup video and keep talking. |

## Likely questions

- **Why Monte Carlo and not a simple average?** Because task overruns are uncertain; a distribution gives P50/P80/P90 and a probability of missing the date instead of one false-precise date.
- **Why the Hungarian algorithm?** It finds the globally best one-to-one matching in polynomial time; greedy "best person for each task in turn" can steal the only skilled person from a later task.
- **Is the risk model real?** No – trained on simulated projects, labelled by the Monte Carlo. It's labelled that way in the UI. The health score and forecast are the primary, formula-based indicators.
- **What stops the LLM making things up?** Planner output is schema-validated and post-processed; Ask sees only this project's data, must cite ids, and cited ids are checked against the data.
- **What would you do next?** Real project history for the risk model, sprint screens, live updates, per-person calendars in the forecast.
