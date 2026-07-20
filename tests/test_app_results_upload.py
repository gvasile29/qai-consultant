"""
Tests for src/app.py — F2 "Attach test execution results" upload +
Risk Register grounding (v3.1).

Follows the existing test_app_*.py convention: static source-text checks
for structural/UI wiring (Streamlit can't be driven headlessly), plus a
few direct behavioral checks against real (bare-mode) st.session_state.
"""

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
APP_SRC = REPO_ROOT / "src"
APP_PY = APP_SRC / "app.py"
sys.path.insert(0, str(APP_SRC))


def read_app_source() -> str:
    return APP_PY.read_text(encoding="utf-8")


def extract_function(source: str, fn_name: str) -> str:
    """Return the source lines of a top-level function (mirrors
    tests/test_app_v03.py's helper of the same name)."""
    pattern = rf'\ndef {fn_name}\('
    start = re.search(pattern, source)
    if not start:
        raise ValueError(f"Function '{fn_name}' not found in app.py")
    rest = source[start.start():]
    next_def = re.search(r'\ndef \w', rest[4:])
    if next_def:
        return rest[:next_def.start() + 4]
    return rest


# ── init_session_state() ─────────────────────────────────────────────────────────

def test_init_session_state_has_results_analysis_key():
    fn = extract_function(read_app_source(), "init_session_state")
    assert '"results_analysis"' in fn
    assert "results_analysis = None" in fn


# ── render_review() upload expander ─────────────────────────────────────────────

def test_render_review_has_results_upload_expander():
    fn = extract_function(read_app_source(), "render_review")
    assert "Attach test execution results" in fn
    assert 'st.file_uploader(' in fn
    assert "accept_multiple_files=True" in fn
    assert 'key="results_uploader"' in fn


def test_render_review_parses_xml_and_csv_by_extension():
    fn = extract_function(read_app_source(), "render_review")
    assert "parse_results_csv(content)" in fn
    assert "parse_junit_xml(content, run_id=" in fn
    assert 'endswith(".csv")' in fn


def test_render_review_stores_results_analysis_in_session_state():
    fn = extract_function(read_app_source(), "render_review")
    assert "st.session_state.results_analysis = compute_results_analysis(records)" in fn


def test_render_review_shows_compact_metrics_panel():
    fn = extract_function(read_app_source(), "render_review")
    for metric in ("Runs", "Pass Rate", "Flaky Tests", "Ever-Failing"):
        assert f'.metric("{metric}"' in fn, f"Missing metric panel entry: {metric}"


# ── Risk Register grounding in render_strategy() ────────────────────────────────

def test_render_strategy_passes_results_summary_to_risk_prompt():
    fn = extract_function(read_app_source(), "render_strategy")
    assert "results_analysis = st.session_state.get(\"results_analysis\")" in fn
    assert "summarize_for_prompt(results_analysis)" in fn
    assert "results_summary=results_summary" in fn


def test_render_strategy_appends_execution_data_appendix():
    fn = extract_function(read_app_source(), "render_strategy")
    assert "append_execution_data_appendix(risk_register, results_summary)" in fn


# ── Session-state cleanup: both handlers clear results_analysis + uploader ──────

def test_start_over_clears_results_analysis_and_uploader():
    fn = extract_function(read_app_source(), "render_sidebar")
    assert '"results_analysis"' in fn
    assert 'st.session_state.pop("results_uploader", None)' in fn


def test_generate_another_strategy_clears_results_analysis_and_uploader():
    fn = extract_function(read_app_source(), "render_strategy")
    assert '"results_analysis"' in fn
    assert 'st.session_state.pop("results_uploader", None)' in fn


# ── Behavioral: init_session_state() actually sets the real default ─────────────

def test_init_session_state_sets_results_analysis_none_in_real_session_state():
    import streamlit as st
    import app

    st.session_state.pop("results_analysis", None)
    app.init_session_state()
    assert st.session_state.get("results_analysis") is None


# ── Imports wiring ───────────────────────────────────────────────────────────────

def test_app_imports_results_core_symbols():
    source = read_app_source()
    assert "from results_core import" in source
    for symbol in ("parse_junit_xml", "parse_results_csv", "summarize_for_prompt"):
        assert symbol in source
    assert "append_execution_data_appendix" in source
