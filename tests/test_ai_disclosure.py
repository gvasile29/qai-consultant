"""
Tests for src/ai_disclosure.py — EU AI Act Article 50 transparency (v2.5.2).

Covers:
1. AI_INTERACTION_NOTICE — sidebar disclosure text mentions AI system interaction
2. AI_GENERATED_FOOTER — visible "AI-generated" marker text
3. with_ai_footer() — appends footer to markdown content, preserves original text
4. with_ai_footer() — empty/falsy input passes through unchanged (no footer-only doc
   when a generation step failed and returned "")
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from ai_disclosure import (
    AI_INTERACTION_NOTICE,
    AI_GENERATED_FOOTER,
    EU_AI_ICON_DIR,
    pdf_icon_html,
    with_ai_footer,
)


def test_ai_interaction_notice_mentions_ai_system():
    """Sidebar notice explicitly informs the user they are interacting with an AI system."""
    assert "AI system" in AI_INTERACTION_NOTICE
    print("  PASS: AI_INTERACTION_NOTICE mentions 'AI system'")


def test_ai_generated_footer_is_visibly_labeled():
    """Footer text is a clear, human-readable 'AI-generated' label."""
    assert "AI-generated" in AI_GENERATED_FOOTER
    print("  PASS: AI_GENERATED_FOOTER contains 'AI-generated' label")


def test_with_ai_footer_appends_footer_to_content():
    """with_ai_footer() returns the original content plus the AI-generated footer."""
    content = "# Risk Register — Sample\n\nSome generated body text."
    result = with_ai_footer(content)

    assert content in result, "Original content missing from footed result"
    assert "AI-generated" in result, "Footer label missing from result"
    assert result.index(content) < result.index("AI-generated"), \
        "Footer must come after the document body, not before it"

    print("  PASS: with_ai_footer() appends visible label after original content")


def test_with_ai_footer_empty_string_passthrough():
    """Empty content (e.g. a failed generation step) is returned unchanged, no bare footer."""
    assert with_ai_footer("") == ""
    print("  PASS: with_ai_footer('') returns '' unchanged")


def test_pdf_icon_html_returns_data_uri_img_tag():
    """pdf_icon_html() returns a base64 data-URI <img> tag for the vendored PNG."""
    html = pdf_icon_html()
    assert html.startswith("<img "), f"Expected an <img> tag, got: {html[:50]!r}"
    assert "data:image/png;base64," in html
    assert "alt=" in html, "Missing alt text for assistive technologies"
    print("  PASS: pdf_icon_html() returns a data-URI <img> tag")


def test_pdf_icon_html_missing_file_returns_empty_string():
    """A missing/renamed asset file fails soft — no exception, no broken PDF."""
    assert pdf_icon_html("does_not_exist.png") == ""
    print("  PASS: pdf_icon_html() with a missing file returns ''")


def test_vendored_icon_assets_exist():
    """Guards against accidental deletion/rename of the vendored icon files."""
    for fname in (
        "eu_ai_generated_icon.svg",
        "eu_ai_generated_icon_dark.svg",
        "eu_ai_generated_icon.png",
    ):
        path = EU_AI_ICON_DIR / fname
        assert path.is_file(), f"Missing vendored asset: {path}"
    print("  PASS: all three vendored EU AI icon assets exist")


if __name__ == "__main__":
    tests = [
        test_ai_interaction_notice_mentions_ai_system,
        test_ai_generated_footer_is_visibly_labeled,
        test_with_ai_footer_appends_footer_to_content,
        test_with_ai_footer_empty_string_passthrough,
        test_pdf_icon_html_returns_data_uri_img_tag,
        test_pdf_icon_html_missing_file_returns_empty_string,
        test_vendored_icon_assets_exist,
    ]
    passed = failed = 0
    for fn in tests:
        print(f"\n[TEST] {fn.__name__}")
        try:
            fn()
            passed += 1
        except AssertionError as e:
            print(f"  FAIL: {e}")
            failed += 1
    print(f"\nResults: {passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)
