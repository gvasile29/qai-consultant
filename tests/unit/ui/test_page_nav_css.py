"""build_page_nav_css(): the in-page mode switcher's styles."""
from qai_consultant.ui.components import APP_MODES, build_page_nav_css, build_sidebar_nav_css
from qai_consultant.ui.theme import DARK_TOKENS, LIGHT_TOKENS


def test_active_mode_is_lit_in_the_accent():
    css = build_page_nav_css(DARK_TOKENS, "maturity")
    assert ".st-key-pagenav-maturity button:disabled" in css
    assert DARK_TOKENS["accent"] in css
    assert ".st-key-pagenav-doc_review button:disabled" not in css


def test_landing_or_unknown_mode_lights_nothing():
    for mode in (None, "intro", "nonsense"):
        assert "button:disabled" not in build_page_nav_css(LIGHT_TOKENS, mode)


def test_every_mode_gets_its_index():
    css = build_page_nav_css(DARK_TOKENS, None)
    for mode_id, idx, _label in APP_MODES:
        assert f'.st-key-pagenav-{mode_id} button p::before {{ content: "{idx}"' in css


def test_row_wraps_instead_of_overflowing_a_phone():
    css = build_page_nav_css(DARK_TOKENS, None)
    assert ".st-key-page-nav { flex-wrap: wrap" in css


def test_page_nav_and_sidebar_rules_do_not_catch_each_other():
    """The sidebar's rules select [class*="st-key-nav-"]; the page chips' keys
    (st-key-pagenav-*) must not contain that substring, and vice versa."""
    assert "st-key-pagenav-" not in build_sidebar_nav_css(DARK_TOKENS, "strategy")
    assert 'class*="st-key-nav-"' not in build_page_nav_css(DARK_TOKENS, "strategy")
