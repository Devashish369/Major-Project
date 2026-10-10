"""Browser check for: per-project numbers, admin override of AI assignments, "Skills to learn",
the Security page (activity, change password, sign out everywhere) and the register password rules.

Run with the backend on :8000 and the frontend on :5173.
"""
import sys, time, uuid
import httpx
from playwright.sync_api import sync_playwright

WEB = "http://localhost:5173"; API = "http://localhost:8000/api/v1"
sfx = uuid.uuid4().hex[:6]
PW = "Secure#2026"
results = []
def check(name, ok): results.append(bool(ok)); print(("PASS " if ok else "FAIL ") + name)

def api_user(name, skills):
    r = httpx.post(f"{API}/auth/register", json={"email": f"{name}{sfx}@feat.org", "username": f"{name}_{sfx}",
                                                 "full_name": name.title(), "password": PW})
    tok = r.json()["data"]["access_token"]; H = {"Authorization": "Bearer " + tok}
    httpx.patch(f"{API}/auth/me", json={"skills": skills}, headers=H)
    return H, r.json()["data"]["user"]["id"]

# Data: two projects; the second one's tasks must start at #1
admin, admin_id = api_user("manager", {"rag": 4, "python": 4})
member, member_id = api_user("riya", {"react": 5})
other = httpx.post(f"{API}/projects", json={"title": f"Other {sfx}"}, headers=admin).json()["data"]["id"]
for i in range(10):
    httpx.post(f"{API}/projects/{other}/tasks", json={"title": f"Old {i}"}, headers=admin)
pid = httpx.post(f"{API}/projects", json={"title": f"Chatbot {sfx}", "due_date": "2030-01-01"}, headers=admin).json()["data"]["id"]
httpx.post(f"{API}/projects/{pid}/members", json={"email": f"riya{sfx}@feat.org", "role": "member"}, headers=admin)
for title, skills in [("Build chat UI", ["ReactJS"]), ("LLM answers", ["Gen AI"]), ("Retrieval", ["python"])]:
    httpx.post(f"{API}/projects/{pid}/tasks", json={"title": title, "estimate_hours": 8, "required_skills": skills}, headers=admin)
httpx.post(f"{API}/projects/{pid}/decisions", json={"title": "Use pgvector", "decision": "yes"}, headers=admin)

with sync_playwright() as p:
    b = p.chromium.launch(channel="msedge", headless=True)
    page = b.new_context(viewport={"width": 1500, "height": 950}).new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(WEB + "/login"); page.wait_for_load_state("networkidle")
    page.fill('input[type="email"]', f"manager{sfx}@feat.org"); page.fill('input[type="password"]', PW)
    page.get_by_role("button", name="Sign in").click(); page.wait_for_url("**/dashboard"); page.wait_for_load_state("networkidle")

    # 1. numbering on the board and decisions
    page.goto(f"{WEB}/projects/{pid}"); page.wait_for_load_state("networkidle"); time.sleep(1)
    board = page.locator("main").inner_text()
    check("board shows #1 #2 #3 for the second project", all(f"#{n}" in board for n in (1, 2, 3)) and "#11" not in board)
    page.get_by_role("button", name="Decisions", exact=True).click(); page.wait_for_load_state("networkidle"); time.sleep(0.8)
    check("decision log starts at D1", "D1" in page.locator("main").inner_text())

    # 2. Team tab: skills to learn + override
    page.get_by_role("button", name="Team", exact=True).click(); page.wait_for_load_state("networkidle"); time.sleep(1)
    gap = page.locator('[data-gap="generative ai"]')
    check("Skills to learn lists Gen AI", gap.count() == 1)
    gtxt = gap.inner_text() if gap.count() else ""
    check("Gen AI: closest = the RAG person (Manager), lowest workload shown", "Manager" in gtxt and "rag" in gtxt.lower() and "Lowest workload" in gtxt)
    page.locator("#recommend-btn").click(); page.wait_for_selector("[data-task-row]"); time.sleep(0.5)
    rows = page.locator("[data-task-row]")
    check("recommendation rows show task numbers and titles", rows.count() == 3 and "Build chat UI" in page.locator("main").inner_text())
    sel = page.locator("[data-assignee-select]").first
    options = sel.locator("option").all_inner_texts()
    check("admin gets a dropdown with every member + leave unassigned", len(options) == 3 and any("AI pick" in o for o in options))
    current = sel.input_value()
    new_value = [v for v in sel.locator("option").evaluate_all("els => els.map(e => e.value)") if v not in (current, "skip")][0]
    sel.select_option(new_value); time.sleep(0.3)
    check("changed row is marked 'Changed by admin'", "Changed by admin" in page.locator("main").inner_text())
    page.locator("[data-assignee-select]").nth(1).select_option("skip"); time.sleep(0.3)
    check("apply button counts 2 (one left unassigned)", "Apply 2 assignments" in page.locator("#apply-assignments-btn").inner_text())
    page.locator("#apply-assignments-btn").click(); time.sleep(1.5)
    check("applied with 1 change by the admin", "1 changed by you" in page.locator("main").inner_text())
    tasks = httpx.get(f"{API}/projects/{pid}/tasks", headers=admin).json()["data"]
    check("server state: 2 assigned, 1 unassigned, the changed one went to the chosen person",
          sum(1 for t in tasks if t["assignee_id"]) == 2 and any(t["assignee_id"] == int(new_value) for t in tasks))

    # 3. member sees no dropdown
    mpage = b.new_context(viewport={"width": 1400, "height": 900}).new_page()
    mpage.goto(WEB + "/login"); mpage.wait_for_load_state("networkidle")
    mpage.fill('input[type="email"]', f"riya{sfx}@feat.org"); mpage.fill('input[type="password"]', PW)
    mpage.get_by_role("button", name="Sign in").click(); mpage.wait_for_url("**/dashboard")
    httpx.patch(f"{API}/tasks/{tasks[0]['id']}", json={"assignee_id": None}, headers=admin)
    mpage.goto(f"{WEB}/projects/{pid}"); mpage.wait_for_load_state("networkidle")
    mpage.get_by_role("button", name="Team", exact=True).click(); mpage.wait_for_load_state("networkidle")
    mpage.locator("#recommend-btn").click(); mpage.wait_for_selector("[data-task-row]"); time.sleep(0.4)
    check("non-admin sees suggestions but no dropdown / apply", mpage.locator("[data-assignee-select]").count() == 0
          and mpage.locator("#apply-assignments-btn").count() == 0)

    # 4. Security page
    page.goto(WEB + "/dashboard"); page.wait_for_load_state("networkidle")
    page.locator("#security-link").click(); page.wait_for_url("**/security"); page.wait_for_load_state("networkidle"); time.sleep(0.8)
    check("security page lists sign-in activity", page.locator('[data-event="login_success"]').count() >= 1)
    page.fill("#pw-current", PW); page.fill("#pw-new", "password123"); page.fill("#pw-confirm", "password123")
    page.locator("#change-password-form button[type=submit]").click(); time.sleep(0.4)
    check("weak new password refused in the browser", "too common" in page.locator("main").inner_text())
    old_token = page.evaluate("sessionStorage.getItem('intellipm_token')")
    page.fill("#pw-new", "Fresh#Pass2026"); page.fill("#pw-confirm", "Fresh#Pass2026")
    page.locator("#change-password-form button[type=submit]").click(); time.sleep(1.5)
    check("password changed message", "Password changed" in page.locator("main").inner_text())
    check("old token revoked, this tab still signed in",
          httpx.get(f"{API}/auth/me", headers={"Authorization": "Bearer " + old_token}).status_code == 401
          and httpx.get(f"{API}/auth/me", headers={"Authorization": "Bearer " + page.evaluate("sessionStorage.getItem('intellipm_token')")}).status_code == 200)
    page.once("dialog", lambda d: d.accept())
    page.locator("#logout-all-button").click(); page.wait_for_url("**/login", timeout=10000)
    check("sign out everywhere returns to login", "/login" in page.url)

    # 5. register password rules
    page.goto(WEB + "/register"); page.wait_for_load_state("networkidle")
    for i, v in enumerate(["Weak Person", f"weak{sfx}@feat.org", f"weak_{sfx}", "password123", "password123"]):
        page.locator("form input").nth(i).fill(v)
    page.get_by_role("button", name="Create account").click(); time.sleep(0.6)
    check("register refuses a common password with a clear message", "too common" in page.locator("main, form").first.inner_text().lower() or "too common" in page.content().lower())
    check("no JavaScript errors", not errors)
    b.close()

print(f"\n{sum(results)}/{len(results)} checks passed")
sys.exit(0 if all(results) else 1)
