# Interactive Flow Redesign — Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Apply the "Power-On Sequence" visual language (established in Phase 1, `landing_hero.py`) to the dialogue, review, and sidebar screens — a themed progress bar and `.ledger-card` hover on the dialogue, styled read-only summary tiles with a one-shot entrance on the review screen, and hover-state polish on the sidebar. No new colors, no new fonts, `theme.py` untouched.

**Architecture:** One new pure-function module, `src/interactive_flow_style.py`, with three functions (one per screen), following `landing_hero.py`'s pattern exactly — no Streamlit dependency, unit-testable without a runtime. `app.py`'s `render_dialogue()`, `render_review()`, and `render_sidebar()` each call their respective function and render the result via `st.markdown(html, unsafe_allow_html=True)`.

**Tech Stack:** Python, Streamlit, plain CSS (transitions + one gated keyframe animation), pytest, Playwright (manual visual verification, not wired into CI, following Phase 1's `scripts/verify_landing_visual.py` precedent).

## Global Constraints

- `theme.py` is **not modified** — no new color tokens, no new fonts, no new rules added to `build_css()`. Per `docs/superpowers/specs/2026-08-06-interactive-flow-power-on-redesign-design.md`.
- The new `.ledger-card:hover` rule lives in `interactive_flow_style.py`'s own `<style>` block, not in `theme.py` — this is safe because it's an additive pseudo-class selector that composes with `.ledger-card`'s existing base rule in `theme.py` regardless of stylesheet load order (confirmed during design: not an override, a different selector).
- **No per-card entrance animation on the dialogue screen, and no entrance animation anywhere in the sidebar** — both rerun far more often than once per visit (dialogue on template changes, sidebar on every interaction anywhere in the app), so a mount-triggered animation there would replay distractingly rather than read as "power-on."
- The review screen's entrance animation **must** be gated behind `st.session_state.review_intro_animated` (set `True` after first render) so editing the "Additional context" field — which reruns the script — does not replay it. This is the same idiom `app.py` already uses for `mcp_announcement_seen`.
- `review_intro_animated` must **not** be cleared by either the "Start Over" (`render_sidebar()`) or "Generate Another Strategy" (`render_strategy()`) cleanup blocks — same precedent as `mcp_announcement_seen`. (Re-animating on an actual restart would be harmless, but excluding it keeps the pattern consistent with the existing precedent and needs no new code in the cleanup blocks — simply never add the key to either list.)
- All user-supplied text rendered by `build_review_summary_html()` (project name, tech stack, etc.) **must** be HTML-escaped — these are user-typed fields flowing into `unsafe_allow_html=True`, the same XSS concern `ledger_components.py` already documents and handles via `html.escape()`.
- `interactive_flow_style.py` is a Streamlit-app-only module, like `theme.py`/`ledger_components.py`/`landing_hero.py` — it must **not** be added to `pyproject.toml`'s `[tool.setuptools] py-modules` list (that whitelist is for the separate `qai-consultant-mcp` package).
- Must not break the existing regression tests that source-inspect these functions: `tests/test_app_v03.py` (additional-context widgets, cleanup blocks), `tests/test_app_results_upload.py` (`render_review()`'s results-upload expander — untouched code below the summary-tiles change).
- No Phase 3 (output-screen) changes. No new Playwright POM test suite (separate work stream).

---

### Task 1: `interactive_flow_style.py` — three pure HTML/CSS builders + unit tests

**Files:**
- Create: `src/interactive_flow_style.py`
- Create: `tests/test_interactive_flow_style.py`

**Interfaces:**
- Produces: `build_dialogue_header_html(tokens: dict, answered: int, total: int) -> str`
- Produces: `build_review_summary_html(tokens: dict, context, animate: bool) -> str` — `context` is duck-typed (any object exposing the 10 attributes read below; avoids importing `dialogue.ProjectContext` into this Streamlit-free module, matching the module's no-heavy-imports design)
- Produces: `build_sidebar_polish_css(tokens: dict) -> str`
- Task 2 imports all three functions by name.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_interactive_flow_style.py`:

```python
"""Tests for src/interactive_flow_style.py -- Phase 2 interactive-flow
styling (dialogue, review, sidebar). See
docs/superpowers/specs/2026-08-06-interactive-flow-power-on-redesign-design.md."""
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from theme import LIGHT_TOKENS, DARK_TOKENS  # noqa: E402
from interactive_flow_style import (  # noqa: E402
    build_dialogue_header_html,
    build_review_summary_html,
    build_sidebar_polish_css,
)


@dataclass
class _FakeContext:
    project_name: str = "ShopFlow"
    project_type: str = "Web app"
    tech_stack: str = "React + Django"
    methodology: str = "Scrum"
    timeline: str = "3 months"
    team_qa_size: str = "2"
    team_dev_size: str = "6"
    known_risks: str = "Payment integration"
    existing_automation: str = "Selenium suite"
    compliance_requirements: str = "GDPR"


def test_dialogue_header_uses_the_given_tokens_not_a_hardcoded_theme():
    light = build_dialogue_header_html(LIGHT_TOKENS, 3, 11)
    dark = build_dialogue_header_html(DARK_TOKENS, 3, 11)
    assert LIGHT_TOKENS["accent"] in light
    assert DARK_TOKENS["accent"] not in light
    assert DARK_TOKENS["accent"] in dark
    assert LIGHT_TOKENS["accent"] not in dark


def test_dialogue_header_computes_progress_percentage():
    html = build_dialogue_header_html(LIGHT_TOKENS, 3, 12)
    assert "width: 25%;" in html


def test_dialogue_header_handles_zero_total_without_dividing_by_zero():
    html = build_dialogue_header_html(LIGHT_TOKENS, 0, 0)
    assert "width: 0%;" in html


def test_dialogue_header_adds_ledger_card_hover_without_touching_base_rule():
    html = build_dialogue_header_html(LIGHT_TOKENS, 1, 11)
    assert ".ledger-card:hover" in html


def test_review_summary_escapes_html_in_user_supplied_fields():
    context = _FakeContext(project_name="<script>alert(1)</script>")
    html = build_review_summary_html(LIGHT_TOKENS, context, animate=False)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_review_summary_contains_all_ten_fields():
    html = build_review_summary_html(LIGHT_TOKENS, _FakeContext(), animate=False)
    for value in ["ShopFlow", "React + Django", "Scrum", "GDPR"]:
        assert value in html


def test_review_summary_animate_flag_controls_the_css_class():
    animated = build_review_summary_html(LIGHT_TOKENS, _FakeContext(), animate=True)
    static = build_review_summary_html(LIGHT_TOKENS, _FakeContext(), animate=False)
    assert 'class="review-grid animate"' in animated
    assert 'class="review-grid animate"' not in static
    assert 'class="review-grid"' in static


def test_review_summary_zeroes_animation_delay_for_reduced_motion():
    html = build_review_summary_html(LIGHT_TOKENS, _FakeContext(), animate=True)
    assert "@media (prefers-reduced-motion: reduce)" in html
    assert "animation-delay: 0s !important" in html


def test_sidebar_polish_css_scopes_to_sidebar_testid():
    html = build_sidebar_polish_css(LIGHT_TOKENS)
    assert '[data-testid="stSidebar"]' in html
    assert LIGHT_TOKENS["accent"] in html
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_interactive_flow_style.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'interactive_flow_style'`

- [ ] **Step 3: Write the implementation**

Create `src/interactive_flow_style.py`:

```python
"""
QAI Consultant -- Phase 2 interactive-flow styling ("Power-On Sequence",
continuing Phase 1's landing_hero.py -- see
docs/superpowers/specs/2026-08-06-interactive-flow-power-on-redesign-design.md).

Three pure functions, one per screen (dialogue, review, sidebar), each
building a self-contained HTML+CSS string. No Streamlit dependency --
callers pass the app.py-derived tokens dict (theme.LIGHT_TOKENS or
theme.DARK_TOKENS) and render the result via
st.markdown(html, unsafe_allow_html=True), same as landing_hero.py and
ledger_components.py.

theme.py is NOT modified by this module. .ledger-card's base rule stays
there untouched; the :hover rule added here composes with it safely
regardless of <style> tag load order (an additive pseudo-class selector,
not an override). All CSS here is scoped to its own class names
(dialogue-*, review-*) plus the one .ledger-card:hover addition, and
lives in this module's own <style> blocks -- never added to theme.py's
build_css().

Unlike the landing screen (rendered once per session in the common
case), the dialogue and review screens rerun on user interaction
(template selection, "Additional context" edits). Mount-triggered CSS
keyframe animations would replay every time, which is why:
- the dialogue screen gets NO entrance animation at all (only a CSS
  *transition* on the progress bar's width, which is expected to
  re-fire on every value change -- that's what makes a progress bar
  feel alive, not a bug);
- the review screen's one-shot entrance is controlled entirely by the
  caller-supplied `animate` flag, which app.py derives from a
  session_state "seen" flag (the same idiom already used for
  mcp_announcement_seen);
- the sidebar gets no entrance animation at all -- it persists across
  every screen and rerun in the app.
"""
import html as _html


def build_dialogue_header_html(tokens: dict, answered: int, total: int) -> str:
    """Pure function: token dict + progress counts -> dialogue header HTML
    (eyebrow label + animated-width progress bar) plus the .ledger-card
    hover rule. Directly unit-testable -- see
    tests/test_interactive_flow_style.py."""
    pct = round((answered / total) * 100) if total else 0
    return f"""
<style>
.ledger-card:hover {{ border-color: {tokens['accent']}; box-shadow: 0 4px 14px rgba(0,0,0,0.08); transform: translateY(-2px); transition: transform 0.2s ease-out, box-shadow 0.2s ease-out, border-color 0.2s ease-out; }}
.dialogue-eyebrow {{ font-family: 'Plex Mono', monospace; font-size: 0.7rem; letter-spacing: 0.06em; text-transform: uppercase; color: {tokens['ink_dim']}; margin-bottom: 0.4rem; }}
.dialogue-progress-track {{ height: 6px; background: {tokens['surface_2']}; border-radius: 3px; overflow: hidden; margin: 0.6rem 0 1.2rem; }}
.dialogue-progress-fill {{ height: 100%; background: {tokens['accent']}; transition: width 0.4s ease-out; }}
</style>
<div class="dialogue-eyebrow">&gt; project discovery sequence: {answered}/{total} instruments calibrated</div>
<div class="dialogue-progress-track"><div class="dialogue-progress-fill" style="width: {pct}%;"></div></div>
"""


def build_review_summary_html(tokens: dict, context, animate: bool) -> str:
    """Pure function: token dict + a duck-typed project-context object
    (any object exposing project_name, project_type, tech_stack,
    methodology, timeline, team_qa_size, team_dev_size, known_risks,
    existing_automation, compliance_requirements) + whether to play the
    one-shot entrance -> review summary tiles HTML. All field values are
    HTML-escaped (user-supplied text, same XSS concern
    ledger_components.py documents)."""
    fields = [
        ("Project Name", context.project_name),
        ("Project Type", context.project_type),
        ("Tech Stack", context.tech_stack),
        ("Methodology", context.methodology),
        ("Timeline", context.timeline),
        ("QA Team Size", context.team_qa_size),
        ("Dev Team Size", context.team_dev_size),
        ("Known Risks", context.known_risks),
        ("Existing Automation", context.existing_automation),
        ("Compliance", context.compliance_requirements),
    ]
    animate_class = " animate" if animate else ""
    delay_rules = "\n".join(
        f".review-grid.animate .review-tile:nth-child({i}) {{ animation-delay: {i * 0.05:.2f}s; }}"
        for i in range(1, len(fields) + 1)
    )
    tiles = "".join(
        f'<div class="review-tile"><div class="rt-label">{_html.escape(label)}</div>'
        f'<div class="rt-value">{_html.escape(value)}</div></div>'
        for label, value in fields
    )
    return f"""
<style>
.review-grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 0.7rem; margin-bottom: 1rem; }}
.review-tile {{ background: {tokens['surface']}; border: 1px solid {tokens['line']}; border-radius: 8px; padding: 0.8rem 1rem; }}
.review-tile .rt-label {{ font-family: 'Plex Mono', monospace; font-size: 0.62rem; letter-spacing: 0.06em; text-transform: uppercase; color: {tokens['ink_dim']}; margin-bottom: 0.3rem; }}
.review-tile .rt-value {{ font-family: 'Plex Sans', sans-serif; font-size: 0.92rem; color: {tokens['ink']}; word-break: break-word; }}
@keyframes review-tile-in {{ from {{ opacity: 0; transform: translateY(8px); }} to {{ opacity: 1; transform: translateY(0); }} }}
.review-grid.animate .review-tile {{ opacity: 0; animation: review-tile-in 0.4s ease-out forwards; }}
{delay_rules}
@media (prefers-reduced-motion: reduce) {{
    .review-grid.animate .review-tile {{ animation-delay: 0s !important; }}
}}
</style>
<div class="review-grid{animate_class}">{tiles}</div>
"""


def build_sidebar_polish_css(tokens: dict) -> str:
    """Pure function: token dict -> sidebar hover-state CSS only -- no
    entrance animations, since the sidebar persists across every screen
    and rerun in the app."""
    return f"""
<style>
[data-testid="stSidebar"] button:hover {{ border-color: {tokens['accent']}; color: {tokens['accent']}; transition: border-color 0.15s ease-out, color 0.15s ease-out; }}
[data-testid="stSidebar"] [data-testid="stExpander"] summary:hover {{ color: {tokens['accent']}; transition: color 0.15s ease-out; }}
</style>
"""
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_interactive_flow_style.py -v`
Expected: PASS (9 tests)

- [ ] **Step 5: Lint and type-check**

Run: `ruff check src/interactive_flow_style.py tests/test_interactive_flow_style.py`
Run: `mypy src/interactive_flow_style.py`
Expected: both clean.

- [ ] **Step 6: Commit**

```bash
git add src/interactive_flow_style.py tests/test_interactive_flow_style.py
git commit -m "feat: add interactive_flow_style.py -- Phase 2 dialogue/review/sidebar builders"
```

---

### Task 2: Wire the three builders into `render_dialogue()`, `render_review()`, `render_sidebar()`

**Files:**
- Modify: `src/app.py` (three call sites — `render_dialogue()`, `render_review()`, `render_sidebar()`)
- Modify: `tests/test_app_mcp_banner.py` OR create `tests/test_app_interactive_flow.py` (regression test for the `review_intro_animated` cleanup exclusion — see Step 4)

**Interfaces:**
- Consumes: `interactive_flow_style.build_dialogue_header_html`, `build_review_summary_html`, `build_sidebar_polish_css` (Task 1), `theme.LIGHT_TOKENS` / `theme.DARK_TOKENS` (already exist).

- [ ] **Step 1: Wire `render_dialogue()`**

In `src/app.py`, `render_dialogue()` currently starts with:

```python
def render_dialogue():
    st.markdown("## 📋 Project Discovery")
    st.markdown("Answer the questions below to help QAI understand your project.")
    st.markdown("---")

    total = len(QUESTIONS)
    answered = sum(1 for v in st.session_state.answers.values() if v and v.strip())
    progress = answered / total
    st.progress(progress, text=f"Progress: {answered}/{total} questions answered")
    st.markdown("###")
```

Replace the `progress = ...` / `st.progress(...)` lines with:

```python
def render_dialogue():
    st.markdown("## 📋 Project Discovery")
    st.markdown("Answer the questions below to help QAI understand your project.")
    st.markdown("---")

    total = len(QUESTIONS)
    answered = sum(1 for v in st.session_state.answers.values() if v and v.strip())

    from interactive_flow_style import build_dialogue_header_html
    from theme import DARK_TOKENS, LIGHT_TOKENS

    _dialogue_tokens = DARK_TOKENS if st.context.theme.type == "dark" else LIGHT_TOKENS
    st.markdown(build_dialogue_header_html(_dialogue_tokens, answered, total), unsafe_allow_html=True)
    st.markdown("###")
```

Everything below (the template selector, the `st.form("dialogue_form")` block, submission handling) is **not modified**.

- [ ] **Step 2: Wire `render_review()`**

`render_review()` currently has, right after `context = st.session_state.dialogue.get_context()`:

```python
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Project Name**")
        st.code(context.project_name)
        st.markdown("**Project Type**")
        st.code(context.project_type)
        st.markdown("**Tech Stack**")
        st.code(context.tech_stack)
        st.markdown("**Methodology**")
        st.code(context.methodology)
        st.markdown("**Timeline**")
        st.code(context.timeline)

    with col2:
        st.markdown("**QA Team Size**")
        st.code(context.team_qa_size)
        st.markdown("**Dev Team Size**")
        st.code(context.team_dev_size)
        st.markdown("**Known Risks**")
        st.code(context.known_risks)
        st.markdown("**Existing Automation**")
        st.code(context.existing_automation)
        st.markdown("**Compliance**")
        st.code(context.compliance_requirements)
```

Replace that entire block (both columns) with:

```python
    from interactive_flow_style import build_review_summary_html
    from theme import DARK_TOKENS, LIGHT_TOKENS

    _review_tokens = DARK_TOKENS if st.context.theme.type == "dark" else LIGHT_TOKENS
    _animate = not st.session_state.get("review_intro_animated")
    st.markdown(
        build_review_summary_html(_review_tokens, context, animate=_animate),
        unsafe_allow_html=True,
    )
    st.session_state.review_intro_animated = True
```

Everything from `st.markdown("**Project Description**")` onward (project description, additional-context text area, results-upload expander, navigation buttons) is **not modified**.

- [ ] **Step 3: Wire `render_sidebar()`**

`render_sidebar()` currently starts:

```python
def render_sidebar():
    with st.sidebar:
        st.markdown("## 🧪 QAI Consultant")
```

Add the CSS injection as the first line inside the `with st.sidebar:` block:

```python
def render_sidebar():
    with st.sidebar:
        from interactive_flow_style import build_sidebar_polish_css
        from theme import DARK_TOKENS, LIGHT_TOKENS

        _sidebar_tokens = DARK_TOKENS if st.context.theme.type == "dark" else LIGHT_TOKENS
        st.markdown(build_sidebar_polish_css(_sidebar_tokens), unsafe_allow_html=True)

        st.markdown("## 🧪 QAI Consultant")
```

Everything else in `render_sidebar()` (including the "Start Over" cleanup block) is **not modified** — `review_intro_animated` is deliberately never added to that cleanup list.

- [ ] **Step 4: Add the cleanup-exclusion regression test**

Create `tests/test_app_interactive_flow.py`:

```python
"""Tests for src/app.py's Phase 2 interactive-flow wiring (dialogue,
review, sidebar) -- see
docs/superpowers/specs/2026-08-06-interactive-flow-power-on-redesign-design.md."""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
APP_SRC = REPO_ROOT / "src"
APP_PY = APP_SRC / "app.py"
sys.path.insert(0, str(APP_SRC))


def read_app_source() -> str:
    return APP_PY.read_text(encoding="utf-8")


def extract_function(source: str, fn_name: str) -> str:
    """Return the source lines of a top-level function (same helper used
    across the app.py test suite, e.g. tests/test_app_mcp_banner.py)."""
    import re
    pattern = rf'\ndef {fn_name}\('
    match = re.search(pattern, source)
    assert match, f"Could not find 'def {fn_name}(' in app.py"
    start = match.start() + 1
    next_def = re.search(r'\ndef \w+\(', source[start + len(f"def {fn_name}("):])
    end = start + len(f"def {fn_name}(") + next_def.start() if next_def else len(source)
    return source[start:end]


def test_dialogue_uses_the_new_header_builder():
    fn = extract_function(read_app_source(), "render_dialogue")
    assert "build_dialogue_header_html" in fn
    assert "st.progress(" not in fn, \
        "render_dialogue() should no longer call the native st.progress()"


def test_review_uses_the_new_summary_builder_and_sets_the_seen_flag():
    fn = extract_function(read_app_source(), "render_review")
    assert "build_review_summary_html" in fn
    assert "st.session_state.review_intro_animated = True" in fn
    assert "st.code(context.project_name)" not in fn, \
        "render_review() should no longer render the old plain st.code() summary"


def test_sidebar_uses_the_new_polish_css():
    fn = extract_function(read_app_source(), "render_sidebar")
    assert "build_sidebar_polish_css" in fn


def test_cleanup_blocks_do_not_clear_review_intro_animated():
    source = read_app_source()
    for fn_name in ["render_sidebar", "render_strategy"]:
        fn = extract_function(source, fn_name)
        assert '"review_intro_animated"' not in fn, \
            f"{fn_name}() must NOT clear review_intro_animated"
```

- [ ] **Step 5: Run the new and existing regression tests**

Run: `python -m pytest tests/test_app_interactive_flow.py tests/test_app_v03.py tests/test_app_results_upload.py tests/test_app_mcp_banner.py -v`
Expected: all PASS.

- [ ] **Step 6: Run the full test suite**

Run: `python -m pytest tests/ -q`
Expected: PASS, no new failures versus the pre-Phase-2 baseline. (`tests/test_live_contracts.py::test_openrouter_fallback` is a known flaky live-API test unrelated to this change — ignore it either way.)

- [ ] **Step 7: Lint and type-check**

Run: `ruff check src/app.py tests/test_app_interactive_flow.py`
Run: `mypy src/app.py`
Expected: both clean.

- [ ] **Step 8: Commit**

```bash
git add src/app.py tests/test_app_interactive_flow.py
git commit -m "feat: wire Phase 2 Power-On styling into dialogue/review/sidebar"
```

---

### Task 3: Manual Playwright visual verification

**Files:**
- Create: `scripts/verify_interactive_flow_visual.py`

**Interfaces:**
- Consumes: a locally running `streamlit run src/app.py` instance at `http://localhost:8501` (started manually by the implementer, not by this script) — same convention as Phase 1's `scripts/verify_landing_visual.py`.

- [ ] **Step 1: Write the verification script**

Create `scripts/verify_interactive_flow_visual.py`:

```python
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


def main() -> int:
    out_dir = Path(tempfile.mkdtemp(prefix="qai_interactive_flow_visual_"))

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 1400})
        page.goto(URL, timeout=30000, wait_until="networkidle")
        page.wait_for_timeout(1500)

        page.get_by_role("button", name="Start — Generate a Test Strategy").click(timeout=10000)
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
        page.wait_for_timeout(800)
        fill_width_after = page.eval_on_selector(
            ".dialogue-progress-fill", "el => getComputedStyle(el).width"
        )
        print(f"Dialogue progress fill after template applied (expect > 0px, wider): {fill_width_after}")
        page.screenshot(path=str(out_dir / "dialogue_filled.png"), full_page=True)

        page.get_by_role("button", name="✅ Review & Generate Strategy").click(timeout=10000)
        page.wait_for_selector(".review-grid", timeout=15000)
        page.wait_for_timeout(600)  # let the one-shot entrance finish (longest delay ~0.5s + 0.4s anim)
        page.screenshot(path=str(out_dir / "review_first_visit.png"), full_page=True)
        first_visit_class = page.eval_on_selector(".review-grid", "el => el.className")
        print(f"Review grid class on first visit (expect contains 'animate'): {first_visit_class}")

        # Edit "Additional context" to trigger a rerun, then confirm the
        # entrance does NOT replay (tiles already at rest, no 'animate' class).
        textarea = page.locator("textarea").last
        textarea.click()
        textarea.type(" - extra note", delay=30)
        page.wait_for_timeout(800)
        second_render_class = page.eval_on_selector(".review-grid", "el => el.className")
        print(f"Review grid class after editing additional context (expect NOT contains 'animate'): {second_render_class}")
        page.screenshot(path=str(out_dir / "review_after_edit.png"), full_page=True)

        browser.close()

        # Reduced-motion pass on the review screen.
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 1400}, reduced_motion="reduce")
        page.goto(URL, timeout=30000, wait_until="networkidle")
        page.wait_for_timeout(1000)
        page.get_by_role("button", name="Start — Generate a Test Strategy").click(timeout=10000)
        page.wait_for_selector(".dialogue-progress-track", timeout=15000)
        page.locator('[data-testid="stSelectbox"]').first.click()
        page.get_by_text("🌐 Web Application", exact=False).click(timeout=10000)
        page.get_by_role("button", name="Apply template").click(timeout=10000)
        page.wait_for_timeout(500)
        page.get_by_role("button", name="✅ Review & Generate Strategy").click(timeout=10000)
        page.wait_for_selector(".review-grid", timeout=15000)
        page.wait_for_timeout(200)  # reduced motion should already be at rest almost immediately
        page.screenshot(path=str(out_dir / "review_reduced_motion.png"), full_page=True)
        browser.close()

    print(f"Screenshots saved to: {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run it against the local app**

Run in one terminal: `streamlit run src/app.py`
Run in another: `python scripts/verify_interactive_flow_visual.py`
Expected: both progress-fill-width prints show growth (0px → a nonzero, wider value); the review grid class print shows `animate` present on first visit and absent after the edit; all 5 screenshots produced without errors.

- [ ] **Step 3: Visually inspect all 5 screenshots**

Open each PNG from the printed `out_dir` path. Confirm: `dialogue_empty.png` shows a near-empty progress bar and visible `.ledger-card` question cards; `dialogue_filled.png` shows a fuller bar; `review_first_visit.png` shows the summary tiles (check none are stuck at `opacity: 0`, i.e. not invisible, given the 600ms wait exceeds the longest ~0.9s delay+duration — if any tile looks faded/missing, the wait may need to be longer, adjust and re-run); `review_after_edit.png` looks identical in layout to `review_first_visit.png` (no stuck mid-animation state); `review_reduced_motion.png` shows tiles fully visible immediately. If anything looks wrong, fix `interactive_flow_style.py` (Task 1) or the wiring (Task 2) and re-run this task from Step 2 — do not proceed to Step 4 until all 5 screenshots look correct.

- [ ] **Step 4: Lint and commit**

Run: `ruff check scripts/verify_interactive_flow_visual.py`
Expected: clean.

```bash
git add scripts/verify_interactive_flow_visual.py
git commit -m "test: add manual Playwright visual check for interactive-flow redesign"
```
