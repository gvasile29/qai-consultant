"""Phase 3 of the Mission Control redesign: the discovery wizard's phases and header."""

import re

from qai_consultant.core.dialogue import QUESTIONS
from qai_consultant.ui.components import DISCOVERY_PHASES, build_discovery_header_html
from qai_consultant.ui.theme import DARK_TOKENS, LIGHT_TOKENS


def test_phases_cover_every_question_once_in_order():
    keys = [k for _name, phase_keys in DISCOVERY_PHASES for k in phase_keys]
    assert keys == [q["key"] for q in QUESTIONS]


def test_header_has_one_segment_per_question_lit_when_answered():
    html = build_discovery_header_html(LIGHT_TOKENS, 0, {"project_name", "timeline"})
    assert len(re.findall(r'<i class="(?:on)?"></i>', html)) == len(QUESTIONS)
    assert html.count('<i class="on"></i>') == 2
    assert "2/11 instruments calibrated" in html


def test_header_marks_done_active_and_ahead_phases():
    html = build_discovery_header_html(LIGHT_TOKENS, 1, set())
    assert re.findall(r'class="dq-step (\w+)"', html) == ["done", "active", "ahead"]
    assert "phase 2 of 3" in html


def test_header_clamps_an_out_of_range_phase():
    assert "phase 3 of 3" in build_discovery_header_html(LIGHT_TOKENS, 9, set())
    assert "phase 1 of 3" in build_discovery_header_html(LIGHT_TOKENS, -2, set())


def test_header_ignores_keys_that_are_not_questions():
    assert "0/11" in build_discovery_header_html(LIGHT_TOKENS, 0, {"additional_context"})


def test_header_uses_the_theme_tokens_and_keeps_the_card_hover():
    light = build_discovery_header_html(LIGHT_TOKENS, 0, set())
    dark = build_discovery_header_html(DARK_TOKENS, 0, set())
    assert LIGHT_TOKENS["accent"] in light and DARK_TOKENS["accent"] not in light
    assert DARK_TOKENS["accent"] in dark
    assert ".ledger-card:hover" in light
