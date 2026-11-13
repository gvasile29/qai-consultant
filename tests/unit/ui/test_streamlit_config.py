"""Tests for .streamlit/config.toml -- the Streamlit-side half of the theme.

Streamlit paints the page, the widgets and the sidebar from config.toml;
src/qai_consultant/ui/theme.py paints everything the app draws itself. The two
are separate files with no shared source, so these tests are what keeps a
palette change in one from silently missing the other.
"""
from pathlib import Path

import pytest

tomllib = pytest.importorskip("tomllib")  # stdlib from Python 3.11; pyproject allows 3.10

from qai_consultant.ui.theme import DARK_TOKENS, LIGHT_TOKENS

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
CONFIG_PATH = REPO_ROOT / ".streamlit" / "config.toml"

_CONFIG_KEY_TO_TOKEN = {
    "backgroundColor": "page",
    "secondaryBackgroundColor": "surface",
    "textColor": "ink",
    "primaryColor": "accent",
    "borderColor": "line",
}


def _theme() -> dict:
    return tomllib.loads(CONFIG_PATH.read_text(encoding="utf-8"))["theme"]


@pytest.mark.parametrize("table, tokens", [("dark", DARK_TOKENS), ("light", LIGHT_TOKENS)])
def test_config_colors_match_the_theme_tokens(table, tokens):
    section = _theme()[table]
    assert set(section) == set(_CONFIG_KEY_TO_TOKEN) | {"showWidgetBorder"}
    for config_key, token in _CONFIG_KEY_TO_TOKEN.items():
        assert section[config_key] == tokens[token], f"[theme.{table}] {config_key} drifted from tokens[{token!r}]"


def test_config_does_not_pin_one_theme():
    # A top-level `base` or color forces every visitor onto one theme and
    # st.context.theme.type stops following the browser, which is what picks
    # the logo variant and the token set.
    theme = _theme()
    assert set(theme) == {"dark", "light"}


def test_brand_backgrounds_are_the_ocean_pair():
    # assets/brand/README_BRAND.md: #0F172A and #F1F5F9 are the two brand
    # backgrounds the logo variants are drawn for.
    assert DARK_TOKENS["page"] == "#0F172A"
    assert LIGHT_TOKENS["page"] == "#F1F5F9"


@pytest.mark.parametrize("table", ["dark", "light"])
def test_input_widgets_keep_a_border(table):
    # Streamlit fills inputs with secondaryBackgroundColor, which is the
    # "surface" token the app's cards use. Seen in a browser on the Document
    # Review tray: with the border off, the textarea, select and uploader had
    # no visible edge in either theme.
    assert _theme()[table]["showWidgetBorder"] is True
