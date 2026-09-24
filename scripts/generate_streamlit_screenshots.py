"""Regenerate the README's Streamlit screenshots (docs/screenshots/streamlit_*.png).

Needs the app running locally with real API keys (the results screenshots come from a
full 4-stage generation, ~2-3 min):

    streamlit run src/app.py --server.port 8599 --server.headless true
    python scripts/generate_streamlit_screenshots.py [--url http://localhost:8599]

Captures a 1440x900 viewport per screen (the local-only "Deploy" toolbar is hidden).
"""
import argparse
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "docs" / "screenshots"
VIEWPORT = {"width": 1440, "height": 900}
HIDE_TOOLBAR = '[data-testid="stToolbar"], [data-testid="stDecoration"] { display: none !important; }'


def open_home(page: Page, url: str) -> None:
    page.goto(url, timeout=60000, wait_until="networkidle")
    page.wait_for_selector(".pom-stats", timeout=60000)
    page.add_style_tag(content=HIDE_TOOLBAR)
    page.wait_for_timeout(4500)  # let the landing entrance animation finish


def shot(page: Page, name: str, scroll_to=None) -> None:
    if scroll_to is not None:
        scroll_to.scroll_into_view_if_needed()
        scroll_to.evaluate("el => el.scrollIntoView({block: 'start'})")
        # leave room for Streamlit's fixed header, which would otherwise cover the element's top
        page.evaluate("document.querySelector('[data-testid=\"stMain\"]')?.scrollBy(0, -90)")
        page.wait_for_timeout(600)
    page.screenshot(path=str(OUT / name))
    print("saved", name)


def main(url: str) -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport=VIEWPORT)

        # 1-2. Landing page, then the sidebar's MCP panel expanded
        open_home(page, url)
        shot(page, "streamlit_intro.png")
        # Match on the panel's own summary: the Release Notes panel's body also contains this text
        mcp_summary = page.locator('[data-testid="stSidebar"] summary').filter(has_text="Use QAI in your AI tools")
        mcp_summary.click()
        page.wait_for_timeout(800)
        mcp_summary.evaluate("el => el.scrollIntoView({block: 'start'})")  # the sidebar scrolls independently
        page.wait_for_timeout(600)
        shot(page, "streamlit_mcp_sidebar.png")
        mcp_summary.click()
        page.wait_for_timeout(500)

        # 3. Project Discovery dialogue with the Web Application template applied
        page.get_by_role("button", name="Start — Generate a Test Strategy").click(timeout=10000)
        page.wait_for_selector(".dialogue-progress-track", timeout=15000)
        page.locator('[data-testid="stSelectbox"]').first.click()
        page.get_by_text("🌐 Web Application", exact=False).click(timeout=10000)
        page.get_by_role("button", name="Apply template").click(timeout=10000)
        page.wait_for_timeout(2500)
        shot(page, "streamlit_dialogue.png", page.locator(".dialogue-progress-track"))

        # 4-7. Full generation, then one screenshot per output tab
        page.get_by_role("button", name="✅ Review & Generate Strategy").click(timeout=10000)
        page.wait_for_selector(".review-grid", timeout=20000)
        page.get_by_role("button", name="🤖 Generate Test Strategy").click(timeout=10000)
        page.wait_for_selector('[data-testid="stTabs"]', timeout=900000)
        page.wait_for_timeout(2000)
        shot(page, "streamlit_risk_register.png", page.locator(".ledger-card").filter(has_text="Executive readout").first)
        tabs = page.locator('[data-testid="stTab"]')
        for i, name in enumerate(["streamlit_risk_ledger.png", "streamlit_effort.png",
                                  "streamlit_strategy.png", "streamlit_test_plan.png"]):
            tabs.nth(i).click()
            page.wait_for_timeout(1200)
            shot(page, name, page.locator('[data-testid="stTabs"]'))

        # 8. QA Document Quality Review (deterministic, no LLM call)
        open_home(page, url)
        page.get_by_role("button", name="📝 Review an existing QA document instead").click(timeout=10000)
        page.wait_for_selector(".st-key-doc-review-input", timeout=15000)
        page.locator("textarea").last.fill((REPO / "evals/fixtures/review/strong_test_plan.md").read_text(encoding="utf-8"))
        page.keyboard.press("Tab")  # blur so Streamlit registers the text_area value
        page.wait_for_timeout(1500)
        page.get_by_role("button", name="🔍 Review Document").click(timeout=10000)
        page.wait_for_selector(".output-tiles", timeout=20000)
        page.wait_for_timeout(1500)
        shot(page, "streamlit_doc_review.png", page.locator(".output-tiles").first)

        # 9. QA Maturity Assessment (deterministic, no LLM call)
        open_home(page, url)
        page.get_by_role("button", name="📈 Assess QA Maturity").click(timeout=10000)
        page.wait_for_selector(".st-key-maturity-input", timeout=15000)
        page.locator("textarea").last.fill((REPO / "evals/fixtures/maturity/level3_strong.txt").read_text(encoding="utf-8"))
        page.keyboard.press("Tab")
        page.wait_for_timeout(1500)
        page.get_by_role("button", name="🔍 Assess Maturity").click(timeout=10000)
        page.wait_for_selector(".output-tiles", timeout=20000)
        page.wait_for_timeout(1500)
        shot(page, "streamlit_maturity.png", page.locator(".output-tiles").first)

        browser.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8599")
    main(ap.parse_args().url)
