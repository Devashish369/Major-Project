"""
seed/verify_demo.py – Does every demo story show the behaviour it was designed for?

    python -m seed.verify_demo

Logs in as the demo presenter and calls the real API (health, forecast, workload)
for each demo project, then prints the designed health level / delay-probability
band next to what the app actually computes.  Exit code 1 if any story is off.
"""

import sys

from fastapi.testclient import TestClient

from app.main import app
from seed.demo_projects import DEMO_PASSWORD, PRESENTER, PROJECTS

API = "/api/v1"
SHORT = {"Low risk": "Low", "Medium risk": "Medium", "High risk": "High"}


def main() -> int:
    client = TestClient(app)
    r = client.post(f"{API}/auth/login", json={"email": PRESENTER[0], "password": DEMO_PASSWORD})
    if r.status_code != 200:
        print("Cannot log in as the demo presenter - run `python -m seed.seed_demo` first.")
        return 1
    h = {"Authorization": f"Bearer {r.json()['data']['access_token']}"}

    listed = client.get(f"{API}/projects", headers=h).json()["data"]
    by_title = {p["title"]: p for p in listed}

    header = (f"{'#':>2} {'Project':<27}{'Designed':<9}{'Actual':<8}{'Score':>6}  "
              f"{'Delay P':>7} {'Band':<11}{'MaxUtil':>8}{'Blocked':>8}{'Overdue':>8}  OK?")
    print(header)
    print("-" * len(header))
    bad = 0
    for i, spec in enumerate(PROJECTS, 1):
        proj = by_title.get(spec["title"])
        if not proj:
            print(f"{i:>2} {spec['title']:<27}MISSING - not seeded")
            bad += 1
            continue
        pid = proj["id"]
        health = client.get(f"{API}/projects/{pid}/analytics/health", headers=h).json()["data"]
        fc = client.get(f"{API}/projects/{pid}/analytics/forecast", headers=h).json()["data"]
        diag = health["diagnostics"]
        level = health["level"]
        want_level, (lo, hi) = spec["expect"]
        delay = fc.get("delay_probability")
        delay = 0.0 if delay is None else delay

        level_ok = level == want_level
        delay_ok = lo <= delay <= hi
        ok = level_ok and delay_ok
        bad += 0 if ok else 1
        flags = "" if ok else (" <- level" if not level_ok else "") + (" <- delay" if not delay_ok else "")
        print(f"{i:>2} {spec['title']:<27}{SHORT[want_level]:<9}{SHORT[level]:<8}{health['health_score']:>6.1f}  "
              f"{delay:>7.0%} {f'{lo:.0%}-{hi:.0%}':<11}{diag['max_utilization']:>8.2f}"
              f"{diag['blocked_ratio']:>8.0%}{diag['overdue_ratio']:>8.0%}  {'OK' if ok else 'NO'}{flags}")

    print("-" * len(header))
    print(f"{len(PROJECTS) - bad}/{len(PROJECTS)} stories show the intended behaviour.")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
