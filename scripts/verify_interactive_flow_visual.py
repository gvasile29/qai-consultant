"""
Manual dev script -- screenshots the local dialogue and review screens to
visually verify the Phase 2 interactive-flow redesign
(docs/superpowers/specs/2026-08-06-interactive-flow-power-on-redesign-design.md).
Not part of pytest/CI: run manually.

Usage:
    streamlit run src/app.py                        # in one terminal, leave running
    python scripts/verify_interactive_flow_visual.py  # in another
"""
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

URL = "http://localhost:8501"


def _reveal(page, locator, max_scrolls=40, step=1200, pause=100):
    """Streamlit lazy-mounts elements far below the fold (IntersectionObserver-
    gated rendering -- confirmed by inspecting document.querySelectorAll('button')
    before/after scrolling: the intro screen's "Start" button and the dialogue
    form's submit button are absent from the DOM entirely until scrolled near
    view, not just off-screen). Scroll incrementally until `locator` is
    attached before interacting with it; a no-op if it's already present."""
    for _ in range(max_scrolls):
        if locator.count() > 0:
            return
        page.mouse.wheel(0, step)
        page.wait_for_timeout(pause)


def main() -> int:
    out_dir = Path(tempfile.mkdtemp(prefix="qai_interactive_flow_visual_"))

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 1400})
        page.goto(URL, timeout=30000, wait_until="networkidle")
        page.wait_for_timeout(1500)

        start_btn = page.get_by_role("button", name="Start — Generate a Test Strategy")
        _reveal(page, start_btn)
        start_btn.click(timeout=10000)
        page.wait_for_selector(".dialogue-progress-track", timeout=15000)
        page.wait_for_timeout(500)
        page.screenshot(path=str(out_dir / "dialogue_empty.png"), full_page=True)
        fill_width = page.eval_on_selector(
            ".dialogue-progress-fill", "el => getComputedStyle(el).width"
        )
        print(f"Dialogue progress fill at 0/11 answered (expect ~0px): {fill_width}")

        # Apply a template to answer all questions, then re-check the bar.
        # Label verified against src/templates.py's TEMPLATE_OPTIONS.
        page.locator('[data-testid="stSelectbox"]').first.click()
        page.get_by_text("🌐 Web Application", exact=False).click(timeout=10000)
        page.get_by_role("button", name="Apply template").click(timeout=10000)
        # 800ms wasn't enough here in practice -- the server round-trip for
        # the template rerun plus the 0.4s CSS width transition together can
        # exceed it, leaving the bar screenshotted mid-transition.
        page.wait_for_timeout(1500)
        fill_width_after = page.eval_on_selector(
            ".dialogue-progress-fill", "el => getComputedStyle(el).width"
        )
        print(f"Dialogue progress fill after template applied (expect > 0px, wider): {fill_width_after}")
        page.screenshot(path=str(out_dir / "dialogue_filled.png"), full_page=True)

        submit_btn = page.get_by_role("button", name="✅ Review & Generate Strategy")
        _reveal(page, submit_btn)
        submit_btn.click(timeout=10000)
        page.wait_for_selector(".review-grid", timeout=15000)
        page.wait_for_timeout(600)  # let the one-shot entrance finish (longest delay ~0.5s + 0.4s anim)
        page.screenshot(path=str(out_dir / "review_first_visit.png"), full_page=True)
        first_visit_class = page.eval_on_selector(".review-grid", "el => el.className")
        print(f"Review grid class on first visit (expect contains 'animate'): {first_visit_class}")

        # Edit "Additional context" to trigger a rerun, then confirm the
        # entrance does NOT replay (tiles already at rest, no 'animate' class).
        # st.text_area only sends its value to the server (triggering the
        # rerun) on blur, not on every keystroke -- Tab explicitly blurs it.
        textarea = page.locator("textarea").last
        textarea.click()
        textarea.type(" - extra note", delay=30)
        page.keyboard.press("Tab")
        page.wait_for_timeout(1000)
        second_render_class = page.eval_on_selector(".review-grid", "el => el.className")
        print(f"Review grid class after editing additional context (expect NOT contains 'animate'): {second_render_class}")
        page.screenshot(path=str(out_dir / "review_after_edit.png"), full_page=True)

        browser.close()

        # Reduced-motion pass on the review screen.
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 1400}, reduced_motion="reduce")
        page.goto(URL, timeout=30000, wait_until="networkidle")
        page.wait_for_timeout(1000)
        start_btn = page.get_by_role("button", name="Start — Generate a Test Strategy")
        _reveal(page, start_btn)
        start_btn.click(timeout=10000)
        page.wait_for_selector(".dialogue-progress-track", timeout=15000)
        page.locator('[data-testid="stSelectbox"]').first.click()
        page.get_by_text("🌐 Web Application", exact=False).click(timeout=10000)
        page.get_by_role("button", name="Apply template").click(timeout=10000)
        page.wait_for_timeout(500)
        submit_btn = page.get_by_role("button", name="✅ Review & Generate Strategy")
        _reveal(page, submit_btn)
        submit_btn.click(timeout=10000)
        page.wait_for_selector(".review-grid", timeout=15000)
        page.wait_for_timeout(200)  # reduced motion should already be at rest almost immediately
        page.screenshot(path=str(out_dir / "review_reduced_motion.png"), full_page=True)
        browser.close()

    print(f"Screenshots saved to: {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
