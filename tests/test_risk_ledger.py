"""
Tests for src/risk_ledger.py -- deterministic parsing of the "Risk Matrix
Overview" markdown table that risk_analyzer.py's RISK prompt already forces
the LLM to produce in an exact column format (see build_risk_prompt() in
src/risk_analyzer.py):

    | Risk ID | Risk Description | Likelihood | Impact | Risk Level | Priority |
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from risk_ledger import parse_risk_matrix, severity_tier  # noqa: E402

SAMPLE_REGISTER = """
# Risk Register — Example Project

## Executive Summary
This project carries Medium overall risk.

## Risk Matrix Overview

| Risk ID | Risk Description | Likelihood | Impact | Risk Level | Priority |
|---|---|---|---|---|---|
| R01 | Auth token expiry has no covering test case | High | High | Critical | 1 |
| R02 | No load test executed above 200 rps | Medium | Medium | Medium | 2 |
| R03 | Minor copy inconsistency in confirmation email | Low | Low | Low | 3 |

## Detailed Risk Analysis

### R01 — Auth token expiry
- **Category:** Technical
"""


def test_parse_risk_matrix_extracts_all_rows_in_order():
    rows = parse_risk_matrix(SAMPLE_REGISTER)
    assert [r["risk_id"] for r in rows] == ["R01", "R02", "R03"]


def test_parse_risk_matrix_extracts_all_columns():
    rows = parse_risk_matrix(SAMPLE_REGISTER)
    assert rows[0] == {
        "risk_id": "R01",
        "description": "Auth token expiry has no covering test case",
        "likelihood": "High",
        "impact": "High",
        "risk_level": "Critical",
        "priority": "1",
    }


def test_parse_risk_matrix_strips_markdown_bold_from_cells():
    # Real Mistral output routinely wraps Risk ID/Description cells in
    # **bold** even though the prompt doesn't ask for it -- found via a live
    # end-to-end browser check, not covered by SAMPLE_REGISTER above.
    text = (
        "## Risk Matrix Overview\n\n"
        "| Risk ID | Risk Description | Likelihood | Impact | Risk Level | Priority |\n"
        "|---|---|---|---|---|---|\n"
        "| **R01** | **Authentication & Session Security Flaws (OWASP A2, A5, A7)** "
        "| High | Critical | Critical | 1 |\n"
    )
    rows = parse_risk_matrix(text)
    assert rows[0]["risk_id"] == "R01"
    assert rows[0]["description"] == "Authentication & Session Security Flaws (OWASP A2, A5, A7)"
    assert "*" not in rows[0]["risk_id"]
    assert "*" not in rows[0]["description"]


def test_parse_risk_matrix_returns_empty_list_when_no_table_present():
    assert parse_risk_matrix("# Just a heading\n\nNo table here.") == []


def test_parse_risk_matrix_never_raises_on_malformed_input():
    malformed_inputs = [
        "",
        "| only one column |",
        "| Risk ID | Risk Description |\n|---|---|\n| R01 |",  # ragged row, too few cells
        "not markdown at all \x00\x01",
    ]
    for text in malformed_inputs:
        assert parse_risk_matrix(text) == [] or isinstance(parse_risk_matrix(text), list)


def test_severity_tier_maps_risk_levels():
    assert severity_tier("Low") == "pass"
    assert severity_tier("low") == "pass"
    assert severity_tier("Medium") == "hold"
    assert severity_tier("High") == "fail"
    assert severity_tier("Critical") == "fail"


def test_severity_tier_unknown_value_defaults_to_hold():
    assert severity_tier("Unknown") == "hold"
    assert severity_tier("") == "hold"
