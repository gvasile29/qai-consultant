"""
Manual dev script -- screenshots the local landing page to visually verify
the Power-On Sequence redesign (docs/superpowers/specs/2026-08-06-landing-
power-on-redesign-design.md, Task 3). Not part of pytest/CI: run manually.

Usage:
    streamlit run src/app.py          # in one terminal, leave running
    python scripts/verify_landing_visual.py   # in another
"""
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

URL = "http://localhost:8501"


def main() -> int:
    out_dir = Path(tempfile.mkdtemp(prefix="qai_landing_visual_"))

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(URL, timeout=30000, wait_until="networkidle")
        # "networkidle" only tracks HTTP -- Streamlit renders the actual DOM
        # over a websocket after that, so wait for the hero itself before
        # timing the entrance animations against it.
        page.wait_for_selector(".pom-hero", timeout=30000)
        page.wait_for_timeout(2500)  # let the one-shot entrance animations finish
        page.screenshot(path=str(out_dir / "landing_normal_motion.png"), full_page=True)
        fill_width = page.eval_on_selector(
            ".pom-gauge.strategy .pom-gfill", "el => getComputedStyle(el).width"
        )
        print(f"Strategy gauge fill width after animation (expect > 0px): {fill_width}")
        browser.close()

        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 900}, reduced_motion="reduce")
        page.goto(URL, timeout=30000, wait_until="networkidle")
        page.wait_for_selector(".pom-hero", timeout=30000)
        page.wait_for_timeout(300)  # should already be at resting state almost immediately
        page.screenshot(path=str(out_dir / "landing_reduced_motion.png"), full_page=True)
        fill_width_reduced = page.eval_on_selector(
            ".pom-gauge.strategy .pom-gfill", "el => getComputedStyle(el).width"
        )
        print(f"Strategy gauge fill width with reduced motion (expect same, near-instant): {fill_width_reduced}")
        browser.close()

    print(f"Screenshots saved to: {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
