"""
Tests for src/app.py's "Assess QA Maturity" mode (v3.5) — session-state
cleanup-list membership and the reset helper's key-clearing behavior.
Mirrors tests/test_app_v03.py's Streamlit integration style: import app.py
with sys.path set up, exercise pure helpers and session-state dict logic
directly rather than driving a real Streamlit runtime.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

import app  # noqa: E402


def test_maturity_mode_state_keys_defined():
    assert isinstance(app.MATURITY_MODE_STATE_KEYS, list)
    assert "maturity_result" in app.MATURITY_MODE_STATE_KEYS
    assert "maturity_narrative" in app.MATURITY_MODE_STATE_KEYS
    assert "maturity_pdf_bytes" in app.MATURITY_MODE_STATE_KEYS


def test_reset_maturity_mode_state_clears_all_keys(monkeypatch):
    fake_state = {key: "x" for key in app.MATURITY_MODE_STATE_KEYS}
    fake_state["maturity_input_text"] = "some text"
    monkeypatch.setattr(app.st, "session_state", fake_state)

    app._reset_maturity_mode_state()

    for key in app.MATURITY_MODE_STATE_KEYS:
        assert key not in fake_state


def test_start_over_cleanup_includes_maturity_reset():
    import inspect
    source = inspect.getsource(app.render_sidebar)
    assert "_reset_maturity_mode_state()" in source


def test_generate_another_strategy_cleanup_includes_maturity_reset():
    import inspect
    source = inspect.getsource(app.render_strategy)
    assert "_reset_maturity_mode_state()" in source
