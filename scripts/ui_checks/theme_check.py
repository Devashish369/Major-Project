"""Browser check for the Light / Dark / Auto theme switch.

  - Auto follows the device setting, also when it changes while the page is open
  - Light and Dark override it, survive a reload, and are applied BEFORE the page first paints
  - another tab follows the change; the switch is an accessible radio group
  - text contrast scan of the main screens in both themes (WCAG AA: 4.5:1, large text 3:1)
Run with the backend on :8000 and the frontend on :5173 (demo data seeded).
"""
import sys, time
from playwright.sync_api import sync_playwright

WEB = "http://localhost:5173"
results = []
def check(name, ok, extra=""): results.append(bool(ok)); print(("PASS " if ok else "FAIL ") + name + (f"  ({extra})" if extra else ""))

# records the theme at the moment <body> first exists, i.e. before anything can be painted
FIRST_PAINT = """
new MutationObserver((_, obs) => {
  if (document.body) { window.__themeAtFirstPaint = document.documentElement.getAttribute('data-theme'); obs.disconnect(); }
}).observe(document, { childList: true, subtree: true });   // <html> doesn't exist yet here
"""

CONTRAST = r"""
() => {
  // any CSS colour (rgb, oklch, color-mix …) -> sRGB, by painting it on a 1x1 canvas
  const cv = document.createElement('canvas'); cv.width = cv.height = 1;
  const cx = cv.getContext('2d', { willReadFrequently: true });
  const parse = (c) => { if (!c || c === 'transparent') return { r: 0, g: 0, b: 0, a: 0 };
    cx.clearRect(0, 0, 1, 1); cx.fillStyle = '#000'; cx.fillStyle = c; cx.fillRect(0, 0, 1, 1);
    const [r, g, b, a] = cx.getImageData(0, 0, 1, 1).data; return { r, g, b, a: a / 255 }; };
  const lum = ({ r, g, b }) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; };
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
  const blend = (top, under) => ({ r: top.r * top.a + under.r * (1 - top.a), g: top.g * top.a + under.g * (1 - top.a),
    b: top.b * top.a + under.b * (1 - top.a), a: 1 });
  const bgOf = (el) => { const layers = []; for (let n = el; n; n = n.parentElement) {
      const c = parse(getComputedStyle(n).backgroundColor); if (c && c.a > 0) { layers.push(c); if (c.a >= 1) break; } }
    let out = parse(getComputedStyle(document.body).backgroundColor);
    if (out.a < 1) out = blend(out, { r: 255, g: 255, b: 255, a: 1 });
    for (const l of layers.reverse()) out = blend(l, out); return out; };
  const bad = [];
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  const seen = new Set();
  while (walker.nextNode()) {
    const el = walker.currentNode.parentElement; const text = walker.currentNode.textContent.trim();
    if (!el || !text || seen.has(el)) continue; seen.add(el);
    if (!/[\p{L}\p{N}]/u.test(text)) continue;   // decorative symbols only (● / ↳): not text for WCAG
    const cs = getComputedStyle(el); const rect = el.getBoundingClientRect();
    if (rect.width === 0 || cs.visibility === 'hidden' || +cs.opacity === 0 || el.closest('[disabled], .print-doc, .react-flow')) continue;
    if (el.closest('select, option, input, textarea')) continue;
    let fg = parse(cs.color); if (!fg) continue; const bg = bgOf(el); fg = blend(fg, bg);
    const [L1, L2] = [lum(fg), lum(bg)].sort((a, b) => b - a); const ratio = (L1 + 0.05) / (L2 + 0.05);
    const size = parseFloat(cs.fontSize); const bold = +cs.fontWeight >= 700;
    const need = size >= 24 || (size >= 18.66 && bold) ? 3 : 4.5;
    if (ratio < need) bad.push(`${ratio.toFixed(2)} "${text.slice(0, 40)}"`);
  }
  return bad;
}
"""

with sync_playwright() as p:
    b = p.chromium.launch(channel="msedge", headless=True)

    # 1. Auto follows the device, live
    ctx = b.new_context(viewport={"width": 1400, "height": 900}, color_scheme="dark")
    ctx.add_init_script(FIRST_PAINT)
    page = ctx.new_page()
    page.goto(WEB + "/login"); page.wait_for_load_state("networkidle")
    theme = lambda pg=page: pg.evaluate("document.documentElement.getAttribute('data-theme')")
    bg = lambda pg=page: pg.evaluate("getComputedStyle(document.body).backgroundColor")
    check("Auto + device dark -> dark", theme() == "dark" and page.get_attribute('[data-theme-option="system"]', "aria-checked") == "true")
    dark_bg = bg()
    page.emulate_media(color_scheme="light"); time.sleep(0.4)
    check("Auto follows a live device switch to light", theme() == "light" and bg() != dark_bg, bg())
    page.emulate_media(color_scheme="dark"); time.sleep(0.3)

    # 2. explicit Light overrides a dark device, persists, applied before first paint
    page.click('[data-theme-option="light"]'); time.sleep(0.4)
    check("Light chosen on a dark device -> light", theme() == "light" and page.evaluate("localStorage.getItem('intellipm_theme')") == "light")
    page.reload(); page.wait_for_load_state("networkidle")
    check("Light survives a reload, set before first paint (no flash)", theme() == "light" and page.evaluate("window.__themeAtFirstPaint") == "light")
    other = ctx.new_page(); other.goto(WEB + "/login"); other.wait_for_load_state("networkidle")
    page.click('[data-theme-option="dark"]'); time.sleep(0.6)
    check("Dark chosen -> dark, and the other open tab follows", theme() == "dark" and theme(other) == "dark")
    page.emulate_media(color_scheme="light"); time.sleep(0.3)
    check("explicit Dark ignores the device setting", theme() == "dark")
    page.click('[data-theme-option="system"]'); time.sleep(0.4)
    check("back to Auto: follows the device again, saved choice removed",
          theme() == "light" and page.evaluate("localStorage.getItem('intellipm_theme')") is None)
    radios = page.locator('#theme-toggle [role="radio"]')
    check("switch is a radio group with exactly one option checked",
          radios.count() == 3 and [radios.nth(i).get_attribute("aria-checked") for i in range(3)].count("true") == 1)
    ctx.close()

    # 3. contrast in both themes on the main screens
    for mode in ("light", "dark"):
        ctx = b.new_context(viewport={"width": 1400, "height": 900})
        ctx.add_init_script(f"localStorage.setItem('intellipm_theme', '{mode}')")
        pg = ctx.new_page()
        pg.goto(WEB + "/login"); pg.wait_for_load_state("networkidle")
        problems = [f"login: {x}" for x in pg.evaluate(CONTRAST)]
        pg.fill('input[type="email"]', "demo@intellipm.demo"); pg.fill('input[type="password"]', "Demo@1234")
        pg.get_by_role("button", name="Sign in").click(); pg.wait_for_url("**/dashboard"); pg.wait_for_load_state("networkidle"); time.sleep(0.6)
        problems += [f"dashboard: {x}" for x in pg.evaluate(CONTRAST)]
        pg.locator("main .cursor-pointer").filter(has_text="E-commerce").first.click(); pg.wait_for_load_state("networkidle"); time.sleep(1)
        for tab in ["Board", "Team", "Analytics", "Decisions", "Overview"]:
            pg.get_by_role("button", name=tab, exact=True).first.click(); pg.wait_for_load_state("networkidle"); time.sleep(1.2)
            problems += [f"{tab}: {x}" for x in pg.evaluate(CONTRAST)]
        pg.goto(WEB + "/security"); pg.wait_for_load_state("networkidle"); time.sleep(0.6)
        problems += [f"security: {x}" for x in pg.evaluate(CONTRAST)]
        for x in sorted(set(problems))[:25]:
            print("   low contrast", mode, x)
        check(f"{mode}: all text meets WCAG AA contrast", not problems, f"{len(set(problems))} element(s) below")
        ctx.close()
    b.close()

print(f"\n{sum(results)}/{len(results)} checks passed")
sys.exit(0 if all(results) else 1)
