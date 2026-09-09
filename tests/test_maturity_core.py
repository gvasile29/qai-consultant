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
