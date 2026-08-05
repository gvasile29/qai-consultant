"""Tests for src/theme.py -- the Calibration Bench CSS token system."""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from theme import LIGHT_TOKENS, DARK_TOKENS, build_css  # noqa: E402

_REQUIRED_KEYS = {
    "surface", "surface_2", "ink", "ink_dim", "line",
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
    # "ink" is used by .ledger-card .qtitle and table.risk-ledger td -- pick a
    # token that build_css() actually interpolates, not one merely defined in
    # the dict (there is no "bg" key -- see Task 1's Interfaces note on why).
    light_css = build_css(LIGHT_TOKENS)
    dark_css = build_css(DARK_TOKENS)
    assert LIGHT_TOKENS["ink"] in light_css
    assert DARK_TOKENS["ink"] not in light_css
    assert DARK_TOKENS["ink"] in dark_css
    assert LIGHT_TOKENS["ink"] not in dark_css


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
