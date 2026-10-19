"""
Manual dev script -- regression check for "typed input lost on the first try"
(2026-10 QA report). Types into the project-name field and clicks
"Review & Generate" without any blur/Enter, then asserts the review screen shows
the typed value. Not part of pytest/CI: run manually.

Usage:
    streamlit run src/app.py --server.port 8517   # leave running
    python scripts/verify_typed_input_kept.py
"""

import re
import sys

from playwright.sync_api import sync_playwright

URL = "http://localhost:8517"
with sync_playwright() as p:
    b = p.chromium.launch()
    page = b.new_page(viewport={"width": 1280, "height": 1400})
    page.goto(URL, wait_until="networkidle")
    page.wait_for_timeout(1500)
    btn = page.get_by_role("button", name=__import__("re").compile("Start: generate"))
    btn.scroll_into_view_if_needed()
    btn.click()
    page.wait_for_selector(".dialogue-progress-track")
    page.wait_for_timeout(500)
    page.locator('[data-testid="stSelectbox"]').first.click()
    page.get_by_text("🌐 Web Application", exact=False).click()
    page.get_by_role("button", name="Apply template").click()
    page.wait_for_timeout(2000)
    failures = 0
    for mode in ("fill", "type"):
        inp = (
            page.locator("input[aria-label^='What is the name']").first
            if page.locator("input[aria-label^='What is the name']").count()
            else page.locator("input[type=text]").first
        )
        inp.click()
        inp.press("Control+A")
        txt = f"Typed-{mode}-XYZ"
        if mode == "fill":
            inp.fill(txt)
        else:
            inp.press_sequentially(txt, delay=30)
        go = page.get_by_role("button", name="Review & Generate Strategy")
        go.scroll_into_view_if_needed()
        go.click()
        page.wait_for_timeout(2500)
        body = page.inner_text("body")
        ok = "Review Project Context" in body and txt in body
        print(mode, "->", "OK" if ok else "FAIL: typed value lost")
        failures += 0 if ok else 1
        if "Review Project Context" in body:
            page.get_by_role(
                "button", name=__import__("re").compile("Go Back")
            ).first.click() if page.get_by_role(
                "button", name=__import__("re").compile("Go Back")
            ).count() else None
            page.wait_for_timeout(1500)
    b.close()
    sys.exit(1 if failures else 0)
