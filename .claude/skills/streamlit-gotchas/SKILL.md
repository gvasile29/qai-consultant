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
- **Hover CSS on real Streamlit buttons must exclude primary buttons from `color` overrides** — a primary button is filled with `primaryColor`, which `.streamlit/config.toml` sets to the accent token, so an accent hover label vanishes into its own fill. `theme.py`'s `build_css()` owns the primary label color (the `page` token; Streamlit's white default measured 1.86:1 on the dark theme's teal). Scope `color` changes to `button:not([data-testid$="-primary"]):hover`; `border-color` is safe unscoped.
- **A Session-State value reaches the browser only in the run that set it.** A widget key set in one run (e.g. by a callback) for a widget first created in a later run shows the widget's empty default in the browser, which then posts `""` back on the next interaction. Set the key in the run that creates the widget (`st.session_state[k] = st.session_state.get(k, fallback)` just before it, key-only, no `value=`). AppTest reads backend state and cannot see this; only a browser check can (`scripts/verify_interactive_flow_visual.py`, discovery wizard).
- **Navigate with `on_click` callbacks, not `st.rerun()`, when the next screen has different widgets.** After an in-script `st.rerun()`, AppTest's element tree keeps the aborted pass's widgets and the next interaction raises `KeyError` on their keys. A callback that changes state before the script avoids the second pass. It must first copy the outgoing screen's widget values into the surviving layer (`answers`): a value typed and clicked with no blur arrives in the click's run, where its widget no longer renders.
