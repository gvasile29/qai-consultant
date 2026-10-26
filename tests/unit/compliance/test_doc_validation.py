"""compliance/doc_validation.py: review-rubric gate and cross-document consistency."""

from pathlib import Path
from types import SimpleNamespace

from qai_consultant.compliance import doc_validation as dv
from qai_consultant.generation.consistency import effort_facts, enforce_effort_totals

FIXTURES = Path(__file__).resolve().parents[3] / "evals" / "fixtures" / "review"

REGISTER = """# Risk Register

## Risk Matrix Overview

| Risk ID | Description | Likelihood | Impact | Risk Level | Priority |
|---|---|---|---|---|---|
| R01 | Gateway integration failures | High | High | Critical | P1 |
| R02 | Optimiser wrong dispatch | Medium | High | High | P1 |
| R03 | Reporting drift | Low | Low | Low | P3 |
"""
EFFORT = SimpleNamespace(
    pert_total_expected=332.7, final_effort_min=290.0, final_effort_max=410.5,
    available_person_days=283.5, capacity_gap=-49.2, qa_team_size=2, project_duration_days=189,
)
PLAN_OK = "Exit criteria: R01 and R02 closed. R03 (Low) accepted."
LEVEL_TABLE = "| Risk ID | Feature | Risk Level |\n|---|---|---|\n"


def _fake_review(monkeypatch, overall, **dims):
    scores = {"structure_completeness": 90, "risk_coverage": 90, **dims}
    fake = SimpleNamespace(status="ok", overall_score=overall, dimension_scores=scores)
    monkeypatch.setattr(dv, "review_document", lambda *_: fake)


# ── review gate ──────────────────────────────────────────────────────────────

def test_strong_plan_passes_review_gate():
    assert dv.review_problems((FIXTURES / "strong_test_plan.md").read_text(encoding="utf-8"), "test_plan") == []


def test_weak_plan_fails_review_gate():
    problems = dv.review_problems((FIXTURES / "weak_test_plan.md").read_text(encoding="utf-8"), "test_plan")
    assert any("review score" in p for p in problems)
    assert any("structure_completeness" in p for p in problems)


def test_overall_floor_fails_below_threshold(monkeypatch):
    _fake_review(monkeypatch, 60)
    problems = dv.review_problems("x", "test_plan")
    assert len(problems) == 1 and problems[0].startswith("review score 60 < 70")


def test_dimension_floor_fails_even_when_overall_passes(monkeypatch):
    _fake_review(monkeypatch, 85, risk_coverage=40)
    assert dv.review_problems("x", "test_plan") == ["risk_coverage 40 < 60"]


def test_unscorable_text_is_reported_not_raised():
    assert dv.review_problems("hi", "test_plan")[0].startswith("review rubric could not score it")


# ── cross-document consistency ───────────────────────────────────────────────

def test_consistent_documents_have_no_problems():
    assert dv.consistency_problems(REGISTER, PLAN_OK, PLAN_OK, EFFORT) == []


def test_unknown_risk_id_flagged_per_document():
    problems = dv.consistency_problems(REGISTER, "R01 R09", PLAN_OK + " R07")
    assert any("Strategy" in p and "R09" in p for p in problems)
    assert any("Test Plan" in p and "R07" in p for p in problems)


def test_inline_rerating_flagged():
    problems = dv.consistency_problems(REGISTER, "", PLAN_OK + " R01 (Medium) is minor.")
    assert any("R01 written as Medium" in p for p in problems)


def test_rated_phrase_rerating_flagged():
    assert any("R02" in p for p in dv.consistency_problems(REGISTER, "", PLAN_OK + " R02 is rated Low here."))


def test_table_rerating_flagged_by_risk_level_column_only():
    low = PLAN_OK + "\n" + LEVEL_TABLE + "| R02 | Optimiser | Low |"
    high = PLAN_OK + "\n" + LEVEL_TABLE + "| R02 | Optimiser | High |"
    assert any("R02" in p for p in dv.consistency_problems(REGISTER, "", low))
    assert dv.consistency_problems(REGISTER, "", high) == []


def test_priority_and_adjective_words_are_not_rerating():
    mapping = "| Risk ID | Test | Priority |\n|---|---|---|\n| R01 | Gateway | High |\n| R02 | Dispatch | Low |"
    text = PLAN_OK + "\nR02: High availability tested.\nR01 - Low latency checks.\nR01 (High-volume load).\n" + mapping
    assert dv.consistency_problems(REGISTER, "", text) == []


def test_unreferenced_critical_risk_flagged():
    problems = dv.consistency_problems(REGISTER, "", "Exit criteria: R02 closed.")
    assert any("Critical risk(s) never referenced: R01" in p for p in problems)


def test_critical_reference_matches_whole_id_only():
    problems = dv.consistency_problems(REGISTER, "", "Closed: R02, R010, R011.")
    assert any("never referenced: R01" in p for p in problems)


def test_effort_total_mismatch_flagged_and_match_passes():
    bad = "## 8. Resources\n- Total QA effort: 100 person-days\n## 9. Next\n"
    good = "## 8. Resources\n- Total QA effort: 332.7 person-days\n## 9. Next\n"
    assert enforce_effort_totals(good, effort_facts(EFFORT)) == good
    assert any("QA total" in p for p in dv.consistency_problems(REGISTER, bad, PLAN_OK, EFFORT))
    assert dv.consistency_problems(REGISTER, good, PLAN_OK, EFFORT) == []


def test_missing_inputs_skip_checks_instead_of_failing():
    assert dv.consistency_problems("", "R09", "R09", None) == []
    assert dv.consistency_problems(REGISTER, "", "", {}) == []
