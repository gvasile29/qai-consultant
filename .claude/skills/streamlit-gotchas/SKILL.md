---
name: streamlit-gotchas
description: Streamlit/PDF/session-state pitfalls for this repo (widget-state layers, PDF caching, session cleanup lists, render_strategy resumability, xhtml2pdf images, button hover CSS, Streamlit screenshots). Load before editing src/app.py, anything under src/qai_consultant/ui/ or compliance/pdf_export.py, or before verifying Streamlit UI visually.
user-invocable: false
---

# Streamlit gotchas (QAI Consultant)

Moved out of CLAUDE.md so they load only when working on the UI. The two always-on UI rules
(`st.image` ban, `StopException`/`RerunException` re-raise) stay in CLAUDE.md's Gotchas.

- **Streamlit widget state:** `st.session_state["input_{key}"]` and `st.session_state.answers[key]` are separate layers. Both must be updated together when pre-filling fields (e.g. template application).
- **PDF caching:** `markdown_to_pdf()` is slow (1–5s). Results are cached in `st.session_state.*_pdf_bytes`. Never call it inside the tab rendering block.
- **Session state cleanup:** "Start Over" and "Generate Another Strategy" must clear answers, widget input keys, PDF byte caches, `_feedback_partial`, `run_count`, plus the F1/F2/maturity mode keys (`REVIEW_MODE_STATE_KEYS`, `results_analysis`+`results_uploader`, `MATURITY_MODE_STATE_KEYS`). Missing any key causes stale data or broken run limits.
- **`render_strategy()` resumability:** gated by an explicit `results_complete` flag (set after the final PDF-bytes precompute), not any single stage's output, so a mid-pipeline rerun (websocket reconnect) isn't treated as done. `generation_started` gates the `run_count` increment; each of the 4 stages has its own reuse guard. Both flags stay in the cleanup lists.
- **xhtml2pdf renders raster images (PNG) via base64 data URIs but not SVG** — any image added to a PDF export (`pdf_export.py`'s `extra_body_html`) needs a PNG, not SVG.
- **`page.screenshot(full_page=True)` silently crops a Streamlit page** (independently-scrolling `stMain`/`stSidebarContent`). Use `full_screenshot()` from `scripts/verify_visual_common.py` instead.
- **Hover CSS on real Streamlit buttons must exclude primary buttons from `color` overrides** — Streamlit's default primary button is a red fill with a white label; overriding just the label color on hover can drop contrast far below WCAG AA while the fill stays red. Scope `color` changes to `button:not([data-testid$="-primary"]):hover`; `border-color` is safe unscoped.
