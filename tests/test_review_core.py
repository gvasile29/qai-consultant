"""
Tests for src/review_core.py — deterministic QA document quality review (v3.1).

Pure stdlib module: six weighted dimensions scored via mechanical
regex/keyword checks. No LLM anywhere in this file's call path.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from review_core import (  # noqa: E402
    DOC_TYPES,
    MIN_CONTENT_CHARS,
    WEIGHTS,
    ReviewFinding,
    ReviewResult,
    _detect_doc_type,
    _strip_front_matter_and_footer,
    review_document,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────

STRONG_TEST_PLAN = """
# Test Plan — Acme Checkout

## Scope
This document defines the scope of testing for the checkout service.

## Test Items
The checkout API and payment gateway integration are the items to be tested.

## Features to be Tested
The following will be tested: cart totals, tax calculation, discount codes.

## Features Not to be Tested
Out of scope: third-party fraud detection internals are excluded from this plan.

## Objectives
The objective of this test plan is to validate checkout correctness end-to-end.

## Test Levels
Testing includes unit test, integration test, system test, and regression test levels.

## Approach
A risk-based testing approach is used, with risk-based prioritization of test cases.

## Pass/Fail Criteria
A test case passes when the expected result matches the observed output exactly.

## Entry Criteria
Entry criteria: all REQ-101 and REQ-102 requirements are code-complete and deployed to QA.

## Exit Criteria
Exit criteria: 95% of test cases pass and code coverage of 80% is achieved.

## Suspension Criteria
Testing will be suspended if the build fails smoke tests; resumption criteria apply after a fix.

## Deliverables
Test deliverables include the traceability matrix and the final test summary report.

## Schedule
The testing schedule spans two weeks per the project milestones.

## Risks
### R01 — Payment gateway instability
- **Severity:** Critical
- **Likelihood:** High priority risk requiring mitigation.
- **Mitigation:** A contingency plan and mitigation strategy are documented for R01.

Quality metrics tracked include defect density, coverage %, and pass rate (KPI).

Expected result: the total is calculated to the exact cent per REQ-101.
Expected result: the discount code REQ-102 reduces the total by exactly 10%.

## Approvals
Sign-off is required from the QA Lead and Project Manager before release.
"""

WEAK_DOC = """
# Notes

We tested the app a bit. Everything works correctly and functions properly
as expected. There were no real problems, it should work fine in production.
We did some testing on the login page and the checkout page. It should
function properly overall. No major issues. Testing was fine and everything
seemed to work as intended when we tried it out over the last couple of days
of ad-hoc manual clicking around the staging environment before the release.
"""

STRONG_TEST_STRATEGY = """
# Test Strategy — Acme Platform

## Scope
This strategy covers the Acme platform services.

## Objectives
The goal is to ensure release quality across all services.

## Test Levels
We perform unit test, integration test, and performance test activities.

## Approach
Our methodology follows a risk-based test approach with risk-based prioritization.

## Entry Criteria
Entry criteria: environment provisioned and REQ-200 complete.

## Exit Criteria
Exit criteria: 90% pass rate and coverage of 75%.

## Risks
### R05 — Data migration risk
Critical priority. Mitigation: contingency plan documented for R05.

## Resources
Roles and responsibilities are defined for the QA team.

## Tools and Environment
The test environment uses staging infrastructure with dedicated tools.

## References
This strategy references ISO/IEC 25010 and ISTQB standards. Defect density
and coverage % are tracked as KPI. Expected result: all services pass REQ-200
validation with a traceability matrix maintained throughout.
"""

STRONG_TEST_CASES = """
# Test Cases — Login Module

## TC-001 — Test Case ID
Precondition: user account REQ-301 exists and is active.
Steps: 1. Navigate to login page. 2. Enter valid credentials. 3. Submit.
Expected result: the user is redirected to the dashboard within 2 seconds.

## TC-002 — Test Case ID
Precondition: prerequisite account is locked after 5 failed attempts.
Steps: 1. Enter invalid credentials 5 times.
Expected result: an error message with code AUTH-409 is displayed exactly.

This test case set traces to REQ-301 and covers risk R02, a critical risk
with mitigation and contingency planned, prioritized via risk-based testing.
Coverage of 100% for this module is required per the traceability matrix.
"""


# ── Input hygiene: front matter / footer stripping ────────────────────────────

def test_strip_front_matter_and_footer_removes_both():
    text = (
        "---\n"
        "generated_by: QAI Consultant\n"
        "ai_generated: true\n"
        "---\n"
        "\n"
        "# Real content here\n"
        "\n\n---\n\n"
        "*🤖 AI-generated content — produced by QAI Consultant.*\n"
    )
    cleaned = _strip_front_matter_and_footer(text)
    assert cleaned == "# Real content here"


def test_strip_front_matter_and_footer_handles_no_front_matter():
    text = "# Just content\nNo front matter or footer here."
    cleaned = _strip_front_matter_and_footer(text)
    assert cleaned == text.strip()


def test_strip_front_matter_and_footer_handles_crlf():
    text = "---\r\ngenerated_by: X\r\n---\r\n\r\nBody text\r\n"
    cleaned = _strip_front_matter_and_footer(text)
    assert cleaned == "Body text"


def test_review_document_scores_content_after_stripping_marks():
    body = STRONG_TEST_PLAN.strip()
    front_matter = "---\ngenerated_by: QAI Consultant\nai_generated: true\n---\n"
    footer = "\n\n---\n\n*🤖 AI-generated content — produced by QAI Consultant.*\n"
    marked = front_matter + "\n" + body + footer
    plain = review_document(body, doc_type="test_plan")
    with_marks = review_document(marked, doc_type="test_plan")
    assert with_marks.overall_score == plain.overall_score
    assert with_marks.dimension_scores == plain.dimension_scores


# ── Insufficient content ───────────────────────────────────────────────────────

def test_review_document_insufficient_content_short_text():
    result = review_document("Too short.", doc_type="test_plan")
    assert result.doc_type == "insufficient_content"
    assert result.overall_score == 0
    assert result.dimension_scores == {}
    assert result.findings == []
    assert result.stats["char_count"] < MIN_CONTENT_CHARS


def test_review_document_insufficient_content_empty_string():
    result = review_document("", doc_type="auto")
    assert result.doc_type == "insufficient_content"


def test_review_document_insufficient_content_none_like_input_does_not_raise():
    result = review_document("   \n\n  ", doc_type="auto")
    assert result.doc_type == "insufficient_content"


def test_review_document_content_at_exactly_min_chars_is_not_insufficient():
    text = "x" * MIN_CONTENT_CHARS
    result = review_document(text, doc_type="test_plan")
    assert result.doc_type != "insufficient_content"


# ── doc_type auto-detection ─────────────────────────────────────────────────────

def test_detect_doc_type_test_plan_wins_on_test_plan_keywords():
    lower = STRONG_TEST_PLAN.lower()
    assert _detect_doc_type(lower) == "test_plan"


def test_detect_doc_type_test_strategy_wins_on_strategy_keywords():
    lower = STRONG_TEST_STRATEGY.lower()
    assert _detect_doc_type(lower) == "test_strategy"


def test_detect_doc_type_test_cases_wins_on_test_case_keywords():
    lower = STRONG_TEST_CASES.lower()
    assert _detect_doc_type(lower) == "test_cases"


def test_detect_doc_type_ties_default_to_test_plan():
    # Sparse text with no section keywords at all -> all-zero vote tie.
    lower = "just some generic prose with no headings or keywords at all here."
    assert _detect_doc_type(lower) == "test_plan"


def test_review_document_auto_resolves_and_reports_auto_detected_flag():
    result = review_document(STRONG_TEST_STRATEGY, doc_type="auto")
    assert result.doc_type == "test_strategy"
    assert result.stats["auto_detected"] is True


def test_review_document_explicit_doc_type_not_auto_detected():
    result = review_document(STRONG_TEST_PLAN, doc_type="test_plan")
    assert result.stats["auto_detected"] is False


def test_review_document_unknown_doc_type_falls_back_to_auto():
    result = review_document(STRONG_TEST_STRATEGY, doc_type="not_a_real_type")
    assert result.doc_type == "test_strategy"
    assert result.stats["auto_detected"] is True


# ── Score ordering: strong vs weak ─────────────────────────────────────────────

def test_strong_test_plan_scores_at_least_20_above_weak_doc():
    strong = review_document(STRONG_TEST_PLAN, doc_type="test_plan")
    weak = review_document(WEAK_DOC, doc_type="test_plan")
    assert strong.overall_score - weak.overall_score >= 20


def test_strong_test_strategy_scores_at_least_20_above_weak_doc():
    strong = review_document(STRONG_TEST_STRATEGY, doc_type="test_strategy")
    weak = review_document(WEAK_DOC, doc_type="test_strategy")
    assert strong.overall_score - weak.overall_score >= 20


def test_strong_test_cases_scores_at_least_20_above_weak_doc():
    strong = review_document(STRONG_TEST_CASES, doc_type="test_cases")
    weak = review_document(WEAK_DOC, doc_type="test_cases")
    assert strong.overall_score - weak.overall_score >= 20


def test_every_finding_on_weak_doc_has_at_least_one_citation_query():
    weak = review_document(WEAK_DOC, doc_type="test_plan")
    assert weak.findings, "expected findings on a weak document"
    for finding in weak.findings:
        assert isinstance(finding, ReviewFinding)
        assert len(finding.citation_queries) >= 1
        assert all(isinstance(q, str) and q for q in finding.citation_queries)


# ── Per-dimension scoring on minimal fixtures ───────────────────────────────────

def test_structure_completeness_full_marks_when_all_sections_present():
    result = review_document(STRONG_TEST_PLAN, doc_type="test_plan")
    assert result.dimension_scores["structure_completeness"] == 100


def test_structure_completeness_low_when_no_sections_present():
    result = review_document(WEAK_DOC, doc_type="test_plan")
    assert result.dimension_scores["structure_completeness"] < 30


def test_structure_completeness_missing_scope_is_critical_severity():
    text = (
        "## Test Items\nThe checkout API is the item under test.\n\n"
        "## Approach\nA structured testing approach is used throughout.\n\n"
        "## Schedule\nTesting runs across two sprints per the milestones.\n\n"
        "This paragraph exists purely to pad the fixture past the minimum "
        "content length threshold required for a real review to run, with "
        "no mention whatsoever of the word this dimension checks for."
    )
    result = review_document(text, doc_type="test_plan")
    scope_findings = [f for f in result.findings if f.evidence == "scope"]
    assert scope_findings
    assert scope_findings[0].severity == "critical"


def test_objectives_scope_clarity_high_when_objectives_and_scope_present():
    result = review_document(STRONG_TEST_PLAN, doc_type="test_plan")
    assert result.dimension_scores["objectives_scope_clarity"] >= 75


def test_objectives_scope_clarity_low_on_weak_doc():
    result = review_document(WEAK_DOC, doc_type="test_plan")
    assert result.dimension_scores["objectives_scope_clarity"] < 75


def test_entry_exit_criteria_full_marks_with_measurable_criteria():
    result = review_document(STRONG_TEST_PLAN, doc_type="test_plan")
    assert result.dimension_scores["entry_exit_criteria"] == 100


def test_entry_exit_criteria_flags_non_measurable_exit():
    text = (
        "## Entry Criteria\nEntry criteria: the environment is provisioned "
        "and ready for the team to begin.\n\n"
        "## Exit Criteria\nExit criteria: testing is done when the team "
        "feels confident about the release and stakeholders agree it is "
        "ready to ship without further changes needed.\n\n"
        "This paragraph pads the fixture past the minimum content length "
        "threshold required for a real review to run, without adding any "
        "digits or percentage signs anywhere in the surrounding text."
    )
    result = review_document(text, doc_type="test_plan")
    messages = " ".join(f.message for f in result.findings)
    assert "not measurable" in messages


def test_traceability_full_marks_with_req_ids_risk_ids_and_matrix():
    result = review_document(STRONG_TEST_PLAN, doc_type="test_plan")
    assert result.dimension_scores["traceability"] == 100


def test_traceability_zero_on_weak_doc_with_no_ids():
    result = review_document(WEAK_DOC, doc_type="test_plan")
    assert result.dimension_scores["traceability"] == 0


def test_measurability_penalizes_vague_expected_results():
    result = review_document(WEAK_DOC, doc_type="test_plan")
    assert result.dimension_scores["measurability"] < 50


def test_measurability_rewards_concrete_expected_results_and_metrics():
    result = review_document(STRONG_TEST_PLAN, doc_type="test_plan")
    assert result.dimension_scores["measurability"] >= 80


def test_measurability_no_expected_result_statements_scores_low():
    text = "This document has plenty of words but never spells out concretely what a passing run should look like anywhere in its body, just general descriptions of the system under test and its various components across many paragraphs of filler text to pass the minimum length threshold for review."
    result = review_document(text, doc_type="test_plan")
    assert result.dimension_scores["measurability"] <= 20


def test_risk_coverage_full_marks_with_severity_and_mitigation():
    result = review_document(STRONG_TEST_PLAN, doc_type="test_plan")
    assert result.dimension_scores["risk_coverage"] == 100


def test_risk_coverage_critical_finding_when_no_risk_section_at_all():
    text = WEAK_DOC * 3  # pad past MIN_CONTENT_CHARS without ever mentioning risk
    assert "risk" not in text.lower()
    result = review_document(text, doc_type="test_plan")
    risk_findings = [f for f in result.findings if f.dimension == "risk_coverage"]
    assert any(f.severity == "critical" for f in risk_findings)


# ── Weight normalization guard ──────────────────────────────────────────────────

def test_weights_sum_to_100():
    assert sum(WEIGHTS.values()) == 100


def test_overall_score_is_bounded_0_to_100():
    for fixture in (STRONG_TEST_PLAN, STRONG_TEST_STRATEGY, STRONG_TEST_CASES, WEAK_DOC):
        result = review_document(fixture, doc_type="auto")
        assert 0 <= result.overall_score <= 100


def test_overall_score_matches_manual_weighted_mean():
    result = review_document(STRONG_TEST_PLAN, doc_type="test_plan")
    total_weight = sum(WEIGHTS.values())
    expected = round(
        sum(result.dimension_scores[d] * (WEIGHTS[d] / total_weight) for d in result.dimension_scores)
    )
    assert result.overall_score == expected


# ── Determinism ──────────────────────────────────────────────────────────────

def test_review_document_is_deterministic_across_repeated_calls():
    r1 = review_document(STRONG_TEST_PLAN, doc_type="test_plan")
    r2 = review_document(STRONG_TEST_PLAN, doc_type="test_plan")
    assert r1 == r2


def test_review_document_deterministic_for_weak_doc_too():
    r1 = review_document(WEAK_DOC, doc_type="auto")
    r2 = review_document(WEAK_DOC, doc_type="auto")
    assert r1 == r2


# ── Stats ────────────────────────────────────────────────────────────────────

def test_review_document_stats_contains_expected_keys():
    result = review_document(STRONG_TEST_PLAN, doc_type="test_plan")
    assert set(result.stats.keys()) == {"char_count", "word_count", "heading_count", "auto_detected"}
    assert result.stats["char_count"] > 0
    assert result.stats["word_count"] > 0
    assert result.stats["heading_count"] > 0


def test_review_document_never_raises_on_huge_input():
    huge = STRONG_TEST_PLAN * 5000  # well past MAX_INPUT_CHARS
    result = review_document(huge, doc_type="test_plan")
    assert result.doc_type != "insufficient_content"


def test_doc_types_constant_matches_section_synonym_keys():
    from review_core import SECTION_SYNONYMS
    assert set(DOC_TYPES) == set(SECTION_SYNONYMS.keys())
