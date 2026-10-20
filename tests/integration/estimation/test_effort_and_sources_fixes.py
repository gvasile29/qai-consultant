"""Regression tests for the v3.7.2 live-QA findings: effort table totals,
range/confidence explanations, and Knowledge Sources numbering/names."""
import re
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent / "src"))

from dialogue import ProjectContext  # noqa: E402
from effort_core import (  # noqa: E402
    capacity_utilization_pct,
    compute_estimation,
    confidence_breakdown,
    explain_effort_range,
)
from executive_readout import build_readout  # noqa: E402
from source_labels import build_source_labels, display_name  # noqa: E402


def _ctx(**kw):
    base = dict(
        project_name="X", project_type="web app", methodology="agile",
        team_dev_size="6", team_qa_size="3", timeline="4 months",
        compliance_requirements="GDPR", existing_automation="none",
        known_risks="integration", tech_stack="python",
    )
    base.update(kw)
    return ProjectContext(**base)


GOLDEN = [
    _ctx(),
    _ctx(project_type="embedded ECU", methodology="v-model", compliance_requirements="ASIL D, A-SPICE level 3",
         team_dev_size="12", team_qa_size="2", timeline="9 months"),
    _ctx(project_type="mobile app", team_dev_size="3", team_qa_size="1", timeline="8 weeks", existing_automation="some unit tests"),
    _ctx(project_type="api", team_dev_size="4", team_qa_size="2", timeline="2 months", compliance_requirements="PCI-DSS"),
    _ctx(project_type="data pipeline", team_dev_size="7", team_qa_size="4", timeline="1 year", tech_stack="legacy cobol"),
]


# ── Finding 1: displayed total == sum of displayed rows ───────────────────────

@pytest.mark.parametrize("ctx", GOLDEN)
def test_pert_totals_equal_sum_of_rows(ctx):
    d = compute_estimation(ctx)
    for key, total in (
        ("optimistic", d.pert_total_optimistic),
        ("most_likely", d.pert_total_most_likely),
        ("pessimistic", d.pert_total_pessimistic),
        ("expected", d.pert_total_expected),
    ):
        assert round(sum(a[key] for a in d.pert_activities), 1) == total, key


@pytest.mark.parametrize("ctx", GOLDEN)
def test_rendered_report_table_total_row_matches_rows(ctx):
    from effort_estimator import EffortEstimator
    est = EffortEstimator(MagicMock())
    d = compute_estimation(ctx)
    table = est._build_pert_table(d).splitlines()[2:]
    values = [[float(v) for v in re.findall(r"(\d+\.?\d*)d", row)[:4]] for row in table]
    *rows, total = values
    for col in range(4):
        assert round(sum(r[col] for r in rows), 1) == total[col]


def test_capacity_gap_and_percent_use_displayed_expected_total():
    d = compute_estimation(GOLDEN[0])
    assert d.capacity_gap == round(d.available_person_days - d.pert_total_expected, 1)
    pct = capacity_utilization_pct(d)
    assert pct == round(d.pert_total_expected / d.available_person_days * 100)


# ── Finding 2: range / deficit explanation ────────────────────────────────────

def test_range_explanation_uses_real_numbers():
    d = compute_estimation(GOLDEN[1])
    text = explain_effort_range(d)
    for n in (d.final_effort_min, d.final_effort_max, d.pert_total_optimistic,
              d.pert_total_pessimistic, d.available_person_days, d.pert_total_expected):
        assert f"{n:g}" in text
    assert "minus PERT expected effort" in text
    assert ("deficit" in text) == (d.capacity_gap < 0)


def test_report_contains_explanation_and_utilization():
    from effort_estimator import EffortEstimator
    agent = MagicMock()
    agent.ask.return_value = "EXECUTIVE_SUMMARY: ok\nASSUMPTIONS: - a\nRECOMMENDATIONS: - r"
    report, data = EffortEstimator(agent).estimate(GOLDEN[0])
    assert "How to read the range and gap" in report
    assert "Expected Effort vs Capacity" in report
    prompt = agent.ask.call_args[0][0]
    assert f"PERT EXPECTED EFFORT: {data.pert_total_expected}" in prompt


# ── Finding 5: confidence explanation matches the score ───────────────────────

@pytest.mark.parametrize("ctx", GOLDEN)
def test_confidence_breakdown_sums_to_score(ctx):
    d = compute_estimation(ctx)
    parts = confidence_breakdown(d)
    assert [p[0] for p in parts] == ["PERT spread", "Capacity gap", "Data quality", "Multiplier magnitude"]
    raw = sum(p[1] for p in parts)
    capped = any("capped at" in w for w in d.warnings)  # plausibility caps lower the score below the factor sum
    assert (raw > d.confidence_score) if capped else (raw == d.confidence_score)
    assert all(0 <= p[1] <= p[2] for p in parts)


def test_readout_exposes_and_renders_explanations():
    from components import executive_readout_html
    d = compute_estimation(GOLDEN[0])
    ro = build_readout([], d)
    assert ro.range_explanation and len(ro.confidence_factors) == 4
    html = executive_readout_html(ro)
    assert "How this is calculated" in html
    assert "Why this range" in html
    assert "PERT spread" in html


# ── Findings 3, 4, 6: sources ─────────────────────────────────────────────────

def _chunk(filename, category="Standard"):
    return SimpleNamespace(metadata={"filename": filename, "category": category}, page_content="x")


def test_labels_keep_prompt_numbering_for_duplicate_documents():
    chunks = [
        _chunk("A.md"), _chunk("B.md", "Methodology"), _chunk("A.md"),
        _chunk("C.md"), _chunk("A.md"),
    ]
    labels = build_source_labels(chunks)
    assert labels == [
        "[Source 1, 3, 5] [Standard] A",
        "[Source 2] [Methodology] B",
        "[Source 4] [Standard] C",
    ]


def test_every_prompt_source_number_appears_in_panel():
    from agent import QAIAgent
    chunks = [_chunk(f"doc{i % 3}.md") for i in range(5)]
    ctx = QAIAgent.format_knowledge_context(MagicMock(), chunks)
    in_prompt = {int(n) for n in re.findall(r"\[Source (\d+) —", ctx)}
    in_panel = {int(n) for label in build_source_labels(chunks) for n in re.findall(r"\d+", label.split("]")[0])}
    assert in_prompt == in_panel == {1, 2, 3, 4, 5}


@pytest.mark.parametrize("raw,clean", [
    ("ISTQB_CTAL-TM_Syllabus_v3.0_zKjKsaN.pdf", "ISTQB CTAL-TM Syllabus v3.0"),
    ("ISTQB_CT-AI_Syllabus_v1.0_mghocmT (1).pdf", "ISTQB CT-AI Syllabus v1.0"),
    ("tmpab12cd9_Quality_Plan.md", "Quality Plan"),
    ("Risk_Based_Testing.md", "Risk Based Testing"),
    ("AI-DrivenQA_case_studies.md", "AI-DrivenQA case studies"),
    ("Case_Study_Boeing_737MAX_MCAS.md", "Case Study Boeing 737MAX MCAS"),
    ("ISTQB_CTFL_Syllabus_v4.0.1.pdf", "ISTQB CTFL Syllabus v4.0.1"),
    ("ISTQB_CT-ATLaS_Syllabus_v2.0.pdf", "ISTQB CT-ATLaS Syllabus v2.0"),
    ("Process_Reference_Model.md", "Process Reference Model"),
    ("", "Unknown"),
])
def test_display_name(raw, clean):
    assert display_name(raw) == clean


def test_prompt_context_uses_clean_names():
    from agent import QAIAgent
    ctx = QAIAgent.format_knowledge_context(MagicMock(), [_chunk("ISTQB_CTAL-TM_Syllabus_v3.0_zKjKsaN.pdf")])
    assert "zKjKsaN" not in ctx
