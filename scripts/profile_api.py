"""
Profile the API: wall time and number of SQL queries per endpoint, on the seeded demo data.

Why the query count matters: in the deployed app every query is a network round trip from the
Render server to the Neon database (tens of ms each), so 100 queries ~ seconds even when each
query is tiny.

    cd backend
    python ../scripts/profile_api.py                 # uses DATABASE_URL / the local SQLite file
Run `python -m seed.seed_demo` first.  Output is a table; nothing is changed in the database.
"""
import sys, time, statistics
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from fastapi.testclient import TestClient            # noqa: E402
from sqlalchemy import event                          # noqa: E402

from app.database import engine                       # noqa: E402
from app.main import app                              # noqa: E402

A = "/api/v1"
counter = {"n": 0}


@event.listens_for(engine, "before_cursor_execute")
def _count(conn, cursor, statement, parameters, context, executemany):
    counter["n"] += 1


def measure(client, headers, path, repeats=3):
    """(first call seconds, median of repeats seconds, queries per call)"""
    counter["n"] = 0
    t0 = time.perf_counter(); r = client.get(A + path, headers=headers); first = time.perf_counter() - t0
    q = counter["n"]
    times = []
    for _ in range(repeats):
        t0 = time.perf_counter(); client.get(A + path, headers=headers); times.append(time.perf_counter() - t0)
    return r.status_code, first, statistics.median(times), q


def main():
    c = TestClient(app)
    tok = c.post(A + "/auth/login", json={"email": "demo@intellipm.demo", "password": "Demo@1234"}).json()["data"]["access_token"]
    H = {"Authorization": "Bearer " + tok}
    ps = {p["title"]: p["id"] for p in c.get(A + "/projects", headers=H).json()["data"]}
    big = ps["Learning Management System"]          # 30 tasks, 9 members: the heaviest demo project
    ec = ps["E-commerce Platform"]
    rows = [
        ("GET /auth/me", "/auth/me"),
        ("GET /projects  (dashboard, 16 cards)", "/projects"),
        (f"GET project (30-task project)", f"/projects/{big}"),
        ("GET members", f"/projects/{big}/members"),
        ("GET tasks", f"/projects/{big}/tasks"),
        ("GET analytics/health", f"/projects/{big}/analytics/health"),
        ("GET analytics/forecast", f"/projects/{big}/analytics/forecast"),
        ("GET analytics/workload", f"/projects/{big}/analytics/workload"),
        ("GET analytics/burndown", f"/projects/{big}/analytics/burndown"),
        ("GET report", f"/projects/{big}/report"),
        ("GET decisions", f"/projects/{ec}/decisions"),
        ("GET sprints", f"/projects/{big}/sprints"),
    ]
    print(f"{'endpoint':42} {'status':>6} {'1st call':>9} {'median':>8} {'queries':>8}")
    total_q = 0
    for label, path in rows:
        status, first, med, q = measure(c, H, path)
        total_q += q
        print(f"{label:42} {status:>6} {first*1000:>7.0f}ms {med*1000:>6.0f}ms {q:>8}")
    print(f"\nTotal queries for one pass over these screens: {total_q}")
    print("Deployed estimate = queries x (Render<->Neon round trip). 1 ms same region, 30-80 ms across regions.")


if __name__ == "__main__":
    main()
