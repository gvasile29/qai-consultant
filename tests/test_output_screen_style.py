"""Tests for src/output_screen_style.py -- Phase 3 output-screen styling,
shared by render_strategy() and render_doc_review(). See
docs/superpowers/specs/2026-08-17-output-screens-power-on-redesign-design.md."""
import re
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


def test_content_polish_css_scopes_hover_color_away_from_primary_buttons():
    # Regression guard: Streamlit's default primaryColor is red (#FF4B4B)
    # with a white label; repainting a primary button's label to this app's
    # blue accent on hover leaves near-illegible contrast against the still-
    # red fill. border-color has no such conflict and stays unscoped; the
    # `color` override must exclude buttons whose real rendered <button>
    # carries data-testid="stBaseButton-primary" (confirmed via a live
    # Streamlit + Playwright DOM probe -- see this module's docstring).
    html = build_content_polish_css(LIGHT_TOKENS)
    assert 'button:not([data-testid$="-primary"]):hover {' in html
    color_rule_start = html.index('button:not([data-testid$="-primary"]):hover {')
    color_rule_body = html[color_rule_start:html.index("}", color_rule_start)]
    assert "color:" in color_rule_body
    assert "border-color:" not in color_rule_body

    border_rule_start = html.index("button:hover,")
    border_rule_body = html[border_rule_start:html.index("}", border_rule_start)]
    assert "border-color:" in border_rule_body
    # A bare "color:" declaration (not "border-color:", and not the word
    # "color" inside the transition property list) must NOT be present here.
    assert not re.search(r"(?<!-)color:\s*#", border_rule_body)


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
