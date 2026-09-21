"""Pytest wrapper over evals/results_integrity.py's real shipped-code checks.
Same migration rationale as tests/test_estimate_integrity.py."""
import pytest

from evals import results_integrity as RI


@pytest.fixture(scope="module")
def outcomes():
    return {o.name: o for o in RI.run_all()}


def _msg(outcome):
    return RI.format_table([outcome])


def test_flaky_and_ever_failing_boundaries(outcomes):
    o = outcomes["flaky_and_ever_failing_boundaries"]
    assert o.passed, _msg(o)


def test_cluster_count(outcomes):
    o = outcomes["cluster_count"]
    assert o.passed, _msg(o)


def test_malformed_input_never_crashes(outcomes):
    o = outcomes["malformed_input_never_crashes"]
    assert o.passed, _msg(o)


def test_csv_xml_parity(outcomes):
    o = outcomes["csv_xml_parity"]
    assert o.passed, _msg(o)
