# Running IntelliPM for ₹0 – what is free, the limits, and how to make sure nothing is ever charged

Checked against the providers' own pages on 2026-10-11 (Render "Deploy for Free", Neon "Plans").
Prices and limits can change; re-check the two pages before the final submission.

## 1. What the project uses

| Part | Service and plan | Cost |
|---|---|---|
| API (FastAPI) | Render **Free** web service (`plan: free` in `render.yaml`) | ₹0 |
| Website (React) | Render **static site** | ₹0 |
| Database | Neon **Free** PostgreSQL | ₹0 |
| AI planner / Ask | Groq free API key, Gemini free API key (fallback) | ₹0 |
| Keep-awake pings | GitHub Actions, free and unlimited for **public** repositories | ₹0 |
| Code | GitHub public repository | ₹0 |

There are no paid add-ons anywhere in the code or the Blueprint: no persistent disk, no background
worker, no cron job on Render, no paid instance type, no Docker registry, no email/SMS service, no
paid AI model, and no analytics or monitoring SaaS.

## 2. Free limits and what happens at the limit

| Service | Free limit | When it is reached |
|---|---|---|
| Render web service | 750 instance hours / month per workspace; sleeps after 15 min without traffic (≈1 min to wake) | All free web services are **paused** until next month (not billed) |
| Render bandwidth | Monthly included outbound bandwidth (shared by the API and site) | **Billed only if a payment method is on file**; without one, free services are paused instead |
| Render build minutes | Monthly included pipeline minutes | **Billed only if a payment method is on file**; without one, new builds stop, the running site keeps working |
| Neon | 100 CU-hours / month (≈400 h of the smallest compute), 1 GB storage, 5 GB egress, sleeps after 5 idle minutes | Compute is **suspended** until next month; storage over 1 GB makes writes fail. Neon says no data is deleted |
| Groq / Gemini free keys | Requests per minute / per day set by each provider | Requests are refused; IntelliPM falls back to the cached plan or shows "AI service could not be reached" |

## 3. The rules that keep it at ₹0

1. **Do not add a payment method to Render.** Without a card, Render cannot bill: at a limit it can only pause.
2. **Keep `plan: free`** on the web service in `render.yaml`. Never click "Upgrade" or pick a paid instance type.
3. **Do not upgrade Neon**, and do not enable billing on the Google Cloud project that owns the Gemini key
   (Gemini's free tier only stays free while billing is off). Groq's free key cannot be charged unless you upgrade.
4. Keep the repository **public**: GitHub Actions minutes are free and unlimited only for public repos.

## 4. What the project does to stay inside the limits

| Measure | Where | Why |
|---|---|---|
| `buildFilter` on both services | `render.yaml` | A push that only changes `docs/` or `scripts/` (or only backend tests) does not rebuild anything, so build minutes last |
| Keep-awake pings only 06:30–00:30 IST | `.github/workflows/keep-awake.yml` | ≈560 of the 750 free hours; the API still sleeps at night. Pings hit `/api/v1/health`, which does **not** touch the database, so Neon still sleeps and its compute hours are not used |
| gzip responses, cached `/assets/*` files (1 year, content-hashed names) | `app/main.py`, `render.yaml` | Less bandwidth |
| Per-user AI limits: 10 plans, 20 questions, 60 estimates per 10 min | `app/ratelimit.py` | One account (or a stolen token) cannot use up the free AI quota |
| Sign-up limit per network (30/hour) and sign-in brute-force limits | `services/security_events.py` | Bots cannot fill the 1 GB database or hammer the API |
| 1 MB maximum request body; bounded text and list sizes | `app/middleware.py`, `app/schemas.py` | Nobody can store huge payloads |
| Bulk queries and Server-Timing | `routers/*`, `app/middleware.py` | Fewer database round trips means less Neon compute time per page |

## 5. If something stops

- **API shows "Service suspended"** → the 750 hours or the bandwidth ran out; it comes back on the 1st of next
  month. Delete `.github/workflows/keep-awake.yml` if you run other free services in the same Render workspace.
- **Database errors after a quiet month** → Neon compute suspended for the month (CU-hours used up). Check Neon → Usage.
- **"AI service could not be reached"** → the free AI quota for the minute or day is used up; try again later.
  Everything except the planner and Ask works without AI.
