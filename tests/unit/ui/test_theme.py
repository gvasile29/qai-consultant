"""Tests for src/qai_consultant/ui/theme.py -- the Ocean palette CSS token system."""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SRC_DIR = REPO_ROOT / "src"

from qai_consultant.ui.theme import LIGHT_TOKENS, DARK_TOKENS, build_css  # noqa: E402

_REQUIRED_KEYS = {
    "page", "surface", "surface_2", "ink", "ink_dim", "line",
    "accent", "pass_", "hold", "fail",
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
    # "accent" is interpolated by build_css() and unique to its theme. "ink"
    # is not usable here: the Ocean palette swaps navy and off-white between
    # themes, so one theme's ink is the other's page color.
    light_css = build_css(LIGHT_TOKENS)
    dark_css = build_css(DARK_TOKENS)
    assert LIGHT_TOKENS["accent"] in light_css
    assert DARK_TOKENS["accent"] not in light_css
    assert DARK_TOKENS["accent"] in dark_css
    assert LIGHT_TOKENS["accent"] not in dark_css


def test_build_css_respects_reduced_motion_and_focus_visibility():
    css = build_css(LIGHT_TOKENS)
    assert "prefers-reduced-motion" in css
    assert ":focus-visible" in css


def test_build_css_preserves_header_logo_centering_rule():
    # This rule scopes centering to ONLY the header logo's st.container(key="header-logo")
    # (src/app.py:1339-1345), not the sidebar's separate EU AI icon st.image() call
    # (src/app.py:295) -- dropping it silently uncenters the header logo. See this
    # plan's Global Constraints and CLAUDE.md's "Streamlit CSS scoping" gotcha.
    css = build_css(LIGHT_TOKENS)
    assert '.st-key-header-logo [data-testid="stImage"]' in css


def test_build_css_keeps_the_sidebar_reopen_button_reachable():
    # The button that reopens a collapsed sidebar (stExpandSidebarButton) lives
    # inside stHeader > stToolbar. Hiding either with display:none strands the
    # mode switcher, the AI notice and Start Over once the sidebar is closed --
    # measured in a browser, not assumed. Only the menu and toolbar actions go.
    css = build_css(DARK_TOKENS)
    hidden = css[css.index('[data-testid="stToolbarActions"]'):]
    hidden = hidden[:hidden.index("}")]
    assert "display: none" in hidden
    assert '[data-testid="stMainMenu"]' in hidden
    for selector in ('[data-testid="stHeader"]', '[data-testid="stToolbar"]', "stExpandSidebarButton"):
        assert selector not in hidden


def _luminance(hex_color: str) -> float:
    channels = [int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast(a: str, b: str) -> float:
    hi, lo = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def test_primary_button_label_clears_aa_on_both_themes():
    # Streamlit fills a primary button with primaryColor (the accent token) and
    # labels it white: 1.86:1 on the dark theme's teal, measured in a browser.
    # build_css() relabels it with the page color instead.
    for tokens in (LIGHT_TOKENS, DARK_TOKENS):
        css = build_css(tokens)
        rule = css[css.index('button[data-testid="stBaseButton-primary"]:not(:disabled),'):]
        rule = rule[:rule.index("}") + 1]
        assert f"color: {tokens['page']};" in rule
        assert _contrast(tokens["accent"], tokens["page"]) >= 4.5


def test_build_css_hides_the_local_deploy_button():
    hidden = build_css(DARK_TOKENS)
    hidden = hidden[hidden.index('[data-testid="stToolbarActions"]'):]
    assert '[data-testid="stAppDeployButton"]' in hidden[:hidden.index("}")]

