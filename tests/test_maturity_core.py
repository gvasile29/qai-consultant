"""
Tests for src/maturity_core.py — deterministic TMMi process-maturity rubric
+ conditional EU AI Act Articles 9-15 readiness dimension (v3.5).

Pure stdlib module: mechanical regex/keyword checks. No LLM anywhere in
this file's call path. Mirrors tests/test_review_core.py's structure.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from maturity_core import (  # noqa: E402
    MAX_INPUT_CHARS,
    MIN_CONTENT_CHARS,
    MaturityFinding,
    MaturityResult,
    assess_maturity,
)


def test_insufficient_content_returns_structured_status():
    result = assess_maturity("Too short.")
    assert result.status == "insufficient_content"
    assert result.indicative_tmmi_level == 0
    assert result.findings == []
    assert result.tmmi_dimension_scores == {}
    assert "reason" in result.stats


def test_disclaimer_always_present():
    result = assess_maturity("word " * 100)
    assert result.disclaimer
    assert "not a certified" in result.disclaimer.lower() or "informal" in result.disclaimer.lower()


_LEVEL2_STRONG = """
Our team maintains a documented test policy and test strategy defining our
test objectives. Every release has a test plan with estimates, a schedule,
and risk-based prioritization. We track defects in a defect log and report
status against the plan, taking corrective action when we fall behind. Test
design follows structured test design techniques with clear entry criteria
and exit criteria; requirements are tracked as REQ-101, REQ-102. We run
everything in a dedicated test environment that is representative of
production.
"""

_LEVEL3_STRONG = _LEVEL2_STRONG + """
We have an independent test team led by a test manager, with defined roles
and responsibilities. New testers go through a formal training program and
onboarding. A master test plan integrates test activities from the
requirements phase onward. Beyond functional checks we run performance
test, security test, and usability test cycles. Every change goes through
a peer review, including requirements review and design review.
"""

_NO_PROCESS_SIGNAL = "We write some code and then people click around the app to see if it works. " * 5


def test_tmmi_scores_all_ten_process_areas():
    result = assess_maturity(_LEVEL3_STRONG)
    assert set(result.tmmi_dimension_scores.keys()) == {
        "test_policy_and_strategy", "test_planning", "test_monitoring_and_control",
        "test_design_and_execution", "test_environment",
        "test_organization", "test_training_program", "test_lifecycle_and_integration",
        "non_functional_testing", "peer_reviews",
    }


def test_tmmi_strong_level3_text_scores_higher_than_no_signal_text():
    strong = assess_maturity(_LEVEL3_STRONG)
    weak = assess_maturity(_NO_PROCESS_SIGNAL)
    for area in strong.tmmi_dimension_scores:
        assert strong.tmmi_dimension_scores[area] >= weak.tmmi_dimension_scores[area]
    assert sum(strong.tmmi_dimension_scores.values()) > sum(weak.tmmi_dimension_scores.values())


def test_tmmi_findings_carry_citation_queries():
    result = assess_maturity(_NO_PROCESS_SIGNAL)
    assert result.findings
    for finding in result.findings:
        assert finding.framework == "tmmi"
        assert finding.citation_queries
        assert finding.level in (2, 3)


_LEVEL3_KEYWORDS_ONLY_NO_LEVEL2 = (
    "We have an independent test team, a test manager, a training program, "
    "a master test plan, performance test and security test cycles, and "
    "every change goes through a peer review and design review. " * 3
)


def test_level3_keywords_without_level2_evidence_never_skips_to_level3():
    result = assess_maturity(_LEVEL3_KEYWORDS_ONLY_NO_LEVEL2)
    assert result.indicative_tmmi_level == 1


def test_strong_level2_and_level3_text_reaches_level3():
    result = assess_maturity(_LEVEL3_STRONG)
    assert result.indicative_tmmi_level == 3


def test_level2_only_text_reaches_level2_not_level3():
    result = assess_maturity(_LEVEL2_STRONG)
    assert result.indicative_tmmi_level == 2


def test_assess_maturity_is_deterministic():
    first = assess_maturity(_LEVEL3_STRONG)
    second = assess_maturity(_LEVEL3_STRONG)
    assert first == second


_AI_RELEVANT_TEXT = """
We are building a machine learning model that screens loan applications.
The model is trained on historical applicant data. We have a documented
risk management process covering the model's full lifecycle, and our
training data governance process checks for dataset bias. Technical
documentation captures design specifications and validation reports. The
system has automatic logging for traceability. Instructions for use state
known limitations and declared accuracy. A human reviewer can override
any decision (human oversight). We test robustness against adversarial
inputs and monitor for model drift.
"""

_NON_AI_TEXT = "We test a standard e-commerce checkout flow with unit and integration tests. " * 5


def test_ai_act_dimension_absent_for_non_ai_project():
    result = assess_maturity(_NON_AI_TEXT)
    assert result.ai_act_relevant is False
    assert result.ai_act_dimension_scores == {}
    assert not any(f.framework == "eu_ai_act" for f in result.findings)


def test_ai_act_dimension_scored_for_ai_project():
    result = assess_maturity(_AI_RELEVANT_TEXT)
    assert result.ai_act_relevant is True
    assert set(result.ai_act_dimension_scores.keys()) == {
        "risk_management", "data_governance", "technical_documentation",
        "record_keeping", "transparency_instructions", "human_oversight",
        "accuracy_robustness_security",
    }


def test_ai_act_findings_carry_citation_queries_and_severity():
    sparse_ai_text = "We are building an AI system using a neural network model. " * 5
    result = assess_maturity(sparse_ai_text)
    assert result.ai_act_relevant is True
    ai_findings = [f for f in result.findings if f.framework == "eu_ai_act"]
    assert ai_findings
    for finding in ai_findings:
        assert finding.citation_queries
        assert finding.severity in ("critical", "major")
        assert finding.level is None


def test_ai_act_risk_management_and_human_oversight_are_critical():
    sparse_ai_text = "We are building an AI system using a neural network model. " * 5
    result = assess_maturity(sparse_ai_text)
    by_dim = {f.dimension: f.severity for f in result.findings if f.framework == "eu_ai_act"}
    assert by_dim.get("risk_management") == "critical"
    assert by_dim.get("human_oversight") == "critical"


def test_ai_act_note_present_when_relevant_and_empty_when_not():
    ai_result = assess_maturity(_AI_RELEVANT_TEXT)
    assert ai_result.ai_act_relevant is True
    assert ai_result.ai_act_note != ""
    from maturity_core import _AI_ACT_NOTE  # noqa: PLC0415
    assert ai_result.ai_act_note == _AI_ACT_NOTE

    non_ai_result = assess_maturity(_NON_AI_TEXT)
    assert non_ai_result.ai_act_relevant is False
    assert non_ai_result.ai_act_note == ""


_EXPLICIT_DENIAL_TEXT = (
    "We have no test policy and no test strategy. There is no test plan, "
    "no test environment, no defect log, no entry criteria or exit "
    "criteria, no test design technique, no risk-based testing, no "
    "schedule, no test objective, and no test approach documented "
    "anywhere at all in this organisation whatsoever today."
)


def test_negated_keywords_are_not_counted_as_evidence():
    result = assess_maturity(_EXPLICIT_DENIAL_TEXT)
    assert result.indicative_tmmi_level == 1

    level2_areas = [
        "test_policy_and_strategy", "test_planning", "test_monitoring_and_control",
        "test_design_and_execution", "test_environment",
    ]
    level2_avg = sum(result.tmmi_dimension_scores[a] for a in level2_areas) / len(level2_areas)
    assert level2_avg < 60


def test_progress_tracking_recognizes_defect_triage_and_pass_rate_paraphrase():
    """Found via live browser QA: a description covering coverage/pass-rate
    per sprint plus a weekly defect triage was scored 0/100 for Test
    Monitoring and Control because the keyword list only recognized
    "defect tracking"/"status report", not semantically equivalent
    phrasing."""
    text = (
        "We track test coverage and pass rate every sprint, and hold a "
        "weekly triage of defects to catch regressions early in each "
        "release cycle. " * 4
    )
    result = assess_maturity(text)
    progress_tracking_findings = [
        f for f in result.findings
        if f.dimension == "test_monitoring_and_control" and f.evidence == "progress_tracking"
    ]
    assert not progress_tracking_findings


def test_requirement_traceability_recognizes_prose_description_without_ticket_ids():
    """Found via live browser QA: a prose description of requirement
    traceability ("traceability from requirements to test cases and
    defects") was scored as no evidence, because the only signal recognized
    was a ticket-ID regex (REQ-101, JIRA-42, ...), not a description of the
    practice itself."""
    text = (
        "We maintain full traceability from requirements to test cases and "
        "defects, with structured test design techniques and clear entry "
        "criteria and exit criteria throughout the project. " * 4
    )
    result = assess_maturity(text)
    traceability_findings = [
        f for f in result.findings
        if f.dimension == "test_design_and_execution" and f.evidence == "requirement_traceability"
    ]
    assert not traceability_findings
