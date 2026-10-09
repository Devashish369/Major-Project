"""Open every tab of several projects in a real browser; report console errors, page errors, failed requests."""
import sys, time
import httpx
from playwright.sync_api import sync_playwright

API = "http://localhost:8000/api/v1"; WEB = "http://localhost:5173"
c = httpx.Client(timeout=30)
tok = c.post(f"{API}/auth/login", json={"email": "demo@intellipm.demo", "password": "Demo@1234"}).json()["data"]["access_token"]
H = {"Authorization": "Bearer " + tok}
projects = {p["title"]: p["id"] for p in c.get(f"{API}/projects", headers=H).json()["data"]}
TABS = ["Overview", "Board", "Plan", "Team", "Analytics", "Graph", "Decisions", "Report"]
problems = []

with sync_playwright() as p:
    b = p.chromium.launch(channel="msedge", headless=True)
    page = b.new_page(viewport={"width": 1600, "height": 900})
    ctx = {"where": ""}
    page.on("console", lambda m: m.type == "error" and problems.append((ctx["where"], "console", m.text[:160])))
    page.on("pageerror", lambda e: problems.append((ctx["where"], "pageerror", str(e)[:160])))
    page.on("response", lambda r: r.status >= 400 and "/ws/" not in r.url and problems.append((ctx["where"], f"HTTP {r.status}", r.url.split("8000")[-1][:90])))
    page.goto(WEB + "/login"); page.evaluate(f"sessionStorage.setItem('intellipm_token', '{tok}')")
    for title in ["Hospital Management System", "E-commerce Platform", "Library Management", "IoT Dashboard", "Event Booking System", "Fitness Tracker"]:
        pid = projects[title]
        for tab in TABS:
            ctx["where"] = f"{title} / {tab}"
            page.goto(f"{WEB}/projects/{pid}"); page.wait_for_load_state("networkidle")
            page.locator("nav button", has_text=tab).first.click()
            page.wait_for_load_state("networkidle"); time.sleep(0.8)
            if not page.locator("main").inner_text().strip():
                problems.append((ctx["where"], "blank", "main area is empty"))
    for path, name in [("/dashboard", "Dashboard"), ("/benchmarks", "Benchmarks")]:
        ctx["where"] = name; page.goto(WEB + path); page.wait_for_load_state("networkidle"); time.sleep(1)
    b.close()

print(f"{len(problems)} problem(s)")
for w, k, d in problems[:30]:
    print(f"  {w:50} {k:12} {d}")
sys.exit(1 if problems else 0)
