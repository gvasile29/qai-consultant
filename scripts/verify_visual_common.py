"""Shared helpers for the manual Playwright visual-verification scripts
(scripts/verify_*_visual.py). Not part of pytest/CI — these scripts are
run manually against a live `streamlit run src/app.py`.
"""
from playwright.sync_api import Page

URL = "http://localhost:8501"


def full_screenshot(page: Page, path: str, viewport: dict) -> None:
    """Streamlit's [data-testid="stMain"] and [data-testid="stSidebarContent"]
    scroll independently of the document -- stApp/stAppViewContainer are
    height:100vh + overflow:hidden, and stMain/stSidebarContent are each
    overflow-y:auto with their own clientHeight capped at the viewport.
    Plain page.screenshot(full_page=True) only captures document scroll
    height, which Streamlit pins to exactly the viewport height, so it
    silently crops anything below the fold in either region (confirmed via
    a live DOM probe: stMain.scrollHeight=1736 vs clientHeight=1400 on a
    real Risk Register tab). Fix: measure the true content height, grow the
    viewport to fit it (stApp's 100vh math then gives every region enough
    room to render without internal scrolling), screenshot, then restore the
    original viewport so subsequent interactions see consistent geometry.

    `viewport` is the caller's normal viewport dict (e.g. {"width": 1280,
    "height": 1400}) to restore afterward — pass whatever you constructed
    the page with, since different scripts use different sizes."""
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
    page.set_viewport_size({"width": viewport["width"], "height": needed + 40})
    page.wait_for_timeout(150)
    page.screenshot(path=path, full_page=True)
    page.set_viewport_size(viewport)
    page.wait_for_timeout(150)


def reveal(page: Page, locator, max_scrolls: int = 40, step: int = 1200, pause: int = 100) -> None:
    """Streamlit lazy-mounts elements far below the fold (IntersectionObserver-
    gated rendering -- confirmed by inspecting document.querySelectorAll('button')
    before/after scrolling: a button can be absent from the DOM entirely until
    scrolled near view, not just off-screen). Scroll incrementally until
    `locator` is attached before interacting with it; a no-op if it's already
    present."""
    for _ in range(max_scrolls):
        if locator.count() > 0:
            return
        page.mouse.wheel(0, step)
        page.wait_for_timeout(pause)
