"""The reported scenario, entirely through the screens (two separate browsers = two different people):
owner creates a project, adds Aditya by email on the Team tab, assigns him a task; Aditya sees ONLY that project."""
import sys, time, uuid
from playwright.sync_api import sync_playwright

WEB = "http://localhost:5173"
sfx = uuid.uuid4().hex[:6]
results = []
def check(name, ok): results.append(ok); print(("PASS " if ok else "FAIL ") + name)

def register(page, full, email, user):
    page.goto(WEB + "/register"); page.wait_for_load_state("networkidle")
    for i, v in enumerate([full, email, user, "Secure#2026", "Secure#2026"]): page.locator("form input").nth(i).fill(v)
    page.get_by_role("button", name="Create account").click(); page.wait_for_url("**/dashboard"); page.wait_for_load_state("networkidle"); time.sleep(1)

def titles(page):
    return [t.strip() for t in page.locator("main h3").all_inner_texts() if t.strip() != "No projects yet"]

with sync_playwright() as p:
    b = p.chromium.launch(channel="msedge", headless=True)
    owner = b.new_context(viewport={"width": 1500, "height": 900}).new_page()      # separate context = separate browser profile
    aditya = b.new_context(viewport={"width": 1500, "height": 900}).new_page()
    a_email = f"aditya{sfx}@journey.org"
    register(owner, "Project Owner", f"owner{sfx}@journey.org", f"owner_{sfx}")
    register(aditya, "Aditya Pande", a_email, f"aditya_{sfx}")

    # owner has two projects; Aditya has none
    for name in (f"Other Project {sfx}", f"Something Management {sfx}"):
        owner.locator("#new-project-btn").click(); owner.fill('input[placeholder="e.g. Hospital Management System"]', name)
        owner.get_by_role("button", name="Create project").click(); time.sleep(1.5)
    check("owner sees both of his projects", len(titles(owner)) == 2)
    check("Aditya sees none yet", len(titles(aditya)) == 0)

    # owner opens Something Management -> Team -> Add member by Aditya's email
    owner.get_by_text(f"Something Management {sfx}", exact=True).first.click(); owner.wait_for_load_state("networkidle")
    owner.locator("nav button", has_text="Team").click(); time.sleep(0.8)
    owner.locator("#add-member-btn").click(); owner.fill("#member-email", a_email)
    owner.get_by_role("button", name="Add member").last.click(); time.sleep(1.5)
    check("Aditya appears in the Team tab", "Aditya Pande" in owner.locator("main").inner_text())

    # owner creates a task assigned to Aditya (the assignee list only offers project members)
    owner.locator("nav button", has_text="Board").click(); time.sleep(0.8)
    owner.locator("#add-task-todo").click(); owner.fill("#task-title", "Write the requirements")
    owner.locator("select").filter(has_text="Unassigned").select_option(label="Aditya Pande");
    owner.get_by_role("button", name="Create task").click(); time.sleep(1.5)
    card = owner.locator("main .cursor-pointer", has_text="Write the requirements").first
    check("task shows Aditya's initials 'AP'", card.locator("span[title='Aditya Pande']").count() == 1)

    # Aditya: within 30 s (or on return to the page) sees exactly that one project, not the owner's other one
    aditya.reload(); aditya.wait_for_load_state("networkidle"); time.sleep(1.2)
    t = titles(aditya)
    check("Aditya sees exactly one project: Something Management", t == [f"Something Management {sfx}"])
    aditya.get_by_text(f"Something Management {sfx}", exact=True).first.click(); aditya.wait_for_load_state("networkidle"); time.sleep(1)
    check("Aditya sees the task assigned to him", "Write the requirements" in aditya.locator("main").inner_text())
    b.close()

print(f"\n{sum(results)}/{len(results)} checks passed")
sys.exit(0 if all(results) else 1)
