"""
Regression tests for the end-to-end MCP test findings against maturity_core:
F4 (mature org under-scored), F7 (language warning), F22 (keyword stuffing).
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SRC_DIR = REPO_ROOT / "src"

from qai_consultant.core.maturity_core import DETECTION_CAVEAT, assess_maturity  # noqa: E402

MATURE = (REPO_ROOT / "evals" / "fixtures" / "maturity" / "mature_paraphrased.txt").read_text(encoding="utf-8")

STUFFING = (
    "test policy, test strategy, test plan, master test plan, defect log, dashboard, "
    "corrective action, test design technique, entry criteria, exit criteria, test environment, "
    "production-like, test team, test manager, training program, peer review, performance test, "
    "security test, usability test, shift-left, onboarding, REQ-101"
)

ROMANIAN = (
    "Echipa noastra de testare lucreaza cu un plan de test pentru fiecare lansare si folosim un "
    "sistem de urmarire a defectelor. Testele sunt executate in mediul de staging, iar rezultatele "
    "sunt raportate saptamanal catre managerul de proiect. Avem o echipa dedicata care se ocupa de "
    "testarea functionala si de performanta, si toate defectele critice trebuie rezolvate inainte "
    "de lansare."
)


# ── F4 ───────────────────────────────────────────────────────────────────────

def test_mature_paraphrased_org_reaches_level_2_or_more():
    r = assess_maturity(MATURE)
    assert r.indicative_tmmi_level >= 2


def test_dashboard_monitoring_and_nonfunctional_trio_are_detected():
    text = (
        "Testing progress is monitored weekly through dashboards with defect metrics shared "
        "at the planning meeting. We run performance, security and usability testing before "
        "each release, and nothing else is formally defined at the moment for this team."
    )
    r = assess_maturity(text)
    assert r.tmmi_dimension_scores["test_monitoring_and_control"] > 0
    assert r.tmmi_dimension_scores["non_functional_testing"] == 100


def test_negated_new_keywords_are_not_evidence():
    text = (
        "We have no performance testing at all, and there is no dashboard or defect metrics "
        "reporting. Everything is done manually by developers right before release without any "
        "plan, and nobody has ever written a test plan or strategy for this project."
    )
    r = assess_maturity(text)
    assert r.tmmi_dimension_scores["non_functional_testing"] == 0
    assert r.tmmi_dimension_scores["test_monitoring_and_control"] == 0
    assert r.indicative_tmmi_level == 1


def test_performance_review_of_staff_is_not_nonfunctional_testing():
    text = (
        "Our annual performance review of employees happens in March and security badges are "
        "issued at the front desk by the facilities team, which has no connection to the "
        "software we build or how we verify it before shipping to customers each quarter."
    )
    assert assess_maturity(text).tmmi_dimension_scores["non_functional_testing"] == 0


def test_every_scored_result_carries_the_keyword_caveat():
    r = assess_maturity(MATURE)
    assert r.detection_caveat == DETECTION_CAVEAT
    assert "keyword-based" in r.detection_caveat


# ── F7 ───────────────────────────────────────────────────────────────────────

def test_romanian_description_carries_language_warning():
    r = assess_maturity(ROMANIAN)
    assert r.language == "ro"
    assert r.score_reliable is False
    assert "NOT reliable" in r.language_warning


def test_english_description_has_no_language_warning():
    r = assess_maturity(MATURE)
    assert r.language_warning == ""
    assert r.score_reliable is True


# ── F22 ──────────────────────────────────────────────────────────────────────

def test_keyword_stuffing_scores_below_realistic_description():
    stuffed = assess_maturity(STUFFING)
    real = assess_maturity(MATURE)
    assert stuffed.indicative_tmmi_level < real.indicative_tmmi_level
    assert sum(stuffed.tmmi_dimension_scores.values()) == 0


def test_keyword_stuffing_is_warned():
    r = assess_maturity(STUFFING)
    assert r.keyword_list_warning
    assert "keyword" in r.keyword_list_warning.lower()


def test_newline_separated_keyword_list_is_warned():
    r = assess_maturity("\n".join(STUFFING.split(", ")))
    assert r.keyword_list_warning
    assert r.indicative_tmmi_level == 1


def test_realistic_description_not_flagged_as_keyword_list():
    assert assess_maturity(MATURE).keyword_list_warning == ""


def test_hard_wrapped_prose_not_flagged_as_keyword_list():
    wrapped = (
        "We keep a documented test policy and every release has a\n"
        "test plan with estimates and a schedule that the team agrees on.\n"
        "Defects go into a defect log and we report status against the\n"
        "plan every week to the whole department and management."
    )
    assert assess_maturity(wrapped).keyword_list_warning == ""


def test_mcp_tool_not_a_qa_description_shape():
    from qai_consultant.mcp import server
    out = server.assess_qa_maturity(
        "Mix 500 g flour with 350 g water and 100 g active starter. Let the sourdough "
        "rest for twelve hours, fold it twice, do the poke test, then bake at 230 C "
        "for forty minutes until golden. High quality flour matters."
    )
    assert out["status"] == "not_a_qa_description"
    assert out["indicative_tmmi_level"] is None
    assert out["findings"] == []
    assert out["message"]
    assert len(str(out)) < 3000


def test_mcp_tool_ok_status_and_negated_ai():
    from qai_consultant.mcp import server
    out = server.assess_qa_maturity(
        "We build a trading backend with Python and test manually before each release, "
        "with no documentation of the process and no regression suite at all today, "
        "and nobody is responsible for quality across the whole team here. "
        "No machine learning is used in the product."
    )
    assert out["status"] == "ok"
    assert out["ai_act_relevant"] is False
    assert out["ai_act_dimension_scores"] == {}
