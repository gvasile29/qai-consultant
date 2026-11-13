"""
Manual dev script -- drives the local landing page (ui/landing.py's
component) in a real browser, the part AppTest cannot click. Not part of
pytest/CI: run manually.

Usage:
    streamlit run src/app.py                  # in one terminal, leave running
    python scripts/verify_landing_visual.py   # in another

For dark and light, at desktop and phone width, it checks that the hero
renders, the carousel arrows move the counter, "See example output" scrolls
to the native details section, and "Start pre-flight" / a mission row open
the right screen. A reduced-motion pass checks the hero is visible at once.
Prints one line per check, screenshots to a temp folder, exits 1 on a failure.
"""
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import Page, sync_playwright
from playwright.sync_api import TimeoutError as PlaywrightTimeout

from verify_visual_common import URL, full_screenshot

VIEWPORTS = {"desktop": {"width": 1440, "height": 900}, "phone": {"width": 390, "height": 844}}
TIMEOUT = 120_000  # a cold local start loads the embedding model first
failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail else ""))
    if not ok:
        failures.append(name)


def open_landing(page: Page) -> None:
    page.goto(URL, timeout=TIMEOUT, wait_until="networkidle")
    page.wait_for_selector(".ql-hero h1", timeout=TIMEOUT)  # Playwright pierces the open shadow root
    # the carousel script has run once it has painted the counter's state
    page.wait_for_function("() => document.querySelector('[data-testid=stBidiComponentIsolated]')"
                           "?.shadowRoot?.querySelector('.ql-arrow[data-dir=\"-1\"]')?.disabled === true", timeout=TIMEOUT)


def wait_until(page: Page, js: str, arg, timeout: int = 10_000) -> bool:
    try:
        page.wait_for_function(js, arg=arg, timeout=timeout)
        return True
    except PlaywrightTimeout:
        return False


# Entrance animations finished (the infinite ones, stars and caret, never do).
_ANIMATIONS_DONE = ("() => { const r = document.querySelector('[data-testid=stBidiComponentIsolated]')?.shadowRoot;"
                    " return !!r && r.getAnimations().every(a => a.playState !== 'running'"
                    " || a.effect.getTiming().iterations === Infinity); }")
_CTA_CONTRAST = """() => {
  const b = document.querySelector('[data-testid=stBidiComponentIsolated]').shadowRoot.querySelector('.ql-cta');
  const cs = getComputedStyle(b);
  const lum = s => { const [r, g, bl] = s.match(/\\d+/g).slice(0, 3).map(v => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; });
                     return 0.2126 * r + 0.7152 * g + 0.0722 * bl; };
  const [a, c] = [lum(cs.backgroundColor), lum(cs.color)].sort((x, y) => y - x);
  return Math.round(((a + 0.05) / (c + 0.05)) * 100) / 100;
}"""
_IN_VIEWPORT = "sel => { const e = document.querySelector(sel); if (!e) return false; const r = e.getBoundingClientRect(); return r.top >= 0 && r.top < innerHeight; }"
_COUNTER_IS_NOT = ("before => document.querySelector('[data-testid=stBidiComponentIsolated]')"
                   "?.shadowRoot?.querySelector('.ql-counter')?.textContent !== before")


def main() -> int:
    out_dir = Path(tempfile.mkdtemp(prefix="qai_landing_visual_"))
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for scheme in ("dark", "light"):
            for name, viewport in VIEWPORTS.items():
                tag = f"{scheme}/{name}"
                page = browser.new_page(viewport=viewport, color_scheme=scheme)
                page.set_default_timeout(TIMEOUT)
                open_landing(page)
                check(f"{tag}: headline", page.locator(".ql-hero h1").inner_text().strip().lower() == "clear your release for launch.")
                wait_until(page, _ANIMATIONS_DONE, None)
                ratio = page.evaluate(_CTA_CONTRAST)
                check(f"{tag}: CTA label contrast >= 4.5", ratio >= 4.5, f"{ratio}:1")
                full_screenshot(page, str(out_dir / f"{scheme}_{name}_landing.png"), viewport)

                counter = page.locator(".ql-counter")
                before = counter.inner_text()
                page.locator('.ql-arrow[data-dir="1"]').click()
                moved = wait_until(page, _COUNTER_IS_NOT, before)
                check(f"{tag}: carousel next", moved, f"{before} -> {counter.inner_text()}")

                page.locator('.ql-link-cta[data-scroll=".st-key-landing-details"]').click()
                check(f"{tag}: example output scroll", wait_until(page, _IN_VIEWPORT, ".st-key-landing-details"))

                page.locator('.ql-cta[data-go="strategy"]').click()
                page.wait_for_selector(".ledger-card", timeout=TIMEOUT)
                check(f"{tag}: start pre-flight opens discovery", page.locator(".ledger-card").count() == 11)

                open_landing(page)  # a fresh load lands back on the intro screen
                page.locator('.ql-mission[data-go="doc_review"]').click()
                page.wait_for_selector(".st-key-doc-review-input", timeout=TIMEOUT)
                check(f"{tag}: mission row opens document review", True)
                page.close()

        page = browser.new_page(viewport=VIEWPORTS["desktop"], reduced_motion="reduce")
        open_landing(page)
        opacity = page.eval_on_selector(".ql-hero h1", "el => getComputedStyle(el).opacity")
        check("reduced motion: hero visible at once", opacity == "1", f"opacity {opacity}")
        page.close()
        browser.close()

    print(f"Screenshots saved to: {out_dir}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
