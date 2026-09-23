"""Tests for src/executive_readout.py and components.executive_readout_html()."""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from components import executive_readout_html
from effort_core import EstimationData
from executive_readout import build_readout

ROWS = [
    {"risk_id": "R03", "description": "Flaky CI", "likelihood": "High", "impact": "Low",
     "risk_level": "Medium", "priority": "3"},
    {"risk_id": "R01", "description": "Payment failure", "likelihood": "High", "impact": "High",
     "risk_level": "Critical", "priority": "1"},
    {"risk_id": "R02", "description": "Auth bypass", "likelihood": "Medium", "impact": "High",
     "risk_level": "High", "priority": "2"},
    {"risk_id": "R04", "description": "Slow reports", "likelihood": "Low", "impact": "Low",
     "risk_level": "Low", "priority": "4"},
]


def _effort(gap: float) -> EstimationData:
    data = EstimationData()
    data.final_effort_min = 42.0
    data.final_effort_max = 51.5
    data.available_person_days = 36.0
    data.capacity_gap = gap
    data.confidence_level = "Medium"
    data.confidence_score = 59
    return data


def test_nothing_to_summarize_returns_none_and_renders_empty():
    assert build_readout([], None) is None
    assert executive_readout_html(None) == ""


def test_overall_risk_is_highest_level_with_breakdown():
    readout = build_readout(ROWS, None)
    assert readout.overall_risk == "Critical"
    assert readout.risk_breakdown == "1 Critical · 1 High · 1 Medium · 1 Low"


def test_address_first_is_top_three_by_priority():
    readout = build_readout(ROWS, None)
    assert [rid for rid, _ in readout.address_first] == ["R01", "R02", "R03"]


def test_effort_capacity_and_confidence_come_from_estimation_data():
    readout = build_readout([], _effort(gap=-9.0))
    assert readout.effort_range == "42–51.5 person-days"
    assert readout.capacity == "36 person-days available — 9 short of expected effort"
    assert readout.capacity_deficit
    assert readout.confidence == "Medium (59/100)"

    surplus = build_readout([], _effort(gap=4.5))
    assert not surplus.capacity_deficit
    assert "4.5 above expected effort" in surplus.capacity


def test_html_escapes_llm_generated_descriptions():
    rows = [dict(ROWS[1], description="<script>alert(1)</script>")]
    html = executive_readout_html(build_readout(rows, _effort(gap=-1)))
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert 'class="sev fail"' in html  # Critical overall risk + capacity deficit
    assert "Executive readout" in html
