"""Golden check: one real generated document set (SaaS web_app template, live
ministral-14b run of 2026-10-26) must pass the generated-document validators,
and known failure shapes must still be caught on that same text.

The clean set pins the validators' thresholds to real output, so a rubric or
threshold change that would fail good documents shows up here before it flaps
the live smoke gate. The mutations reproduce failures seen in saved runs: a
Strategy citing risk IDs missing from its register (6 of 24 energy-trading
Strategies), a re-rated risk, and a Test Plan that drops a Critical risk.

Not covered here (see tests/unit/compliance/test_doc_validation.py): the table-row
re-rating branch, effort-total matching and Critical coverage in the Strategy."""

import re
from pathlib import Path

import pytest

from qai_consultant.compliance.doc_validation import consistency_problems, review_problems

FIXTURES = Path(__file__).resolve().parents[3] / "evals" / "fixtures" / "generated"


def _read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def docs():
    return {
        "register": _read("saas_risk_register.md"),
        "strategy": _read("saas_strategy.md"),
        "plan": _read("saas_test_plan.md"),
    }


def test_real_strategy_and_plan_pass_the_review_gate(docs):
    assert review_problems(docs["strategy"], "test_strategy") == []
    assert review_problems(docs["plan"], "test_plan") == []


def test_real_document_set_is_consistent(docs):
    assert consistency_problems(docs["register"], docs["strategy"], docs["plan"]) == []


def test_invented_risk_ids_in_the_strategy_are_caught(docs):
    strategy = docs["strategy"] + "\n- Ad-hoc testing for R07 (API changes), R08 (optimiser fallback).\n"
    problems = consistency_problems(docs["register"], strategy, docs["plan"])
    assert any("Strategy" in p and "R08" in p for p in problems)


def test_re_rated_risk_in_the_plan_is_caught(docs):
    plan = docs["plan"] + "\nNote: R01 (Low) needs no dedicated test.\n"
    problems = consistency_problems(docs["register"], docs["strategy"], plan)
    assert any("R01 written as Low" in p for p in problems)


def test_plan_that_drops_a_critical_risk_is_caught(docs):
    plan = re.sub(r"\bR01\b", "the first risk", docs["plan"])
    problems = consistency_problems(docs["register"], docs["strategy"], plan)
    assert any("never referenced: R01" in p for p in problems)


def test_stripped_down_plan_fails_the_review_gate(docs):
    skeleton = "\n".join(line for line in docs["plan"].splitlines() if line.startswith("#"))
    assert review_problems(skeleton, "test_plan")
