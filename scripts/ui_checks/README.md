# Browser checks (manual regression, not part of `pytest`)

Real-browser checks of the board, every project tab, accounts, security, sorting and the light / dark theme. They use Playwright driving the
**installed Microsoft Edge** (no browser download needed).

One-time setup (any folder):

```bash
python -m venv pwenv
pwenv\Scripts\python -m pip install playwright httpx
```

Run (backend on :8000 and `npm run dev` on :5173 must be running; `all_tabs_scan.py` needs the demo data: `python -m seed.seed_demo`):

```bash
pwenv\Scripts\python scripts\ui_checks\board_drag_check.py        # real pointer drags incl. EMPTY columns
pwenv\Scripts\python scripts\ui_checks\board_lifecycle_check.py   # create / move / duplicate warning / delete, all live
pwenv\Scripts\python scripts\ui_checks\all_tabs_scan.py           # every tab of six projects: console errors, failed requests
pwenv\Scripts\python scripts\ui_checks\register_check.py          # register screen: bad username shows a message, valid one works
pwenv\Scripts\python scripts\ui_checks\account_switch_check.py    # no data from the previous account after sign-out / sign-in, two tabs
pwenv\Scripts\python scripts\ui_checks\team_journey_check.py      # owner adds a person by email; that person sees ONLY that project
pwenv\Scripts\python scripts\ui_checks\features_check.py          # task numbers, admin override, skills to learn, Security page, password rules
pwenv\Scripts\python scripts\ui_checks\dashboard_sort_check.py    # dashboard Sort: every field, reverse button, remembered
pwenv\Scripts\python scripts\ui_checks\theme_check.py             # Light / Dark / Auto, no flash, other tabs follow, WCAG AA contrast in both themes
pwenv\Scripts\python scripts\ui_checks\request_count.py           # how many API calls a typical visit makes (performance)
node scripts\ui_checks\errors_check.mjs                             # the shared API-error-to-text function
node scripts\ui_checks\project_sort_check.mjs                       # the dashboard sort function
```

Testing the production build with the real security headers (Content-Security-Policy from `render.yaml`):

```bash
cd frontend && npm run build && cd ..
python scripts\ui_checks\serve_dist_with_headers.py                # serves frontend/dist on :5173 (stop `npm run dev` first)
pwenv\Scripts\python scripts\ui_checks\csp_check.py               # every screen, live updates and fonts with no CSP violation
```

For many sign-ups in a row, start the backend with `REGISTER_LIMIT_PER_HOUR=100000` (the default sign-up limit is 30 per hour per IP).

Each prints PASS/FAIL lines (or a problem list) and exits non-zero on failure. They create throw-away users and
projects with `@boardtest.org` emails in whichever database the backend uses.
