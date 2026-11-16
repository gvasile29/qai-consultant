"""Phase 2 of the Mission Control redesign: mission clock, readout tiles, risk map."""

import re

from qai_consultant.core.effort_core import EstimationData
from qai_consultant.generation.executive_readout import ExecutiveReadout, build_readout
from qai_consultant.ui.components import (
    build_readout_tiles_html,
    build_risk_map_html,
    build_stage_sequence_html,
    format_mission_clock,
)
from qai_consultant.ui.theme import DARK_TOKENS, LIGHT_TOKENS

ROWS = [
    {"risk_id": "R01", "description": "Payment failure", "likelihood": "High", "impact": "High",
     "risk_level": "Critical", "priority": "1"},
    {"risk_id": "R02", "description": "Auth bypass", "likelihood": "Medium", "impact": "Critical",
     "risk_level": "High", "priority": "2"},
    {"risk_id": "R03", "description": "Flaky CI", "likelihood": "High", "impact": "Low",
     "risk_level": "Medium", "priority": "3"},
    {"risk_id": "R04", "description": "Slow reports", "likelihood": "Low", "impact": "Low",
     "risk_level": "Low", "priority": "4"},
]


def _effort(gap: float) -> EstimationData:
    data = EstimationData()
    data.final_effort_min = 42.0
    data.final_effort_max = 51.5
    data.pert_total_expected = 46.2
    data.available_person_days = 36.0
    data.capacity_gap = gap
    data.confidence_level = "Medium"
    data.confidence_score = 59
    return data


# ── Mission clock ──────────────────────────────────────────────────────────

def test_mission_clock_formats_minutes_past_an_hour():
    assert format_mission_clock(0) == "T+ 00:00"
    assert format_mission_clock(75.9) == "T+ 01:15"
    assert format_mission_clock(3725) == "T+ 62:05"
    assert format_mission_clock(-4) == "T+ 00:00"


def test_stage_sequence_without_elapsed_has_no_clock_and_no_script():
    html = build_stage_sequence_html(LIGHT_TOKENS, [("Risk", "done")])
    assert 'class="mc-clock"' not in html and "<script" not in html


def test_stage_sequence_with_elapsed_carries_elapsed_not_an_epoch():
    # Elapsed seconds, not a server timestamp: the browser clock may be skewed.
    html = build_stage_sequence_html(LIGHT_TOKENS, [("Risk", "active")], elapsed_s=125.4)
    assert 'data-elapsed="125"' in html
    assert "T+ 02:05" in html
    assert "<script>" in html and "window.__qaiMissionTick" in html


def test_stage_items_are_numbered_in_order():
    html = build_stage_sequence_html(LIGHT_TOKENS, [("Risk", "done"), ("Effort", "active")])
    assert re.findall(r'class="stage-idx">(\d+)<', html) == ["01", "02"]


def test_stage_sequence_respects_reduced_motion():
    assert "prefers-reduced-motion" in build_stage_sequence_html(LIGHT_TOKENS, [("Risk", "active")])


# ── Readout tiles ──────────────────────────────────────────────────────────

def test_tiles_none_or_empty_readout_renders_nothing():
    assert build_readout_tiles_html(LIGHT_TOKENS, None) == ""
    assert build_readout_tiles_html(LIGHT_TOKENS, ExecutiveReadout()) == ""


def test_tiles_show_the_four_numbers_and_address_first():
    html = build_readout_tiles_html(LIGHT_TOKENS, build_readout(ROWS, _effort(gap=-10.2)))
    for label in ("Overall risk", "Expected QA effort", "Team capacity", "Estimate confidence", "Address first"):
        assert label in html
    assert '<div class="mr-tile fail"><div class="mr-label">Overall risk' in html
    assert ">46.2<span class=\"mr-unit\">person-days</span>" in html
    assert "Deficit" in html
    assert '<div class="mr-tile hold"><div class="mr-label">Estimate confidence' in html
    assert "59/100" in html
    assert html.index("R01") < html.index("R02") < html.index("R03")


def test_tiles_capacity_ok_is_pass():
    html = build_readout_tiles_html(LIGHT_TOKENS, build_readout([], _effort(gap=3.0)))
    assert '<div class="mr-tile pass"><div class="mr-label">Team capacity' in html
    assert "Address first" not in html


def test_tiles_escape_llm_text():
    readout = ExecutiveReadout(overall_risk="High", address_first=[("R9<b>", "<img src=x onerror=1>")])
    html = build_readout_tiles_html(LIGHT_TOKENS, readout)
    assert "<img" not in html and "&lt;img" in html and "R9&lt;b&gt;" in html


def test_tiles_have_no_dash_punctuation():
    html = build_readout_tiles_html(DARK_TOKENS, build_readout(ROWS, _effort(gap=-1)))
    assert "—" not in html and "–" not in html


# ── Risk map ───────────────────────────────────────────────────────────────

def _cell_contents(html: str) -> list:
    return re.findall(r'<div class="rm-cell[^"]*">(.*?)</div>', html)


def test_risk_map_empty_rows_renders_nothing():
    assert build_risk_map_html(LIGHT_TOKENS, []) == ""


def test_risk_map_places_each_risk_in_its_cell():
    cells = _cell_contents(build_risk_map_html(LIGHT_TOKENS, ROWS))
    assert len(cells) == 9
    # Row order is High, Medium, Low likelihood; columns Low, Medium, High impact.
    assert "R03" in cells[0] and "R01" in cells[2]
    assert "R02" in cells[5]  # "Critical" impact counts as high
    assert "R04" in cells[6]


def test_risk_map_colors_chips_by_stated_risk_level():
    html = build_risk_map_html(LIGHT_TOKENS, ROWS)
    assert 'class="rm-chip fail"' in html and 'class="rm-chip pass"' in html


def test_risk_map_lists_unreadable_rows_instead_of_dropping_them():
    rows = ROWS + [{"risk_id": "R05", "description": "x", "likelihood": "?", "impact": "High",
                    "risk_level": "High", "priority": "5"}]
    html = build_risk_map_html(LIGHT_TOKENS, rows)
    assert "Not plotted" in html and "R05" in html.split("Not plotted")[1]


def test_risk_map_escapes_ids_and_descriptions():
    rows = [{"risk_id": "<s>", "description": '"><script>', "likelihood": "Low", "impact": "Low",
             "risk_level": "Low", "priority": "1"}]
    html = build_risk_map_html(LIGHT_TOKENS, rows)
    assert "<script>" not in html and "&lt;s&gt;" in html
