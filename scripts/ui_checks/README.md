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
```

Each prints PASS/FAIL lines (or a problem list) and exits non-zero on failure. They create throw-away users and
projects with `@boardtest.org` emails in whichever database the backend uses.
