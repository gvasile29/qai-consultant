"""render_strategy() must keep the quiet progress view: no line-by-line st.write_stream for the 3 streamed stages,
and every stage still passes through _quiet_stream (the live-output expander is the only place the text shows)."""
import re
from pathlib import Path

APP_PY = Path(__file__).resolve().parent.parent.parent.parent / "src" / "app.py"


def _render_strategy_source() -> str:
    src = APP_PY.read_text(encoding="utf-8")
    start = src.index("def render_strategy():")
    end = src.index("\ndef ", start + 1)
    return src[start:end]


def test_pipeline_stages_use_quiet_stream():
    body = _render_strategy_source()
    assert "st.write_stream(" not in body
    labels = re.findall(r'_quiet_stream\(\s*agent\.ask_streaming\(.*?\),\s*"([^"]+)"', body, flags=re.S)
    assert labels == ["Risk Register", "Test Strategy", "Test Plan"]


def test_progress_bar_advances_by_finished_stages_only():
    body = _render_strategy_source()
    assert "progress_placeholder.progress(" in body
    assert "_finished / len(order)" in body
