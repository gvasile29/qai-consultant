"""
Manual dev script -- drives one REAL end-to-end strategy generation in a
browser to check the Mission Control generating and results screens
(render_strategy()). Not part of pytest/CI: run manually.

It uses real LLM/Pinecone calls: one of the session's free runs, a few
Mistral requests, and it bumps the daily usage counters. Budget 5-10 min.

Usage:
    streamlit run src/app.py                          # in one terminal, leave running
    python scripts/verify_output_screens_visual.py    # in another

Checks: the mission clock ticks while generating, a stage is active, and the
results screen shows the readout tiles, the risk map and no running clock,
plus the accent active tab and the download-button hover border. It runs
one theme at desktop width; check dark and 390px by hand (or with a
throwaway page rendering the same builders) when the readout CSS changes.
Prints one line per check, screenshots to a temp folder, exits 1 on a failure.
"""
import re
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

from verify_visual_common import URL, full_screenshot

VIEWPORT = {"width": 1280, "height": 1000}
TIMEOUT = 120_000
failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail else ""))
    if not ok:
        failures.append(name)


def _secs(text: str) -> int:
    m, s = re.findall(r"(\d+):(\d+)", text)[0]
    return int(m) * 60 + int(s)


def main() -> int:
    out_dir = Path(tempfile.mkdtemp(prefix="qai_output_screens_visual_"))
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport=VIEWPORT)
        page.set_default_timeout(TIMEOUT)

        page.goto(URL, wait_until="networkidle")
        page.wait_for_selector(".ql-hero h1")  # Playwright pierces the landing's open shadow root
        page.locator('.ql-cta[data-go="strategy"]').click()
        page.wait_for_selector(".dialogue-progress-track")
        page.locator('[data-testid="stSelectbox"]').first.click()
        page.get_by_text("🌐 Web Application", exact=False).click()
        page.get_by_role("button", name="Apply template").click()
        page.wait_for_timeout(500)
        page.get_by_role("button", name="✅ Review & Generate Strategy").click()
        page.wait_for_selector(".review-grid")
        page.get_by_role("button", name="🤖 Generate Test Strategy").click()

        # ── Generating screen ──────────────────────────────────────────────
        page.wait_for_selector(".stage-item.active")
        page.wait_for_selector(".mc-clock")
        first = page.inner_text(".mc-clock")
        page.wait_for_timeout(3200)
        second = page.inner_text(".mc-clock")
        check("mission clock ticks while generating", 2 <= _secs(second) - _secs(first) <= 5, f"{first} -> {second}")
        full_screenshot(page, str(out_dir / "generating.png"), VIEWPORT)

        # ── Results screen ─────────────────────────────────────────────────
        page.wait_for_selector('[data-testid="stTabs"]', timeout=900_000)
        page.wait_for_timeout(800)
        check("all four stages done", page.locator(".stage-item.done").count() == 4,
              str(page.eval_on_selector_all(".stage-item", "els => els.map(e => e.className)")))
        check("no running clock on results", page.locator(".mc-clock").count() == 0)
        check("readout tiles", page.locator(".mr-tile").count() >= 3, str(page.locator(".mr-tile").count()))
        check("address first strip", page.locator(".mr-first li").count() >= 1)
        cells = page.locator(".rm-cell").all_inner_texts()
        plotted = sum(1 for c in cells for _ in re.findall(r"R\d+", c))
        check("risk map plots the parsed risks", len(cells) == 9 and plotted >= 1, f"{plotted} risks plotted")
        check("detailed readout behind expander",
              page.get_by_text("How these numbers are computed").count() == 1)
        full_screenshot(page, str(out_dir / "results_risk_tab.png"), VIEWPORT)

        accent = page.evaluate("() => getComputedStyle(document.querySelector('.mr-rid')).color")
        tab_color = page.eval_on_selector('[data-testid="stTab"][aria-selected="true"] p',
                                          "el => getComputedStyle(el).color")
        check("active tab uses the accent", tab_color == accent, f"{tab_color} vs {accent}")
        # All 4 tabs' download buttons stay mounted; only :visible ones can be hovered.
        dl_button = page.locator('[data-testid="stDownloadButton"] button:visible').first
        dl_button.hover()
        page.wait_for_timeout(250)  # the border-color transition is 0.15s
        border = dl_button.evaluate("el => getComputedStyle(el).borderTopColor")
        check("download button hover border is the accent", border == accent, f"{border} vs {accent}")
        browser.close()

    print(f"Screenshots saved to: {out_dir}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
