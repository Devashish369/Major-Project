"""Reproduce / verify the Kanban behaviour with REAL pointer drags (Playwright driving Edge).
Usage: python board_test.py        -> prints PASS/FAIL per check"""
import sys, time, uuid
import httpx
from playwright.sync_api import sync_playwright

API = "http://localhost:8000/api/v1"; WEB = "http://localhost:5173"
sfx = uuid.uuid4().hex[:6]
c = httpx.Client(timeout=30)
r = c.post(f"{API}/auth/register", json={"email": f"board{sfx}@boardtest.org", "username": f"board{sfx}",
                                          "full_name": "Board Tester", "password": "Secure#2026"})
tok = r.json()["data"]["access_token"]; H = {"Authorization": "Bearer " + tok}
pid = c.post(f"{API}/projects", json={"title": f"Board test {sfx}"}, headers=H).json()["data"]["id"]
t1 = c.post(f"{API}/projects/{pid}/tasks", json={"title": "Alpha task", "status": "todo"}, headers=H).json()["data"]["id"]
t2 = c.post(f"{API}/projects/{pid}/tasks", json={"title": "Beta task", "status": "todo"}, headers=H).json()["data"]["id"]

def status_of(tid):
    return c.get(f"{API}/tasks/{tid}", headers=H).json()["data"]["status"]

results = []
def check(name, ok): results.append(ok); print(("PASS " if ok else "FAIL ") + name)

def drag(page, title, col_label, dx=0, dy=60):
    """Real pointer drag of the card with `title` to the middle of the column headed `col_label`."""
    card = page.locator("main .cursor-pointer", has_text=title).first
    cb = card.bounding_box()
    col = page.locator("main h3, main span", has_text=col_label).first
    # the column container = nearest ancestor that has the border-t-4 class
    colbox = page.locator(f"xpath=//span[normalize-space()='{col_label}']/ancestor::div[contains(@class,'border-t-4')][1]").bounding_box()
    sx, sy = cb["x"] + cb["width"] / 2, cb["y"] + cb["height"] / 2
    tx, ty = colbox["x"] + colbox["width"] / 2, colbox["y"] + colbox["height"] / 2 + dy
    page.mouse.move(sx, sy); page.mouse.down()
    steps = 12
    for i in range(1, steps + 1):
        page.mouse.move(sx + (tx - sx) * i / steps, sy + (ty - sy) * i / steps); time.sleep(0.03)
    page.mouse.up(); time.sleep(1.2)

with sync_playwright() as p:
    b = p.chromium.launch(channel="msedge", headless=True)
    page = b.new_page(viewport={"width": 1600, "height": 900})
    page.goto(WEB + "/login"); page.evaluate(f"sessionStorage.setItem('intellipm_token', '{tok}')")
    page.goto(f"{WEB}/projects/{pid}"); page.wait_for_load_state("networkidle"); time.sleep(1.5)

    # 1. EMPTY column targets (the reported bug)
    drag(page, "Alpha task", "In Progress"); check("drag To Do -> EMPTY In Progress column", status_of(t1) == "in_progress")
    drag(page, "Alpha task", "Done");         check("drag In Progress -> EMPTY Done column", status_of(t1) == "done")
    # 2. back, and onto a column that already has a card
    drag(page, "Alpha task", "To Do");        check("drag Done -> To Do (has a card)", status_of(t1) == "todo")
    # 3. drop on empty space inside a column below the cards
    drag(page, "Beta task", "Done", dy=150);  check("drop low in the column (below any card)", status_of(t2) == "done")
    # 4. persists after reload + no duplicates created
    page.reload(); page.wait_for_load_state("networkidle"); time.sleep(1.5)
    n = len(c.get(f"{API}/projects/{pid}/tasks", headers=H).json()["data"])
    check("still exactly 2 tasks (no duplicates)", n == 2)
    b.close()

print(f"\n{sum(results)}/{len(results)} checks passed")
sys.exit(0 if all(results) else 1)
