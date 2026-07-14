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

from ai_disclosure import AI_INTERACTION_NOTICE, AI_GENERATED_FOOTER, with_ai_footer


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


if __name__ == "__main__":
    tests = [
        test_ai_interaction_notice_mentions_ai_system,
        test_ai_generated_footer_is_visibly_labeled,
        test_with_ai_footer_appends_footer_to_content,
        test_with_ai_footer_empty_string_passthrough,
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
