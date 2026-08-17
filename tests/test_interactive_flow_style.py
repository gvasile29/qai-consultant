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
