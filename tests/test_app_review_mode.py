"""
Tests for src/app.py — F1 "Review an existing QA document" mode (v3.1).

Follows the existing test_app_*.py convention: static source-text checks
for structural/UI wiring (Streamlit can't be driven headlessly), plus a
few direct behavioral checks against real (bare-mode) st.session_state for
pure state-management logic (_reset_review_mode_state, init_session_state).
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

def test_init_session_state_has_all_review_mode_keys():
    fn = extract_function(read_app_source(), "init_session_state")
    for key in (
        "review_input_text", "review_source_label", "review_result",
        "review_narrative", "review_narrative_sources", "review_output_path",
        "review_pdf_bytes",
    ):
        assert f'"{key}"' in fn, f"{key} not initialized in init_session_state"


def test_review_mode_state_keys_constant_matches_init_session_state():
    import app
    fn = extract_function(read_app_source(), "init_session_state")
    for key in app.REVIEW_MODE_STATE_KEYS:
        assert f'"{key}"' in fn, f"{key} in REVIEW_MODE_STATE_KEYS but not initialized"


# ── Cleanup wiring: both handlers + the mode's own reset call the shared helper ──

def test_start_over_calls_reset_review_mode_state():
    fn = extract_function(read_app_source(), "render_sidebar")
    assert "_reset_review_mode_state()" in fn, \
        "Start Over handler must call _reset_review_mode_state()"


def test_generate_another_strategy_calls_reset_review_mode_state():
    fn = extract_function(read_app_source(), "render_strategy")
    assert "_reset_review_mode_state()" in fn, \
        "Generate Another Strategy handler must call _reset_review_mode_state()"


def test_render_doc_review_calls_reset_review_mode_state():
    fn = extract_function(read_app_source(), "render_doc_review")
    assert fn.count("_reset_review_mode_state()") >= 2, \
        "render_doc_review()'s own reset buttons must call _reset_review_mode_state()"


def test_reset_review_mode_state_clears_real_session_state():
    """Behavioral: _reset_review_mode_state() actually removes every
    REVIEW_MODE_STATE_KEYS entry (plus widget keys) from st.session_state."""
    import streamlit as st
    import app

    for key in app.REVIEW_MODE_STATE_KEYS:
        st.session_state[key] = "sentinel"
    st.session_state["review_doc_uploader"] = "sentinel"
    st.session_state["review_doc_pasted_text"] = "sentinel"
    st.session_state["review_doc_type_select"] = "sentinel"
    st.session_state["unrelated_key"] = "keep-me"

    app._reset_review_mode_state()

    for key in app.REVIEW_MODE_STATE_KEYS:
        assert key not in st.session_state, f"{key} should have been cleared"
    assert "review_doc_uploader" not in st.session_state
    assert "review_doc_pasted_text" not in st.session_state
    assert "review_doc_type_select" not in st.session_state
    assert st.session_state.get("unrelated_key") == "keep-me"


def test_reset_review_mode_state_safe_when_keys_absent():
    import streamlit as st
    import app

    for key in app.REVIEW_MODE_STATE_KEYS:
        st.session_state.pop(key, None)

    app._reset_review_mode_state()  # must not raise


# ── Intro entry point ─────────────────────────────────────────────────────────────

def test_intro_has_review_document_entry_point():
    fn = extract_function(read_app_source(), "render_intro")
    assert 'current_step = "doc_review"' in fn, \
        "render_intro() must have a button that sets current_step to 'doc_review'"
    assert "Review an existing QA document" in fn


# ── main() dispatch ───────────────────────────────────────────────────────────────

def test_main_dispatches_doc_review_step():
    fn = extract_function(read_app_source(), "main")
    assert 'step == "doc_review"' in fn
    assert "render_doc_review()" in fn


# ── render_doc_review(): deterministic step is instant (no LLM before scoring) ────

def test_render_doc_review_calls_review_document_without_llm_gating():
    """The deterministic scoring call must not be behind a run_count / MAX_RUNS
    check — only the narrative step (further down) is."""
    fn = extract_function(read_app_source(), "render_doc_review")
    lines = fn.splitlines()

    call_lines = [i for i, line in enumerate(lines) if "review_document(document_text, doc_type=doc_type)" in line]
    assert call_lines, "review_document(document_text, doc_type=doc_type) call not found"
    call_line = call_lines[0]

    # Walk back to the nearest enclosing `if st.button(` that guards this call.
    button_lines = [
        i for i in range(call_line, -1, -1)
        if lines[i].strip().startswith("if st.button(")
    ]
    assert button_lines, "review_document() call is not inside an 'if st.button(...)' block"
    button_line = button_lines[0]

    guard_snippet = "\n".join(lines[button_line:call_line + 1])
    assert "run_count" not in guard_snippet
    assert "MAX_RUNS_PER_SESSION" not in guard_snippet


def test_render_doc_review_narrative_step_gated_on_run_count():
    fn = extract_function(read_app_source(), "render_doc_review")
    assert "MAX_RUNS_PER_SESSION" in fn
    assert 'st.session_state.get("run_count", 0) >= MAX_RUNS_PER_SESSION' in fn
    assert "st.session_state.run_count += 1" in fn


def test_render_doc_review_handles_insufficient_content():
    fn = extract_function(read_app_source(), "render_doc_review")
    assert 'result.doc_type == "insufficient_content"' in fn


# ── StopException/RerunException guard (CLAUDE.md gotcha) ─────────────────────────

def test_render_doc_review_reraises_stop_and_rerun_exception_before_generic_catch():
    """The narrative-streaming try/except must re-raise StopException/
    RerunException BEFORE its generic except Exception clause — mirrors
    tests/test_app_stopexception.py's check for render_strategy()'s 4 stages."""
    fn = extract_function(read_app_source(), "render_doc_review")
    lines = fn.splitlines()

    log_lines = [
        i for i, line in enumerate(lines)
        if 'logger.error("Quality review narrative generation failed: %s", exc)' in line
    ]
    assert log_lines, "Could not find the narrative-generation generic-except log line"
    log_line = log_lines[0]

    generic_except_lines = [
        i for i in range(max(0, log_line - 3), log_line)
        if lines[i].strip() == "except Exception as exc:"
    ]
    assert generic_except_lines, "Could not find 'except Exception as exc:' directly above the log line"
    generic_except_line = generic_except_lines[0]

    try_indent = len(lines[generic_except_line]) - len(lines[generic_except_line].lstrip(" "))
    gap_start = generic_except_line
    for i in range(generic_except_line - 1, -1, -1):
        stripped = lines[i].strip()
        if stripped == "try:" and (len(lines[i]) - len(lines[i].lstrip(" "))) == try_indent:
            gap_start = i + 1
            break
    preceding = lines[gap_start:generic_except_line]

    other_except_lines = [
        line for line in preceding
        if line.strip().startswith("except") and "StopException" not in line
    ]
    assert not other_except_lines, (
        f"Found another except clause between try/StopException-reraise and the "
        f"generic except: {other_except_lines}"
    )
    assert any("except (StopException, RerunException):" in line for line in preceding), (
        "'except (StopException, RerunException): raise' not found immediately "
        "before the generic 'except Exception as exc:' clause"
    )
    assert any(line.strip() == "raise" for line in preceding), \
        "The StopException/RerunException clause must re-raise, not handle"


def test_render_doc_review_reraise_clause_lists_both_exception_types():
    fn = extract_function(read_app_source(), "render_doc_review")
    count = fn.count("except (StopException, RerunException):")
    assert count == 1, f"Expected exactly 1 StopException/RerunException guard, found {count}"


# ── Save/PDF: Article 50(2) marking + once-only computation ───────────────────────

def test_render_doc_review_saves_via_review_generator_conventions():
    fn = extract_function(read_app_source(), "render_doc_review")
    assert "save_review_report(" in fn
    assert "build_review_report_markdown(" in fn
    assert "with_ai_footer(report_md)" in fn
    assert "pdf_meta_html(" in fn


def test_render_doc_review_pdf_bytes_computed_once_gated():
    fn = extract_function(read_app_source(), "render_doc_review")
    assert 'st.session_state.get("review_pdf_bytes") is None' in fn


# ── review_generator import wiring ─────────────────────────────────────────────────

def test_app_imports_review_core_and_review_generator():
    source = read_app_source()
    assert "from review_core import" in source
    assert "from review_generator import" in source
    assert "review_document" in source
    assert "build_review_prompt" in source
