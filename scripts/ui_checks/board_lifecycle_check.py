"""End-to-end Board lifecycle with a real browser: every change must show up WITHOUT reloading."""
import sys, time, uuid
import httpx
from playwright.sync_api import sync_playwright

API = "http://localhost:8000/api/v1"; WEB = "http://localhost:5173"
sfx = uuid.uuid4().hex[:6]
c = httpx.Client(timeout=30)
tok = c.post(f"{API}/auth/register", json={"email": f"e2e{sfx}@boardtest.org", "username": f"e2e{sfx}",
                                            "full_name": "Priya Nair", "password": "password123"}).json()["data"]["access_token"]
H = {"Authorization": "Bearer " + tok}
pid = c.post(f"{API}/projects", json={"title": f"E2E {sfx}"}, headers=H).json()["data"]["id"]
results = []
def check(name, ok): results.append(ok); print(("PASS " if ok else "FAIL ") + name)
def tasks(): return c.get(f"{API}/projects/{pid}/tasks", headers=H).json()["data"]
def proj_status(): return c.get(f"{API}/projects/{pid}", headers=H).json()["data"]["status"]

def col_titles(page, label):
    box = page.locator(f"xpath=//span[normalize-space()='{label}']/ancestor::div[contains(@class,'border-t-4')][1]")
    return [t.strip() for t in box.locator("p.text-sm").all_inner_texts()]

with sync_playwright() as p:
    b = p.chromium.launch(channel="msedge", headless=True)
    page = b.new_page(viewport={"width": 1600, "height": 900})
    page.goto(WEB + "/login"); page.evaluate(f"localStorage.setItem('intellipm_token', '{tok}')")
    page.goto(f"{WEB}/projects/{pid}"); page.wait_for_load_state("networkidle"); time.sleep(1.2)

    # 1. Empty board shows hints in all three columns
    check("empty columns show a drop hint", page.get_by_text("Drag a task here").count() == 3)

    # 2. Add a task from the + of the To Do column -> appears immediately, no reload
    page.locator("#add-task-todo").click(); page.fill("#task-title", "Kickoff meeting")
    page.get_by_role("button", name="Create task").click(); time.sleep(1.2)
    check("new task appears in To Do without reload", "Kickoff meeting" in col_titles(page, "To Do"))

    # 3. Duplicate warning when typing the same title again
    page.locator("#add-task-todo").click(); page.fill("#task-title", "kickoff MEETING"); time.sleep(0.4)
    check("duplicate-title warning is shown", page.locator("#duplicate-warning").count() == 1)
    page.get_by_role("button", name="Cancel").click(); time.sleep(0.4)
    check("no duplicate was created", len(tasks()) == 1)

    # 4. Open the card, use the drawer's one-click status buttons: To Do -> In Progress -> Done
    page.locator("main .cursor-pointer", has_text="Kickoff meeting").first.click(); time.sleep(0.6)
    page.locator("[data-status-btn='in_progress']").click(); time.sleep(1.2)
    check("drawer button moves the card to In Progress live", "Kickoff meeting" in col_titles(page, "In Progress"))
    check("project status became In Progress automatically", proj_status() == "in_progress")
    page.locator("[data-status-btn='done']").click(); time.sleep(1.2)
    check("drawer button moves the card to Done live", "Kickoff meeting" in col_titles(page, "Done"))
    check("completed_at was set", tasks()[0]["completed_at"] is not None)
    check("project status became Completed automatically", proj_status() == "completed")
    page.locator("[data-status-btn='todo']").click(); time.sleep(1.2)
    check("moving back clears completed_at", tasks()[0]["completed_at"] is None and proj_status() == "pending")
    page.keyboard.press("Escape")

    # 5. Add into the In Progress column directly, with an assignee -> initials shown on the card
    me = c.get(f"{API}/auth/me", headers=H).json()["data"]["id"]
    c.post(f"{API}/projects/{pid}/tasks", json={"title": "Write API docs", "status": "in_progress", "assignee_id": me}, headers=H)
    time.sleep(1.5)   # the live WebSocket update should deliver it - no reload
    check("task created elsewhere appears live (WebSocket)", "Write API docs" in col_titles(page, "In Progress"))
    badge = page.locator("main .cursor-pointer", has_text="Write API docs").locator("span[title='Priya Nair']")
    check("card shows assignee initials 'PN' (not a raw id)", badge.count() == 1 and badge.first.inner_text().strip() == "PN")

    # 6. Delete from the drawer
    page.locator("main .cursor-pointer", has_text="Write API docs").first.click(); time.sleep(0.6)
    page.on("dialog", lambda d: d.accept())
    page.locator("div.fixed button:has(svg.lucide-trash-2)").first.click(); time.sleep(1.5)
    check("deleted task disappears live", "Write API docs" not in col_titles(page, "In Progress") and len(tasks()) == 1)
    b.close()

print(f"\n{sum(results)}/{len(results)} checks passed")
sys.exit(0 if all(results) else 1)
