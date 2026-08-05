"""Tests for src/ledger_components.py -- Signal Ledger / Risk Ledger HTML builders.

These build HTML strings only (no Streamlit runtime needed to test them --
st.markdown() is the caller's job, not this module's).
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from ledger_components import (  # noqa: E402
    risk_ledger_table_html,
    score_tier,
    signal_ledger_html,
)

SAMPLE_ROWS = [
    {"risk_id": "R01", "description": "Auth token expiry untested", "likelihood": "High",
     "impact": "High", "risk_level": "Critical", "priority": "1"},
    {"risk_id": "R02", "description": "No load test above 200 rps", "likelihood": "Medium",
     "impact": "Medium", "risk_level": "Medium", "priority": "2"},
]


def test_score_tier_boundaries():
    assert score_tier(100) == "pass"
    assert score_tier(80) == "pass"
    assert score_tier(79) == "hold"
    assert score_tier(50) == "hold"
    assert score_tier(49) == "fail"
    assert score_tier(0) == "fail"


def test_signal_ledger_html_contains_label_and_score():
    html = signal_ledger_html("Confidence", 72, sub="cited from 6 sources")
    assert "Confidence" in html
    assert "72" in html
    assert "cited from 6 sources" in html
    assert 'class="signal-ledger"' in html


def test_signal_ledger_html_uses_computed_tier_class():
    html = signal_ledger_html("Overall Score", 84)
    assert "sl-score pass" in html
    html = signal_ledger_html("Overall Score", 61)
    assert "sl-score hold" in html
    html = signal_ledger_html("Overall Score", 30)
    assert "sl-score fail" in html


def test_signal_ledger_html_accepts_explicit_tier_override():
    # e.g. effort confidence is a "how sure are we" score, not a "how good
    # is this" score -- callers may want to force the tier explicitly.
    html = signal_ledger_html("Confidence", 90, tier="hold")
    assert "sl-score hold" in html


def test_signal_ledger_html_escapes_label_and_sub_text():
    html = signal_ledger_html("<script>alert(1)</script>", 50, sub="<b>x</b>")
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_risk_ledger_table_html_renders_all_rows():
    html = risk_ledger_table_html(SAMPLE_ROWS)
    # 1 header <tr> (inside <thead>) + 1 per data row (2 rows here) = 3.
    assert html.count("<tr>") == 3
    assert "R01" in html and "R02" in html
    assert "Auth token expiry untested" in html


def test_risk_ledger_table_html_uses_severity_tier_classes():
    html = risk_ledger_table_html(SAMPLE_ROWS)
    assert 'class="sev fail"' in html   # Critical -> fail
    assert 'class="sev hold"' in html   # Medium -> hold


def test_risk_ledger_table_html_empty_rows_returns_empty_string():
    assert risk_ledger_table_html([]) == ""


def test_risk_ledger_table_html_escapes_description():
    rows = [{"risk_id": "R01", "description": "<img src=x onerror=alert(1)>",
              "likelihood": "Low", "impact": "Low", "risk_level": "Low", "priority": "1"}]
    html = risk_ledger_table_html(rows)
    assert "<img" not in html
    assert "&lt;img" in html
