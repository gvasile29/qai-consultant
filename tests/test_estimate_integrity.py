"""Pytest wrapper over evals/estimate_integrity.py's real shipped-code checks.

Migrated from a standalone `python -m evals.estimate_integrity` CLI (removed)
per the 2026-09-17 CI/evals simplification — the check logic (run_all(),
Finding, CheckOutcome) still lives in evals/estimate_integrity.py unchanged;
this file only adapts it to pytest so a second test-runner convention isn't
needed alongside the rest of tests/.
"""
import pytest

from evals import estimate_integrity as EI


@pytest.fixture(scope="module")
def outcomes():
    return {o.name: o for o in EI.run_all()}


def _msg(outcome):
    return EI.format_table([outcome])


def test_duration_bounds(outcomes):
    o = outcomes["duration_bounds"]
    assert o.passed, _msg(o)


def test_team_restatement_invariance(outcomes):
    o = outcomes["team_restatement_invariance"]
    assert o.passed, _msg(o)


def test_name_display_fidelity(outcomes):
    o = outcomes["name_display_fidelity"]
    assert o.passed, _msg(o)


def test_confidence_magnitude_sanity(outcomes):
    o = outcomes["confidence_magnitude_sanity"]
    assert o.passed, _msg(o)


def test_no_fabricated_versions(outcomes):
    o = outcomes["no_fabricated_versions"]
    assert o.passed, _msg(o)
