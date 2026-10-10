"""Register-page checks in a real browser. Bad input must show a readable message (never a blank page);
valid input must create the account and land on the dashboard."""
import sys, time, uuid
import httpx
from playwright.sync_api import sync_playwright

WEB = "http://localhost:5173"; API = "http://localhost:8000/api/v1"
sfx = uuid.uuid4().hex[:6]
results = []
def check(name, ok): results.append(ok); print(("PASS " if ok else "FAIL ") + name)

def fill(page, full, email, user, pw, pw2=None):
    page.goto(WEB + "/register"); page.wait_for_load_state("networkidle")
    inputs = page.locator("form input")
    for i, v in enumerate([full, email, user, pw, pw2 if pw2 is not None else pw]):
        inputs.nth(i).fill(v)

def visible_text(page):
    return page.locator("body").inner_text().strip()

with sync_playwright() as p:
    b = p.chromium.launch(channel="msedge", headless=True)
    page = b.new_page(viewport={"width": 1200, "height": 900})
    errors = []; page.on("pageerror", lambda e: errors.append(str(e)[:120]))

    # 1. the exact input from the report: username contains '@'
    fill(page, "Aditya Pande", f"aditya{sfx}@123.com", "aditya@", "Secure#2026")
    page.get_by_role("button", name="Create account").click(); time.sleep(1.5)
    t = visible_text(page)
    check("bad username: page is NOT blank", len(t) > 20)
    check("bad username: readable message mentions the username rule", "username" in t.lower() and ("letters" in t.lower()))
    check("bad username: no raw object / JS crash", not errors)

    # 2. other invalid inputs give readable messages too
    fill(page, "A B", "not-an-email", "okname", "Secure#2026"); page.get_by_role("button", name="Create account").click(); time.sleep(1.2)
    check("bad email: readable message, page alive", "email" in visible_text(page).lower() and len(visible_text(page)) > 20)
    fill(page, "A B", f"ok{sfx}@123.com", "okname", "short"); page.get_by_role("button", name="Create account").click(); time.sleep(1.2)
    check("short password: readable message, page alive", ("8" in visible_text(page) or "password" in visible_text(page).lower()) and len(visible_text(page)) > 20)

    # 3. valid registration -> dashboard, and the user really exists in the database
    user = f"aditya_{sfx}"
    fill(page, "Aditya Pande", f"aditya{sfx}@123.com", user, "Secure#2026")
    page.get_by_role("button", name="Create account").click(); page.wait_for_url("**/dashboard", timeout=15000); time.sleep(1)
    check("valid registration lands on the dashboard", "/dashboard" in page.url)
    r = httpx.post(f"{API}/auth/login", json={"email": f"aditya{sfx}@123.com", "password": "Secure#2026"})
    check("the account was stored (login works)", r.status_code == 200)

    # 4. duplicate email -> readable message
    fill(page, "Aditya Pande", f"aditya{sfx}@123.com", f"other_{sfx}", "Secure#2026"); page.get_by_role("button", name="Create account").click(); time.sleep(1.2)
    check("duplicate email: readable message", ("already" in visible_text(page).lower() or "registered" in visible_text(page).lower()) and len(visible_text(page)) > 20)
    b.close()

print(f"\n{sum(results)}/{len(results)} checks passed")
sys.exit(0 if all(results) else 1)
