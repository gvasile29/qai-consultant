"""Regression tests for the MCP end-to-end findings F1/F2/F3/F12/F13 in effort_core:
timeline unit parsing, unparseable-timeline warnings, team-size parsing,
confidence plausibility caps and unrecognised compliance/project-type warnings."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import effort_core  # noqa: E402
from dialogue import ProjectContext  # noqa: E402
from effort_core import compute_estimation, parse_duration, parse_team_size  # noqa: E402


def _ctx(**kw) -> ProjectContext:
    d = dict(
        project_name="P", project_description="d", project_type="web application",
        tech_stack="React", team_qa_size="3 engineers", team_dev_size="6 developers",
        timeline="6 months", methodology="Agile", known_risks="none",
        existing_automation="Full CI with Selenium", compliance_requirements="none",
    )
    d.update(kw)
    return ProjectContext(**d)


def _dur(s):
    w = []
    return parse_duration(s, w), w


# ── F1: units ───────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("text,expected", [
    ("2 days", 2),
    ("10 working days", 10),
    ("10 business days", 10),
    ("90 days", 64),
    ("3 weeks", 15),
    ("6 months", 126),
    ("1 year", 230),
    ("2 quarters", 126),
    ("1 quarter", effort_core.WORKING_DAYS_PER_QUARTER),
    ("3 sprints", 30),
    ("6 sprints of 3 weeks", 90),
    ("4 3-week sprints", 60),
    ("1 year and 3 months", 230 + 63),
    ("6 zile", 6),
    ("3 saptamani", 15),
    ("3 săptămâni", 15),
    ("6 luni", 126),
    ("2 ani", 460),
    ("un trimestru", 63),
    ("2 trimestre", 126),
    ("three months", 63),
    ("a year", 230),
])
def test_parse_duration_units(text, expected):
    days, warnings = _dur(text)
    assert days == expected
    assert not [w for w in warnings if "could not parse" in w]


def test_parse_duration_restatement_in_parentheses_not_double_counted():
    assert _dur("6 months (24 weeks)")[0] == 126
    assert _dur("6 months or 26 weeks")[0] == 126


def test_parse_duration_range_uses_midpoint_with_warning():
    days, warnings = _dur("3-4 months")
    assert days == 4 * 21
    assert any("range" in w for w in warnings)


def test_bare_number_keeps_legacy_months_but_warns():
    days, warnings = _dur("6")
    assert days == 126
    assert any("no unit" in w for w in warnings)


def test_calendar_year_is_not_a_duration():
    days, warnings = _dur("release in June 2026")
    assert days == effort_core.DEFAULT_DURATION_DAYS
    assert warnings


# ── F2: unparseable timelines ─────────────────────────────────────────────────

@pytest.mark.parametrize("text", ["Dec 2026", "Q1 2027", "until end of Q1 2027", "ASAP", "soon", ""])
def test_unparseable_timeline_warns_and_names_default(text):
    days, warnings = _dur(text)
    assert days == effort_core.DEFAULT_DURATION_DAYS
    assert any(str(effort_core.DEFAULT_DURATION_DAYS) in w for w in warnings)


def test_a_few_weeks_is_three_weeks_with_assumed_warning():
    days, warnings = _dur("a few weeks")
    assert days == 15
    assert any("vague" in w and "assumed 3" in w for w in warnings)


def test_warnings_surface_on_estimation_data():
    data = compute_estimation(_ctx(timeline="Q1 2027"))
    assert any("timeline" in w and "could not parse" in w for w in data.warnings)
    assert data.project_duration_days == effort_core.DEFAULT_DURATION_DAYS


def test_clean_input_has_no_warnings():
    assert compute_estimation(_ctx()).warnings == []


# ── F3: team size ───────────────────────────────────────────────────────────────

def _team(s):
    w = []
    return parse_team_size(s, w, "team_qa_size"), w


@pytest.mark.parametrize("text,expected", [
    ("2-3", 3), ("8 to 10", 9), ("2 – 4 engineers", 3),
    ("three", 3), ("eight", 8), ("three and eight", 11), ("trei", 3), ("opt", 8),
    ("3 frontend + 2 backend, or 5 full-stack", 5),
    ("none", 0), ("no dedicated QA", 0), ("developers test", 0),
])
def test_parse_team_size(text, expected):
    assert _team(text)[0] == expected


def test_team_range_warns():
    assert any("range" in w for w in _team("2-3")[1])


def test_none_detection_is_whole_word():
    assert _team("Nonetheless 4 testers")[0] == 4
    assert _team("5 engineers (one nonexistent role)")[0] == 6


def test_team_without_number_warns():
    n, w = _team("some people")
    assert n == 1 and any("no number" in x for x in w)


def test_misparsed_number_words_no_longer_inflate_confidence():
    data = compute_estimation(_ctx(team_qa_size="three", team_dev_size="eight"))
    assert data.qa_team_size == 3
    assert data.team_total_size == 11


# ── F12: confidence plausibility ───────────────────────────────────────────────

def test_qa_team_far_larger_than_dev_team_cannot_be_high():
    data = compute_estimation(_ctx(team_qa_size="10", team_dev_size="2"))
    assert data.confidence_level != "High"
    assert any("3x the dev team" in w for w in data.warnings)


def test_extreme_shortfall_is_low_with_warning():
    data = compute_estimation(_ctx(team_qa_size="40", team_dev_size="400", timeline="3 years"))
    assert data.capacity_gap < 0
    assert data.confidence_level == "Low"
    assert any("shortfall" in w.lower() for w in data.warnings)


def test_very_low_data_quality_caps_at_medium():
    data = effort_core.EstimationData()
    data.pert_total_optimistic, data.pert_total_expected, data.pert_total_pessimistic = 90, 100, 100
    data.capacity_gap = 100
    data.data_quality_score = 4
    data.total_multiplier = 0
    assert effort_core.calculate_confidence(data) == "Medium"
    assert any("Data quality" in w for w in data.warnings)


def test_healthy_estimate_is_still_high():
    data = compute_estimation(_ctx(team_qa_size="3", team_dev_size="6", timeline="6 months",
                                   compliance_requirements="GDPR"))
    assert data.capacity_gap > 0
    assert data.confidence_level in ("High", "Medium")
    assert data.warnings == []


# ── F13: compliance / project type ─────────────────────────────────────────────

@pytest.mark.parametrize("text,label", [
    ("SOC 2", "SOC 2"), ("PSD2", "PSD2"), ("ISO 27001", "ISO 27001"),
    ("EU AI Act", "EU AI Act"), ("NIS2", "NIS2"), ("DORA", "DORA"),
])
def test_new_compliance_regimes_apply_a_multiplier(text, label):
    data = compute_estimation(_ctx(compliance_requirements=text))
    assert any(label in reason for reason, _ in data.multipliers)
    assert not any("not recognised" in w for w in data.warnings)


def test_unrecognised_compliance_item_warns_and_has_no_effect():
    base = compute_estimation(_ctx(compliance_requirements="GDPR"))
    data = compute_estimation(_ctx(compliance_requirements="GDPR, Sarbanes-Oxley, FedRAMP"))
    assert data.total_multiplier == base.total_multiplier
    msg = next(w for w in data.warnings if "not recognised" in w)
    assert "Sarbanes-Oxley" in msg and "FedRAMP" in msg and "GDPR" not in msg.split("Recognised")[0]


@pytest.mark.parametrize("text", ["none", "N/A", "No compliance requirements", "None"])
def test_no_compliance_does_not_warn(text):
    assert compute_estimation(_ctx(compliance_requirements=text)).warnings == []


def test_ai_llm_project_types_map_to_data_band():
    for pt in ("LLM chatbot", "AI/ML platform", "GenAI assistant", "machine learning pipeline"):
        data = compute_estimation(_ctx(project_type=pt))
        assert data.project_type_detected == "data", pt


def test_short_keywords_do_not_match_inside_words():
    # "ai" inside "retail"/"email" and "rest" inside "restaurant" used to mis-type projects
    assert compute_estimation(_ctx(project_type="retail email kiosk")).project_type_detected == "default"
    assert compute_estimation(_ctx(project_type="restaurant kiosk")).project_type_detected == "default"


def test_unrecognised_project_type_warns():
    data = compute_estimation(_ctx(project_type="quantum blockchain thing"))
    assert data.project_type_detected == "default"
    assert any("project_type" in w and "not recognised" in w for w in data.warnings)
