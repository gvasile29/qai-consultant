"""Regression tests for end-user findings F3 (negated AI mention gated the EU
AI Act dimension on) and F4 (no non-QA gate)."""
import pytest

from qai_consultant.core import maturity_core
from qai_consultant.core.maturity_core import assess_maturity

_BESS = (
    "We build a battery energy storage trading backend in Python. Dispatch uses "
    "Gurobi optimization, price forecasting and automatic, algorithmic trading "
    "with a smart, intelligent scheduler. Testing is manual before each release "
    "and there is no documentation. "
)

NEGATED = [
    "No machine learning is used in the product.",
    "We do not use AI.",
    "The system works without any ML.",
    "This is not an AI system.",
    "No AI/ML components are involved.",
    "We do not use LLMs.",
    "The product is AI-free.",
    "Our platform is ai free.",
    "No AI, no ML, no LLMs anywhere.",
    "It does not currently use any machine learning.",
    "Machine learning is not used here.",
    "Neither AI nor ML is involved.",
]

AI_POSITIVE = [
    "We ship an ML model for demand forecasting.",
    "The product is an AI-powered chatbot.",
    "Without human oversight our AI model decides loan approvals.",
    "We use machine learning but no deep learning.",
    "The LLM summarises support tickets.",
    "There are no tests yet; the product uses a neural network.",
]


@pytest.mark.parametrize("sentence", NEGATED)
def test_negated_ai_mention_does_not_gate_ai_act_on(sentence):
    result = assess_maturity(_BESS + sentence)
    assert result.status == "ok"
    assert result.ai_act_relevant is False
    assert result.ai_act_dimension_scores == {}
    assert result.ai_act_note == ""


@pytest.mark.parametrize("sentence", AI_POSITIVE)
def test_genuine_ai_description_still_gates_on(sentence):
    result = assess_maturity(_BESS + sentence)
    assert result.ai_act_relevant is True
    assert len(result.ai_act_dimension_scores) == 7


def test_non_ai_words_do_not_gate_on():
    result = assess_maturity(_BESS)
    assert result.ai_act_relevant is False


def test_mixed_negated_and_real_mention_gates_on():
    result = assess_maturity(_BESS + "No LLMs are used, but a neural network forecasts prices.")
    assert result.ai_act_relevant is True


SOURDOUGH = (
    "Mix 500 g flour with 350 g water and 100 g active starter. Let the sourdough "
    "rest for twelve hours, fold it twice, do the poke test, then bake at 230 C "
    "for forty minutes until golden. High quality flour matters."
)


def test_non_qa_text_is_rejected_without_level_or_findings():
    result = assess_maturity(SOURDOUGH)
    assert result.status == maturity_core.STATUS_NOT_QA == "not_a_qa_description"
    assert result.findings == []
    assert result.tmmi_dimension_scores == {}
    assert result.ai_act_relevant is False


def test_meeting_notes_rejected():
    text = "Meeting notes: we discussed the budget, holiday plans and the office move. " * 4
    assert assess_maturity(text).status == "not_a_qa_description"


@pytest.mark.parametrize("text", [
    "We test manually before release, no documentation, and nobody tracks anything about it at all. " * 3,
    "We test everything by hand. There is no plan and nobody owns it, we just hope it works for customers. " * 2,
    "Developers ship to production on Fridays, with no checklist, no staging and no process whatsoever. " * 3,
])
def test_immature_but_qa_related_still_assessed_level_1(text):
    result = assess_maturity(text)
    assert result.status == "ok"
    assert result.indicative_tmmi_level == 1


def test_short_input_still_insufficient_and_deterministic():
    assert assess_maturity("short").status == "insufficient_content"
    assert assess_maturity(SOURDOUGH) == assess_maturity(SOURDOUGH)
