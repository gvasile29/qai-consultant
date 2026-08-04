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
    "surface": "#F5F3EA", "surface_2": "#E4E0D2",
    "ink": "#23281F", "ink_dim": "#5B5F52", "line": "#C9C3AF",
    "accent": "#3E6E85",
    "pass_": "#3F7A4C", "hold": "#9C6B1F", "fail": "#9C3F2C",
    "pass_bg": "#DCE7DA", "hold_bg": "#ECDFC7", "fail_bg": "#EAD7CF",
}

DARK_TOKENS = {
    "surface": "#212821", "surface_2": "#262E27",
    "ink": "#E6E8DF", "ink_dim": "#9BA69C", "line": "#3A453D",
    "accent": "#86ADC2",
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

/* Centers the top-of-page logo within its column. Scoped to the keyed
   container (not a blanket [data-testid="stImage"] rule) so it doesn't
   also apply to the sidebar's EU AI-generated-content icon below.
   Carried over verbatim from the pre-Calibration-Bench inline CSS block
   -- see this plan's Global Constraints. */
.st-key-header-logo [data-testid="stImage"] {{
    display: flex;
    justify-content: center;
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
