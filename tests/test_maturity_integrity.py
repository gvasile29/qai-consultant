"""Pytest wrapper over evals/maturity_integrity.py's real shipped-code checks.
Same migration rationale as tests/test_estimate_integrity.py."""
import pytest

from evals import maturity_integrity as MI


@pytest.fixture(scope="module")
def outcomes():
    return {o.name: o for o in MI.run_all()}


def _msg(outcome):
    return MI.format_table([outcome])


def test_level_ordering(outcomes):
    o = outcomes["level_ordering"]
    assert o.passed, _msg(o)


def test_no_level_skip(outcomes):
    o = outcomes["no_level_skip"]
    assert o.passed, _msg(o)


def test_ai_act_gating(outcomes):
    o = outcomes["ai_act_gating"]
    assert o.passed, _msg(o)


def test_determinism(outcomes):
    o = outcomes["determinism"]
    assert o.passed, _msg(o)


def test_negation_not_counted_as_evidence(outcomes):
    o = outcomes["negation_not_counted_as_evidence"]
    assert o.passed, _msg(o)


def test_insufficient_content_handling(outcomes):
    o = outcomes["insufficient_content_handling"]
    assert o.passed, _msg(o)
