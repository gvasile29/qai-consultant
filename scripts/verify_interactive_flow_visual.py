"""
Manual dev script -- drives the discovery wizard and the review screen in a
real browser. Not part of pytest/CI: run manually.

Usage:
    streamlit run src/app.py                          # in one terminal, leave running
    python scripts/verify_interactive_flow_visual.py  # in another

For dark and light, at desktop and phone width: one phase of questions at a
time, Next with empty answers stays and warns, the template lights all 11
progress segments, a value typed with no blur survives Next (the 2026-10
"typed input lost" report) and Back, the optional context survives leaving
the last phase, the card hover uses the accent, nothing overflows sideways,
and the last phase submits to the review screen. Prints one line per check,
screenshots to a temp folder, exits 1 on a failure. No LLM call.
"""
import re
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import Page, expect, sync_playwright

from verify_visual_common import URL, full_screenshot

VIEWPORTS = {"desktop": {"width": 1440, "height": 900}, "phone": {"width": 390, "height": 844}}
TIMEOUT = 120_000
failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail else ""))
    if not ok:
        failures.append(name)


def pick_template(page: Page, label: str) -> None:
    # Scroll first: when the main column is scrolled down (e.g. to a warning),
    # scrolling back during the click closes the select's popover.
    page.evaluate("() => document.querySelector('[data-testid=stMain]').scrollTo(0, 0)")
    page.locator('[data-testid="stSelectbox"]').first.click()
    page.get_by_role("option", name=re.compile(label)).first.click()


def settled_value(page: Page, selector: str, expected: str, timeout_ms: int = 5000) -> str:
    """A freshly mounted widget can read empty for a moment before it hydrates
    (seen 2 in 25 runs at phone width: '' at once, the typed value 2.5 s later).
    Wait for the expected value, and return whatever it holds when time is up."""
    loc = page.locator(selector)
    try:
        expect(loc).to_have_value(expected, timeout=timeout_ms)
    except AssertionError:
        pass
    return loc.input_value()


def cards(page: Page) -> int:
    return page.locator(".ledger-card").count()


def wait_cards(page: Page, n: int) -> None:
    page.wait_for_function("n => document.querySelectorAll('.ledger-card').length === n", arg=n, timeout=TIMEOUT)


def main() -> int:
    out_dir = Path(tempfile.mkdtemp(prefix="qai_discovery_visual_"))
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for scheme in ("dark", "light"):
            for name, viewport in VIEWPORTS.items():
                tag = f"{scheme}/{name}"
                page = browser.new_page(viewport=viewport, color_scheme=scheme)
                page.set_default_timeout(TIMEOUT)
                page.goto(URL, wait_until="networkidle")
                page.locator('.ql-cta[data-go="strategy"]').click()  # pierces the landing's shadow root
                wait_cards(page, 4)
                check(f"{tag}: phase 1 shows 4 questions", cards(page) == 4)
                check(f"{tag}: header says phase 1 of 3", "phase 1 of 3" in page.inner_text(".dialogue-eyebrow").lower())

                page.get_by_role("button", name="Next: Crew & schedule →").click()
                # Not just stAlert: the sidebar's AI notice is one too, already on screen.
                page.get_by_text("Please fix the following before moving on").wait_for()
                check(f"{tag}: empty Next stays and warns", cards(page) == 4)

                pick_template(page, "Web Application")
                page.get_by_role("button", name="Apply template").click()
                page.wait_for_function("() => document.querySelectorAll('.dq-group i.on').length === 11")
                check(f"{tag}: template lights all 11 segments", page.locator(".dq-group i.on").count() == 11)
                full_screenshot(page, str(out_dir / f"{scheme}_{name}_phase1.png"), viewport)

                card = page.locator(".ledger-card").first
                card.hover()
                page.wait_for_timeout(300)
                accent = page.evaluate("() => getComputedStyle(document.querySelector('.dq-step.active .dq-num')).borderTopColor")
                check(f"{tag}: card hover border is the accent",
                      card.evaluate("el => getComputedStyle(el).borderTopColor") == accent)

                typed = f"Orbit-{scheme}-{name}"
                name_input = page.locator("input[aria-label^='What is the name']")
                name_input.fill(typed)  # no Enter, no blur: the Next click must still carry it
                page.get_by_role("button", name="Next: Crew & schedule →").click()
                page.wait_for_selector("input[aria-label^='How many people are on the QA team']")
                check(f"{tag}: Next opens phase 2", "phase 2 of 3" in page.inner_text(".dialogue-eyebrow").lower())
                page.get_by_role("button", name="← Back").click()
                page.wait_for_selector("input[aria-label^='What is the name']")
                kept = settled_value(page, "input[aria-label^='What is the name']", typed)
                check(f"{tag}: typed name survives Next and Back", kept == typed, kept)

                page.get_by_role("button", name="Next: Crew & schedule →").click()
                page.get_by_role("button", name="Next: Risk & compliance →").click()
                wait_cards(page, 3)
                area = page.locator("textarea[aria-label^='Anything else']")
                area.fill("Legacy SOAP backend")
                page.get_by_role("button", name="← Back").click()
                wait_cards(page, 4)
                page.get_by_role("button", name="Next: Risk & compliance →").click()
                wait_cards(page, 3)
                kept_ctx = settled_value(page, "textarea[aria-label^='Anything else']", "Legacy SOAP backend")
                check(f"{tag}: optional context survives leaving phase 3",
                      kept_ctx == "Legacy SOAP backend", kept_ctx)
                overflow = page.evaluate("() => { const m = document.querySelector('[data-testid=stMain]'); return m.scrollWidth - m.clientWidth; }")
                check(f"{tag}: no sideways overflow", overflow <= 1, str(overflow))
                full_screenshot(page, str(out_dir / f"{scheme}_{name}_phase3.png"), viewport)

                page.get_by_role("button", name="✅ Review & Generate Strategy").click()
                page.wait_for_selector(".review-grid")
                body = page.inner_text("body")
                check(f"{tag}: submit opens review with the typed name", typed in body)
                page.close()
        browser.close()

    print(f"Screenshots saved to: {out_dir}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
