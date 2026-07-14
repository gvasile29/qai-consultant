"""
Tests for src/app.py — EU AI Act Article 50 transparency UI changes (v2.5.2).

Strategy: same source-extraction convention as test_app_v03.py / test_app_run_count.py
(Streamlit can't be driven headlessly here) — read app.py, extract a top-level
function's source text, and assert on it structurally.

Covers:
1. app.py imports AI_INTERACTION_NOTICE / with_ai_footer from ai_disclosure
2. render_sidebar() surfaces the AI_INTERACTION_NOTICE (Article 50(1) disclosure)
3. render_strategy() wraps all 4 markdown_to_pdf() calls with with_ai_footer()
4. render_strategy() wraps all 4 .md download_button data= with with_ai_footer()
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
    """Return the source lines of a top-level function."""
    pattern = rf'\ndef {fn_name}\('
    start = re.search(pattern, source)
    if not start:
        raise ValueError(f"Function '{fn_name}' not found in app.py")
    rest = source[start.start():]
    next_def = re.search(r'\ndef \w', rest[4:])
    if next_def:
        return rest[:next_def.start() + 4]
    return rest


def test_app_imports_ai_disclosure_helpers():
    """app.py imports AI_INTERACTION_NOTICE and with_ai_footer from ai_disclosure."""
    source = read_app_source()
    assert "from ai_disclosure import" in source, "app.py does not import from ai_disclosure"
    assert "AI_INTERACTION_NOTICE" in source, "AI_INTERACTION_NOTICE not referenced in app.py"
    assert "with_ai_footer" in source, "with_ai_footer not referenced in app.py"
    print("  PASS: app.py imports ai_disclosure helpers")


def test_sidebar_shows_ai_interaction_notice():
    """render_sidebar() renders the AI_INTERACTION_NOTICE (Article 50(1) disclosure)."""
    fn = extract_function(read_app_source(), "render_sidebar")
    assert "AI_INTERACTION_NOTICE" in fn, \
        "render_sidebar() does not surface AI_INTERACTION_NOTICE"
    print("  PASS: render_sidebar() surfaces AI_INTERACTION_NOTICE")


def test_pdf_exports_wrapped_with_ai_footer():
    """All 4 markdown_to_pdf() calls in render_strategy() wrap their text with with_ai_footer()."""
    fn = extract_function(read_app_source(), "render_strategy")
    pdf_calls = re.findall(r'markdown_to_pdf\(([^,]+),', fn)
    assert len(pdf_calls) == 4, f"Expected 4 markdown_to_pdf() calls, found {len(pdf_calls)}"
    for call_arg in pdf_calls:
        assert "with_ai_footer(" in call_arg, \
            f"markdown_to_pdf() call not wrapped with with_ai_footer(): {call_arg}"
    print("  PASS: all 4 markdown_to_pdf() calls wrapped with with_ai_footer()")


def test_md_download_buttons_wrapped_with_ai_footer():
    """All 4 .md download_button data= values wrap the document with with_ai_footer()."""
    fn = extract_function(read_app_source(), "render_strategy")
    # Each .md download button is immediately followed by file_name=f"..._{project_name}.md" —
    # matching on that pairing (rather than the whole call) sidesteps the literal "(.md)"
    # in the button label text, which would otherwise prematurely close a paren-balanced match.
    data_values = re.findall(r'data=([^,\n]+),\s*\n\s*file_name=f"[^"]*\.md"', fn)
    assert len(data_values) == 4, f"Expected 4 .md download_button() calls, found {len(data_values)}"
    for data_value in data_values:
        assert "with_ai_footer(" in data_value, \
            f".md download_button data= not wrapped with with_ai_footer(): {data_value}"
    print("  PASS: all 4 .md download_button() data= wrapped with with_ai_footer()")
