"""
Tests for src/app.py — MAX_UPLOAD_BYTES / read_uploaded_text() upload-size
guard (architecture-review Important finding #3).

Streamlit's st.file_uploader() had no size guard of its own beyond the
platform default (200MB) on any of the app's 3 upload sites (Attach test
execution results, Review an Existing QA Document, Assess QA Maturity) —
inconsistent with mcp_server.py's explicit 10MB _MAX_RESULTS_INPUT_BYTES
clamp on the same results_core parsing path. read_uploaded_text() gives
all 3 sites that same ceiling.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

REPO_ROOT = Path(__file__).resolve().parent.parent
APP_SRC = REPO_ROOT / "src"
APP_PY = APP_SRC / "app.py"
sys.path.insert(0, str(APP_SRC))

import re


def read_app_source() -> str:
    return APP_PY.read_text(encoding="utf-8")


def extract_function(source: str, fn_name: str) -> str:
    pattern = rf'\ndef {fn_name}\('
    start = re.search(pattern, source)
    if not start:
        raise ValueError(f"Function '{fn_name}' not found in app.py")
    rest = source[start.start():]
    next_def = re.search(r'\ndef \w', rest[4:])
    if next_def:
        return rest[:next_def.start() + 4]
    return rest


def _fake_uploaded_file(content_bytes: bytes, name: str = "sample.md"):
    f = MagicMock()
    f.name = name
    f.getvalue.return_value = content_bytes
    return f


# ── Behavioral: read_uploaded_text() ─────────────────────────────────────────

def test_read_uploaded_text_returns_decoded_content_under_limit():
    import app

    f = _fake_uploaded_file("hello world".encode("utf-8"))
    assert app.read_uploaded_text(f) == "hello world"


def test_read_uploaded_text_rejects_oversized_file():
    import streamlit as st
    import app

    oversized = b"x" * (app.MAX_UPLOAD_BYTES + 1)
    f = _fake_uploaded_file(oversized, name="huge.md")

    result = app.read_uploaded_text(f)

    assert result is None


def test_read_uploaded_text_accepts_file_exactly_at_limit():
    import app

    exactly_at_limit = ("a" * app.MAX_UPLOAD_BYTES).encode("utf-8")
    f = _fake_uploaded_file(exactly_at_limit)

    result = app.read_uploaded_text(f)

    assert result is not None
    assert len(result) == app.MAX_UPLOAD_BYTES


def test_max_upload_bytes_matches_mcp_server_clamp():
    """The app's guard should use the same ceiling as mcp_server.py's
    analyze_test_results tool, not an independently-chosen number."""
    import app
    import mcp_server

    assert app.MAX_UPLOAD_BYTES == mcp_server._MAX_RESULTS_INPUT_BYTES


# ── Static: all 3 upload sites route through read_uploaded_text() ───────────

def test_results_upload_uses_read_uploaded_text():
    fn = extract_function(read_app_source(), "render_review")
    assert "read_uploaded_text(uploaded_file)" in fn
    assert ".read().decode(" not in fn


def test_doc_review_upload_uses_read_uploaded_text():
    fn = extract_function(read_app_source(), "render_doc_review")
    assert "read_uploaded_text(uploaded)" in fn
    assert ".read().decode(" not in fn


def test_maturity_upload_uses_read_uploaded_text():
    fn = extract_function(read_app_source(), "render_maturity_assessment")
    assert "read_uploaded_text(uploaded)" in fn
    assert ".read().decode(" not in fn
