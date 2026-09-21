"""Pytest wrapper over evals/review_integrity.py's real shipped-code checks.
Same migration rationale as tests/test_estimate_integrity.py."""
import pytest

from evals import review_integrity as RI


@pytest.fixture(scope="module")
def outcomes():
    return {o.name: o for o in RI.run_all()}


def _msg(outcome):
    return RI.format_table([outcome])


def test_score_ordering(outcomes):
    o = outcomes["score_ordering"]
    assert o.passed, _msg(o)


def test_dimension_attribution(outcomes):
    o = outcomes["dimension_attribution"]
    assert o.passed, _msg(o)


def test_determinism(outcomes):
    o = outcomes["determinism"]
    assert o.passed, _msg(o)


def test_insufficient_content_handling(outcomes):
    o = outcomes["insufficient_content_handling"]
    assert o.passed, _msg(o)
