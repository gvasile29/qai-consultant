# Output Screens Redesign — Phase 3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Apply the "Power-On Sequence" visual language (established in Phase 1's `landing_hero.py`, Phase 2's `interactive_flow_style.py`) to the two output screens — `render_strategy()`'s 4-tab result view (Risk Register / Effort Estimation / Test Strategy / Test Plan) and `render_doc_review()`'s upload-then-score flow — plus a small folded-in addendum finishing Phase 1's own landing screen ("What you get in ~2 minutes").

**Architecture:** A new pure-function module, `src/output_screen_style.py` (header eyebrow, a 4-stage sequence status readout unique to `render_strategy()`, and shared button/expander/tab-bar hover-and-entrance CSS), following `landing_hero.py`/`interactive_flow_style.py`'s exact pattern — no Streamlit dependency, unit-testable without a runtime. `landing_hero.py` gets one new function, `build_landing_deliverables_html()`, for the addendum. `app.py`'s `render_strategy()`, `render_doc_review()`, and `render_intro()` each call the relevant builder(s) and render via `st.markdown(html, unsafe_allow_html=True)`.

**Tech Stack:** Python, Streamlit 1.59.1, plain CSS (transitions + gated keyframe animations + one intentionally-looping status-pulse animation), pytest, Playwright (manual visual verification, not wired into CI, following Phases 1-2's `scripts/verify_*_visual.py` precedent).

**Spec:** `docs/superpowers/specs/2026-08-17-output-screens-power-on-redesign-design.md`

## Global Constraints

- `theme.py` is **not modified** — no new color tokens, no new fonts, no new rules added to `build_css()`. `ledger_components.py` is **not modified** either (per the spec's "Signal Ledger / Risk Ledger re-evaluation": already visually consistent, verified in Task 5).
- All new CSS lives inside `output_screen_style.py`'s and `landing_hero.py`'s own returned `<style>` blocks — never appended to `theme.py`'s `build_css()`.
- The `[data-testid="stMain"]`, `[data-testid="stButton"]`, `[data-testid="stDownloadButton"]`, `[data-testid="stExpander"]`, `[data-testid="stTabs"]`, `[data-testid="stTab"]`, and `.react-aria-SelectionIndicator` selectors used in `build_content_polish_css()` are **verified against this app's actual pinned Streamlit version (1.59.1)'s rendered DOM** — inspected via a throwaway local `st.tabs()`/`st.expander()`/`st.button()` probe script and Playwright, not guessed. See Task 1, Step 0.
- `output_intro_animated` (set by `render_strategy()`) and `doc_review_intro_animated` (set by `render_doc_review()`) are session-wide "have you seen this" flags, **excluded from every cleanup list** (`render_sidebar()`'s "Start Over", `render_strategy()`'s "Generate Another Strategy", and `REVIEW_MODE_STATE_KEYS`/`_reset_review_mode_state()`) — same precedent as `mcp_announcement_seen` and Phase 2's `review_intro_animated`. Do not add either flag to any of those lists.
- The stage-sequence indicator (`build_stage_sequence_html()`) is a **live status readout**, not a mount animation — it is never gated behind a session-state flag and must re-render correctly on every call based purely on which of `risk_register`/`effort_report`/`strategy`/`test_plan` are already in `session_state`.
- The score-tile entrance animation (`.output-tiles.animate`) applies to exactly **one tile per location**: `render_strategy()`'s Risk Ledger table (tab 1) and Effort confidence tile (tab 2), and `render_doc_review()`'s Overall Score tile. It deliberately does **not** apply to the per-dimension score row in either screen (`render_doc_review()`'s `dim_cols` loop) — those tiles each render inside their own `st.columns()` cell as an independent `st.markdown()` call, so a CSS `nth-child` stagger across them isn't reliably achievable in one shared parent; leaving them static avoids a fragile implementation for a purely cosmetic effect.
- `output_screen_style.py` is a Streamlit-app-only module, like `theme.py`/`ledger_components.py`/`landing_hero.py`/`interactive_flow_style.py` — it must **not** be added to `pyproject.toml`'s `[tool.setuptools] py-modules` list.
- Must not break the existing regression tests that source-inspect `render_strategy()`/`render_doc_review()`: `tests/test_app_v03.py` (tab labels, the 4-stage try/except isolation fingerprint, cleanup-list keys), `tests/test_app_stopexception.py` (the `except (StopException, RerunException): raise` clause immediately before each stage's generic `except`), `tests/test_app_run_count.py` (`generation_started`/`results_complete`/`run_count` guard logic), `tests/test_app_review_mode.py` (`REVIEW_MODE_STATE_KEYS` cleanup, the `review_doc_uploader`/`review_doc_pasted_text`/`review_doc_type_select` widget keys). None of this plan's insertions touch any `try:`/`except` block internals or rename any existing session-state key.
- No Phase 4 scope (there is no Phase 4 — this is the last of the 3-phase redesign). No new Playwright Page Object Model test suite (separate work stream, per the original brainstorm).

---

### Task 1: `output_screen_style.py` — pure HTML/CSS builders + unit tests

**Files:**
- Create: `src/output_screen_style.py`
- Create: `tests/test_output_screen_style.py`

**Interfaces:**
- Produces: `build_output_eyebrow_html(tokens: dict, label: str) -> str`
- Produces: `build_stage_sequence_html(tokens: dict, stages: list) -> str` — `stages` is an ordered list of `(label: str, status: str)` tuples, `status` in `{"pending", "active", "done"}`
- Produces: `build_content_polish_css(tokens: dict) -> str`
- Produces: `build_doc_review_input_tray_css(tokens: dict) -> str`
- Tasks 2 and 3 import all four functions by name.

- [ ] **Step 0: Verify the real Streamlit DOM selectors before writing any CSS**

This step already ran once during planning (not a repeat needed) — documented here so the rationale travels with the plan. A throwaway script (`st.tabs([...]); st.expander(...); st.button(...)`) was launched locally with `streamlit run` and inspected via a Playwright `page.eval_on_selector(sel, "el => el.outerHTML")` call against the real running app (Streamlit 1.59.1). Findings, used in Step 3 below:
- Each tab is `<div data-testid="stTab" ... aria-selected="true|false" role="tab">`, containing a `<div data-testid="stMarkdownContainer"><p>label</p></div>` and, only on the selected tab, a `<div class="react-aria-SelectionIndicator">`.
- `st.expander()`'s clickable header is a `<summary>` inside `<div data-testid="stExpander">`.
- `st.button()`/`st.download_button()` each render a real `<button>` inside `<div data-testid="stButton">` / `<div data-testid="stDownloadButton">`.
- The main content region (as opposed to the sidebar) has its own `data-testid="stMain"` wrapper — confirmed present in this Streamlit version by grepping the installed package's bundled frontend JS for the literal string `"stMain"` (found in `index.*.js`) before relying on it in CSS.

If re-verification is ever needed (e.g. after a future Streamlit upgrade), repeat with: a scratch script containing the widgets in question, `streamlit run <script> --server.port 8502`, and a Playwright script calling `page.eval_on_selector('[data-testid="..."]', "el => el.outerHTML")`, writing output to a file (not stdout — emoji labels in this app's real tab text can hit `UnicodeEncodeError` on Windows' default console codepage).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_output_screen_style.py`:

```python
"""Tests for src/output_screen_style.py -- Phase 3 output-screen styling,
shared by render_strategy() and render_doc_review(). See
docs/superpowers/specs/2026-08-17-output-screens-power-on-redesign-design.md."""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from theme import LIGHT_TOKENS, DARK_TOKENS  # noqa: E402
from output_screen_style import (  # noqa: E402
    build_output_eyebrow_html,
    build_stage_sequence_html,
    build_content_polish_css,
    build_doc_review_input_tray_css,
)


def test_output_eyebrow_uses_the_given_tokens_not_a_hardcoded_theme():
    light = build_output_eyebrow_html(LIGHT_TOKENS, "output analysis sequence")
    dark = build_output_eyebrow_html(DARK_TOKENS, "output analysis sequence")
    assert LIGHT_TOKENS["ink_dim"] in light
    assert DARK_TOKENS["ink_dim"] not in light
    assert DARK_TOKENS["ink_dim"] in dark
    assert LIGHT_TOKENS["ink_dim"] not in dark


def test_output_eyebrow_renders_the_given_label():
    html = build_output_eyebrow_html(LIGHT_TOKENS, "document review sequence")
    assert "document review sequence" in html


def test_stage_sequence_renders_all_stage_labels_with_correct_status_class():
    stages = [("Risk", "done"), ("Effort", "active"), ("Strategy", "pending"), ("Plan", "pending")]
    html = build_stage_sequence_html(LIGHT_TOKENS, stages)
    assert '<div class="stage-item done">' in html
    assert "Risk" in html
    assert '<div class="stage-item active">' in html
    assert "Effort" in html
    assert html.count('<div class="stage-item pending">') == 2


def test_stage_sequence_defines_the_pulse_animation_for_active_dots():
    html = build_stage_sequence_html(LIGHT_TOKENS, [("Risk", "active")])
    assert "@keyframes stage-pulse" in html
    assert ".stage-item.active .stage-dot" in html
    assert "animation: stage-pulse" in html


def test_stage_sequence_handles_an_empty_stage_list():
    html = build_stage_sequence_html(LIGHT_TOKENS, [])
    assert '<div class="stage-sequence"></div>' in html


def test_stage_sequence_escapes_html_in_labels():
    html = build_stage_sequence_html(LIGHT_TOKENS, [("<script>alert(1)</script>", "pending")])
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_content_polish_css_scopes_buttons_and_expanders_to_main_not_sidebar():
    html = build_content_polish_css(LIGHT_TOKENS)
    assert '[data-testid="stMain"]' in html
    assert '[data-testid="stSidebar"]' not in html
    assert LIGHT_TOKENS["accent"] in html


def test_content_polish_css_styles_the_active_tab_indicator():
    html = build_content_polish_css(LIGHT_TOKENS)
    assert '[data-testid="stTab"][aria-selected="true"]' in html
    assert ".react-aria-SelectionIndicator" in html


def test_content_polish_css_defines_the_output_tiles_entrance_animation():
    html = build_content_polish_css(LIGHT_TOKENS)
    assert "@keyframes output-tiles-in" in html
    assert ".output-tiles.animate" in html


def test_doc_review_input_tray_css_scopes_to_the_keyed_container():
    html = build_doc_review_input_tray_css(LIGHT_TOKENS)
    assert ".st-key-doc-review-input" in html
    assert LIGHT_TOKENS["surface"] in html
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_output_screen_style.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'output_screen_style'`

- [ ] **Step 3: Write the implementation**

Create `src/output_screen_style.py`:

```python
"""
QAI Consultant -- Phase 3 output-screen styling ("Power-On Sequence",
continuing Phase 1's landing_hero.py and Phase 2's interactive_flow_style.py
-- see docs/superpowers/specs/2026-08-17-output-screens-power-on-redesign-design.md).

Four pure functions: a header eyebrow and a shared content-polish CSS block
(both used by render_strategy() AND render_doc_review()), a 4-stage
sequence status readout (render_strategy() only -- the only screen with a
genuinely sequential multi-stage pipeline), and an input-tray CSS block
(render_doc_review() only). No Streamlit dependency -- callers pass the
app.py-derived tokens dict (theme.LIGHT_TOKENS or theme.DARK_TOKENS) and
render the result via st.markdown(html, unsafe_allow_html=True), same as
landing_hero.py, interactive_flow_style.py, and ledger_components.py.

theme.py is NOT modified by this module. All CSS here is scoped to its own
class names (output-eyebrow, stage-*, output-tiles) plus data-testid/
aria-attribute selectors verified against this app's real rendered DOM
(Streamlit 1.59.1 -- see tests/test_output_screen_style.py's docstring
reference and this module's own plan Task 1 Step 0 for how), never added
to theme.py's build_css().

The stage-sequence indicator's "active" dot uses a looping pulse animation
-- unlike every other animation in this 3-phase redesign, which are all
one-shot. This is deliberate: it signals a real, currently-running
background process (an in-flight LLM call), the same category of thing
st.spinner()'s own built-in animation already represents elsewhere in this
app -- a status signal, not decorative motion. theme.py's existing global
prefers-reduced-motion rule (build_css(), zeroing animation-duration)
already disables it for reduced-motion users; no module-local delay
override is needed here, unlike landing_hero.py/interactive_flow_style.py,
because this animation has no animation-delay for that global rule to miss.
"""
import html as _html


def build_output_eyebrow_html(tokens: dict, label: str) -> str:
    """Pure function: token dict + a caller-supplied label -> a mono
    uppercase eyebrow line, reusing the label style
    interactive_flow_style.py's .dialogue-eyebrow established. `label` is
    always a hardcoded string from an app.py call site (never user input),
    so it is not HTML-escaped -- consistent with build_dialogue_header_html()
    not escaping its own interpolations."""
    return f"""
<style>
.output-eyebrow {{ font-family: 'Plex Mono', monospace; font-size: 0.7rem; letter-spacing: 0.06em; text-transform: uppercase; color: {tokens['ink_dim']}; margin-bottom: 0.4rem; }}
</style>
<div class="output-eyebrow">&gt; {label}</div>
"""


def build_stage_sequence_html(tokens: dict, stages: list) -> str:
    """Pure function: token dict + an ordered list of (label, status)
    tuples (status is "pending", "active", or "done") -> a horizontal
    stage-status readout. Used only by render_strategy(). Not gated by any
    session-state "seen" flag: it is a live status readout driven by
    whichever stages are already in session_state, not a mount animation,
    so it must render correctly every time it is called, regardless of how
    many times the screen has been shown before."""
    items = "".join(
        f'<div class="stage-item {status}"><span class="stage-dot"></span>{_html.escape(label)}</div>'
        for label, status in stages
    )
    return f"""
<style>
.stage-sequence {{ display: flex; gap: 0.6rem; margin-bottom: 1.2rem; flex-wrap: wrap; }}
.stage-item {{ display: flex; align-items: center; gap: 0.4rem; font-family: 'Plex Mono', monospace; font-size: 0.68rem; letter-spacing: 0.04em; text-transform: uppercase; padding: 0.3rem 0.7rem; border: 1px solid {tokens['line']}; border-radius: 4px; color: {tokens['ink_dim']}; }}
.stage-item .stage-dot {{ width: 7px; height: 7px; border-radius: 50%; background: {tokens['line']}; display: inline-block; }}
.stage-item.pending {{ opacity: 0.55; }}
.stage-item.active {{ color: {tokens['ink']}; border-color: {tokens['accent']}; }}
.stage-item.active .stage-dot {{ background: {tokens['accent']}; animation: stage-pulse 1.2s ease-in-out infinite; }}
.stage-item.done {{ color: {tokens['ink']}; border-color: {tokens['pass_']}; }}
.stage-item.done .stage-dot {{ background: {tokens['pass_']}; }}
@keyframes stage-pulse {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0.35; }} }}
</style>
<div class="stage-sequence">{items}</div>
"""


def build_content_polish_css(tokens: dict) -> str:
    """Pure function: token dict -> CSS shared by render_strategy() and
    render_doc_review(): main-content button/expander hover states (same
    treatment interactive_flow_style.py's build_sidebar_polish_css() gave
    the sidebar in Phase 2, scoped to [data-testid="stMain"] instead of
    [data-testid="stSidebar"] so both rule sets coexist without conflict),
    a themed tab bar, and the .output-tiles score-tile entrance animation.
    Selectors verified against this app's real Streamlit 1.59.1 DOM -- see
    this module's docstring and tests/test_output_screen_style.py."""
    return f"""
<style>
[data-testid="stMain"] [data-testid="stButton"] button:hover,
[data-testid="stMain"] [data-testid="stDownloadButton"] button:hover {{
    border-color: {tokens['accent']};
    color: {tokens['accent']};
    transition: border-color 0.15s ease-out, color 0.15s ease-out;
}}
[data-testid="stMain"] [data-testid="stExpander"] summary:hover {{
    color: {tokens['accent']};
    transition: color 0.15s ease-out;
}}
[data-testid="stTabs"] [data-testid="stTab"] p {{
    font-family: 'Plex Mono', monospace;
    font-size: 0.78rem;
    letter-spacing: 0.03em;
    text-transform: uppercase;
}}
[data-testid="stTabs"] [data-testid="stTab"][aria-selected="true"] p {{
    color: {tokens['accent']};
}}
[data-testid="stTabs"] .react-aria-SelectionIndicator {{
    background: {tokens['accent']} !important;
}}
@keyframes output-tiles-in {{ from {{ opacity: 0; transform: translateY(8px); }} to {{ opacity: 1; transform: translateY(0); }} }}
.output-tiles.animate {{ animation: output-tiles-in 0.4s ease-out both; }}
</style>
"""


def build_doc_review_input_tray_css(tokens: dict) -> str:
    """Pure function: token dict -> CSS styling the
    st.container(key="doc-review-input") wrapper around render_doc_review()'s
    intake widgets (doc-type selectbox, file uploader, paste text area) as a
    .ledger-card-equivalent input tray. Uses Streamlit's key= scoping
    technique (a container's key="foo" generates a st-key-foo CSS class) --
    the same per-instance scoping app.py's header-logo container already
    uses (v3.3 precedent) -- rather than reusing .ledger-card itself, which
    belongs to the Phase-2 dialogue screen's per-question cards."""
    return f"""
<style>
.st-key-doc-review-input {{
    background: {tokens['surface']};
    border: 1px solid {tokens['line']};
    padding: 1.1rem 1.3rem;
    margin-bottom: 1rem;
}}
</style>
"""
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_output_screen_style.py -v`
Expected: PASS (10 tests)

- [ ] **Step 5: Lint and type-check**

Run: `ruff check src/output_screen_style.py tests/test_output_screen_style.py`
Run: `mypy src/output_screen_style.py`
Expected: both clean.

- [ ] **Step 6: Commit**

```bash
git add src/output_screen_style.py tests/test_output_screen_style.py
git commit -m "feat: add output_screen_style.py -- Phase 3 output-screen builders"
```

---

### Task 2: Wire `output_screen_style.py` into `render_strategy()`

**Files:**
- Modify: `src/app.py` (`render_strategy()`, currently `app.py:716-1125`)
- Create: `tests/test_app_output_screens.py`

**Interfaces:**
- Consumes: `output_screen_style.build_output_eyebrow_html`, `build_stage_sequence_html`, `build_content_polish_css` (Task 1), `theme.LIGHT_TOKENS`/`DARK_TOKENS` (already exist).

- [ ] **Step 1: Add the header eyebrow, content-polish CSS, and stage-sequence placeholder**

In `src/app.py`, `render_strategy()` currently starts:

```python
    st.markdown("## 📄 Generated Test Strategy")
    st.markdown("---")

    agent = st.session_state.get("agent")
```

Replace with:

```python
    from output_screen_style import build_content_polish_css, build_output_eyebrow_html, build_stage_sequence_html
    from theme import DARK_TOKENS, LIGHT_TOKENS

    _strategy_tokens = DARK_TOKENS if st.context.theme.type == "dark" else LIGHT_TOKENS
    st.markdown(build_content_polish_css(_strategy_tokens), unsafe_allow_html=True)
    st.markdown(build_output_eyebrow_html(_strategy_tokens, "output analysis sequence"), unsafe_allow_html=True)
    st.markdown("## 📄 Generated Test Strategy")
    st.markdown("---")

    stage_placeholder = st.empty()

    def _render_stages(active_key=None):
        order = [
            ("Risk", "risk_register"),
            ("Effort", "effort_report"),
            ("Strategy", "strategy"),
            ("Plan", "test_plan"),
        ]
        stages = []
        for label, key in order:
            if st.session_state.get(key) is not None:
                stages.append((label, "done"))
            elif key == active_key:
                stages.append((label, "active"))
            else:
                stages.append((label, "pending"))
        stage_placeholder.markdown(build_stage_sequence_html(_strategy_tokens, stages), unsafe_allow_html=True)

    _render_stages()

    agent = st.session_state.get("agent")
```

- [ ] **Step 2: Wire the stage-sequence updates into the 4-stage generation block**

The 4-stage block (inside `if needs_generation:`) currently reads exactly as follows (this is the full block — reproduced verbatim so the diff below is unambiguous):

```python
        if st.session_state.get("risk_register") is None:
            st.markdown("#### ⚠️ Generating Risk Register...")
            results_analysis = st.session_state.get("results_analysis")
            results_summary = summarize_for_prompt(results_analysis) if results_analysis else None
            risk_prompt = build_risk_prompt(
                context, agent.format_knowledge_context(risk_chunks), results_summary=results_summary,
            )
            try:
                risk_register = clean_markdown_html(st.write_stream(
                    agent.ask_streaming(risk_prompt, system_prompt=RISK_SYSTEM_PROMPT)
                ))
                risk_register = append_execution_data_appendix(risk_register, results_summary)
                risk_path = risk_analyzer.save(risk_register, context)
            except (StopException, RerunException):
                raise
            except Exception as exc:
                logger.error("Risk Register generation failed: %s", exc)
                st.error(f"❌ Risk Register generation failed: {exc}")
                risk_register, risk_path = "", None
            st.session_state.risk_register = risk_register
            st.session_state.risk_sources = risk_sources
            st.session_state.risk_path = risk_path
        else:
            risk_register = st.session_state.risk_register

        # Effort Estimation (deterministic + short LLM narrative)
        if st.session_state.get("effort_report") is None:
            effort_data = None
            try:
                with st.spinner("📊 Generating Effort Estimation..."):
                    effort_report, effort_data = estimator.estimate(context, risk_register)
                    effort_path = estimator.save(effort_report, context)
            except (StopException, RerunException):
                raise
            except Exception as exc:
                logger.error("Effort Estimation generation failed: %s", exc)
                st.error(f"❌ Effort Estimation generation failed: {exc}")
                effort_report, effort_path = "", None
            st.session_state.effort_report = effort_report
            st.session_state.effort_path = effort_path
            st.session_state.effort_data = effort_data
        else:
            effort_report = st.session_state.effort_report

        # Test Strategy (streaming)
        if st.session_state.get("strategy") is None:
            st.markdown("#### 📋 Generating Test Strategy...")
            strategy_prompt = build_strategy_prompt(context, agent.format_knowledge_context(strategy_chunks))
            try:
                strategy = clean_markdown_html(st.write_stream(
                    agent.ask_streaming(strategy_prompt, system_prompt=SYSTEM_PROMPT)
                ))
                output_path = generator.save(strategy, context)
            except (StopException, RerunException):
                raise
            except Exception as exc:
                logger.error("Test Strategy generation failed: %s", exc)
                st.error(f"❌ Test Strategy generation failed: {exc}")
                strategy, output_path = "", None
            st.markdown("---")
            st.session_state.strategy = strategy
            st.session_state.sources = sources
            st.session_state.output_path = output_path
        else:
            strategy = st.session_state.strategy

        # Test Plan (streaming)
        from test_plan_generator import build_test_plan_prompt, TEST_PLAN_SYSTEM_PROMPT
        if st.session_state.get("test_plan") is None:
            st.markdown("#### 📝 Generating Test Plan...")
            test_plan_prompt = build_test_plan_prompt(context, risk_register, agent.format_knowledge_context(test_plan_chunks))
            try:
                test_plan = clean_markdown_html(st.write_stream(
                    agent.ask_streaming(test_plan_prompt, system_prompt=TEST_PLAN_SYSTEM_PROMPT)
                ))
                test_plan_path = test_plan_generator.save(test_plan, context)
            except (StopException, RerunException):
                raise
            except Exception as exc:
                logger.error("Test Plan generation failed: %s", exc)
                st.error(f"❌ Test Plan generation failed: {exc}")
                test_plan, test_plan_path = "", None
            st.markdown("---")
            st.session_state.test_plan = test_plan
            st.session_state.test_plan_path = test_plan_path
            st.session_state.test_plan_sources = test_plan_sources
        else:
            test_plan = st.session_state.test_plan
```

Replace it with the same block plus 8 `_render_stages(...)` calls added — one before and one after each `if/else` pair (the internals of every `try`/`except` are untouched):

```python
        _render_stages(active_key="risk_register")
        if st.session_state.get("risk_register") is None:
            st.markdown("#### ⚠️ Generating Risk Register...")
            results_analysis = st.session_state.get("results_analysis")
            results_summary = summarize_for_prompt(results_analysis) if results_analysis else None
            risk_prompt = build_risk_prompt(
                context, agent.format_knowledge_context(risk_chunks), results_summary=results_summary,
            )
            try:
                risk_register = clean_markdown_html(st.write_stream(
                    agent.ask_streaming(risk_prompt, system_prompt=RISK_SYSTEM_PROMPT)
                ))
                risk_register = append_execution_data_appendix(risk_register, results_summary)
                risk_path = risk_analyzer.save(risk_register, context)
            except (StopException, RerunException):
                raise
            except Exception as exc:
                logger.error("Risk Register generation failed: %s", exc)
                st.error(f"❌ Risk Register generation failed: {exc}")
                risk_register, risk_path = "", None
            st.session_state.risk_register = risk_register
            st.session_state.risk_sources = risk_sources
            st.session_state.risk_path = risk_path
        else:
            risk_register = st.session_state.risk_register
        _render_stages()

        # Effort Estimation (deterministic + short LLM narrative)
        _render_stages(active_key="effort_report")
        if st.session_state.get("effort_report") is None:
            effort_data = None
            try:
                with st.spinner("📊 Generating Effort Estimation..."):
                    effort_report, effort_data = estimator.estimate(context, risk_register)
                    effort_path = estimator.save(effort_report, context)
            except (StopException, RerunException):
                raise
            except Exception as exc:
                logger.error("Effort Estimation generation failed: %s", exc)
                st.error(f"❌ Effort Estimation generation failed: {exc}")
                effort_report, effort_path = "", None
            st.session_state.effort_report = effort_report
            st.session_state.effort_path = effort_path
            st.session_state.effort_data = effort_data
        else:
            effort_report = st.session_state.effort_report
        _render_stages()

        # Test Strategy (streaming)
        _render_stages(active_key="strategy")
        if st.session_state.get("strategy") is None:
            st.markdown("#### 📋 Generating Test Strategy...")
            strategy_prompt = build_strategy_prompt(context, agent.format_knowledge_context(strategy_chunks))
            try:
                strategy = clean_markdown_html(st.write_stream(
                    agent.ask_streaming(strategy_prompt, system_prompt=SYSTEM_PROMPT)
                ))
                output_path = generator.save(strategy, context)
            except (StopException, RerunException):
                raise
            except Exception as exc:
                logger.error("Test Strategy generation failed: %s", exc)
                st.error(f"❌ Test Strategy generation failed: {exc}")
                strategy, output_path = "", None
            st.markdown("---")
            st.session_state.strategy = strategy
            st.session_state.sources = sources
            st.session_state.output_path = output_path
        else:
            strategy = st.session_state.strategy
        _render_stages()

        # Test Plan (streaming)
        from test_plan_generator import build_test_plan_prompt, TEST_PLAN_SYSTEM_PROMPT
        _render_stages(active_key="test_plan")
        if st.session_state.get("test_plan") is None:
            st.markdown("#### 📝 Generating Test Plan...")
            test_plan_prompt = build_test_plan_prompt(context, risk_register, agent.format_knowledge_context(test_plan_chunks))
            try:
                test_plan = clean_markdown_html(st.write_stream(
                    agent.ask_streaming(test_plan_prompt, system_prompt=TEST_PLAN_SYSTEM_PROMPT)
                ))
                test_plan_path = test_plan_generator.save(test_plan, context)
            except (StopException, RerunException):
                raise
            except Exception as exc:
                logger.error("Test Plan generation failed: %s", exc)
                st.error(f"❌ Test Plan generation failed: {exc}")
                test_plan, test_plan_path = "", None
            st.markdown("---")
            st.session_state.test_plan = test_plan
            st.session_state.test_plan_path = test_plan_path
            st.session_state.test_plan_sources = test_plan_sources
        else:
            test_plan = st.session_state.test_plan
        _render_stages()
```

- [ ] **Step 3: Wire the score-tile entrance animation**

`render_strategy()` currently has, right after the 4 tabs are created:

```python
    tab1, tab2, tab3, tab4 = st.tabs(["⚠️ Risk Register", "📊 Effort Estimation", "📋 Test Strategy", "📝 Test Plan"])

    project_name = st.session_state.dialogue.get_context().project_name
```

Replace with:

```python
    tab1, tab2, tab3, tab4 = st.tabs(["⚠️ Risk Register", "📊 Effort Estimation", "📋 Test Strategy", "📝 Test Plan"])

    project_name = st.session_state.dialogue.get_context().project_name
    _output_animate_class = " animate" if not st.session_state.get("output_intro_animated") else ""
    st.session_state.output_intro_animated = True
```

Inside `with tab1:`, currently:

```python
        risk_rows = parse_risk_matrix(st.session_state.risk_register)
        if risk_rows:
            st.markdown(risk_ledger_table_html(risk_rows), unsafe_allow_html=True)
            st.markdown("###")
```

Replace with:

```python
        risk_rows = parse_risk_matrix(st.session_state.risk_register)
        if risk_rows:
            st.markdown(
                f'<div class="output-tiles{_output_animate_class}">{risk_ledger_table_html(risk_rows)}</div>',
                unsafe_allow_html=True,
            )
            st.markdown("###")
```

Inside `with tab2:`, currently:

```python
        effort_data = st.session_state.get("effort_data")
        if effort_data is not None:
            st.markdown(
                signal_ledger_html(
                    "Confidence",
                    effort_data.confidence_score,
                    sub=f"{effort_data.confidence_level} confidence",
                ),
                unsafe_allow_html=True,
            )
            st.markdown("###")
```

Replace with:

```python
        effort_data = st.session_state.get("effort_data")
        if effort_data is not None:
            st.markdown(
                '<div class="output-tiles{}">{}</div>'.format(
                    _output_animate_class,
                    signal_ledger_html(
                        "Confidence",
                        effort_data.confidence_score,
                        sub=f"{effort_data.confidence_level} confidence",
                    ),
                ),
                unsafe_allow_html=True,
            )
            st.markdown("###")
```

- [ ] **Step 4: Write the app.py wiring regression tests**

Create `tests/test_app_output_screens.py`:

```python
"""Tests for src/app.py's Phase 3 output-screen wiring (render_strategy(),
render_doc_review()) -- see
docs/superpowers/specs/2026-08-17-output-screens-power-on-redesign-design.md."""
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
APP_SRC = REPO_ROOT / "src"
APP_PY = APP_SRC / "app.py"
sys.path.insert(0, str(APP_SRC))


def read_app_source() -> str:
    return APP_PY.read_text(encoding="utf-8")


def extract_function(source: str, fn_name: str) -> str:
    pattern = rf'\ndef {fn_name}\('
    match = re.search(pattern, source)
    assert match, f"Could not find 'def {fn_name}(' in app.py"
    start = match.start() + 1
    next_def = re.search(r'\ndef \w+\(', source[start + len(f"def {fn_name}("):])
    end = start + len(f"def {fn_name}(") + next_def.start() if next_def else len(source)
    return source[start:end]


def test_render_strategy_uses_the_new_style_builders():
    fn = extract_function(read_app_source(), "render_strategy")
    assert "build_output_eyebrow_html" in fn
    assert "build_content_polish_css" in fn
    assert "build_stage_sequence_html" in fn


def test_render_strategy_calls_render_stages_before_and_after_each_stage():
    fn = extract_function(read_app_source(), "render_strategy")
    # fn.count("_render_stages(") would also match the helper's own
    # `def _render_stages(active_key=None):` line. That line has
    # "active_key=None" between its parens, never empty parens, so counting
    # the exact "_render_stages()" (bare call) substring cannot collide
    # with it -- no special-casing needed.
    active_calls = fn.count("_render_stages(active_key=")
    bare_calls = fn.count("_render_stages()")
    assert active_calls == 4, f"Expected 4 'active_key=' calls (one per stage), found {active_calls}"
    assert bare_calls == 5, f"Expected 5 bare _render_stages() calls (1 initial + 1 per stage), found {bare_calls}"
    for key in ["risk_register", "effort_report", "strategy", "test_plan"]:
        assert f'_render_stages(active_key="{key}")' in fn


def test_render_strategy_sets_output_intro_animated():
    fn = extract_function(read_app_source(), "render_strategy")
    assert "st.session_state.output_intro_animated = True" in fn


def test_cleanup_blocks_do_not_clear_output_intro_animated():
    source = read_app_source()
    for fn_name in ["render_sidebar", "render_strategy"]:
        fn = extract_function(source, fn_name)
        assert '"output_intro_animated"' not in fn, \
            f"{fn_name}() must NOT clear output_intro_animated"
```

- [ ] **Step 5: Run the new and existing regression tests**

Run: `python -m pytest tests/test_app_output_screens.py tests/test_app_v03.py tests/test_app_stopexception.py tests/test_app_run_count.py -v`
Expected: all PASS.

- [ ] **Step 6: Run the full test suite**

Run: `python -m pytest tests/ -q`
Expected: PASS, no new failures versus the pre-Task-2 baseline. (`tests/test_live_contracts.py::test_openrouter_fallback` is a known flaky live-API test unrelated to this change — ignore it either way.)

- [ ] **Step 7: Lint and type-check**

Run: `ruff check src/app.py tests/test_app_output_screens.py`
Run: `mypy src/app.py`
Expected: both clean.

- [ ] **Step 8: Commit**

```bash
git add src/app.py tests/test_app_output_screens.py
git commit -m "feat: wire Phase 3 Power-On styling into render_strategy()"
```

---

### Task 3: Wire `output_screen_style.py` into `render_doc_review()`

**Files:**
- Modify: `src/app.py` (`render_doc_review()`, currently `app.py:1136-1335`)
- Modify: `tests/test_app_output_screens.py` (created in Task 2)

**Interfaces:**
- Consumes: `output_screen_style.build_output_eyebrow_html`, `build_content_polish_css`, `build_doc_review_input_tray_css` (Task 1), `theme.LIGHT_TOKENS`/`DARK_TOKENS` (already exist).

- [ ] **Step 1: Add the header eyebrow and content-polish CSS**

`render_doc_review()` currently starts:

```python
    MAX_RUNS_PER_SESSION = 3  # mirrors render_strategy()'s per-session cap — narrative is an LLM call

    st.markdown("## 📝 Review an Existing QA Document")
```

Replace with:

```python
    MAX_RUNS_PER_SESSION = 3  # mirrors render_strategy()'s per-session cap — narrative is an LLM call

    from output_screen_style import build_content_polish_css, build_output_eyebrow_html
    from theme import DARK_TOKENS, LIGHT_TOKENS

    _doc_review_tokens = DARK_TOKENS if st.context.theme.type == "dark" else LIGHT_TOKENS
    st.markdown(build_content_polish_css(_doc_review_tokens), unsafe_allow_html=True)
    st.markdown(build_output_eyebrow_html(_doc_review_tokens, "document review sequence"), unsafe_allow_html=True)
    st.markdown("## 📝 Review an Existing QA Document")
```

- [ ] **Step 2: Wrap the intake widgets in the input tray**

Currently:

```python
    if st.session_state.get("review_result") is None:
        label = st.selectbox(
            "Document type",
            options=[label for label, _ in _REVIEW_DOC_TYPE_OPTIONS],
            index=0,
            key="review_doc_type_select",
        )
        doc_type = dict(_REVIEW_DOC_TYPE_OPTIONS)[label]

        uploaded = st.file_uploader(
            "Upload a document (.md, .txt)", type=["md", "txt"], key="review_doc_uploader",
        )
        st.caption("...or paste the document text below")
        pasted = st.text_area(
            "Document text", key="review_doc_pasted_text", height=300, label_visibility="collapsed",
        )

        document_text = ""
```

Replace with:

```python
    if st.session_state.get("review_result") is None:
        from output_screen_style import build_doc_review_input_tray_css
        st.markdown(build_doc_review_input_tray_css(_doc_review_tokens), unsafe_allow_html=True)

        with st.container(key="doc-review-input"):
            label = st.selectbox(
                "Document type",
                options=[label for label, _ in _REVIEW_DOC_TYPE_OPTIONS],
                index=0,
                key="review_doc_type_select",
            )
            doc_type = dict(_REVIEW_DOC_TYPE_OPTIONS)[label]

            uploaded = st.file_uploader(
                "Upload a document (.md, .txt)", type=["md", "txt"], key="review_doc_uploader",
            )
            st.caption("...or paste the document text below")
            pasted = st.text_area(
                "Document text", key="review_doc_pasted_text", height=300, label_visibility="collapsed",
            )

        document_text = ""
```

Everything from `source_label = "Document"` onward through the end of that `if` branch (the two buttons, the `return`) stays exactly as-is, at its original (non-nested) indent.

- [ ] **Step 3: Wire the score-tile entrance animation**

Currently:

```python
    from ledger_components import signal_ledger_html

    st.markdown(f"**Detected document type:** `{result.doc_type}`")
    st.markdown(
        signal_ledger_html("Overall Score", result.overall_score, sub=f"{result.doc_type} · 6-dimension rubric"),
        unsafe_allow_html=True,
    )

    dim_cols = st.columns(len(result.dimension_scores))
```

Replace with:

```python
    from ledger_components import signal_ledger_html

    _doc_review_animate_class = " animate" if not st.session_state.get("doc_review_intro_animated") else ""
    st.session_state.doc_review_intro_animated = True

    st.markdown(f"**Detected document type:** `{result.doc_type}`")
    st.markdown(
        '<div class="output-tiles{}">{}</div>'.format(
            _doc_review_animate_class,
            signal_ledger_html("Overall Score", result.overall_score, sub=f"{result.doc_type} · 6-dimension rubric"),
        ),
        unsafe_allow_html=True,
    )

    dim_cols = st.columns(len(result.dimension_scores))
```

The `dim_cols` loop immediately below is **not modified** — see this plan's Global Constraints for why the per-dimension tiles stay unanimated.

- [ ] **Step 4: Extend the regression tests**

Add to `tests/test_app_output_screens.py` (created in Task 2):

```python
def test_render_doc_review_uses_the_new_style_builders():
    fn = extract_function(read_app_source(), "render_doc_review")
    assert "build_output_eyebrow_html" in fn
    assert "build_content_polish_css" in fn
    assert "build_doc_review_input_tray_css" in fn


def test_render_doc_review_wraps_intake_widgets_in_keyed_container():
    fn = extract_function(read_app_source(), "render_doc_review")
    assert 'st.container(key="doc-review-input")' in fn


def test_render_doc_review_sets_doc_review_intro_animated():
    fn = extract_function(read_app_source(), "render_doc_review")
    assert "st.session_state.doc_review_intro_animated = True" in fn


def test_doc_review_intro_animated_excluded_from_review_mode_state_keys():
    source = read_app_source()
    keys_block = re.search(r"REVIEW_MODE_STATE_KEYS = \[(.*?)\]", source, re.DOTALL)
    assert keys_block, "REVIEW_MODE_STATE_KEYS list not found"
    assert "doc_review_intro_animated" not in keys_block.group(1), \
        "doc_review_intro_animated must NOT be added to REVIEW_MODE_STATE_KEYS"
```

- [ ] **Step 5: Run the new and existing regression tests**

Run: `python -m pytest tests/test_app_output_screens.py tests/test_app_review_mode.py -v`
Expected: all PASS.

- [ ] **Step 6: Run the full test suite**

Run: `python -m pytest tests/ -q`
Expected: PASS, no new failures versus the pre-Task-3 baseline.

- [ ] **Step 7: Lint and type-check**

Run: `ruff check src/app.py tests/test_app_output_screens.py`
Run: `mypy src/app.py`
Expected: both clean.

- [ ] **Step 8: Commit**

```bash
git add src/app.py tests/test_app_output_screens.py
git commit -m "feat: wire Phase 3 Power-On styling into render_doc_review()"
```

---

### Task 4: Landing screen addendum — `build_landing_deliverables_html()`

**Files:**
- Modify: `src/landing_hero.py`
- Modify: `tests/test_landing_hero.py`
- Modify: `src/app.py` (`render_intro()`, currently `app.py:386-472`)

**Interfaces:**
- Produces: `build_landing_deliverables_html(tokens: dict) -> str` (added to `landing_hero.py`)
- Consumes: reuses `landing_hero.py`'s existing `.pom-card`/`.pom-cidx`/`.pom-ctitle`/`.pom-cbody` classes and `pom-card-in` keyframe (defined in `build_landing_hero_html()`, always rendered first on the same screen) — does not redefine them.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_landing_hero.py` (append after the existing tests, keep the existing `from landing_hero import build_landing_hero_html` import and add a second one):

```python
from landing_hero import build_landing_deliverables_html  # noqa: E402


def test_build_landing_deliverables_html_uses_the_given_tokens_not_a_hardcoded_theme():
    light_html = build_landing_deliverables_html(LIGHT_TOKENS)
    dark_html = build_landing_deliverables_html(DARK_TOKENS)
    assert LIGHT_TOKENS["ink"] in light_html
    assert DARK_TOKENS["ink"] not in light_html
    assert DARK_TOKENS["ink"] in dark_html
    assert LIGHT_TOKENS["ink"] not in dark_html


def test_build_landing_deliverables_html_contains_all_four_deliverable_titles():
    html = build_landing_deliverables_html(LIGHT_TOKENS)
    for title in ["Risk Register", "Effort Estimation", "Test Strategy", "Test Plan"]:
        assert title in html


def test_build_landing_deliverables_html_contains_all_four_stat_labels():
    html = build_landing_deliverables_html(LIGHT_TOKENS)
    for label in ["Time to results", "Standards", "Deliverables", "Cost"]:
        assert label in html


def test_build_landing_deliverables_html_does_not_redefine_the_pom_card_in_keyframe():
    # Regression guard: must reuse the pom-card-in keyframe from
    # build_landing_hero_html() (concatenated into the same document) rather
    # than redefining it -- a silent duplicate would be easy to miss since
    # CSS allows redeclaring the same @keyframes name without error.
    html = build_landing_deliverables_html(LIGHT_TOKENS)
    assert "@keyframes pom-card-in" not in html


def test_build_landing_deliverables_html_delay_rules_are_scoped_under_pom_deliverables():
    # Regression guard: nth-child delay overrides must be scoped under
    # .pom-deliverables, never a bare ".pom-card:nth-child(...)" rule, which
    # would also match (and fight with) the "How it works" cards' own delay
    # rules defined in build_landing_hero_html().
    html = build_landing_deliverables_html(LIGHT_TOKENS)
    for line in html.splitlines():
        if ".pom-card:nth-child" in line:
            assert ".pom-deliverables" in line, \
                f"Found a bare (unscoped) .pom-card:nth-child rule: {line!r}"


def test_build_landing_deliverables_html_zeroes_animation_delay_for_reduced_motion():
    html = build_landing_deliverables_html(LIGHT_TOKENS)
    assert "@media (prefers-reduced-motion: reduce)" in html
    assert "animation-delay: 0s !important" in html
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_landing_hero.py -v`
Expected: 6 new FAILs — `ImportError: cannot import name 'build_landing_deliverables_html'`

- [ ] **Step 3: Write the implementation**

Append to `src/landing_hero.py` (after `build_landing_hero_html()`):

```python
def build_landing_deliverables_html(tokens: dict) -> str:
    """Pure function: token dict -> the "What you get in ~2 minutes"
    deliverable cards + stat tiles HTML block. A Phase-3 addendum (folded
    into the Phase 3 spec at the user's request, though it's landing-screen
    content) finishing what Phase 1 left native Streamlit. Continues
    build_landing_hero_html()'s "How it works" cards' visual language and
    animation-delay cadence (which ends at 2.0s) -- reuses the existing
    .pom-card/.pom-cidx/.pom-ctitle/.pom-cbody classes and pom-card-in
    keyframe (defined in that function's <style> block, always rendered
    first on the same screen by render_intro()) rather than redefining
    them. Directly unit-testable -- see tests/test_landing_hero.py."""
    deliverables = [
        ("⚠️", "Risk Register", "Prioritized risks with likelihood, impact &amp; mitigation — before a single line of code is written."),
        ("📊", "Effort Estimation", "PERT-based timeline with team capacity analysis and a confidence score (0–100)."),
        ("📋", "Test Strategy", "ISTQB-aligned approach tailored to your stack, methodology, and compliance requirements."),
        ("📝", "Test Plan", "IEEE 829-aligned plan with test items, entry/exit criteria, schedule, and AI tool oversight."),
    ]
    stats = [
        ("Time to results", "~2 min", "vs. hours of manual work"),
        ("Standards", "ISTQB · OWASP · ISO", "7,100+ knowledge vectors"),
        ("Deliverables", "4 documents", "Risk · Effort · Strategy · Plan"),
        ("Cost", "Free", "No sign-up required"),
    ]
    deliverable_cards = "".join(
        f'<div class="pom-card"><div class="pom-cidx">{icon}</div>'
        f'<div class="pom-ctitle">{title}</div><div class="pom-cbody">{body}</div></div>'
        for icon, title, body in deliverables
    )
    deliverable_delay_rules = "\n".join(
        f".pom-deliverables .pom-card:nth-child({i}) {{ animation-delay: {2.15 + (i - 1) * 0.15:.2f}s; }}"
        for i in range(1, len(deliverables) + 1)
    )
    stat_tiles = "".join(
        f'<div class="pom-stat"><div class="pom-slabel">{label}</div>'
        f'<div class="pom-svalue">{value}</div><div class="pom-ssub">{sub}</div></div>'
        for label, value, sub in stats
    )
    stat_delay_rules = "\n".join(
        f".pom-stats .pom-stat:nth-child({i}) {{ animation-delay: {2.85 + (i - 1) * 0.1:.2f}s; }}"
        for i in range(1, len(stats) + 1)
    )
    return f"""
<style>
.pom-deliverables {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 0.9rem; margin-bottom: 1.6rem; }}
@media (max-width: 640px) {{ .pom-deliverables {{ grid-template-columns: 1fr; }} }}
{deliverable_delay_rules}
.pom-stats {{ display: flex; gap: 1.4rem; flex-wrap: wrap; }}
.pom-stat {{ opacity: 0; animation: pom-card-in 0.5s ease-out both; }}
{stat_delay_rules}
.pom-stat .pom-slabel {{ font-family: 'Plex Mono', monospace; font-size: 0.62rem; letter-spacing: 0.06em; text-transform: uppercase; color: {tokens['ink_dim']}; margin-bottom: 0.25rem; }}
.pom-stat .pom-svalue {{ font-family: 'Plex Mono', monospace; font-size: 1.1rem; font-weight: 500; color: {tokens['ink']}; }}
.pom-stat .pom-ssub {{ font-family: 'Plex Sans', sans-serif; font-size: 0.72rem; color: {tokens['ink_dim']}; }}
@media (prefers-reduced-motion: reduce) {{
  .pom-deliverables .pom-card, .pom-stat {{
    animation-delay: 0s !important;
  }}
}}
</style>
<div class="pom-deliverables">{deliverable_cards}</div>
<div class="pom-stats">{stat_tiles}</div>
"""
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_landing_hero.py -v`
Expected: PASS (13 tests: 7 existing + 6 new)

- [ ] **Step 5: Wire it into `render_intro()`**

`render_intro()` currently has, right after the hero call:

```python
    st.markdown("---")

    st.markdown("#### 🎯 What you get in ~2 minutes")
    d1, d2, d3 = st.columns(3)
    with d1:
        st.success(
            "⚠️ **Risk Register**\n\n"
            "Prioritized risks with likelihood, impact & mitigation — before a single line of code is written."
        )
    with d2:
        st.success(
            "📊 **Effort Estimation**\n\n"
            "PERT-based timeline with team capacity analysis and a confidence score (0–100)."
        )
    with d3:
        st.success(
            "📋 **Test Strategy**\n\n"
            "ISTQB-aligned approach tailored to your stack, methodology, and compliance requirements."
        )
    d4, = st.columns(1)
    with d4:
        st.success(
            "📝 **Test Plan**\n\n"
            "IEEE 829-aligned plan with test items, entry/exit criteria, schedule, and AI tool oversight."
        )

    e1, e2, e3, e4 = st.columns(4)
    e1.metric("⏱️ Time to results", "~2 min", "vs. hours of manual work")
    e2.metric("📚 Standards", "ISTQB · OWASP · ISO", "7,100+ knowledge vectors")
    e3.metric("📄 Deliverables", "4 documents", "Risk · Effort · Strategy · Plan")
    e4.metric("💰 Cost", "Free", "No sign-up required")

    st.markdown("---")
```

Replace with:

```python
    st.markdown("---")

    from landing_hero import build_landing_deliverables_html
    st.markdown(build_landing_deliverables_html(_hero_tokens), unsafe_allow_html=True)

    st.markdown("---")
```

Everything before (`build_landing_hero_html()`) and after (the `st.info()` "Best used at project kick-off" block, both expanders, the two navigation buttons) is **not modified**.

- [ ] **Step 6: Run the existing regression guards**

Run: `python -m pytest tests/test_app_review_mode.py -k test_intro_has_review_document_entry_point -v`
Expected: PASS — confirms the untouched button code below this change still satisfies the existing source-inspection test.

- [ ] **Step 7: Run the full test suite**

Run: `python -m pytest tests/ -q`
Expected: PASS, same pass count as before this task plus the 6 new `test_landing_hero.py` tests.

- [ ] **Step 8: Lint and type-check**

Run: `ruff check src/app.py src/landing_hero.py tests/test_landing_hero.py`
Run: `mypy src/app.py src/landing_hero.py`
Expected: both clean.

- [ ] **Step 9: Commit**

```bash
git add src/app.py src/landing_hero.py tests/test_landing_hero.py
git commit -m "feat: style the landing screen's 'What you get' section (Phase 3 addendum)"
```

---

### Task 5: Manual Playwright visual verification

**Files:**
- Create: `scripts/verify_output_screens_visual.py`

**Interfaces:**
- Consumes: a locally running `streamlit run src/app.py` instance at `http://localhost:8501` (started manually by the implementer, real `.env` API keys required — this script runs one real end-to-end generation, unlike Phases 1-2's scripts, which needed no live API calls).

- [ ] **Step 1: Write the verification script**

Create `scripts/verify_output_screens_visual.py`:

```python
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

from playwright.sync_api import sync_playwright

URL = "http://localhost:8501"


def main() -> int:
    out_dir = Path(tempfile.mkdtemp(prefix="qai_output_screens_visual_"))

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 1400})

        # ── 1. Landing addendum ──────────────────────────────────────────
        page.goto(URL, timeout=30000, wait_until="networkidle")
        # Last stat tile's animation-delay is 3.15s (4 stats x 0.1s steps from
        # a 2.85s base) + its 0.5s duration = finishes at 3.65s -- pad well
        # past that so the screenshot isn't taken mid-animation.
        page.wait_for_timeout(4200)
        page.screenshot(path=str(out_dir / "landing_deliverables.png"), full_page=True)

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
            page.screenshot(path=str(out_dir / "strategy_stage_active.png"), full_page=True)
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
        page.screenshot(path=str(out_dir / "strategy_tab1_risk.png"), full_page=True)

        page.get_by_role("tab", name="📊 Effort Estimation").click(timeout=10000)
        page.wait_for_timeout(300)
        page.screenshot(path=str(out_dir / "strategy_tab2_effort.png"), full_page=True)

        # Hover check: a download button's border should change to the accent color.
        dl_button = page.locator('[data-testid="stDownloadButton"] button').first
        dl_button.hover()
        page.wait_for_timeout(200)
        hover_border_color = dl_button.evaluate("el => getComputedStyle(el).borderColor")
        print(f"Download button border color on hover (expect the accent color): {hover_border_color}")

        browser.close()

        # ── 3. render_doc_review(): deterministic step only (no LLM call) ─
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 1400})
        page.goto(URL, timeout=30000, wait_until="networkidle")
        page.wait_for_timeout(1000)
        page.get_by_role("button", name="Review an existing QA document instead").click(timeout=10000)
        page.wait_for_selector(".st-key-doc-review-input", timeout=15000)
        page.screenshot(path=str(out_dir / "doc_review_input_tray.png"), full_page=True)

        page.locator("textarea").last.fill(
            "# Test Plan\n\nScope: checkout flow.\nEntry criteria: build passes CI.\n"
            "Exit criteria: 0 open critical defects.\n\n## Test Cases\n"
            "1. Verify successful checkout with valid payment.\n"
            "2. Verify checkout rejects an expired card.\n" * 5
        )
        page.get_by_role("button", name="🔍 Review Document").click(timeout=10000)
        page.wait_for_selector(".output-tiles", timeout=15000)
        page.wait_for_timeout(500)  # let the entrance finish
        page.screenshot(path=str(out_dir / "doc_review_results.png"), full_page=True)
        browser.close()

        # ── 4. Reduced-motion pass (landing + doc-review only — cheap to
        #        re-run; a second full real generation for this pass would
        #        double the API cost for a check the pulse/entrance CSS
        #        rules already cover deterministically) ────────────────
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 1400}, reduced_motion="reduce")
        page.goto(URL, timeout=30000, wait_until="networkidle")
        page.wait_for_timeout(300)
        page.screenshot(path=str(out_dir / "landing_deliverables_reduced_motion.png"), full_page=True)
        page.get_by_role("button", name="Review an existing QA document instead").click(timeout=10000)
        page.wait_for_selector(".st-key-doc-review-input", timeout=15000)
        page.locator("textarea").last.fill("# Test Plan\n\nScope: checkout flow.\n" * 20)
        page.get_by_role("button", name="🔍 Review Document").click(timeout=10000)
        page.wait_for_selector(".output-tiles", timeout=15000)
        page.wait_for_timeout(150)
        page.screenshot(path=str(out_dir / "doc_review_results_reduced_motion.png"), full_page=True)
        browser.close()

    print(f"Screenshots saved to: {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run it against the local app**

Run in one terminal: `streamlit run src/app.py`
Run in another: `python scripts/verify_output_screens_visual.py`
Expected: no unhandled exceptions; the final stage-classes print shows all 4 `"stage-item done"`; the active-tab-color and hover-border-color prints both show the accent hex value (not a default black/red); 9 screenshots produced (8 always, or 9 if the mid-generation poll caught an active stage).

- [ ] **Step 3: Visually inspect all screenshots**

Open each PNG from the printed `out_dir` path. Confirm: `landing_deliverables.png` shows 4 deliverable cards + 4 stat tiles, none stuck at `opacity: 0`; `strategy_stage_active.png` (if produced) shows one stage with a highlighted/pulsing dot mid-sequence; `strategy_tab1_risk.png`/`strategy_tab2_effort.png` show all 4 stage chips marked done, a themed (mono, accent-underlined) active tab, and the Risk Ledger table / Confidence tile not stuck invisible; `doc_review_input_tray.png` shows the intake widgets inside a bordered/backgrounded tray matching the dialogue's `.ledger-card` look; `doc_review_results.png` shows the Overall Score tile visible; both `*_reduced_motion.png` screenshots show the same content fully visible with no mid-animation artifacts. Additionally, place a fresh screenshot of any existing Signal Ledger tile (e.g. `strategy_tab2_effort.png`'s Confidence tile) side by side with `strategy_tab1_risk.png`'s stage-sequence chips and the landing screen's stat tiles — per the spec's "Signal Ledger / Risk Ledger re-evaluation," confirm they read as one visual system (same mono labels, same accent/pass/hold/fail coloring, same border/spacing rhythm). If they don't, that re-evaluation's "no migration needed" conclusion was wrong — stop and flag it rather than proceeding, per the spec's own instruction to reopen that decision within this implementation pass if a real mismatch turns up here.

If anything looks wrong, fix the relevant Task (1-4) and re-run this task from Step 2 — do not proceed to Step 4 until every screenshot looks correct.

- [ ] **Step 4: Lint and commit**

Run: `ruff check scripts/verify_output_screens_visual.py`
Expected: clean.

```bash
git add scripts/verify_output_screens_visual.py
git commit -m "test: add manual Playwright visual check for the Phase 3 output-screen redesign"
```
