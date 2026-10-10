"""Count the HTTP requests (incl. CORS preflights) a real browser makes on a typical visit.

Run with the backend on :8000 and the frontend on :5173 (demo data seeded).
"""
import time
from collections import Counter
from playwright.sync_api import sync_playwright

WEB = "http://localhost:5173"
reqs = []

with sync_playwright() as p:
    b = p.chromium.launch(channel="msedge", headless=True)
    page = b.new_context(viewport={"width": 1400, "height": 900}).new_page()
    page.on("request", lambda r: reqs.append((r.method, r.url)) if ":8000" in r.url else None)

    def step(name, fn):
        start = len(reqs); fn(); page.wait_for_load_state("networkidle"); time.sleep(0.8)
        new = reqs[start:]
        pre = sum(1 for m, _ in new if m == "OPTIONS")
        print(f"{name:28} {len(new) - pre:3} API calls  + {pre:2} CORS preflights")

    step("open login page", lambda: page.goto(WEB + "/login"))
    def login():
        page.fill('input[type="email"]', "demo@intellipm.demo"); page.fill('input[type="password"]', "Demo@1234")
        page.get_by_role("button", name="Sign in").click(); page.wait_for_url("**/dashboard")
    step("sign in -> dashboard", login)
    step("open a project (Board)", lambda: page.locator("main .cursor-pointer").first.click())
    for tab in ["Plan", "Team", "Analytics", "Graph", "Decisions", "Report", "Overview", "Board"]:
        step(f"tab {tab}", lambda t=tab: page.get_by_role("button", name=t, exact=True).first.click())
    step("back to dashboard", lambda: page.go_back())
    b.close()

total_pre = sum(1 for m, _ in reqs if m == "OPTIONS")
print(f"\nTOTAL {len(reqs) - total_pre} API calls + {total_pre} preflights")
paths = Counter(u.split(":8000")[1].split("?")[0] for m, u in reqs if m != "OPTIONS")
for path, n in paths.most_common(40):
    print(f"  {n}x {path}")
