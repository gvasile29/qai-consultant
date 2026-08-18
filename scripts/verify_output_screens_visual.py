"""
Manual dev script -- screenshots the local output screens (render_strategy(),
render_doc_review()) and the landing addendum to visually verify the Phase 3
redesign (docs/superpowers/specs/2026-08-17-output-screens-power-on-redesign-
design.md). Not part of pytest/CI: run manually.

Runs one REAL end-to-end strategy generation (real Mistral/Pinecone calls,
consuming one of the session's 3 free runs) to reach render_strategy()'s
tabs -- unlike Phases 1-2's verification scripts, which needed no live API
calls. Budget a few minutes for this step.

Usage:
    streamlit run src/app.py                          # in one terminal, leave running
    python scripts/verify_output_screens_visual.py    # in another
"""
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

URL = "http://localhost:8501"
VIEWPORT = {"width": 1280, "height": 1400}


def full_screenshot(page: Page, path: str) -> None:
    """Streamlit's [data-testid="stMain"] and [data-testid="stSidebarContent"]
    scroll independently of the document -- stApp/stAppViewContainer are
    height:100vh + overflow:hidden, and stMain/stSidebarContent are each
    overflow-y:auto with their own clientHeight capped at the viewport.
    Plain page.screenshot(full_page=True) only captures document scroll
    height, which Streamlit pins to exactly the viewport height, so it
    silently crops anything below the fold in either region (confirmed via
    a live DOM probe: stMain.scrollHeight=1736 vs clientHeight=1400 on the
    real Risk Register tab). Fix: measure the true content height, grow the
    viewport to fit it (stApp's 100vh math then gives every region enough
    room to render without internal scrolling), screenshot, then restore the
    original viewport so subsequent interactions see consistent geometry."""
    needed = page.evaluate(
        """
        () => {
            const main = document.querySelector('[data-testid="stMain"]');
            const sidebar = document.querySelector('[data-testid="stSidebarContent"]');
            return Math.max(
                main ? main.scrollHeight : 0,
                sidebar ? sidebar.scrollHeight : 0,
                window.innerHeight,
            );
        }
        """
    )
    page.set_viewport_size({"width": VIEWPORT["width"], "height": needed + 40})
    page.wait_for_timeout(150)
    page.screenshot(path=path, full_page=True)
    page.set_viewport_size(VIEWPORT)
    page.wait_for_timeout(150)


def main() -> int:
    out_dir = Path(tempfile.mkdtemp(prefix="qai_output_screens_visual_"))

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport=VIEWPORT)

        # ── 1. Landing addendum ──────────────────────────────────────────
        page.goto(URL, timeout=30000, wait_until="networkidle")
        # "networkidle" doesn't wait for Streamlit's own server-side script run
        # (a fresh session_state init, including a real synchronous Pinecone
        # call for the visit counter) to finish and push content over the
        # websocket -- wait for the actual landing content first.
        page.wait_for_selector(".pom-stats", timeout=30000)
        # Last stat tile's animation-delay is 3.15s (4 stats x 0.1s steps from
        # a 2.85s base) + its 0.5s duration = finishes at 3.65s -- pad well
        # past that so the screenshot isn't taken mid-animation.
        page.wait_for_timeout(4200)
        full_screenshot(page, str(out_dir / "landing_deliverables.png"))

        # ── 2. render_strategy(): full real generation ──────────────────
        page.get_by_role("button", name="Start — Generate a Test Strategy").click(timeout=10000)
        page.wait_for_selector(".dialogue-progress-track", timeout=15000)
        page.locator('[data-testid="stSelectbox"]').first.click()
        page.get_by_text("🌐 Web Application", exact=False).click(timeout=10000)
        page.get_by_role("button", name="Apply template").click(timeout=10000)
        page.wait_for_timeout(500)
        page.get_by_role("button", name="✅ Review & Generate Strategy").click(timeout=10000)
        page.wait_for_selector(".review-grid", timeout=15000)
        page.get_by_role("button", name="🤖 Generate Test Strategy").click(timeout=10000)

        page.wait_for_selector(".stage-sequence", timeout=20000)
        # Try to catch a mid-generation "active" stage — best-effort, since
        # streamed LLM generation timing isn't deterministic. If this
        # particular poll misses it, the final all-done screenshot below
        # still verifies the indicator renders correctly.
        try:
            page.wait_for_selector(".stage-item.active", timeout=15000)
            full_screenshot(page, str(out_dir / "strategy_stage_active.png"))
            print("Caught a mid-generation 'active' stage screenshot.")
        except Exception:
            print("Did not catch a mid-generation 'active' stage in time (non-fatal) — "
                  "the final all-done screenshot still covers the indicator.")

        page.wait_for_selector('[data-testid="stTabs"]', timeout=240000)  # full 4-stage pipeline
        page.wait_for_timeout(600)  # let the .output-tiles entrance finish
        stage_classes = page.eval_on_selector_all(".stage-item", "els => els.map(e => e.className)")
        print(f"Final stage classes (expect all 'stage-item done'): {stage_classes}")
        active_tab_color = page.eval_on_selector(
            '[data-testid="stTab"][aria-selected="true"] p', "el => getComputedStyle(el).color"
        )
        print(f"Active tab label color (expect the accent color, not default black/red): {active_tab_color}")
        full_screenshot(page, str(out_dir / "strategy_tab1_risk.png"))

        page.get_by_role("tab", name="📊 Effort Estimation").click(timeout=10000)
        page.wait_for_timeout(300)
        full_screenshot(page, str(out_dir / "strategy_tab2_effort.png"))

        # Hover check: a download button's border should change to the accent color.
        # Streamlit keeps all 4 tabs' download buttons mounted in the DOM (only the
        # active tab panel is visible), so scope to :visible or .first grabs a hidden
        # button from the Risk Register tab and hover() times out waiting for it to
        # become visible.
        dl_button = page.locator('[data-testid="stDownloadButton"] button:visible').first
        dl_button.hover()
        page.wait_for_timeout(200)
        hover_border_color = dl_button.evaluate("el => getComputedStyle(el).borderColor")
        print(f"Download button border color on hover (expect the accent color): {hover_border_color}")

        browser.close()

        # ── 3. render_doc_review(): deterministic step only (no LLM call) ─
        browser = p.chromium.launch()
        page = browser.new_page(viewport=VIEWPORT)
        page.goto(URL, timeout=30000, wait_until="networkidle")
        page.wait_for_selector(".pom-stats", timeout=30000)
        page.wait_for_timeout(1000)
        page.get_by_role("button", name="Review an existing QA document instead").click(timeout=10000)
        page.wait_for_selector(".st-key-doc-review-input", timeout=15000)
        full_screenshot(page, str(out_dir / "doc_review_input_tray.png"))

        page.locator("textarea").last.fill(
            "# Test Plan\n\nScope: checkout flow.\nEntry criteria: build passes CI.\n"
            "Exit criteria: 0 open critical defects.\n\n## Test Cases\n"
            "1. Verify successful checkout with valid payment.\n"
            "2. Verify checkout rejects an expired card.\n" * 5
        )
        # .fill() alone doesn't blur the widget, so Streamlit's text_area never
        # commits the value to session state and the "Review Document" button
        # (disabled until document_text.strip() is truthy) never re-enables.
        # Tab away to blur, then give the resulting rerun time to land.
        page.keyboard.press("Tab")
        page.wait_for_timeout(1000)
        page.get_by_role("button", name="🔍 Review Document").click(timeout=10000)
        page.wait_for_selector(".output-tiles", timeout=15000)
        page.wait_for_timeout(500)  # let the entrance finish
        full_screenshot(page, str(out_dir / "doc_review_results.png"))
        browser.close()

        # ── 4. Reduced-motion pass (landing + doc-review only — cheap to
        #        re-run; a second full real generation for this pass would
        #        double the API cost for a check the pulse/entrance CSS
        #        rules already cover deterministically) ────────────────
        browser = p.chromium.launch()
        page = browser.new_page(viewport=VIEWPORT, reduced_motion="reduce")
        page.goto(URL, timeout=30000, wait_until="networkidle")
        # A fresh browser context is a brand-new Streamlit session (its own
        # session_state init, including a real synchronous Pinecone call for
        # the visit counter) -- "networkidle" doesn't wait for that server-side
        # script run to finish and push content over the websocket, so wait for
        # the actual landing content instead of a fixed short timeout.
        page.wait_for_selector(".pom-stats", timeout=30000)
        page.wait_for_timeout(300)
        full_screenshot(page, str(out_dir / "landing_deliverables_reduced_motion.png"))
        page.get_by_role("button", name="Review an existing QA document instead").click(timeout=10000)
        page.wait_for_selector(".st-key-doc-review-input", timeout=15000)
        page.locator("textarea").last.fill("# Test Plan\n\nScope: checkout flow.\n" * 20)
        page.keyboard.press("Tab")
        page.wait_for_timeout(1000)
        page.get_by_role("button", name="🔍 Review Document").click(timeout=10000)
        page.wait_for_selector(".output-tiles", timeout=15000)
        page.wait_for_timeout(150)
        full_screenshot(page, str(out_dir / "doc_review_results_reduced_motion.png"))
        browser.close()

    print(f"Screenshots saved to: {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
