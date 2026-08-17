"""Tests for src/app.py's Phase 2 interactive-flow wiring (dialogue,
review, sidebar) -- see
docs/superpowers/specs/2026-08-06-interactive-flow-power-on-redesign-design.md."""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
APP_SRC = REPO_ROOT / "src"
APP_PY = APP_SRC / "app.py"
sys.path.insert(0, str(APP_SRC))


def read_app_source() -> str:
    return APP_PY.read_text(encoding="utf-8")


def extract_function(source: str, fn_name: str) -> str:
    """Return the source lines of a top-level function (same helper used
    across the app.py test suite, e.g. tests/test_app_mcp_banner.py)."""
    import re
    pattern = rf'\ndef {fn_name}\('
    match = re.search(pattern, source)
    assert match, f"Could not find 'def {fn_name}(' in app.py"
    start = match.start() + 1
    next_def = re.search(r'\ndef \w+\(', source[start + len(f"def {fn_name}("):])
    end = start + len(f"def {fn_name}(") + next_def.start() if next_def else len(source)
    return source[start:end]


def test_dialogue_uses_the_new_header_builder():
    fn = extract_function(read_app_source(), "render_dialogue")
    assert "build_dialogue_header_html" in fn
    assert "st.progress(" not in fn, \
        "render_dialogue() should no longer call the native st.progress()"


def test_review_uses_the_new_summary_builder_and_sets_the_seen_flag():
    fn = extract_function(read_app_source(), "render_review")
    assert "build_review_summary_html" in fn
    assert "st.session_state.review_intro_animated = True" in fn
    assert "st.code(context.project_name)" not in fn, \
        "render_review() should no longer render the old plain st.code() summary"


def test_sidebar_uses_the_new_polish_css():
    fn = extract_function(read_app_source(), "render_sidebar")
    assert "build_sidebar_polish_css" in fn


def test_cleanup_blocks_do_not_clear_review_intro_animated():
    source = read_app_source()
    for fn_name in ["render_sidebar", "render_strategy"]:
        fn = extract_function(source, fn_name)
        assert '"review_intro_animated"' not in fn, \
            f"{fn_name}() must NOT clear review_intro_animated"
