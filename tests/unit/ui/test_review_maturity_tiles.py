"""Tiles on the Document Review and QA Maturity result screens."""
import re

import pytest

from qai_consultant.ui.components import (
    build_score_grid_html,
    maturity_level_tier,
    score_tier,
    signal_ledger_html,
)


@pytest.mark.parametrize("level,tier", [(1, "fail"), (2, "hold"), (3, "pass")])
def test_maturity_level_tier(level, tier):
    assert maturity_level_tier(level) == tier


def test_top_level_is_not_read_as_a_failing_score():
    """Regression: the level (1-3) went through score_tier(), so the maximum
    level 3 rendered as a red 3 out of 100 with an empty meter."""
    assert score_tier(3) == "fail"
    html = signal_ledger_html(
        "Indicative TMMi Level", 3, tier=maturity_level_tier(3), segments=3, filled=3
    )
    assert 'class="sl-score pass"' in html
    assert html.count('class="on pass"') == 3
    assert html.count("<i") == 3


def test_meter_has_one_segment_per_scale_step():
    html = signal_ledger_html("Level", 2, tier="hold", segments=3, filled=2)
    assert html.count('class="on hold"') == 2
    assert html.count("<i></i>") == 1


def test_default_meter_is_unchanged_for_a_percent_score():
    html = signal_ledger_html("Overall Score", 70)
    assert html.count('class="on hold"') == 7
    assert html.count("<i></i>") == 3


def test_filled_is_clamped_to_the_scale():
    assert signal_ledger_html("x", 0, segments=3, filled=9).count("<i></i>") == 0
    assert signal_ledger_html("x", 0, segments=3, filled=-4).count('class="on') == 0


def test_score_grid_has_a_card_per_item_and_the_requested_columns():
    html = build_score_grid_html([("test_planning", 100), ("test_environment", 50)], per_row=3)
    assert html.count('class="signal-ledger"') == 2
    assert "--cols: 3" in html
    assert "Test Planning" in html and "Test Environment" in html


def test_score_grid_is_two_columns_on_a_phone():
    html = build_score_grid_html([("a", 1)])
    m = re.search(r"@media \(max-width: 640px\) \{[^}]*repeat\(2, minmax\(0, 1fr\)\)", html)
    assert m, "no two-column rule below 640px"


def test_score_grid_escapes_labels():
    html = build_score_grid_html([("<img src=x onerror=alert(1)>", 50)])
    assert "<img" not in html.lower()
    assert "&lt;img" in html.lower()


def test_header_logo_is_smaller_on_a_phone():
    from qai_consultant.ui.theme import DARK_TOKENS, build_css

    css = build_css(DARK_TOKENS)
    m = re.search(r"@media \(max-width: 640px\) \{\s*\.st-key-header-logo \.header-logo \{ max-width: (\d+)px", css)
    assert m and int(m.group(1)) < 280
