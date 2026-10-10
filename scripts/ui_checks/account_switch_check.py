"""Account isolation in the browser: switching accounts in the SAME tab / browser must never show the
previous account's data, and a project appears for a new user only once they are added to it."""
import sys, time, uuid
import httpx
from playwright.sync_api import sync_playwright

WEB = "http://localhost:5173"; API = "http://localhost:8000/api/v1"
sfx = uuid.uuid4().hex[:6]
results = []
def check(name, ok): results.append(ok); print(("PASS " if ok else "FAIL ") + name)

def cards(page):  # project cards on the dashboard
    return page.locator("main .cursor-pointer").count()

def login_ui(page, email, pw, spa=False):
    if not spa:
        page.goto(WEB + "/login")
    page.wait_for_load_state("networkidle")
    page.fill('input[type="email"]', email); page.fill('input[type="password"]', pw)
    page.get_by_role("button", name="Sign in").click(); page.wait_for_url("**/dashboard"); page.wait_for_load_state("networkidle"); time.sleep(1.2)

def register_ui(page, full, email, user, pw, spa=False):
    if spa:                      # what a person does: click "Create one" on the sign-in page (no page reload, cache survives)
        page.get_by_role("link", name="Create one").click(); page.wait_for_url("**/register")
    else:
        page.goto(WEB + "/register")
    page.wait_for_load_state("networkidle")
    for i, v in enumerate([full, email, user, pw, pw]): page.locator("form input").nth(i).fill(v)
    page.get_by_role("button", name="Create account").click(); page.wait_for_url("**/dashboard"); page.wait_for_load_state("networkidle"); time.sleep(1.2)

def signout(page):
    page.locator("#logout-button").click(); page.wait_for_url("**/login"); time.sleep(0.4)

with sync_playwright() as p:
    b = p.chromium.launch(channel="msedge", headless=True)
    page = b.new_page(viewport={"width": 1600, "height": 900})

    # A: the demo presenter sees the 16 demo projects
    login_ui(page, "demo@intellipm.demo", "Demo@1234")
    n_demo = cards(page); check(f"demo user sees many projects ({n_demo})", n_demo >= 16)

    # B: sign out and IMMEDIATELY register a new person in the same tab (the reported flow)
    signout(page)
    email = f"newuser{sfx}@isolation.org"
    register_ui(page, "Aditya Pande", email, f"aditya_{sfx}", "Secure#2026", spa=True)
    check("new account sees 0 projects (not the previous user's)", cards(page) == 0)
    txt = page.locator("main").inner_text()
    check("empty state explains how to get access and shows the user's email", "ask a project admin" in txt.lower() and email in txt)
    check("header shows the new account's name", "Aditya Pande" in page.locator("header").inner_text())

    # C: a project owner adds the new user to ONE project -> exactly that one appears (no reload needed after returning)
    tok = httpx.post(f"{API}/auth/login", json={"email": "demo@intellipm.demo", "password": "Demo@1234"}).json()["data"]["access_token"]
    H = {"Authorization": "Bearer " + tok}
    pid = httpx.post(f"{API}/projects", json={"title": f"Something Management {sfx}"}, headers=H).json()["data"]["id"]
    r = httpx.post(f"{API}/projects/{pid}/members", json={"email": email, "role": "member"}, headers=H)
    check("owner can add the new user by email", r.status_code == 201)
    page.reload(); page.wait_for_load_state("networkidle"); time.sleep(1.2)
    check("new user now sees exactly that one project", cards(page) == 1 and f"Something Management {sfx}" in page.locator("main").inner_text())

    # D: sign out, log back in as demo -> demo sees its own list again, not the 1-project list
    signout(page); login_ui(page, "demo@intellipm.demo", "Demo@1234", spa=True)
    check("switching back shows the demo user's full list again", cards(page) >= 17)
    httpx.delete(f"{API}/projects/{pid}", headers=H)

    # E: TWO TABS of ONE browser, each signed in as a DIFFERENT person at the same time (login is per tab)
    ctx = b.new_context(viewport={"width": 1400, "height": 900})
    t1 = ctx.new_page(); t2 = ctx.new_page()
    login_ui(t1, "demo@intellipm.demo", "Demo@1234")
    t1_before = cards(t1)
    t2.goto(WEB + "/login"); t2.wait_for_load_state("networkidle")
    check("a second tab does NOT start logged in as tab 1's account", "/login" in t2.url)
    register_ui(t2, "Second Person", f"second{sfx}@isolation.org", f"second_{sfx}", "Secure#2026", spa=False)
    time.sleep(2.5)                                    # give any (removed) cross-tab sync time to misbehave
    check("tab 1 is STILL the demo user", "Demo Presenter" in t1.locator("header").inner_text())
    check("tab 2 is the second person", "Second Person" in t2.locator("header").inner_text())
    check("tab 1 still shows its projects, tab 2 shows none", t1_before >= 16 and cards(t1) >= 16 and cards(t2) == 0)
    t1.reload(); t1.wait_for_load_state("networkidle"); time.sleep(1.2)
    t2.reload(); t2.wait_for_load_state("networkidle"); time.sleep(1.2)
    check("each tab keeps its own login after a refresh", "Demo Presenter" in t1.locator("header").inner_text() and "Second Person" in t2.locator("header").inner_text())
    # signing out in one tab must not sign out the other
    signout(t2); t1.reload(); t1.wait_for_load_state("networkidle"); time.sleep(1)
    check("signing out in tab 2 leaves tab 1 signed in", "/dashboard" in t1.url and cards(t1) >= 16)
    b.close()

print(f"\n{sum(results)}/{len(results)} checks passed")
sys.exit(0 if all(results) else 1)
