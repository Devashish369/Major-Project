# Browser checks (manual regression, not part of `pytest`)

Real-browser checks of the Kanban board and every project tab. They use Playwright driving the
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
node scripts\ui_checks\errors_check.mjs                             # the shared API-error-to-text function
```

Each prints PASS/FAIL lines (or a problem list) and exits non-zero on failure. They create throw-away users and
projects with `@boardtest.org` emails in whichever database the backend uses.
