"""Open every screen of the production build (served by serve_dist_with_headers.py) and fail on any
Content-Security-Policy violation or JavaScript error – proves render.yaml's headers don't break the site."""
import sys, time
from playwright.sync_api import sync_playwright

WEB = "http://localhost:5173"
problems = []
with sync_playwright() as p:
    b = p.chromium.launch(channel="msedge", headless=True)
    page = b.new_context(viewport={"width": 1400, "height": 900}).new_page()
    page.on("console", lambda m: problems.append(m.text) if ("Content Security Policy" in m.text or m.type == "error") else None)
    page.on("pageerror", lambda e: problems.append(str(e)))
    r = page.goto(WEB + "/login"); page.wait_for_load_state("networkidle")
    csp = r.headers.get("content-security-policy", "")
    print("CSP header present:", bool(csp))
    page.fill('input[type="email"]', "demo@intellipm.demo"); page.fill('input[type="password"]', "Demo@1234")
    page.get_by_role("button", name="Sign in").click(); page.wait_for_url("**/dashboard"); page.wait_for_load_state("networkidle")
    page.locator("main .cursor-pointer").first.click(); page.wait_for_load_state("networkidle"); time.sleep(1.5)
    live = "Live" in page.locator("body").inner_text()
    for tab in ["Overview", "Plan", "Team", "Analytics", "Graph", "Decisions", "Report", "Board"]:
        page.get_by_role("button", name=tab, exact=True).first.click(); page.wait_for_load_state("networkidle"); time.sleep(1.2)
    page.goto(WEB + "/security"); page.wait_for_load_state("networkidle"); time.sleep(0.8)
    page.goto(WEB + "/benchmarks"); page.wait_for_load_state("networkidle"); time.sleep(0.8)
    font_ok = page.evaluate("document.fonts.check('16px Inter')")
    b.close()

print("live updates (WebSocket) connected under the CSP:", live)
print("Google font Inter loaded under the CSP:", font_ok)
for x in problems:
    print("PROBLEM:", x[:200])
ok = bool(csp) and live and not problems
print("CSP check:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
