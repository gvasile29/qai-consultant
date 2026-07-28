# Calibration Bench Visual Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Apply the approved "Calibration Bench" visual identity (color tokens, IBM Plex typography, and a reusable "Signal Ledger" score/severity component) to the QAI Consultant Streamlit app, and wire the Signal Ledger into the three places that already have real structured scores (Document Review, Effort confidence, Results Analysis) plus a fourth place (Risk Register) that needs a small deterministic parser first since its severity data currently lives only inside free-text LLM markdown.

**Architecture:** Two new small modules — `src/theme.py` (token-based CSS, IBM Plex webfonts embedded as base64 data URIs, injected via `st.markdown`) and `src/ledger_components.py` (Streamlit-rendering helpers built on `theme.py`'s CSS classes) — plus one new deterministic, dependency-free parsing module `src/risk_ledger.py` (extracts the already-tabular "Risk Matrix Overview" markdown table into structured rows, mirroring the existing `results_core.py`/`review_core.py` pattern: no LLM, unit-testable in isolation). `src/app.py` is modified at its existing render functions to call the new components instead of raw `st.metric`/`st.markdown` calls.

**Tech Stack:** Streamlit (existing), no new Python dependencies — CSS/HTML only, injected the same way `src/app.py`'s existing custom CSS block already is (`st.markdown(..., unsafe_allow_html=True)`).

## Global Constraints

- **Visual-only change.** No existing interaction flow, session-state key, or cleanup list changes. Every existing feature must work exactly as it does today; only how it looks changes.
- **The intake form stays a single scrollable form**, not the one-question-at-a-time pagination shown in the original design mockup — the real app renders all 11 questions in one `st.form` (`src/app.py:521-547`). Rebuilding that as paginated would be a behavior change, not a visual one, and is out of scope. Apply the "ledger card" look to each question's existing block instead.
- **No `.stApp` / sidebar / native-widget background reskin.** Streamlit's own buttons, inputs, selectboxes, and sidebar chrome keep rendering under Streamlit's own light/dark theme. This plan only restyles: (a) typography app-wide, and (b) this app's own custom-HTML blocks (the existing `.sub-header`/`.source-item` classes, plus the new ledger components). A full native-widget reskin is a separate, much larger follow-up if ever wanted — attempting it here risks half-restyled, low-contrast Streamlit chrome.
- **Both Streamlit themes must stay legible.** Pick light vs. dark tokens from `st.context.theme.type` — the exact mechanism `src/app.py:61-71` already uses to pick the light/dark logo variant. `None`/unset falls back to the **light** token set (matching that existing code's `else` branch).
- **Brand logo/wordmark is preserved untouched — no task in this plan touches it.** The sidebar `st.logo()` call (`src/app.py:63-71`, swapping `assets/brand/qai_logo.svg`/`qai_logo_dark.svg`) and the header `st.image()` call (`src/app.py:1326-1333`, swapping `qai_logo_horizontal_1680.png`/`_dark_1680.png`) already pick their light/dark variant from `st.context.theme.type` independently of this plan's new CSS. `theme.py`'s injected `<style>` block must not resize, recolor, or reposition these two elements — they're pre-rendered image/SVG assets, not text, so the new Plex typefaces and color tokens don't apply to them. Verified visually in the approved implementation-preview mockup (both logo variants render correctly against both token sets).
- **Fonts are embedded as base64 `data:` URIs, no external font CDN calls at runtime** — consistent with the rest of the app having no client-side network dependencies beyond what the user's browser already needs for Streamlit itself.
- **PDF export (`src/pdf_export.py`) is untouched.** Downloaded `.md`/`.pdf` files keep their current appearance; this plan only changes the in-browser Streamlit rendering.
- **Preserve existing custom CSS class names** `.sub-header` and `.source-item` — both have live call sites (`src/app.py:404`, and 4 call sites at lines 949, 998, 1025, 1267) that must keep working unmodified.
- **Signal color meaning is fixed:** score/severity ≥ 80 (or risk level Low) → `pass`; 50–79 (or Medium) → `hold`; < 50 (or Critical/High) → `fail`. Used identically everywhere the Signal Ledger appears.

---

### Task 1: `src/theme.py` — token CSS system + embedded IBM Plex fonts

**Files:**
- Create: `src/_theme_fonts.py` (generated — base64 font data URI constants)
- Create: `src/theme.py`
- Test: `tests/test_theme.py`
- Modify: `src/app.py:73-112` (replace the existing inline `<style>` block with a call to `theme.inject_theme_css()`)

**Interfaces:**
- Produces: `theme.inject_theme_css() -> None` (call once, near the top of `app.py`, same place the old CSS block was) — injects the full `<style>` block via `st.markdown(..., unsafe_allow_html=True)`.
- Produces: `theme.LIGHT_TOKENS: dict` and `theme.DARK_TOKENS: dict` — each has keys `bg, surface, surface_2, ink, ink_dim, line, accent, accent_ink, pass_, hold, fail, pass_bg, hold_bg, fail_bg` (all `str` hex values). `ledger_components.py` (Task 3) imports these.
- Produces: `theme.build_css(tokens: dict) -> str` — pure function, used by both `inject_theme_css()` and the test below.

- [ ] **Step 1: Fetch the 5 IBM Plex webfont files**

Run from the repo root:

```bash
mkdir -p /tmp/plex_fonts && cd /tmp/plex_fonts
curl -s -o mono400.woff2 "https://fonts.gstatic.com/s/ibmplexmono/v20/-F63fjptAgt5VM-kVkqdyU8n1i8q1w.woff2"
curl -s -o mono500.woff2 "https://fonts.gstatic.com/s/ibmplexmono/v20/-F6qfjptAgt5VM-kVkqdyU8n3twJwlBFgg.woff2"
curl -s -o sans400.woff2 "https://fonts.gstatic.com/s/ibmplexsans/v23/zYXzKVElMYYaJe8bpLHnCwDKr932-G7dytD-Dmu1syxeKYY.woff2"
curl -s -o sans600.woff2 "https://fonts.gstatic.com/s/ibmplexsans/v23/zYXGKVElMYYaJe8bpLHnCwDKr932-G7dytD-Dmu1swZSAXcomDVmadSDNF5DB6g4.woff2"
curl -s -o cond700.woff2 "https://fonts.gstatic.com/s/ibmplexsanscondensed/v15/Gg8gN4UfRSqiPg7Jn2ZI12V4DCEwkj1E4LVeHY4S7bvspYY.woff2"
```

Expected: 5 files, `file *.woff2` reports `Web Open Font Format (Version 2)` for each. (These are direct, versioned `fonts.gstatic.com` URLs from Google Fonts' CSS2 API for IBM Plex Mono 400/500, IBM Plex Sans 400/600, and IBM Plex Sans Condensed 700 — Latin subset only.)

- [ ] **Step 2: Generate `src/_theme_fonts.py` from the downloaded files**

Run from the repo root:

```bash
python3 -c "
import base64
files = {
    'MONO_400': '/tmp/plex_fonts/mono400.woff2',
    'MONO_500': '/tmp/plex_fonts/mono500.woff2',
    'SANS_400': '/tmp/plex_fonts/sans400.woff2',
    'SANS_600': '/tmp/plex_fonts/sans600.woff2',
    'COND_700': '/tmp/plex_fonts/cond700.woff2',
}
lines = ['\"\"\"Generated by docs/superpowers/plans/2026-07-23-calibration-bench-redesign.md Task 1.', 'IBM Plex webfonts (Mono 400/500, Sans 400/600, Sans Condensed 700 -- Latin subset)', 'embedded as base64 data: URIs so theme.py needs no external font CDN at runtime.\"\"\"', '']
for name, path in files.items():
    data = open(path, 'rb').read()
    b64 = base64.b64encode(data).decode('ascii')
    lines.append(f'{name} = \"data:font/woff2;base64,{b64}\"')
open('src/_theme_fonts.py', 'w').write('\n'.join(lines) + '\n')
print('wrote src/_theme_fonts.py')
"
```

Expected: `wrote src/_theme_fonts.py`, and `python3 -c "import sys; sys.path.insert(0,'src'); import _theme_fonts; print(len(_theme_fonts.SANS_400))"` prints a number greater than 50000 (the base64 string length).

- [ ] **Step 3: Write the failing test for `build_css()`**

Create `tests/test_theme.py`:

```python
"""Tests for src/theme.py -- the Calibration Bench CSS token system."""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from theme import LIGHT_TOKENS, DARK_TOKENS, build_css  # noqa: E402

_REQUIRED_KEYS = {
    "bg", "surface", "surface_2", "ink", "ink_dim", "line",
    "accent", "accent_ink", "pass_", "hold", "fail",
    "pass_bg", "hold_bg", "fail_bg",
}


def test_light_and_dark_tokens_have_same_keys():
    assert set(LIGHT_TOKENS.keys()) == _REQUIRED_KEYS
    assert set(DARK_TOKENS.keys()) == _REQUIRED_KEYS


def test_light_and_dark_tokens_are_distinct():
    # Every token must actually differ between themes -- a copy-paste bug
    # that leaves one theme identical to the other defeats the point.
    assert LIGHT_TOKENS != DARK_TOKENS
    for key in _REQUIRED_KEYS:
        assert LIGHT_TOKENS[key] != DARK_TOKENS[key], f"token {key!r} is identical in both themes"


def test_build_css_embeds_all_five_font_faces():
    css = build_css(LIGHT_TOKENS)
    for family, weight in [
        ("Plex Mono", "400"), ("Plex Mono", "500"),
        ("Plex Sans", "400"), ("Plex Sans", "600"),
        ("Plex Cond", "700"),
    ]:
        assert f"font-family: '{family}'" in css
        assert f"font-weight: {weight}" in css
    assert css.count("data:font/woff2;base64,") == 5


def test_build_css_uses_the_given_tokens_not_a_hardcoded_theme():
    light_css = build_css(LIGHT_TOKENS)
    dark_css = build_css(DARK_TOKENS)
    assert LIGHT_TOKENS["bg"] in light_css
    assert DARK_TOKENS["bg"] not in light_css
    assert DARK_TOKENS["bg"] in dark_css
    assert LIGHT_TOKENS["bg"] not in dark_css


def test_build_css_respects_reduced_motion_and_focus_visibility():
    css = build_css(LIGHT_TOKENS)
    assert "prefers-reduced-motion" in css
    assert ":focus-visible" in css
```

- [ ] **Step 4: Run the test to verify it fails**

Run: `python -m pytest tests/test_theme.py -v`
Expected: `ModuleNotFoundError: No module named 'theme'` (or collection error) — `src/theme.py` doesn't exist yet.

- [ ] **Step 5: Write `src/theme.py`**

```python
"""
QAI Consultant -- visual identity system ("Calibration Bench").

Token-based CSS: light mode reads as certificate paper, dark mode reads as
an instrument panel at night. Three signal colors (pass/hold/fail) carry
real meaning everywhere they're used -- never decorative.

inject_theme_css() picks the token set from st.context.theme.type, the
exact mechanism app.py's st.logo() call already uses to pick the light/dark
logo variant (see app.py's page-config section) -- None/unset falls back
to the light set, matching that existing code's else branch.
"""
import streamlit as st

from _theme_fonts import COND_700, MONO_400, MONO_500, SANS_400, SANS_600

LIGHT_TOKENS = {
    "bg": "#EDEAE0", "surface": "#F5F3EA", "surface_2": "#E4E0D2",
    "ink": "#23281F", "ink_dim": "#5B5F52", "line": "#C9C3AF",
    "accent": "#3E6E85", "accent_ink": "#F5F3EA",
    "pass_": "#3F7A4C", "hold": "#9C6B1F", "fail": "#9C3F2C",
    "pass_bg": "#DCE7DA", "hold_bg": "#ECDFC7", "fail_bg": "#EAD7CF",
}

DARK_TOKENS = {
    "bg": "#1B211D", "surface": "#212821", "surface_2": "#262E27",
    "ink": "#E6E8DF", "ink_dim": "#9BA69C", "line": "#3A453D",
    "accent": "#86ADC2", "accent_ink": "#14201F",
    "pass_": "#7FBC8A", "hold": "#D8AE68", "fail": "#CB7862",
    "pass_bg": "#23342A", "hold_bg": "#332C1F", "fail_bg": "#35251F",
}


def build_css(tokens: dict) -> str:
    """Pure function: token dict -> full <style> block. Kept pure (no
    Streamlit calls) so it's directly unit-testable without a Streamlit
    runtime -- see tests/test_theme.py."""
    return f"""
<style>
@font-face {{ font-family: 'Plex Mono'; font-weight: 400; font-style: normal; font-display: swap; src: url('{MONO_400}') format('woff2'); }}
@font-face {{ font-family: 'Plex Mono'; font-weight: 500; font-style: normal; font-display: swap; src: url('{MONO_500}') format('woff2'); }}
@font-face {{ font-family: 'Plex Sans'; font-weight: 400; font-style: normal; font-display: swap; src: url('{SANS_400}') format('woff2'); }}
@font-face {{ font-family: 'Plex Sans'; font-weight: 600; font-style: normal; font-display: swap; src: url('{SANS_600}') format('woff2'); }}
@font-face {{ font-family: 'Plex Cond'; font-weight: 700; font-style: normal; font-display: swap; src: url('{COND_700}') format('woff2'); }}

html, body, [class*="css"] {{
    font-family: 'Plex Sans', -apple-system, "Segoe UI", sans-serif;
}}

.sub-header {{
    font-family: 'Plex Sans', sans-serif;
    font-size: 1rem;
    color: {tokens['ink_dim']};
    margin-bottom: 2rem;
}}
.source-item {{
    font-family: 'Plex Mono', monospace;
    background-color: {tokens['surface_2']};
    border-left: 2px solid {tokens['accent']};
    padding: 0.3rem 0.6rem;
    margin: 0.2rem 0;
    font-size: 0.78rem;
    color: {tokens['ink_dim']};
}}

/* Intake ledger card (Task 6) */
.ledger-card {{
    background: {tokens['surface']};
    border: 1px solid {tokens['line']};
    padding: 1.1rem 1.3rem;
    margin-bottom: 1rem;
}}
.ledger-card .idx {{
    font-family: 'Plex Mono', monospace;
    color: {tokens['accent']};
    font-size: 0.78rem;
    margin-bottom: 0.3rem;
    letter-spacing: 0.04em;
    text-transform: uppercase;
}}
.ledger-card .qtitle {{
    font-family: 'Plex Sans', sans-serif;
    font-weight: 600;
    font-size: 1.02rem;
    margin-bottom: 0.2rem;
    color: {tokens['ink']};
}}

/* Signal Ledger: score/severity component reused across Review, Effort, Results (Tasks 4/5/7/8) */
.signal-ledger {{
    border: 1px solid {tokens['line']};
    background: {tokens['surface']};
    padding: 1rem 1.2rem;
    margin-bottom: 0.8rem;
}}
.signal-ledger .sl-label {{
    font-family: 'Plex Mono', monospace;
    font-size: 0.68rem;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: {tokens['ink_dim']};
    margin-bottom: 0.5rem;
}}
.signal-ledger .sl-score {{
    font-family: 'Plex Mono', monospace;
    font-size: 2rem;
    font-weight: 500;
    font-variant-numeric: tabular-nums;
    line-height: 1;
}}
.signal-ledger .sl-score.pass {{ color: {tokens['pass_']}; }}
.signal-ledger .sl-score.hold {{ color: {tokens['hold']}; }}
.signal-ledger .sl-score.fail {{ color: {tokens['fail']}; }}
.signal-ledger .sl-sub {{
    font-size: 0.82rem;
    color: {tokens['ink_dim']};
    margin: 0.3rem 0 0.6rem;
}}
.signal-ledger .sl-meter {{ display: inline-flex; gap: 2px; }}
.signal-ledger .sl-meter i {{
    width: 7px; height: 14px;
    background: {tokens['line']};
    display: inline-block;
}}
.signal-ledger .sl-meter i.on.pass {{ background: {tokens['pass_']}; }}
.signal-ledger .sl-meter i.on.hold {{ background: {tokens['hold']}; }}
.signal-ledger .sl-meter i.on.fail {{ background: {tokens['fail']}; }}

/* Risk ledger table (Task 5) */
table.risk-ledger {{
    width: 100%;
    border-collapse: collapse;
    font-family: 'Plex Sans', sans-serif;
    font-size: 0.88rem;
}}
table.risk-ledger th {{
    text-align: left;
    font-family: 'Plex Mono', monospace;
    font-size: 0.66rem;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    color: {tokens['ink_dim']};
    font-weight: 400;
    padding: 0.6rem 0.9rem 0.4rem;
    border-bottom: 1px solid {tokens['line']};
}}
table.risk-ledger td {{
    padding: 0.65rem 0.9rem;
    border-bottom: 1px solid {tokens['line']};
    vertical-align: top;
    color: {tokens['ink']};
}}
table.risk-ledger tr:last-child td {{ border-bottom: none; }}
table.risk-ledger .rid {{
    font-family: 'Plex Mono', monospace;
    color: {tokens['ink_dim']};
    white-space: nowrap;
}}
table.risk-ledger .sev {{
    display: inline-block;
    font-family: 'Plex Mono', monospace;
    font-size: 0.7rem;
    letter-spacing: 0.03em;
    text-transform: uppercase;
    padding: 0.2rem 0.5rem;
    white-space: nowrap;
}}
table.risk-ledger .sev.pass {{ background: {tokens['pass_bg']}; color: {tokens['pass_']}; }}
table.risk-ledger .sev.hold {{ background: {tokens['hold_bg']}; color: {tokens['hold']}; }}
table.risk-ledger .sev.fail {{ background: {tokens['fail_bg']}; color: {tokens['fail']}; }}

:focus-visible {{ outline: 2px solid {tokens['accent']}; outline-offset: 2px; }}
@media (prefers-reduced-motion: reduce) {{
    *, *::before, *::after {{
        animation-duration: 0.001ms !important;
        transition-duration: 0.001ms !important;
    }}
}}
</style>
"""


def inject_theme_css() -> None:
    """Call once per page load, same place the old inline <style> block
    used to live in app.py."""
    theme_type = st.context.theme.type
    tokens = DARK_TOKENS if theme_type == "dark" else LIGHT_TOKENS
    st.markdown(build_css(tokens), unsafe_allow_html=True)
```

- [ ] **Step 6: Run the test to verify it passes**

Run: `python -m pytest tests/test_theme.py -v`
Expected: `5 passed`

- [ ] **Step 7: Wire `inject_theme_css()` into `app.py`, replacing the old CSS block**

In `src/app.py`, replace lines 73-112 (the `# ── Custom CSS ──` comment through the closing `""", unsafe_allow_html=True)`) with:

```python
# ── Custom CSS ─────────────────────────────────────────────────────────────────
from theme import inject_theme_css

inject_theme_css()
```

- [ ] **Step 8: Manual smoke test**

Run: `streamlit run src/app.py`
Expected: app loads with no exceptions in the terminal; the intro page's subtitle (`.sub-header`) and the sidebar render in the new body font (visibly different letterforms from Streamlit's default — check descenders on "g"/"y" against the pre-change screenshot). Toggle Streamlit's own theme setting (top-right menu → Settings → Theme) between light and dark and confirm the page doesn't error either way.

- [ ] **Step 9: Commit**

```bash
git add src/_theme_fonts.py src/theme.py tests/test_theme.py src/app.py
git commit -m "feat: add Calibration Bench token CSS system (theme.py)"
```

---

### Task 2: `src/risk_ledger.py` — deterministic Risk Matrix table parser

**Files:**
- Create: `src/risk_ledger.py`
- Test: `tests/test_risk_ledger.py`

**Interfaces:**
- Consumes: nothing from earlier tasks (standalone, dependency-free — same tier as `results_core.py`/`review_core.py`).
- Produces: `risk_ledger.parse_risk_matrix(markdown_text: str) -> list[dict]`. Each dict has keys `risk_id: str, description: str, likelihood: str, impact: str, risk_level: str, priority: str`. Returns `[]` if no matching table is found — never raises.
- Produces: `risk_ledger.severity_tier(risk_level: str) -> str` — returns `"pass"`, `"hold"`, or `"fail"`. Case-insensitive; `"low"` → `pass`, `"medium"` → `hold`, `"high"`/`"critical"` → `fail`; anything unrecognized → `"hold"` (safe default, never raises). Task 4 (`ledger_components.py`) imports both.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_risk_ledger.py`:

```python
"""
Tests for src/risk_ledger.py -- deterministic parsing of the "Risk Matrix
Overview" markdown table that risk_analyzer.py's RISK prompt already forces
the LLM to produce in an exact column format (see build_risk_prompt() in
src/risk_analyzer.py):

    | Risk ID | Risk Description | Likelihood | Impact | Risk Level | Priority |
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from risk_ledger import parse_risk_matrix, severity_tier  # noqa: E402

SAMPLE_REGISTER = """
# Risk Register — Example Project

## Executive Summary
This project carries Medium overall risk.

## Risk Matrix Overview

| Risk ID | Risk Description | Likelihood | Impact | Risk Level | Priority |
|---|---|---|---|---|---|
| R01 | Auth token expiry has no covering test case | High | High | Critical | 1 |
| R02 | No load test executed above 200 rps | Medium | Medium | Medium | 2 |
| R03 | Minor copy inconsistency in confirmation email | Low | Low | Low | 3 |

## Detailed Risk Analysis

### R01 — Auth token expiry
- **Category:** Technical
"""


def test_parse_risk_matrix_extracts_all_rows_in_order():
    rows = parse_risk_matrix(SAMPLE_REGISTER)
    assert [r["risk_id"] for r in rows] == ["R01", "R02", "R03"]


def test_parse_risk_matrix_extracts_all_columns():
    rows = parse_risk_matrix(SAMPLE_REGISTER)
    assert rows[0] == {
        "risk_id": "R01",
        "description": "Auth token expiry has no covering test case",
        "likelihood": "High",
        "impact": "High",
        "risk_level": "Critical",
        "priority": "1",
    }


def test_parse_risk_matrix_returns_empty_list_when_no_table_present():
    assert parse_risk_matrix("# Just a heading\n\nNo table here.") == []


def test_parse_risk_matrix_never_raises_on_malformed_input():
    malformed_inputs = [
        "",
        "| only one column |",
        "| Risk ID | Risk Description |\n|---|---|\n| R01 |",  # ragged row, too few cells
        "not markdown at all \x00\x01",
    ]
    for text in malformed_inputs:
        assert parse_risk_matrix(text) == [] or isinstance(parse_risk_matrix(text), list)


def test_severity_tier_maps_risk_levels():
    assert severity_tier("Low") == "pass"
    assert severity_tier("low") == "pass"
    assert severity_tier("Medium") == "hold"
    assert severity_tier("High") == "fail"
    assert severity_tier("Critical") == "fail"


def test_severity_tier_unknown_value_defaults_to_hold():
    assert severity_tier("Unknown") == "hold"
    assert severity_tier("") == "hold"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_risk_ledger.py -v`
Expected: `ModuleNotFoundError: No module named 'risk_ledger'`

- [ ] **Step 3: Write `src/risk_ledger.py`**

```python
"""
QAI Consultant -- deterministic Risk Matrix table parser.

risk_analyzer.py's RISK_SYSTEM_PROMPT forces the LLM to emit a "Risk Matrix
Overview" section as a markdown pipe-table with an EXACT, fixed column set
(see build_risk_prompt() in risk_analyzer.py). This module parses that
table back into structured rows so app.py can render it with the Signal
Ledger's heat-swatch treatment instead of raw markdown.

Dependency-free, no LLM call, never raises -- same tier as results_core.py
and review_core.py.
"""
import re

_TABLE_HEADER_RE = re.compile(r"^\|\s*Risk ID\s*\|", re.IGNORECASE | re.MULTILINE)

_SEVERITY_TIERS = {
    "low": "pass",
    "medium": "hold",
    "high": "fail",
    "critical": "fail",
}


def severity_tier(risk_level: str) -> str:
    """Map a Risk Level string (Low/Medium/High/Critical) to a Signal
    Ledger tier (pass/hold/fail). Unrecognized or empty input defaults to
    "hold" rather than raising -- a wrong-but-visible middle tier is safer
    than crashing the whole Risk Register render over one bad LLM token."""
    return _SEVERITY_TIERS.get((risk_level or "").strip().lower(), "hold")


def parse_risk_matrix(markdown_text: str) -> list:
    """Extract the "Risk Matrix Overview" pipe-table into a list of dicts
    with keys: risk_id, description, likelihood, impact, risk_level,
    priority. Returns [] if no matching table is found or the input is
    malformed -- never raises."""
    if not markdown_text:
        return []

    match = _TABLE_HEADER_RE.search(markdown_text)
    if not match:
        return []

    lines = markdown_text[match.start():].splitlines()
    rows = []
    for line in lines[2:]:  # skip the header row and the |---|---| separator
        stripped = line.strip()
        if not stripped.startswith("|"):
            break  # table ended
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if len(cells) != 6:
            continue  # ragged row -- skip rather than guess
        risk_id, description, likelihood, impact, risk_level, priority = cells
        if not risk_id or set(risk_id) == {"-"}:
            continue  # stray separator-like row
        rows.append({
            "risk_id": risk_id,
            "description": description,
            "likelihood": likelihood,
            "impact": impact,
            "risk_level": risk_level,
            "priority": priority,
        })
    return rows
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_risk_ledger.py -v`
Expected: `7 passed`

- [ ] **Step 5: Commit**

```bash
git add src/risk_ledger.py tests/test_risk_ledger.py
git commit -m "feat: add deterministic Risk Matrix table parser (risk_ledger.py)"
```

---

### Task 3: `src/ledger_components.py` — Signal Ledger + Risk Ledger render helpers

**Files:**
- Create: `src/ledger_components.py`
- Test: `tests/test_ledger_components.py`

**Interfaces:**
- Consumes: `theme.LIGHT_TOKENS`/`DARK_TOKENS` keys (just the CSS class names defined in Task 1 — `signal-ledger`, `risk-ledger`, `sev`, etc. — no direct token import needed since colors come from the already-injected CSS).
- Consumes: `risk_ledger.severity_tier` (Task 2).
- Produces: `ledger_components.score_tier(score: int) -> str` — `"pass"` if `score >= 80`, `"hold"` if `50 <= score < 80`, else `"fail"`.
- Produces: `ledger_components.signal_ledger_html(label: str, score: int, sub: str = "", tier: str = None) -> str` — returns an HTML string (not yet rendered); if `tier` is omitted it's computed via `score_tier(score)`. Task 5/6/7/8 call `st.markdown(signal_ledger_html(...), unsafe_allow_html=True)`.
- Produces: `ledger_components.risk_ledger_table_html(rows: list) -> str` — returns an HTML `<table class="risk-ledger">` string built from `risk_ledger.parse_risk_matrix()`'s output shape. Returns `""` for an empty list.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_ledger_components.py`:

```python
"""Tests for src/ledger_components.py -- Signal Ledger / Risk Ledger HTML builders.

These build HTML strings only (no Streamlit runtime needed to test them --
st.markdown() is the caller's job, not this module's).
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from ledger_components import (  # noqa: E402
    risk_ledger_table_html,
    score_tier,
    signal_ledger_html,
)

SAMPLE_ROWS = [
    {"risk_id": "R01", "description": "Auth token expiry untested", "likelihood": "High",
     "impact": "High", "risk_level": "Critical", "priority": "1"},
    {"risk_id": "R02", "description": "No load test above 200 rps", "likelihood": "Medium",
     "impact": "Medium", "risk_level": "Medium", "priority": "2"},
]


def test_score_tier_boundaries():
    assert score_tier(100) == "pass"
    assert score_tier(80) == "pass"
    assert score_tier(79) == "hold"
    assert score_tier(50) == "hold"
    assert score_tier(49) == "fail"
    assert score_tier(0) == "fail"


def test_signal_ledger_html_contains_label_and_score():
    html = signal_ledger_html("Confidence", 72, sub="cited from 6 sources")
    assert "Confidence" in html
    assert "72" in html
    assert "cited from 6 sources" in html
    assert 'class="signal-ledger"' in html


def test_signal_ledger_html_uses_computed_tier_class():
    html = signal_ledger_html("Overall Score", 84)
    assert "sl-score pass" in html
    html = signal_ledger_html("Overall Score", 61)
    assert "sl-score hold" in html
    html = signal_ledger_html("Overall Score", 30)
    assert "sl-score fail" in html


def test_signal_ledger_html_accepts_explicit_tier_override():
    # e.g. effort confidence is a "how sure are we" score, not a "how good
    # is this" score -- callers may want to force the tier explicitly.
    html = signal_ledger_html("Confidence", 90, tier="hold")
    assert "sl-score hold" in html


def test_signal_ledger_html_escapes_label_and_sub_text():
    html = signal_ledger_html("<script>alert(1)</script>", 50, sub="<b>x</b>")
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_risk_ledger_table_html_renders_all_rows():
    html = risk_ledger_table_html(SAMPLE_ROWS)
    assert html.count("<tr>") == 2
    assert "R01" in html and "R02" in html
    assert "Auth token expiry untested" in html


def test_risk_ledger_table_html_uses_severity_tier_classes():
    html = risk_ledger_table_html(SAMPLE_ROWS)
    assert 'class="sev fail"' in html   # Critical -> fail
    assert 'class="sev hold"' in html   # Medium -> hold


def test_risk_ledger_table_html_empty_rows_returns_empty_string():
    assert risk_ledger_table_html([]) == ""


def test_risk_ledger_table_html_escapes_description():
    rows = [{"risk_id": "R01", "description": "<img src=x onerror=alert(1)>",
              "likelihood": "Low", "impact": "Low", "risk_level": "Low", "priority": "1"}]
    html = risk_ledger_table_html(rows)
    assert "<img" not in html
    assert "&lt;img" in html
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_ledger_components.py -v`
Expected: `ModuleNotFoundError: No module named 'ledger_components'`

- [ ] **Step 3: Write `src/ledger_components.py`**

```python
"""
QAI Consultant -- Signal Ledger / Risk Ledger HTML builders.

Builds the HTML strings for the Calibration Bench's signature reusable
device (a heat-tier score/severity readout) and the Risk Register table.
Callers pass the result to st.markdown(html, unsafe_allow_html=True) --
this module has no Streamlit dependency itself, so it's directly
unit-testable (see tests/test_ledger_components.py).

All user-supplied text (labels, descriptions) is HTML-escaped -- this
renders LLM-generated and user-uploaded content, so unescaped interpolation
would be a stored-XSS path via unsafe_allow_html=True.
"""
import html as _html

from risk_ledger import severity_tier


def score_tier(score: int) -> str:
    """Map a 0-100 score to a Signal Ledger tier. >=80 pass, 50-79 hold,
    <50 fail -- the same thresholds used app-wide (see this plan's Global
    Constraints)."""
    if score >= 80:
        return "pass"
    if score >= 50:
        return "hold"
    return "fail"


def signal_ledger_html(label: str, score: int, sub: str = "", tier: str = None) -> str:
    """A compact score readout: an uppercase mono label, a large tabular
    score, an optional sub-line, and a 10-segment meter. `tier` overrides
    the auto-computed pass/hold/fail class when the caller's score isn't a
    "higher is better toward 100" quality score (e.g. it's fine to leave
    unset for Review/Results scores, and explicit for anything where the
    caller has better domain judgment than the generic 80/50 split)."""
    resolved_tier = tier or score_tier(score)
    filled = max(0, min(10, round(score / 10)))
    meter = "".join(
        f'<i class="on {resolved_tier}"></i>' if i < filled else "<i></i>"
        for i in range(10)
    )
    sub_html = f'<div class="sl-sub">{_html.escape(sub)}</div>' if sub else ""
    return (
        '<div class="signal-ledger">'
        f'<div class="sl-label">{_html.escape(label)}</div>'
        f'<div class="sl-score {resolved_tier}">{score}</div>'
        f"{sub_html}"
        f'<div class="sl-meter">{meter}</div>'
        "</div>"
    )


def risk_ledger_table_html(rows: list) -> str:
    """Render parsed Risk Matrix rows (risk_ledger.parse_risk_matrix()'s
    output shape) as a <table class="risk-ledger">. Empty input returns ""
    so callers can `if html: st.markdown(html, ...)` without a blank
    table appearing."""
    if not rows:
        return ""

    body_rows = []
    for row in rows:
        tier = severity_tier(row.get("risk_level", ""))
        body_rows.append(
            "<tr>"
            f'<td class="rid">{_html.escape(row.get("risk_id", ""))}</td>'
            f'<td><span class="sev {tier}">{_html.escape(row.get("risk_level", ""))}</span></td>'
            f'<td>{_html.escape(row.get("description", ""))}</td>'
            f'<td>{_html.escape(row.get("likelihood", ""))}</td>'
            f'<td>{_html.escape(row.get("impact", ""))}</td>'
            f'<td class="rid">{_html.escape(row.get("priority", ""))}</td>'
            "</tr>"
        )

    return (
        '<table class="risk-ledger">'
        "<thead><tr>"
        "<th>ID</th><th>Severity</th><th>Risk</th>"
        "<th>Likelihood</th><th>Impact</th><th>Priority</th>"
        "</tr></thead>"
        f"<tbody>{''.join(body_rows)}</tbody>"
        "</table>"
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_ledger_components.py -v`
Expected: `9 passed`

- [ ] **Step 5: Commit**

```bash
git add src/ledger_components.py tests/test_ledger_components.py
git commit -m "feat: add Signal Ledger / Risk Ledger HTML builders (ledger_components.py)"
```

---

### Task 4: Wire the Risk Register tab to the Risk Ledger table

**Files:**
- Modify: `src/app.py:944-949` (inside `render_strategy()`'s `tab1`)
- Test: `tests/test_app_v03.py` (existing file — add one test)

**Interfaces:**
- Consumes: `risk_ledger.parse_risk_matrix` (Task 2), `ledger_components.risk_ledger_table_html` (Task 3).

- [ ] **Step 1: Modify `app.py`'s Risk Register tab**

In `src/app.py`, replace:

```python
    with tab1:
        st.markdown(st.session_state.risk_register)
        st.markdown("---")
```

with:

```python
    with tab1:
        from risk_ledger import parse_risk_matrix
        from ledger_components import risk_ledger_table_html

        risk_rows = parse_risk_matrix(st.session_state.risk_register)
        if risk_rows:
            st.markdown(risk_ledger_table_html(risk_rows), unsafe_allow_html=True)
            st.markdown("###")
        st.markdown(st.session_state.risk_register)
        st.markdown("---")
```

(The full markdown still renders below the table — Executive Summary, Detailed Risk Analysis, Testing Priorities, and Recommendations aren't structured data, so they stay as narrative text. `parse_risk_matrix` returning `[]` — e.g. if the LLM ever deviates from the exact prompted format — just skips the table with no error, falling back to exactly today's behavior.)

- [ ] **Step 2: Add a regression test**

In `tests/test_app_v03.py`, find the existing imports at the top of the file (they already `sys.path.insert` into `src/` — match that pattern) and add:

```python
def test_risk_ledger_table_renders_for_well_formed_risk_register():
    from risk_ledger import parse_risk_matrix
    from ledger_components import risk_ledger_table_html

    sample = """## Risk Matrix Overview

| Risk ID | Risk Description | Likelihood | Impact | Risk Level | Priority |
|---|---|---|---|---|---|
| R01 | Sample risk | High | High | Critical | 1 |
"""
    rows = parse_risk_matrix(sample)
    assert len(rows) == 1
    html = risk_ledger_table_html(rows)
    assert "R01" in html
    assert 'class="sev fail"' in html


def test_risk_ledger_table_is_skipped_gracefully_for_freeform_risk_register():
    from risk_ledger import parse_risk_matrix
    from ledger_components import risk_ledger_table_html

    rows = parse_risk_matrix("Just some prose the LLM wrote, no table.")
    assert rows == []
    assert risk_ledger_table_html(rows) == ""
```

- [ ] **Step 3: Run the tests to verify they pass**

Run: `python -m pytest tests/test_app_v03.py -v -k risk_ledger`
Expected: `2 passed`

- [ ] **Step 4: Manual smoke test**

Run: `streamlit run src/app.py`, complete the 11-question intake with any answers, generate a strategy, and check the "⚠️ Risk Register" tab: the heat-swatch table should appear above the narrative markdown, with `Critical`/`High` rows tinted `fail`, `Medium` tinted `hold`, `Low` tinted `pass`.

- [ ] **Step 5: Commit**

```bash
git add src/app.py tests/test_app_v03.py
git commit -m "feat: render Risk Register severity as a heat-tiered ledger table"
```

---

### Task 5: Persist `EstimationData` in session state + wire the Effort tab

**Files:**
- Modify: `src/app.py:866-880` (persist `effort_data`)
- Modify: `src/app.py:970-971` (render the Signal Ledger)
- Test: `tests/test_app_v03.py`

**Interfaces:**
- Consumes: `ledger_components.signal_ledger_html` (Task 3).
- Produces: `st.session_state.effort_data: EstimationData | None` — new session-state key, must be added to both cleanup lists per this app's existing convention (see Step 3 below).

- [ ] **Step 1: Persist `effort_data` alongside `effort_report`**

In `src/app.py`, replace:

```python
        # Effort Estimation (deterministic + short LLM narrative)
        if st.session_state.get("effort_report") is None:
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
        else:
            effort_report = st.session_state.effort_report
```

with:

```python
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
```

- [ ] **Step 2: Initialize the new session-state key**

In `src/app.py`'s `init_session_state()` (near line 135, right next to the existing `effort_report` init), add:

```python
    if "effort_data" not in st.session_state:
        st.session_state.effort_data = None
```

- [ ] **Step 3: Add `effort_data` to both cleanup lists**

Search `src/app.py` for the two places that clear `"effort_report", "effort_path"` together (one is "Start Over", one is "Generate Another Strategy" — CLAUDE.md's Gotchas section documents these must stay in sync). At each occurrence, add `"effort_data"` to the same list, e.g. change:

```python
                        "effort_report", "effort_path",
```

to:

```python
                        "effort_report", "effort_path", "effort_data",
```

Run `grep -n '"effort_report", "effort_path"' src/app.py` first to find both exact line numbers before editing — do not guess; edit both occurrences.

- [ ] **Step 4: Render the Signal Ledger in the Effort tab**

In `src/app.py`, replace:

```python
    with tab2:
        st.markdown(st.session_state.effort_report)
        st.markdown("---")
```

with:

```python
    with tab2:
        from ledger_components import signal_ledger_html

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
        st.markdown(st.session_state.effort_report)
        st.markdown("---")
```

(`effort_data` is `None` on a resumed session where only `effort_report` was persisted before this change shipped — e.g. an in-flight session from before this deploy. Guarding on `is not None` means the ledger just doesn't render rather than crashing; the markdown report still shows the confidence score in its own table row as it always has.)

- [ ] **Step 5: Add a regression test**

In `tests/test_app_v03.py`, add:

```python
def test_effort_data_confidence_renders_as_signal_ledger():
    from ledger_components import signal_ledger_html

    html = signal_ledger_html("Confidence", 72, sub="Medium confidence")
    assert "72" in html
    assert "Medium confidence" in html
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `python -m pytest tests/test_app_v03.py -v -k effort_data`
Expected: `1 passed`

- [ ] **Step 7: Manual smoke test**

Run: `streamlit run src/app.py`, generate a strategy, check the "📊 Effort Estimation" tab shows the Signal Ledger confidence readout above the narrative report. Then click "Generate Another Strategy" (or "Start Over") and confirm no `KeyError`/stale-data issues on the next run — this is exactly the class of bug CLAUDE.md's session-state-cleanup gotcha warns about.

- [ ] **Step 8: Commit**

```bash
git add src/app.py tests/test_app_v03.py
git commit -m "feat: persist EstimationData in session state, render confidence as Signal Ledger"
```

---

### Task 6: Wire Document Review score display

**Files:**
- Modify: `src/app.py:1192-1197` (inside `render_doc_review()`)
- Test: `tests/test_app_v03.py`

**Interfaces:**
- Consumes: `ledger_components.signal_ledger_html` (Task 3).

- [ ] **Step 1: Modify `app.py`'s Document Review score display**

In `src/app.py`, replace:

```python
    st.markdown(f"**Detected document type:** `{result.doc_type}`")
    st.metric("Overall Score", f"{result.overall_score}/100")

    dim_cols = st.columns(len(result.dimension_scores))
    for col, (dim, score) in zip(dim_cols, result.dimension_scores.items()):
        col.metric(dim.replace("_", " ").title(), f"{score}")
```

with:

```python
    from ledger_components import signal_ledger_html

    st.markdown(f"**Detected document type:** `{result.doc_type}`")
    st.markdown(
        signal_ledger_html("Overall Score", result.overall_score, sub=f"{result.doc_type} · 6-dimension rubric"),
        unsafe_allow_html=True,
    )

    dim_cols = st.columns(len(result.dimension_scores))
    for col, (dim, score) in zip(dim_cols, result.dimension_scores.items()):
        with col:
            st.markdown(
                signal_ledger_html(dim.replace("_", " ").title(), score),
                unsafe_allow_html=True,
            )
```

- [ ] **Step 2: Add a regression test**

In `tests/test_app_v03.py`, add:

```python
def test_review_dimension_scores_render_as_signal_ledgers():
    from ledger_components import signal_ledger_html

    dimension_scores = {"structure_completeness": 92, "traceability": 70, "measurability": 45}
    for dim, score in dimension_scores.items():
        html = signal_ledger_html(dim.replace("_", " ").title(), score)
        assert dim.replace("_", " ").title() in html
        assert str(score) in html
    # Sanity: the three thresholds actually land in different tiers, proving
    # the display isn't silently uniform.
    from ledger_components import score_tier
    assert score_tier(92) == "pass"
    assert score_tier(70) == "hold"
    assert score_tier(45) == "fail"
```

- [ ] **Step 3: Run the test to verify it passes**

Run: `python -m pytest tests/test_app_v03.py -v -k review_dimension`
Expected: `1 passed`

- [ ] **Step 4: Manual smoke test**

Run: `streamlit run src/app.py`, use "Review an existing QA document" mode, paste any short Test Plan text, click "Review Document", and confirm the Overall Score and each dimension render as Signal Ledger cards instead of `st.metric` widgets.

- [ ] **Step 5: Commit**

```bash
git add src/app.py tests/test_app_v03.py
git commit -m "feat: render Document Review scores as Signal Ledger cards"
```

---

### Task 7: Wire Results Analysis display

**Files:**
- Modify: `src/app.py:656-667` (inside `render_review()`'s "Attach test execution results" expander)
- Test: `tests/test_app_v03.py`

**Interfaces:**
- Consumes: `ledger_components.signal_ledger_html` (Task 3).

- [ ] **Step 1: Modify `app.py`'s Results Analysis display**

In `src/app.py`, replace:

```python
        analysis = st.session_state.get("results_analysis")
        if analysis is not None:
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Runs", analysis.runs)
            m2.metric("Pass Rate", f"{analysis.overall_pass_rate:.0%}")
            m3.metric("Flaky Tests", len(analysis.flaky))
            m4.metric("Ever-Failing", len(analysis.ever_failing))
```

with:

```python
        analysis = st.session_state.get("results_analysis")
        if analysis is not None:
            from ledger_components import signal_ledger_html

            pass_rate_pct = round(analysis.overall_pass_rate * 100)
            m1, m2, m3, m4 = st.columns(4)
            with m1:
                st.markdown(signal_ledger_html("Runs", analysis.runs, tier="hold"), unsafe_allow_html=True)
            with m2:
                st.markdown(signal_ledger_html("Pass Rate", pass_rate_pct, sub="%"), unsafe_allow_html=True)
            with m3:
                flaky_count = len(analysis.flaky)
                st.markdown(
                    signal_ledger_html("Flaky Tests", flaky_count, tier="pass" if flaky_count == 0 else "fail"),
                    unsafe_allow_html=True,
                )
            with m4:
                failing_count = len(analysis.ever_failing)
                st.markdown(
                    signal_ledger_html("Ever-Failing", failing_count, tier="pass" if failing_count == 0 else "fail"),
                    unsafe_allow_html=True,
                )
```

(`Runs` uses a fixed `tier="hold"` — a run count is informational, not a quality signal, so it shouldn't flash green/red. `Flaky`/`Ever-Failing` are inverted from the default score-tier logic: zero is good here, not a high number, so the tier is picked explicitly rather than via `score_tier()`.)

- [ ] **Step 2: Add a regression test**

In `tests/test_app_v03.py`, add:

```python
def test_results_analysis_flaky_count_tier_is_inverted():
    from ledger_components import signal_ledger_html

    # Zero flaky tests is good news -> pass tier, not score_tier(0) == "fail".
    html_zero = signal_ledger_html("Flaky Tests", 0, tier="pass")
    assert "sl-score pass" in html_zero
    html_some = signal_ledger_html("Flaky Tests", 4, tier="fail")
    assert "sl-score fail" in html_some
```

- [ ] **Step 3: Run the test to verify it passes**

Run: `python -m pytest tests/test_app_v03.py -v -k flaky_count_tier`
Expected: `1 passed`

- [ ] **Step 4: Manual smoke test**

Run: `streamlit run src/app.py`, reach the "Review Project Context" step, expand "📊 Attach test execution results", upload a small JUnit XML file, and confirm the four metrics render as Signal Ledger cards with `Runs` always neutral-toned and `Flaky Tests`/`Ever-Failing` green when zero, red when nonzero.

- [ ] **Step 5: Commit**

```bash
git add src/app.py tests/test_app_v03.py
git commit -m "feat: render Results Analysis metrics as Signal Ledger cards"
```

---

### Task 8: Intake Ledger card styling

**Files:**
- Modify: `src/app.py:521-532` (inside `render_dialogue()`'s question loop)
- Modify: `src/app.py:403-404` (`render_intro()` — minor, uses the already-restyled `.sub-header`, no change needed beyond what Task 1 already did — verify only)

**Interfaces:**
- Consumes: the `.ledger-card` CSS class from Task 1's `theme.py`.

- [ ] **Step 1: Wrap each intake question in a ledger card**

In `src/app.py`, inside `render_dialogue()`, replace:

```python
    with st.form("dialogue_form"):
        for question in QUESTIONS:
            key = question["key"]
            st.markdown(f"**{question['question']}**")
            st.caption(f"💡 {question['hint']}")
            st.session_state.answers[key] = st.text_input(
                label=question["question"],
                value=st.session_state.answers.get(key, ""),
                key=f"input_{key}",
                label_visibility="collapsed",
            )
            st.markdown("###")
```

with:

```python
    with st.form("dialogue_form"):
        for idx, question in enumerate(QUESTIONS, start=1):
            key = question["key"]
            st.markdown(
                f'<div class="ledger-card">'
                f'<div class="idx">{idx:02d} / {len(QUESTIONS):02d}</div>'
                f'<div class="qtitle">{question["question"]}</div>'
                f"</div>",
                unsafe_allow_html=True,
            )
            st.caption(f"💡 {question['hint']}")
            st.session_state.answers[key] = st.text_input(
                label=question["question"],
                value=st.session_state.answers.get(key, ""),
                key=f"input_{key}",
                label_visibility="collapsed",
            )
            st.markdown("###")
```

(`question["question"]` values come from `dialogue.py`'s `QUESTIONS` constant — static, developer-authored strings, not user input, so this one spot is fine without `html.escape()`; every other task in this plan escapes because it renders LLM output or user uploads.)

- [ ] **Step 2: Manual smoke test**

Run: `streamlit run src/app.py`, click through to "Project Discovery", and confirm each of the 11 questions renders inside a bordered card with a `NN / 11` mono index label above the question text, followed immediately by its existing hint caption and text input (unchanged functionality — same single scrollable form, same validation on submit).

- [ ] **Step 3: Commit**

```bash
git add src/app.py
git commit -m "feat: apply ledger-card styling to the intake question list"
```

---

### Task 9: Full visual verification pass

**Files:** none (verification only)

- [ ] **Step 1: Run the full test suite**

Run: `python -m pytest tests/ -v`
Expected: all tests pass (baseline count plus the new tests from Tasks 1-3 and the additions to `test_app_v03.py` in Tasks 4-7).

- [ ] **Step 2: Run lint and type checks**

Run: `ruff check src/ tests/`
Expected: `All checks passed!`

Run: `mypy src/`
Expected: `Success: no issues found in N source files`

- [ ] **Step 3: Manual pass through every mode, both Streamlit themes**

Run: `streamlit run src/app.py`. For **both** Streamlit theme settings (Settings → Theme → Light, then Dark), walk through:
1. Intro page
2. Project Discovery (intake ledger cards)
3. Review Project Context (results-analysis Signal Ledger, if a file is attached)
4. Generated Test Strategy — all 4 tabs (Risk Register table, Effort confidence ledger, Test Strategy, Test Plan)
5. "Review an existing QA document" mode (Overall Score + per-dimension Signal Ledgers)

Confirm in each: text is legible against its background in both themes (no `ink`-on-`ink` or low-contrast combinations), the mono font is visibly applied to scores/IDs, focus rings are visible when tabbing through interactive elements, no raw HTML tags leak into the visible page (a sign of a missed `unsafe_allow_html=True` or an escaping bug), and **the sidebar wordmark + header lockup still render correctly and swap light/dark variant** (see the Global Constraints "Brand logo/wordmark is preserved" entry — nothing in Tasks 1-8 should have changed this, but confirm it directly rather than assuming).

- [ ] **Step 4: Compare against the approved design proposal**

Open the approved artifact (https://claude.ai/code/artifact/45b80d37-b43d-4fdb-974b-b82d72a8745c) side by side with the running app. Confirm: color tokens match, type roles match (condensed for headers, mono for scores/IDs, sans for body), and the Signal Ledger's visual shape (label, big score, meter) matches the mockup's Section 06 cluster cards. Note any deliberate deviations (e.g. the intake form staying single-page per this plan's Global Constraints) — these are expected, not bugs.

Also compare against the implementation-preview mockup (https://claude.ai/code/artifact/adaa57a5-26c0-45ba-9fdf-ae97a66bbb14), built directly from this plan's real content (the actual 11 dialogue questions, the actual 6 review dimensions, the real brand SVG/PNG logo swapping light/dark) — closer to a literal "after" screenshot than the original proposal.

- [ ] **Step 5: Commit any fixes found during verification**

If Step 3 or 4 surfaces a real bug (contrast, escaping, layout), fix it in the relevant file from Tasks 1-8 and commit as a normal fix commit — do not batch unrelated fixes into one commit.
