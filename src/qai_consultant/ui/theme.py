"""
QAI Consultant -- visual identity system (Ocean palette).

Token-based CSS built on the brand's Ocean palette (assets/brand/README_BRAND.md):
navy #0F172A and off-white #F1F5F9 swap roles between the dark and light
themes, with the logo's teal as the accent. Three signal colors
(pass/hold/fail) carry real meaning everywhere they're used -- never
decorative.

The page background, text and widget colors come from
.streamlit/config.toml's [theme.dark] / [theme.light] tables, which
tests/unit/ui/test_streamlit_config.py keeps in step with the tokens below.

inject_theme_css() picks the token set from st.context.theme.type, the
exact mechanism app.py's st.logo() call already uses to pick the light/dark
logo variant (see app.py's page-config section) -- None/unset falls back
to the light set, matching that existing code's else branch.
"""
import streamlit as st

from qai_consultant.ui._theme_fonts import COND_700, MONO_400, MONO_500, SANS_400, SANS_600

# "page" is the Streamlit page background (config.toml backgroundColor);
# "surface" is a card sitting on it, "surface_2" a track or inset inside a card.
# On light backgrounds text-colored accent uses a darker teal than the logo's
# #14B8A6, which only reaches 2.5:1 against #F1F5F9.
LIGHT_TOKENS = {
    "page": "#F1F5F9",
    "surface": "#FFFFFF", "surface_2": "#E2E8F0",
    "ink": "#0F172A", "ink_dim": "#475569", "line": "#CBD5E1",
    "accent": "#0F766E",
    "pass_": "#047857", "hold": "#92400E", "fail": "#B91C1C",
    "pass_bg": "#D1FAE5", "hold_bg": "#FEF3C7", "fail_bg": "#FEE2E2",
}

DARK_TOKENS = {
    "page": "#0F172A",
    "surface": "#17223B", "surface_2": "#243049",
    "ink": "#F1F5F9", "ink_dim": "#9FB0C7", "line": "#334155",
    "accent": "#2DD4BF",
    "pass_": "#6EE7B7", "hold": "#FCD34D", "fail": "#FDA4AF",
    "pass_bg": "#1B3836", "hold_bg": "#3A3320", "fail_bg": "#4A2630",
}


def build_css(tokens: dict) -> str:
    """Pure function: token dict -> full <style> block. Kept pure (no
    Streamlit calls) so it's directly unit-testable without a Streamlit
    runtime -- see tests/unit/ui/test_theme.py."""
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
.st-key-header-logo [data-testid="stImage"],
.st-key-header-logo .header-logo-wrap {{
    display: flex;
    justify-content: center;
}}
.st-key-header-logo .header-logo {{ max-width: 100%; height: auto; }}

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
    font-size: 0.64rem;
    letter-spacing: 0.03em;
    overflow-wrap: normal;
    word-break: normal;
    hyphens: none;
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

/* Streamlit's own header bar: its menu and toolbar actions are hidden. The
   header itself must stay in the DOM -- the button that reopens a collapsed
   sidebar lives inside it (stExpandSidebarButton), so display:none on
   stHeader or stToolbar strands everything in the sidebar. It also keeps its
   opaque page-colored fill: made transparent, scrolled content showed through
   behind the logo and the reopen button (seen at phone width). */
[data-testid="stToolbarActions"],
[data-testid="stAppDeployButton"],
[data-testid="stMainMenu"] {{ display: none; }}

/* Primary buttons: Streamlit labels them white, which measured 1.86:1 on the
   dark theme's teal. The page color is navy there and off-white on the light
   theme's dark teal, so the label clears 4.5:1 on both. Disabled buttons keep
   Streamlit's own greyed pair. */
button[data-testid="stBaseButton-primary"]:not(:disabled),
button[data-testid="stBaseButton-primary"]:not(:disabled):hover,
button[data-testid="stBaseButton-primary"]:not(:disabled):active,
button[data-testid="stBaseButton-primary"]:not(:disabled):focus-visible,
button[data-testid="stBaseButton-primary"]:not(:disabled) p {{ color: {tokens['page']}; }}

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
