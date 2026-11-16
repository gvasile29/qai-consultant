"""
Tests for src/app.py — EU AI Act Article 50 transparency UI changes (v2.5.2).

Strategy: same source-extraction convention as test_app_v03.py / test_app_run_count.py
(Streamlit can't be driven headlessly here) — read app.py, extract a top-level
function's source text, and assert on it structurally.

Covers:
1. app.py imports AI_INTERACTION_NOTICE / with_ai_footer from ai_disclosure
2. render_ai_notice() surfaces the AI_INTERACTION_NOTICE and the EU icon (Article 50(1)),
   and main() / render_intro() put it on every screen (it used to live in the sidebar only)
3. render_strategy() wraps all 4 markdown_to_pdf() calls with with_ai_footer()
4. render_strategy() wraps all 4 .md download_button data= with with_ai_footer()
"""

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
APP_SRC = REPO_ROOT / "src"
APP_PY = APP_SRC / "app.py"


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
    assert "from qai_consultant.compliance.ai_disclosure import" in source, "app.py does not import from ai_disclosure"
    assert "AI_INTERACTION_NOTICE" in source, "AI_INTERACTION_NOTICE not referenced in app.py"
    assert "with_ai_footer" in source, "with_ai_footer not referenced in app.py"
    print("  PASS: app.py imports ai_disclosure helpers")


def test_page_shows_ai_interaction_notice_and_icon():
    """render_ai_notice() renders the full AI_INTERACTION_NOTICE with the EU icon."""
    fn = extract_function(read_app_source(), "render_ai_notice")
    assert "AI_INTERACTION_NOTICE" in fn, "render_ai_notice() does not surface AI_INTERACTION_NOTICE"
    assert "build_ai_notice_html" in fn
    assert "_ai_icon_html()" in fn, "render_ai_notice() does not show the EU AI-generated icon"
    assert "eu_ai_generated_icon" in extract_function(read_app_source(), "_ai_icon_html")
    print("  PASS: render_ai_notice() surfaces AI_INTERACTION_NOTICE and the icon")


def test_notice_is_rendered_on_every_screen():
    """main() shows it on every screen but the landing page, whose own render_intro()
    shows it; neither may depend on the sidebar, which can be closed or collapsed."""
    source = read_app_source()
    main_fn = extract_function(source, "main")
    assert re.search(r"if not on_landing:\s+render_ai_notice\(\)", main_fn), \
        "main() must render the notice on every screen but the landing page"
    intro = extract_function(source, "render_intro")
    assert "render_ai_notice(" in intro
    assert "ai_icon_html=_ai_icon_html()" in intro, "the landing hero must carry the EU icon"
    assert "AI_INTERACTION_NOTICE" not in extract_function(source, "render_sidebar"),         "the notice must not live only in the sidebar"
    error_branch = main_fn[main_fn.index("if error:"):main_fn.index("st.stop()")]
    assert "render_ai_notice()" in error_branch, "the agent-load error screen must show the notice too"
    print("  PASS: the notice is rendered in the page on every screen")


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
