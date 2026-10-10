"""Browser check: the dashboard "Sort by" menu reorders the cards and is remembered after a reload."""
import re, sys, time
from playwright.sync_api import sync_playwright

WEB = "http://localhost:5173"
results = []
def check(name, ok): results.append(bool(ok)); print(("PASS " if ok else "FAIL ") + name)

def cards(page):
    out = []
    for c in page.locator("main .cursor-pointer").all():
        t = c.inner_text()
        m = re.search(r"Progress\s+(\d+)%", t); h = re.search(r"Health (\d+)", t)
        out.append({"progress": int(m.group(1)) if m else 0, "health": int(h.group(1)) if h else 999,
                    "status": "Pending" if "Pending" in t else "Completed" if "Completed" in t else "In Progress"})
    return out

with sync_playwright() as p:
    b = p.chromium.launch(channel="msedge", headless=True)
    page = b.new_context(viewport={"width": 1500, "height": 900}).new_page()
    page.goto(WEB + "/login"); page.wait_for_load_state("networkidle")
    page.fill('input[type="email"]', "demo@intellipm.demo"); page.fill('input[type="password"]', "Demo@1234")
    page.get_by_role("button", name="Sign in").click(); page.wait_for_url("**/dashboard"); page.wait_for_load_state("networkidle")
    page.wait_for_selector("#project-sort"); sel = page.locator("#project-sort")
    check("sort menu has 6 choices", sel.locator("option").count() == 6)

    def run(value):
        sel.select_option(value); time.sleep(0.4); return cards(page)

    r = run("risk"); hs = [c["health"] for c in r]
    check("risk: lowest health first", hs == sorted(hs) and len(r) >= 16)
    r = run("progress_desc"); ps = [c["progress"] for c in r]
    check("progress (highest): descending", ps == sorted(ps, reverse=True))
    r = run("progress_asc"); ps = [c["progress"] for c in r]
    check("progress (lowest): ascending", ps == sorted(ps))
    r = run("pending"); rank = {"Pending": 0, "In Progress": 1, "Completed": 2}
    st = [rank[c["status"]] for c in r]
    check("pending first, completed last", st == sorted(st))
    run("priority")
    borders = page.locator("main .cursor-pointer").evaluate_all(
        "els => els.map(e => e.className.match(/border-l-(red|amber|slate)-500/)?.[1] || 'none')")
    order = {"red": 0, "amber": 1, "slate": 2, "none": 3}
    check("priority: high, medium, low", [order[x] for x in borders] == sorted(order[x] for x in borders))
    page.reload(); page.wait_for_load_state("networkidle"); time.sleep(0.5)
    check("choice remembered after reload", page.locator("#project-sort").input_value() == "priority")
    page.locator("#project-sort").select_option("default")
    b.close()

print(f"\n{sum(results)}/{len(results)} checks passed")
sys.exit(0 if all(results) else 1)
