---
name: browser-ui-testing
description: How to verify local Streamlit UI changes in this repo — prefer a Playwright Python CLI script over MCP browser tools for repeatable checks, and match review process to change risk. Use before claiming a UI/browser change works, or whenever the "start the dev server and use the feature in a browser" step comes up.
---

# Browser / UI Testing (QAI Consultant)

For local Streamlit UI verification, **default to the Playwright Python CLI, not the Playwright/claude-in-chrome MCP browser tools.** Write a small script using `playwright.sync_api` and run it via Bash (`python script.py`), printing only what's needed (e.g. a specific `console.log`/assertion result) — a multi-step MCP browser session round-trips a full accessibility snapshot/DOM into context on every single action, which burns far more tokens than one script execution that returns just the final result.

MCP browser tools (claude-in-chrome, Playwright MCP) are still the right choice for genuinely exploratory/ad-hoc work — debugging an unfamiliar page, poking around when you don't know the DOM structure yet. For repeatable/deterministic checks (does the page load, does a button work, does a redesign render correctly), use the CLI by default without waiting to be asked.

Playwright is installed (`playwright==1.62.0`, pinned in `requirements-dev.txt`) with the Chromium browser binary already downloaded locally — no setup needed before writing a script.

Before writing a script that takes screenshots, check the `page.screenshot(full_page=True)` entry in CLAUDE.md's Gotchas — it silently crops a Streamlit page with independently-scrolling containers. Use the `full_screenshot()` helper in `scripts/verify_visual_common.py` instead.

**Process scale for visual/CSS-only changes:** the 3-phase "Power-On Sequence" redesign (v3.4.1-v3.4.3) used `superpowers:subagent-driven-development` with an independent implementer + reviewer per task, plus a separate final whole-branch review, for each phase. That level of process is proportionate for a multi-task redesign spanning several screens, but it is not the default for a small, single-screen, cosmetic-only CSS/styling change with no logic, security, or data-handling surface — those can go through the normal direct-implementation workflow (write the change, verify visually per above, commit) without a dedicated multi-agent review pass. Reserve the heavier process for changes that touch application logic, security-sensitive code, or anything with a real behavioral surface to get wrong.
