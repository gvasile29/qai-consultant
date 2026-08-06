# Landing Page Redesign — "Power-On Sequence" (Phase 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the landing/intro screen's plain native Streamlit blocks (`st.info`/`st.success`/`st.columns`) with a "Power-On Sequence" hero — a one-shot boot animation (headline readout reveal, three progress gauges, a staggered standards checklist, fading-in "How it works" cards) built from the existing Calibration Bench tokens/fonts, no new design system.

**Architecture:** A new pure-function module, `src/landing_hero.py`, builds a self-contained HTML+CSS string (following the existing `ledger_components.py`/`theme.py` pattern — no Streamlit dependency, directly unit-testable). `app.py:render_intro()` calls it and renders the result via `st.markdown(html, unsafe_allow_html=True)`, replacing only the top hero block; everything below (the "What you get" cards, metrics row, info box, expanders, navigation buttons) is untouched.

**Tech Stack:** Python, Streamlit, plain CSS (keyframe animations, no JS), pytest, Playwright (manual visual verification only, not wired into CI this phase).

## Global Constraints

- `theme.py` is **not modified** — no new color tokens, no new fonts, no new rules added to `build_css()`. Read verbatim from `docs/superpowers/specs/2026-08-06-landing-power-on-redesign-design.md`.
- All new CSS lives inside `landing_hero.py`'s own returned `<style>` block, scoped to `pom-`-prefixed class names. It must **never** reuse or reference `.ledger-card` — that class belongs to the Phase-2 dialogue screen and has no existing `:hover` rule to inherit (a corrected error from an earlier spec draft).
- No changes to the dialogue, review, or output screens (`render_dialogue()`, `render_review()`, `render_strategy()`, `render_doc_review()`) — Phase 2/3 scope, not this plan.
- No PDF export changes (`pdf_export.py`, `ai_disclosure.py` untouched).
- The existing header logo (`app.py:1353-1361`, a real 280px `qai_logo_horizontal_*.png` rendered once in `main()` before any screen-specific render function runs) is **not duplicated and not animated** in this phase — out of scope, see this plan's discussion in the session for why.
- `landing_hero.py` is a Streamlit-app-only module, like `theme.py` and `ledger_components.py` — it must **not** be added to `pyproject.toml`'s `[tool.setuptools] py-modules` list (that whitelist is for the separate `qai-consultant-mcp` package; adding it there would be wrong and could break `tests/test_packaging.py`).
- No Playwright Page Object Model test suite in this plan — that's a separate, later work stream the user requested independently.
- Must not break `tests/test_app_review_mode.py::test_intro_has_review_document_entry_point`, which source-inspects `render_intro()` for the "Review an existing QA document" button — that button's code is below the part this plan touches and must remain unchanged.

---

### Task 1: `landing_hero.py` — pure HTML/CSS builder + unit tests

**Files:**
- Create: `src/landing_hero.py`
- Create: `tests/test_landing_hero.py`

**Interfaces:**
- Produces: `build_landing_hero_html(tokens: dict) -> str` — a pure function, no Streamlit import. `tokens` is `theme.LIGHT_TOKENS` or `theme.DARK_TOKENS` (same dict shape `theme.build_css()` already consumes: keys `surface`, `surface_2`, `ink`, `ink_dim`, `line`, `accent`, `pass_`, `hold`, `fail`, plus the `_bg` variants, though this function only needs `ink`, `ink_dim`, `surface`, `surface_2`, `line`, `accent`, `pass_`, `hold`). Task 2 imports this function by name.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_landing_hero.py`:

```python
"""Tests for src/landing_hero.py -- the "Power-On Sequence" landing hero
(Phase 1 of the 2026-08-06 redesign, see
docs/superpowers/specs/2026-08-06-landing-power-on-redesign-design.md)."""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from theme import LIGHT_TOKENS, DARK_TOKENS  # noqa: E402
from landing_hero import build_landing_hero_html  # noqa: E402


def test_build_landing_hero_html_uses_the_given_tokens_not_a_hardcoded_theme():
    light_html = build_landing_hero_html(LIGHT_TOKENS)
    dark_html = build_landing_hero_html(DARK_TOKENS)
    assert LIGHT_TOKENS["ink"] in light_html
    assert DARK_TOKENS["ink"] not in light_html
    assert DARK_TOKENS["ink"] in dark_html
    assert LIGHT_TOKENS["ink"] not in dark_html


def test_build_landing_hero_html_defines_all_keyframes():
    html = build_landing_hero_html(LIGHT_TOKENS)
    for name in [
        "pom-reveal", "pom-fill-risk", "pom-fill-effort",
        "pom-fill-strategy", "pom-tick", "pom-card-in",
    ]:
        assert f"@keyframes {name}" in html


def test_build_landing_hero_html_does_not_reuse_ledger_card_class():
    # Regression guard for the design-spec correction: .ledger-card belongs
    # to the Phase-2 dialogue screen and has no :hover rule to inherit --
    # this phase must define its own class, never touch .ledger-card.
    html = build_landing_hero_html(LIGHT_TOKENS)
    assert "ledger-card" not in html
    assert ".pom-card:hover" in html


def test_build_landing_hero_html_contains_the_standards_row():
    html = build_landing_hero_html(LIGHT_TOKENS)
    for standard in ["ISTQB", "OWASP", "IEEE 829", "ISO 25010"]:
        assert standard in html


def test_build_landing_hero_html_contains_how_it_works_copy():
    html = build_landing_hero_html(LIGHT_TOKENS)
    assert "Answer a few questions" in html
    assert "AI analyzes" in html
    assert "Download your strategy" in html


def test_build_landing_hero_html_respects_reduced_motion_globally():
    # This module relies on theme.py's existing global
    # `prefers-reduced-motion` rule (build_css(), not duplicated here) --
    # confirm that global rule still exists so this reliance stays valid.
    from theme import build_css
    assert "prefers-reduced-motion" in build_css(LIGHT_TOKENS)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_landing_hero.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'landing_hero'`

- [ ] **Step 3: Write the implementation**

Create `src/landing_hero.py`:

```python
"""
QAI Consultant -- Landing page hero ("Power-On Sequence", Phase 1 of the
2026-08-06 redesign -- see
docs/superpowers/specs/2026-08-06-landing-power-on-redesign-design.md).

Builds a self-contained HTML+CSS block for the landing screen's hero +
"How it works" cards. All animations are one-shot on page load (a
headline readout reveal, three progress gauges sweeping to rest, a
staggered standards checklist, fading-in cards) -- nothing loops
forever, matching the "instrument powering on, not a marketing site"
concept the direction was chosen for.

No Streamlit dependency -- callers pass the app.py-derived tokens dict
(theme.LIGHT_TOKENS or theme.DARK_TOKENS) and render the result via
st.markdown(html, unsafe_allow_html=True), same as ledger_components.py.

All CSS here is scoped to "pom-" prefixed classes and lives in this
module's own <style> block -- it is NOT added to theme.py's build_css(),
so it can't leak onto the Phase 2/3 screens that load theme.py's global
stylesheet, and it must never reuse ".ledger-card" (that belongs to the
Phase-2 dialogue screen and has no :hover rule of its own -- seeing it
reused here was a caught error in an earlier draft of the design spec).
Relies on theme.py's existing global `prefers-reduced-motion` rule
(build_css()) to disable these animations for users who've turned off
motion -- deliberately not duplicated here.
"""


def build_landing_hero_html(tokens: dict) -> str:
    """Pure function: token dict -> hero + "How it works" HTML block.
    Directly unit-testable without a Streamlit runtime -- see
    tests/test_landing_hero.py."""
    return f"""
<style>
@keyframes pom-reveal {{ from {{ clip-path: inset(0 100% 0 0); }} to {{ clip-path: inset(0 0 0 0); }} }}
@keyframes pom-fill-risk {{ from {{ width: 0%; }} to {{ width: 82%; }} }}
@keyframes pom-fill-effort {{ from {{ width: 0%; }} to {{ width: 58%; }} }}
@keyframes pom-fill-strategy {{ from {{ width: 0%; }} to {{ width: 94%; }} }}
@keyframes pom-tick {{ from {{ opacity: 0; transform: translateY(4px); }} to {{ opacity: 1; transform: translateY(0); }} }}
@keyframes pom-card-in {{ from {{ opacity: 0; transform: translateY(10px); }} to {{ opacity: 1; transform: translateY(0); }} }}

.pom-hero {{ padding: 0.5rem 0 1.5rem; }}
.pom-headline {{ font-family: 'Plex Sans', sans-serif; font-weight: 700; font-size: 2rem; line-height: 1.18; color: {tokens['ink']}; margin-bottom: 0.4rem; overflow: hidden; }}
.pom-headline span {{ display: inline-block; animation: pom-reveal 0.9s steps(30) 0.1s both; }}
.pom-readout {{ font-family: 'Plex Mono', monospace; font-size: 0.78rem; color: {tokens['ink_dim']}; margin-bottom: 1.4rem; }}

.pom-gauges {{ display: flex; gap: 0.8rem; margin-bottom: 1.6rem; max-width: 480px; }}
.pom-gauge {{ flex: 1; }}
.pom-gauge .pom-glabel {{ font-family: 'Plex Mono', monospace; font-size: 0.62rem; letter-spacing: 0.06em; text-transform: uppercase; color: {tokens['ink_dim']}; margin-bottom: 0.25rem; }}
.pom-gauge .pom-gtrack {{ height: 6px; background: {tokens['surface_2']}; border-radius: 3px; overflow: hidden; }}
.pom-gauge .pom-gfill {{ height: 100%; }}
.pom-gauge.risk .pom-gfill {{ background: {tokens['pass_']}; animation: pom-fill-risk 1.4s ease-out 0.5s both; }}
.pom-gauge.effort .pom-gfill {{ background: {tokens['hold']}; animation: pom-fill-effort 1.4s ease-out 0.7s both; }}
.pom-gauge.strategy .pom-gfill {{ background: {tokens['accent']}; animation: pom-fill-strategy 1.4s ease-out 0.9s both; }}

.pom-standards {{ display: flex; gap: 0.5rem; flex-wrap: wrap; margin-bottom: 1.8rem; }}
.pom-standards span {{ font-family: 'Plex Mono', monospace; font-size: 0.62rem; letter-spacing: 0.03em; color: {tokens['accent']}; border: 1px solid {tokens['line']}; padding: 0.15rem 0.5rem; border-radius: 4px; opacity: 0; animation: pom-tick 0.3s ease-out both; }}
.pom-standards span:nth-child(1) {{ animation-delay: 1.1s; }}
.pom-standards span:nth-child(2) {{ animation-delay: 1.25s; }}
.pom-standards span:nth-child(3) {{ animation-delay: 1.4s; }}
.pom-standards span:nth-child(4) {{ animation-delay: 1.55s; }}

.pom-cards {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.9rem; }}
.pom-card {{ background: {tokens['surface']}; border: 1px solid {tokens['line']}; border-radius: 8px; padding: 1rem 1.1rem; opacity: 0; animation: pom-card-in 0.5s ease-out both; transition: transform 0.2s ease-out, box-shadow 0.2s ease-out, border-color 0.2s ease-out; }}
.pom-card:hover {{ border-color: {tokens['accent']}; box-shadow: 0 4px 14px rgba(0,0,0,0.08); transform: translateY(-2px); }}
.pom-card:nth-child(1) {{ animation-delay: 1.7s; }}
.pom-card:nth-child(2) {{ animation-delay: 1.85s; }}
.pom-card:nth-child(3) {{ animation-delay: 2.0s; }}
.pom-card .pom-cidx {{ font-family: 'Plex Mono', monospace; font-size: 0.62rem; color: {tokens['ink_dim']}; margin-bottom: 0.35rem; }}
.pom-card .pom-ctitle {{ font-family: 'Plex Sans', sans-serif; font-weight: 600; font-size: 0.92rem; color: {tokens['ink']}; margin-bottom: 0.2rem; }}
.pom-card .pom-cbody {{ font-family: 'Plex Sans', sans-serif; font-size: 0.8rem; color: {tokens['ink_dim']}; }}
</style>

<div class="pom-hero">
  <div class="pom-headline"><span>Your AI QA Architect, grounded in standards.</span></div>
  <div class="pom-readout">&gt; calibration sequence: 3 instruments online</div>
  <div class="pom-gauges">
    <div class="pom-gauge risk"><div class="pom-glabel">Risk</div><div class="pom-gtrack"><div class="pom-gfill"></div></div></div>
    <div class="pom-gauge effort"><div class="pom-glabel">Effort</div><div class="pom-gtrack"><div class="pom-gfill"></div></div></div>
    <div class="pom-gauge strategy"><div class="pom-glabel">Strategy</div><div class="pom-gtrack"><div class="pom-gfill"></div></div></div>
  </div>
  <div class="pom-standards">
    <span>&#10003; ISTQB</span>
    <span>&#10003; OWASP</span>
    <span>&#10003; IEEE 829</span>
    <span>&#10003; ISO 25010</span>
  </div>
  <div class="pom-cards">
    <div class="pom-card"><div class="pom-cidx">01</div><div class="pom-ctitle">Answer a few questions</div><div class="pom-cbody">About your project.</div></div>
    <div class="pom-card"><div class="pom-cidx">02</div><div class="pom-ctitle">AI analyzes</div><div class="pom-cbody">Using QA methodologies &amp; standards.</div></div>
    <div class="pom-card"><div class="pom-cidx">03</div><div class="pom-ctitle">Download your strategy</div><div class="pom-cbody">Tailored Test Strategy (Markdown &amp; PDF).</div></div>
  </div>
</div>
"""
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_landing_hero.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Lint and type-check**

Run: `ruff check src/landing_hero.py tests/test_landing_hero.py`
Run: `mypy src/landing_hero.py`
Expected: both clean (no errors) — these are blocking CI jobs (`CLAUDE.md`'s CI table).

- [ ] **Step 6: Commit**

```bash
git add src/landing_hero.py tests/test_landing_hero.py
git commit -m "feat: add landing_hero.py -- Power-On Sequence hero builder (Phase 1)"
```

---

### Task 2: Wire the new hero into `render_intro()`

**Files:**
- Modify: `src/app.py:377-385`

**Interfaces:**
- Consumes: `landing_hero.build_landing_hero_html(tokens: dict) -> str` (Task 1), `theme.LIGHT_TOKENS` / `theme.DARK_TOKENS` (already exist, `src/theme.py:17,25`).

- [ ] **Step 1: Replace the native hero block**

In `src/app.py`, `render_intro()` currently starts (line 377) with:

```python
    st.markdown('<p class="sub-header">Your AI-powered QA Architect — Test Strategy Generator</p>', unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.info("📋 **Answer** a few questions about your project")
    with col2:
        st.info("🧠 **AI analyzes** using QA methodologies & standards")
    with col3:
        st.info("📄 **Download** your tailored Test Strategy (Markdown & PDF)")
```

Replace exactly those 9 lines (through the `col3` block, leaving the `st.markdown("---")` that follows untouched) with:

```python
    from landing_hero import build_landing_hero_html
    from theme import DARK_TOKENS, LIGHT_TOKENS

    _hero_tokens = DARK_TOKENS if st.context.theme.type == "dark" else LIGHT_TOKENS
    st.markdown(build_landing_hero_html(_hero_tokens), unsafe_allow_html=True)
```

Everything from the original line 387 (`st.markdown("---")`) onward — the "What you get in ~2 minutes" cards, the metrics row, the info box, both expanders, and the two navigation buttons — is **not modified**.

- [ ] **Step 2: Run the existing regression guard**

Run: `python -m pytest tests/test_app_review_mode.py -k test_intro_has_review_document_entry_point -v`
Expected: PASS — confirms the untouched button code below this change still satisfies the existing source-inspection test.

- [ ] **Step 3: Run the full test suite**

Run: `python -m pytest tests/ -q`
Expected: PASS, same pass count as before this task (no new failures).

- [ ] **Step 4: Lint and type-check**

Run: `ruff check src/app.py`
Run: `mypy src/app.py`
Expected: both clean.

- [ ] **Step 5: Commit**

```bash
git add src/app.py
git commit -m "feat: wire Power-On Sequence hero into render_intro()"
```

---

### Task 3: Manual Playwright visual verification

**Files:**
- Create: `scripts/verify_landing_visual.py`

**Interfaces:**
- Consumes: a locally running `streamlit run src/app.py` instance at `http://localhost:8501` (started manually by the implementer, not by this script).

- [ ] **Step 1: Write the verification script**

Create `scripts/verify_landing_visual.py`:

```python
"""
Manual dev script -- screenshots the local landing page to visually verify
the Power-On Sequence redesign (docs/superpowers/specs/2026-08-06-landing-
power-on-redesign-design.md, Task 3). Not part of pytest/CI: run manually.

Usage:
    streamlit run src/app.py          # in one terminal, leave running
    python scripts/verify_landing_visual.py   # in another
"""
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

URL = "http://localhost:8501"


def main() -> int:
    out_dir = Path(tempfile.mkdtemp(prefix="qai_landing_visual_"))

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(URL, timeout=30000, wait_until="networkidle")
        page.wait_for_timeout(2500)  # let the one-shot entrance animations finish
        page.screenshot(path=str(out_dir / "landing_normal_motion.png"), full_page=True)
        fill_width = page.eval_on_selector(
            ".pom-gauge.strategy .pom-gfill", "el => getComputedStyle(el).width"
        )
        print(f"Strategy gauge fill width after animation (expect > 0px): {fill_width}")
        browser.close()

        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 900}, reduced_motion="reduce")
        page.goto(URL, timeout=30000, wait_until="networkidle")
        page.wait_for_timeout(300)  # should already be at resting state almost immediately
        page.screenshot(path=str(out_dir / "landing_reduced_motion.png"), full_page=True)
        fill_width_reduced = page.eval_on_selector(
            ".pom-gauge.strategy .pom-gfill", "el => getComputedStyle(el).width"
        )
        print(f"Strategy gauge fill width with reduced motion (expect same, near-instant): {fill_width_reduced}")
        browser.close()

    print(f"Screenshots saved to: {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run it against the local app**

Run in one terminal: `streamlit run src/app.py`
Run in another: `python scripts/verify_landing_visual.py`
Expected: both printed fill-width values are non-zero pixel widths (e.g. `"280px"`, not `"0px"`); both screenshots show the hero — the normal-motion one mid/post-animation, the reduced-motion one already at rest with no visible motion.

- [ ] **Step 3: Visually inspect both screenshots**

Open both PNGs from the printed `out_dir` path. Confirm: headline text fully visible (not clipped mid-reveal, since the 2.5s wait exceeds the ~2.0s longest animation delay), three gauges filled to their resting widths, four standards badges visible, three cards visible with no leftover `opacity: 0` (i.e. not invisible). If anything looks wrong, fix `landing_hero.py` (Task 1) and re-run this task from Step 2 — do not proceed to Step 4 until both screenshots look correct.

- [ ] **Step 4: Lint and commit**

Run: `ruff check scripts/verify_landing_visual.py`
Expected: clean.

```bash
git add scripts/verify_landing_visual.py
git commit -m "test: add manual Playwright visual check for landing redesign"
```
