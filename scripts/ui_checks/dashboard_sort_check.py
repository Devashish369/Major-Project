"""Browser check: dashboard sort = one field menu + a direction button; both remembered after a reload."""
import re, sys, time
from playwright.sync_api import sync_playwright

WEB = "http://localhost:5173"
results = []
def check(name, ok): results.append(bool(ok)); print(("PASS " if ok else "FAIL ") + name)

RANK = {"Pending": 0, "In Progress": 1, "Completed": 2}
def cards(page):
    out = []
    for c in page.locator("main .cursor-pointer").all():
        t = c.inner_text()
        m = re.search(r"Progress\s+(\d+)%", t); h = re.search(r"Health (\d+)", t)
        out.append({"progress": int(m.group(1)) if m else 0, "health": int(h.group(1)) if h else None,
                    "status": RANK["Pending" if "Pending" in t else "Completed" if "Completed" in t else "In Progress"]})
    return out

with sync_playwright() as p:
    b = p.chromium.launch(channel="msedge", headless=True)
    page = b.new_context(viewport={"width": 1500, "height": 900}).new_page()
    page.goto(WEB + "/login"); page.wait_for_load_state("networkidle")
    page.fill('input[type="email"]', "demo@intellipm.demo"); page.fill('input[type="password"]', "Demo@1234")
    page.get_by_role("button", name="Sign in").click(); page.wait_for_url("**/dashboard"); page.wait_for_load_state("networkidle")
    page.wait_for_selector("#project-sort")
    sel, flip = page.locator("#project-sort"), page.locator("#project-sort-direction")
    check("five short field names, no duplicates",
          sel.locator("option").all_inner_texts() == ["Date", "Risk", "Priority", "Status", "Progress"])

    def run(field, reverse):
        sel.select_option(field); time.sleep(0.3)
        if reverse:
            flip.click(); time.sleep(0.3)
        return cards(page)

    for field, attr in [("risk", "health"), ("status", "status"), ("progress", "progress")]:
        natural = [c[attr] for c in run(field, False) if c[attr] is not None]
        rev = [c[attr] for c in run(field, True) if c[attr] is not None]
        if field == "progress":
            check(f"{field}: Highest then reversed Lowest", natural == sorted(natural, reverse=True) and rev == sorted(rev))
        else:
            check(f"{field}: natural then reversed", natural == sorted(natural) and rev == sorted(rev, reverse=True))
    check("direction label follows the field (Progress reversed shows 'Lowest')", "Lowest" in flip.inner_text())
    run("priority", True)
    check("choosing a field resets to its natural direction, button flips it", "Low" in flip.inner_text())
    page.reload(); page.wait_for_load_state("networkidle"); page.wait_for_selector("#project-sort"); time.sleep(0.4)
    check("field and direction remembered after reload",
          page.locator("#project-sort").input_value() == "priority" and "Low" in page.locator("#project-sort-direction").inner_text())
    page.locator("#project-sort").select_option("date")
    b.close()

print(f"\n{sum(results)}/{len(results)} checks passed")
sys.exit(0 if all(results) else 1)
