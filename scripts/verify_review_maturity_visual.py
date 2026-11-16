"""
Manual dev script -- drives the Document Review and QA Maturity result screens
in a real browser. Not part of pytest/CI: run manually.

Usage:
    streamlit run src/app.py                            # in one terminal, leave running
    python scripts/verify_review_maturity_visual.py     # in another

For dark and light, at desktop and phone width: the score cards sit in one CSS
grid with the right column count (5 TMMi / 3 review on desktop, always 2 on a
phone, not one card per row), the maturity level tile reads as the top level
(pass tone, 3 of 3 segments lit, not a failing 3/100), the phone header logo
is smaller than on desktop, the in-page mode switcher fits the screen, lights the
active mode and switches screens on a click, and nothing overflows sideways. Prints one line per
check, screenshots to a temp folder, exits 1 on a failure. No LLM call.
"""
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import Page, expect, sync_playwright

from verify_visual_common import URL

REPO = Path(__file__).resolve().parent.parent
VIEWPORTS = {"desktop": {"width": 1440, "height": 900}, "phone": {"width": 390, "height": 844}}
TIMEOUT = 120_000
failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail else ""))
    if not ok:
        failures.append(name)


def columns(page: Page) -> int:
    return page.evaluate(
        "() => getComputedStyle(document.querySelector('.score-grid')).gridTemplateColumns.split(' ').length"
    )


def overflow(page: Page) -> int:
    return page.evaluate(
        "() => { const m = document.querySelector('[data-testid=stMain]'); return m.scrollWidth - m.clientWidth; }"
    )


def run_mode(page: Page, mode: str, text: str, button: str) -> None:
    page.goto(URL, wait_until="networkidle")
    page.locator(f'.ql-mission[data-go="{mode}"]').click()  # pierces the landing's shadow root
    page.wait_for_selector('[data-testid="stTextArea"]')
    area = page.locator("textarea").last
    area.fill(text)
    area.press("Tab")  # blur: the gated button only enables once Streamlit has the value
    page.get_by_role("button", name=button).click()
    page.wait_for_selector(".score-grid")


def check_page_nav(page: Page, tag: str, vw: int) -> None:
    page.goto(URL, wait_until="networkidle")
    page.locator('.ql-mission[data-go="maturity"]').click()
    page.wait_for_selector('[data-testid="stTextArea"]')
    chips = page.locator(".st-key-page-nav button")
    check(f"{tag}: page nav shows three modes", chips.count() == 3, str(chips.count()))
    boxes = [chips.nth(i).bounding_box() for i in range(chips.count())]
    check(f"{tag}: page nav chips stay inside the screen",
          all(b and b["x"] >= 0 and b["x"] + b["width"] <= vw for b in boxes), str([b and round(b["x"] + b["width"]) for b in boxes]))
    check(f"{tag}: active mode is disabled, the others are not",
          [chips.nth(i).is_disabled() for i in range(3)] == [False, False, True])
    page.locator(".st-key-pagenav-doc_review button").click()
    expect(page.get_by_role("heading", name="Review an Existing QA Document")).to_be_visible()
    check(f"{tag}: page nav click opens document review",
          page.locator(".st-key-pagenav-doc_review button").is_disabled())


def check_dialogue_text_kept(page: Page, tag: str) -> None:
    """A value typed with no blur, then a mode chip clicked, then back: kept."""
    page.goto(URL, wait_until="networkidle")
    page.locator('.ql-cta[data-go="strategy"]').click()
    name_input = page.locator("input[aria-label^='What is the name']")
    typed = f"Orbit-{tag.replace('/', '-')}"
    name_input.fill(typed)  # no Enter, no blur: the chip click must still carry it
    page.locator(".st-key-pagenav-maturity button").click()
    page.wait_for_selector('[data-testid="stTextArea"]')
    page.locator(".st-key-pagenav-strategy button").click()
    kept = settled_value(page, "input[aria-label^='What is the name']", typed)
    check(f"{tag}: typed project name survives a page nav round trip", kept == typed, kept)


def settled_value(page: Page, selector: str, expected: str, timeout_ms: int = 5000) -> str:
    """A freshly mounted widget can read empty for a moment before it hydrates:
    wait for the expected value and return whatever it holds when time is up."""
    loc = page.locator(selector)
    try:
        expect(loc).to_have_value(expected, timeout=timeout_ms)
    except AssertionError:
        pass
    return loc.input_value()


def main() -> int:
    out_dir = Path(tempfile.mkdtemp(prefix="qai_review_maturity_visual_"))
    maturity_text = (REPO / "evals/fixtures/maturity/level3_strong.txt").read_text(encoding="utf-8")
    review_text = (REPO / "evals/fixtures/review/strong_test_plan.md").read_text(encoding="utf-8")
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for scheme in ("dark", "light"):
            for name, viewport in VIEWPORTS.items():
                tag = f"{scheme}/{name}"
                page = browser.new_page(viewport=viewport, color_scheme=scheme)
                page.set_default_timeout(TIMEOUT)

                check_page_nav(page, tag, viewport["width"])
                check_dialogue_text_kept(page, tag)
                run_mode(page, "maturity", maturity_text, "Assess Maturity")
                want = 5 if name == "desktop" else 2
                check(f"{tag}: maturity grid has {want} columns", columns(page) == want, str(columns(page)))
                check(f"{tag}: maturity shows ten area cards", page.locator(".score-grid .signal-ledger").count() == 10)
                level = page.locator(".output-tiles .signal-ledger").first
                check(f"{tag}: level 3 reads as pass", "pass" in (level.locator(".sl-score").get_attribute("class") or ""))
                check(f"{tag}: level meter has 3 segments, all lit",
                      level.locator(".sl-meter i").count() == 3 and level.locator(".sl-meter i.on").count() == 3)
                logo = page.evaluate("() => document.querySelector('.header-logo').getBoundingClientRect().width")
                check(f"{tag}: header logo size", (logo <= 150) if name == "phone" else (logo > 200), str(round(logo)))
                check(f"{tag}: maturity no sideways overflow", overflow(page) <= 1, str(overflow(page)))
                page.evaluate("() => document.querySelector('[data-testid=stMain]').scrollTo(0, 0)")
                page.screenshot(path=str(out_dir / f"{scheme}_{name}_maturity.png"))

                run_mode(page, "doc_review", review_text, "Review Document")
                want = 3 if name == "desktop" else 2
                check(f"{tag}: review grid has {want} columns", columns(page) == want, str(columns(page)))
                check(f"{tag}: review shows six dimension cards", page.locator(".score-grid .signal-ledger").count() == 6)
                check(f"{tag}: review no sideways overflow", overflow(page) <= 1, str(overflow(page)))
                expect(page.locator(".score-grid").first).to_be_visible()
                page.screenshot(path=str(out_dir / f"{scheme}_{name}_review.png"))
                page.close()
    print(f"Screenshots saved to: {out_dir}")
    if failures:
        print(f"{len(failures)} FAILED: {failures}")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
