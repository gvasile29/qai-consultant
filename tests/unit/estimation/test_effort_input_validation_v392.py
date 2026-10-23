"""v3.9.2 end-user findings F1/F2/F10/N1/N2 for estimate_qa_effort inputs."""
import pytest

from qai_consultant.core.dialogue import ProjectContext
from qai_consultant.core.effort_core import (
    compute_estimation,
    parse_team_size,
    validate_numeric_inputs,
)


def _ctx(**kw):
    base = dict(
        project_name="P", project_description="d", project_type="web", tech_stack="python",
        team_qa_size="2", team_dev_size="4", timeline="6 months", methodology="agile",
        known_risks="none", existing_automation="some unit tests",
        compliance_requirements="none",
    )
    base.update(kw)
    return ProjectContext(**base)


@pytest.mark.parametrize("qa,dev,tl,field", [
    ("-3", "4", "6 months", "team_qa_size"),
    ("2", "-5", "6 months", "team_dev_size"),
    ("2", "4", "-2 months", "timeline"),
    ("minus two", "4", "6 months", "team_qa_size"),
    ("2", "4", "0 months", "timeline"),
    ("2", "4", "0", "timeline"),
])
def test_rejects_negative_and_zero(qa, dev, tl, field):
    assert field in validate_numeric_inputs(qa, dev, tl)


@pytest.mark.parametrize("qa,dev,tl", [
    ("2-3", "8 to 10", "3-4 months"),
    ("2", "0", "6 months"),
    ("3 frontend + 2 backend", "4", "1 year 3 months"),
])
def test_accepts_valid(qa, dev, tl):
    assert validate_numeric_inputs(qa, dev, tl) == {}


@pytest.mark.parametrize("text,expected", [
    ("2.5", 3), ("2,5", 3), ("0.5", 1), ("1.0", 1), ("3.4", 3), ("two", 2), ("2-3", 3),
])
def test_decimal_team_sizes_rounded_half_up(text, expected):
    w = []
    assert parse_team_size(text, w, "team_qa_size") == expected


def test_decimal_warns_with_original_and_used_value():
    w = []
    parse_team_size("2.5", w, "team_qa_size")
    assert any("2.5" in m and "3" in m for m in w)
    w2 = []
    parse_team_size("1.0", w2, "team_qa_size")
    assert not w2


def test_decimal_does_not_sum_digits():
    d = compute_estimation(_ctx(team_qa_size="2.5", team_dev_size="4"))
    assert d.qa_team_size == 3 and d.team_total_size == 7


def test_capacity_status_and_note():
    d = compute_estimation(_ctx(team_qa_size="20", team_dev_size="4"))
    assert d.capacity_gap > 0 and d.capacity_status == "surplus"
    assert "POSITIVE" in d.capacity_note and "surplus" in d.capacity_note
    d = compute_estimation(_ctx(team_qa_size="1", team_dev_size="10", timeline="1 month"))
    assert d.capacity_gap < 0 and d.capacity_status == "deficit"


def test_confidence_note_reports_data_quality_scale():
    d = compute_estimation(_ctx())
    assert d.data_quality_max == 20
    assert "/20" in d.confidence_note
    vague = compute_estimation(_ctx(timeline="unknown?", team_qa_size="not sure",
                                    team_dev_size="tbd", compliance_requirements="unknown",
                                    existing_automation=""))
    assert vague.data_quality_score <= 8
    assert vague.confidence_level != "High"
    assert any("capped at Medium" in w for w in vague.warnings)


def test_confidence_deterministic():
    a = compute_estimation(_ctx())
    b = compute_estimation(_ctx())
    assert (a.confidence_level, a.confidence_note) == (b.confidence_level, b.confidence_note)


def test_methodology_note_only_when_it_matters():
    mobile = compute_estimation(_ctx(project_type="mobile app", methodology="Waterfall"))
    assert "label only" in mobile.methodology_note
    web_wf = compute_estimation(_ctx(methodology="Waterfall"))
    assert web_wf.methodology_note == ""
    assert compute_estimation(_ctx(methodology="Chaos")).methodology_note.startswith("methodology 'Chaos'")


@pytest.mark.parametrize("c", ["none", "None", "n/a", "N/A", "not applicable", "No compliance"])
def test_no_compliance_values_do_not_warn(c):
    d = compute_estimation(_ctx(compliance_requirements=c))
    assert not any("Compliance item" in w for w in d.warnings)
