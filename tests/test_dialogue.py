"""
Tests for src/dialogue.py — InputValidator and DialogueManager (v1.0).

No external dependencies — tests run without Ollama or ChromaDB.

Covers (21 tests):

InputValidator:
1.  Empty string → invalid, error contains "Please provide"
2.  Whitespace-only string → invalid
3.  project_name: valid name → spaces preserved (display fidelity)
4.  project_name: name with invalid filename chars (/ \\ : * ?) → chars stripped
5.  project_name: only invalid chars (e.g. '???') → invalid
6.  project_name: name > 50 chars → truncated to 50 chars
7.  project_description: < 10 chars → invalid, error contains "more specific"
8.  project_description: >= 10 chars → valid
9.  team_qa_size: "3" (digit) → valid
10. team_qa_size: "no dedicated QA" → valid (has 'no ' keyword)
11. team_qa_size: "three" (word number) → valid
12. team_qa_size: "yes definitely" → invalid (no number or known pattern)
13. Dangerous chars (<>{}|\\) stripped from answer
14. Answer > 500 chars → invalid, error contains "too long"

DialogueManager:
15. QUESTIONS list has exactly 11 entries
16. submit_answer() returns ValidationResult with valid=True on good input
17. submit_answer() returns ValidationResult with valid=False on empty input
18. submit_answer() does NOT advance current_question_index on failed validation
19. submit_answer() advances current_question_index on successful validation
20. get_context() returns ProjectContext with correct field stored
21. reset() clears all answers and resets index to 0
"""

import sys
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR   = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from dialogue import (
    InputValidator, DialogueManager, ProjectContext,
    QUESTIONS, ValidationResult,
    MAX_ANSWER_LENGTH, MAX_PROJECT_NAME_LENGTH, MIN_DESCRIPTION_LENGTH,
    MAX_ADDITIONAL_CONTEXT_LENGTH,
)


# ── Shared instances (stateless per test) ─────────────────────────────────────

def _v() -> InputValidator:
    return InputValidator()


# ── InputValidator tests ──────────────────────────────────────────────────────

def test_empty_string_invalid():
    """Empty string → invalid; error message contains 'Please provide'."""
    result = _v().validate("timeline", "")
    assert not result.valid, "Expected invalid for empty string"
    assert "Please provide" in result.error, \
        f"Expected 'Please provide' in error, got: '{result.error}'"
    print(f"  PASS: '' → invalid (error: '{result.error}')")


def test_whitespace_only_invalid():
    """Whitespace-only string → invalid (treated as empty after strip)."""
    result = _v().validate("timeline", "   ")
    assert not result.valid, "Expected invalid for whitespace-only input"
    print("  PASS: '   ' → invalid")


def test_project_name_preserves_spaces():
    """Valid project name: spaces are preserved in cleaned output (display fidelity);
    filename sanitization happens independently in each save() method."""
    result = _v().validate("project_name", "My Cool Project")
    assert result.valid, f"Expected valid, got error: '{result.error}'"
    assert result.cleaned == "My Cool Project", \
        f"Expected 'My Cool Project', got '{result.cleaned}'"
    print(f"  PASS: 'My Cool Project' → cleaned = '{result.cleaned}'")


def test_project_name_strips_invalid_filename_chars():
    """project_name: invalid filename chars (/ \\ : * ?) are stripped."""
    result = _v().validate("project_name", "my/project:test")
    assert result.valid, f"Expected valid after stripping, got: '{result.error}'"
    assert "/" not in result.cleaned, "/ should be stripped from project name"
    assert ":" not in result.cleaned, ": should be stripped from project name"
    assert len(result.cleaned) > 0, "Cleaned name should not be empty"
    print(f"  PASS: 'my/project:test' → cleaned = '{result.cleaned}' (invalid chars stripped)")


def test_project_name_only_invalid_chars():
    """project_name: name consisting only of invalid filename chars → invalid."""
    # '???' → all chars stripped by INVALID_FILENAME_CHARS → empty string → invalid
    result = _v().validate("project_name", "???")
    assert not result.valid, \
        f"Expected invalid for name with only invalid chars, got cleaned='{result.cleaned}'"
    print("  PASS: '???' → invalid (only invalid chars)")


def test_project_name_truncated_at_50():
    """project_name > 50 chars → cleaned is truncated to exactly 50 chars."""
    long_name = "A" * 60
    result = _v().validate("project_name", long_name)
    assert result.valid, f"Expected valid after truncation, got: '{result.error}'"
    assert len(result.cleaned) == MAX_PROJECT_NAME_LENGTH, \
        f"Expected cleaned length={MAX_PROJECT_NAME_LENGTH}, got {len(result.cleaned)}"
    print(f"  PASS: 60-char name → truncated to {len(result.cleaned)} chars")


def test_project_description_too_short_invalid():
    """project_description < 10 chars → invalid; error contains 'more specific'."""
    short = "web app"   # 7 chars, below MIN_DESCRIPTION_LENGTH=10
    assert len(short) < MIN_DESCRIPTION_LENGTH, \
        f"Precondition: '{short}' must be shorter than {MIN_DESCRIPTION_LENGTH}"
    result = _v().validate("project_description", short)
    assert not result.valid, "Expected invalid for short description"
    assert "more specific" in result.error.lower(), \
        f"Expected 'more specific' in error, got: '{result.error}'"
    print(f"  PASS: '{short}' ({len(short)} chars) → invalid (error: '{result.error}')")


def test_project_description_valid_at_minimum_length():
    """project_description >= 10 chars → valid."""
    desc = "A web app."   # exactly 10 chars
    assert len(desc) >= MIN_DESCRIPTION_LENGTH, \
        f"Precondition: must be >= {MIN_DESCRIPTION_LENGTH} chars"
    result = _v().validate("project_description", desc)
    assert result.valid, f"Expected valid for 10-char description, got: '{result.error}'"
    print(f"  PASS: '{desc}' ({len(desc)} chars) → valid")


def test_team_qa_size_number_valid():
    """team_qa_size: '3' (digit present) → valid."""
    result = _v().validate("team_qa_size", "3")
    assert result.valid, f"Expected valid for '3', got: '{result.error}'"
    print("  PASS: team_qa_size='3' → valid")


def test_team_qa_size_no_dedicated_qa_valid():
    """team_qa_size: 'no dedicated QA' (has 'no ' keyword) → valid."""
    result = _v().validate("team_qa_size", "no dedicated QA")
    assert result.valid, \
        f"Expected valid for 'no dedicated QA', got: '{result.error}'"
    print("  PASS: team_qa_size='no dedicated QA' → valid")


def test_team_qa_size_word_number_valid():
    """team_qa_size: 'three' (word number) → valid."""
    result = _v().validate("team_qa_size", "three")
    assert result.valid, f"Expected valid for 'three', got: '{result.error}'"
    print("  PASS: team_qa_size='three' → valid")


def test_team_qa_size_invalid():
    """team_qa_size: 'yes definitely' → invalid (no digit, no word number, no 'no' keyword)."""
    result = _v().validate("team_qa_size", "yes definitely")
    assert not result.valid, \
        f"Expected invalid for 'yes definitely', but got valid with cleaned='{result.cleaned}'"
    print(f"  PASS: team_qa_size='yes definitely' → invalid (error: '{result.error}')")


def test_dangerous_chars_stripped():
    """Dangerous chars (<>{}|\\) are stripped before validation.

    Input 'test<>{}' → dangerous chars removed → 'test' used for validation.
    The cleaned result must not contain any of the dangerous characters.
    """
    dangerous = "test<>{}"
    result = _v().validate("timeline", dangerous)
    # The answer becomes 'test' after stripping <, >, {, }
    # 'test' is 4 chars and passes default validation (>= 2 chars)
    for ch in "<>{}":
        assert ch not in result.cleaned, \
            f"Dangerous char '{ch}' should be stripped from '{result.cleaned}'"
    print(f"  PASS: 'test<>{{}}' → dangerous chars stripped; cleaned='{result.cleaned}'")


def test_answer_too_long_invalid():
    """Answer > 500 chars → invalid; error contains 'too long'."""
    long_answer = "x" * (MAX_ANSWER_LENGTH + 1)
    result = _v().validate("timeline", long_answer)
    assert not result.valid, "Expected invalid for answer exceeding max length"
    assert "too long" in result.error.lower(), \
        f"Expected 'too long' in error, got: '{result.error}'"
    print(f"  PASS: {len(long_answer)}-char answer → invalid (error: '{result.error[:60]}...')")


# ── Additional context tests ──────────────────────────────────────────────────

def test_additional_context_empty_valid():
    """validate_additional_context: empty/whitespace → valid with cleaned='' (field is optional)."""
    for raw in ["", "   ", "\n\t "]:
        result = _v().validate_additional_context(raw)
        assert result.valid, f"Expected valid for {raw!r}, got error: '{result.error}'"
        assert result.cleaned == "", f"Expected cleaned='' for {raw!r}, got '{result.cleaned}'"
    print("  PASS: empty/whitespace additional context → valid, cleaned=''")


def test_additional_context_length_boundary():
    """validate_additional_context: exactly 2000 chars valid; 2001 invalid with 'too long'."""
    at_limit = "x" * MAX_ADDITIONAL_CONTEXT_LENGTH
    result = _v().validate_additional_context(at_limit)
    assert result.valid, f"Expected valid at {MAX_ADDITIONAL_CONTEXT_LENGTH} chars, got: '{result.error}'"

    over_limit = "x" * (MAX_ADDITIONAL_CONTEXT_LENGTH + 1)
    result = _v().validate_additional_context(over_limit)
    assert not result.valid, f"Expected invalid at {len(over_limit)} chars"
    assert "too long" in result.error.lower(), \
        f"Expected 'too long' in error, got: '{result.error}'"
    print(f"  PASS: {MAX_ADDITIONAL_CONTEXT_LENGTH} chars valid; {MAX_ADDITIONAL_CONTEXT_LENGTH + 1} → invalid ('too long')")


def test_additional_context_dangerous_chars_stripped():
    """validate_additional_context: dangerous chars (<>{}) stripped, result still valid."""
    result = _v().validate_additional_context("legacy system<>{} with SOAP APIs")
    assert result.valid, f"Expected valid after stripping, got: '{result.error}'"
    for ch in "<>{}":
        assert ch not in result.cleaned, \
            f"Dangerous char '{ch}' should be stripped from '{result.cleaned}'"
    print(f"  PASS: dangerous chars stripped; cleaned='{result.cleaned}'")


def test_set_additional_context_valid_stored():
    """set_additional_context: valid input lands on context.additional_context."""
    dm = DialogueManager()
    result = dm.set_additional_context("The backend depends on a legacy SOAP service.")
    assert result.valid, f"Expected valid, got error: '{result.error}'"
    assert dm.context.additional_context == "The backend depends on a legacy SOAP service.", \
        f"Expected stored text, got '{dm.context.additional_context}'"
    print("  PASS: set_additional_context() stores valid text on the context")


def test_set_additional_context_invalid_keeps_prior_value():
    """set_additional_context: invalid input returns valid=False and leaves the prior value intact."""
    dm = DialogueManager()
    dm.set_additional_context("prior value")
    result = dm.set_additional_context("x" * (MAX_ADDITIONAL_CONTEXT_LENGTH + 1))
    assert not result.valid, "Expected valid=False for over-length input"
    assert dm.context.additional_context == "prior value", \
        f"Prior value should be untouched, got '{dm.context.additional_context}'"
    print("  PASS: invalid set_additional_context() leaves prior value intact")


def test_to_summary_includes_additional_context_when_set():
    """to_summary() includes the ADDITIONAL CONTEXT section only when the field is set."""
    ctx = ProjectContext(project_name="MyProject")
    assert "ADDITIONAL CONTEXT FROM THE USER" not in ctx.to_summary(), \
        "Empty additional_context must not add a section to to_summary()"

    ctx.additional_context = "Depends on a legacy SOAP service."
    summary = ctx.to_summary()
    assert "ADDITIONAL CONTEXT FROM THE USER" in summary, \
        "Section header missing from to_summary() when additional_context is set"
    assert "Depends on a legacy SOAP service." in summary, \
        "Additional context text missing from to_summary()"
    print("  PASS: to_summary() includes section when set, omits when empty")


def test_reset_clears_additional_context():
    """reset() clears additional_context along with the rest of the context."""
    dm = DialogueManager()
    dm.set_additional_context("some extra context here")
    assert dm.context.additional_context, "Precondition: additional_context should be set"
    dm.reset()
    assert dm.context.additional_context == "", \
        f"After reset: expected '', got '{dm.context.additional_context}'"
    print("  PASS: reset() clears additional_context")


# ── DialogueManager tests ─────────────────────────────────────────────────────

def test_11_questions_defined():
    """QUESTIONS list contains exactly 11 entries covering all project fields."""
    assert len(QUESTIONS) == 11, \
        f"Expected 11 questions, got {len(QUESTIONS)}"
    keys = [q["key"] for q in QUESTIONS]
    print(f"  PASS: {len(QUESTIONS)} questions defined: {keys}")


def test_submit_valid_returns_valid_result():
    """submit_answer() with valid input returns ValidationResult with valid=True."""
    dm = DialogueManager()
    # First question is 'project_name'
    result = dm.submit_answer("MyProject")
    assert isinstance(result, ValidationResult), \
        f"Expected ValidationResult, got {type(result)}"
    assert result.valid, \
        f"Expected valid=True for 'MyProject', got error='{result.error}'"
    print(f"  PASS: submit_answer('MyProject') → valid=True, cleaned='{result.cleaned}'")


def test_submit_empty_returns_invalid_result():
    """submit_answer() with empty string returns ValidationResult with valid=False."""
    dm = DialogueManager()
    result = dm.submit_answer("")
    assert isinstance(result, ValidationResult), \
        f"Expected ValidationResult, got {type(result)}"
    assert not result.valid, \
        "Expected valid=False for empty input"
    print(f"  PASS: submit_answer('') → valid=False (error: '{result.error}')")


def test_submit_invalid_does_not_advance_index():
    """submit_answer() with invalid input does NOT advance current_question_index."""
    dm = DialogueManager()
    index_before = dm.current_question_index
    dm.submit_answer("")   # invalid — empty string
    index_after = dm.current_question_index
    assert index_after == index_before, \
        f"Index should not advance on failed validation: before={index_before}, after={index_after}"
    print(f"  PASS: Failed submission: index stays at {index_after} (not advanced)")


def test_submit_valid_advances_index():
    """submit_answer() with valid input advances current_question_index by 1."""
    dm = DialogueManager()
    index_before = dm.current_question_index
    dm.submit_answer("MyProject")   # valid project name
    index_after = dm.current_question_index
    assert index_after == index_before + 1, \
        f"Expected index to advance from {index_before} to {index_before + 1}, got {index_after}"
    print(f"  PASS: Valid submission: index advanced from {index_before} to {index_after}")


def test_get_context_returns_correct_field():
    """get_context() returns ProjectContext with project_name set after submitting first answer."""
    dm = DialogueManager()
    dm.submit_answer("MyProject")   # submits to 'project_name' question
    context = dm.get_context()
    assert isinstance(context, ProjectContext), \
        f"Expected ProjectContext, got {type(context)}"
    assert context.project_name == "MyProject", \
        f"Expected project_name='MyProject', got '{context.project_name}'"
    print(f"  PASS: get_context().project_name = '{context.project_name}'")


def test_reset_clears_state():
    """reset() resets current_question_index to 0 and clears all stored answers."""
    dm = DialogueManager()

    # Submit two valid answers to advance the dialogue
    dm.submit_answer("MyProject")                    # Q1: project_name
    dm.submit_answer("A web application for managing tasks")  # Q2: project_description

    assert dm.current_question_index == 2, \
        f"Precondition: expected index=2, got {dm.current_question_index}"
    assert dm.context.project_name == "MyProject", \
        "Precondition: project_name should be set"

    # Reset
    dm.reset()

    assert dm.current_question_index == 0, \
        f"After reset: expected index=0, got {dm.current_question_index}"
    assert dm.context.project_name == "", \
        f"After reset: expected project_name='', got '{dm.context.project_name}'"
    assert not dm.completed, \
        "After reset: completed should be False"
    print("  PASS: reset() → index=0, project_name='', completed=False")


# ── Runner ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [
        # InputValidator
        ("empty string → invalid, error contains 'Please provide'",
            test_empty_string_invalid),
        ("whitespace-only string → invalid",
            test_whitespace_only_invalid),
        ("project_name: spaces preserved in cleaned",
            test_project_name_preserves_spaces),
        ("project_name: invalid filename chars (/ : ?) stripped",
            test_project_name_strips_invalid_filename_chars),
        ("project_name: only invalid chars → invalid",
            test_project_name_only_invalid_chars),
        ("project_name: > 50 chars → truncated to 50",
            test_project_name_truncated_at_50),
        ("project_description: < 10 chars → invalid, 'more specific' in error",
            test_project_description_too_short_invalid),
        ("project_description: >= 10 chars → valid",
            test_project_description_valid_at_minimum_length),
        ("team_qa_size: '3' → valid",
            test_team_qa_size_number_valid),
        ("team_qa_size: 'no dedicated QA' → valid",
            test_team_qa_size_no_dedicated_qa_valid),
        ("team_qa_size: 'three' (word number) → valid",
            test_team_qa_size_word_number_valid),
        ("team_qa_size: 'yes definitely' → invalid",
            test_team_qa_size_invalid),
        ("dangerous chars (<>{}) stripped from answer",
            test_dangerous_chars_stripped),
        ("answer > 500 chars → invalid, 'too long' in error",
            test_answer_too_long_invalid),
        # Additional context
        ("additional_context: empty/whitespace → valid, cleaned=''",
            test_additional_context_empty_valid),
        ("additional_context: 2000 chars valid, 2001 → 'too long'",
            test_additional_context_length_boundary),
        ("additional_context: dangerous chars stripped, still valid",
            test_additional_context_dangerous_chars_stripped),
        ("set_additional_context: valid text stored on context",
            test_set_additional_context_valid_stored),
        ("set_additional_context: invalid input keeps prior value",
            test_set_additional_context_invalid_keeps_prior_value),
        ("to_summary(): section present when set, absent when empty",
            test_to_summary_includes_additional_context_when_set),
        ("reset() clears additional_context",
            test_reset_clears_additional_context),
        # DialogueManager
        ("QUESTIONS list has exactly 11 entries",
            test_11_questions_defined),
        ("submit_answer() with valid input → valid=True",
            test_submit_valid_returns_valid_result),
        ("submit_answer() with empty input → valid=False",
            test_submit_empty_returns_invalid_result),
        ("submit_answer() invalid input → index NOT advanced",
            test_submit_invalid_does_not_advance_index),
        ("submit_answer() valid input → index advanced by 1",
            test_submit_valid_advances_index),
        ("get_context() returns ProjectContext with stored field",
            test_get_context_returns_correct_field),
        ("reset() clears answers and resets index to 0",
            test_reset_clears_state),
    ]

    passed = failed = 0

    print("=" * 68)
    print("  QAI Consultant — Dialogue Module v1.0 Tests")
    print("=" * 68)

    for name, fn in tests:
        print(f"\n[TEST] {name}")
        try:
            fn()
            passed += 1
        except AssertionError as e:
            print(f"  FAIL: {e}")
            failed += 1
        except Exception as e:
            import traceback
            print(f"  ERROR: {type(e).__name__}: {e}")
            traceback.print_exc()
            failed += 1

    print(f"\n{'=' * 68}")
    print(f"  Results: {passed} passed, {failed} failed")
    print(f"{'=' * 68}")

    import sys as _sys
    _sys.exit(0 if failed == 0 else 1)
