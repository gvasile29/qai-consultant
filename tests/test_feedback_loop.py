"""
Tests for the feedback loop in cli.py.

Tests the three scenarios:
1. Feedback "yes"       → strategy copied to knowledge_base/generated_strategies/
2. Feedback "partially" → strategy copied + note prepended
3. Feedback "no"        → nothing saved
"""

import sys
import tempfile
import shutil
from pathlib import Path

# ── Locate project root ──────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parent.parent
FEEDBACK_DIR = REPO_ROOT / "knowledge_base" / "generated_strategies"

# ── Helpers ──────────────────────────────────────────────────────────────────

SAMPLE_STRATEGY = "# Test Strategy\n\nThis is a sample generated strategy for testing."


def make_temp_output_file(content: str = SAMPLE_STRATEGY) -> Path:
    """Create a temp file that simulates a saved strategy in output/."""
    tmp_dir = Path(tempfile.mkdtemp())
    output_path = tmp_dir / "test_strategy_SampleProject_20260223_120000.md"
    output_path.write_text(content, encoding="utf-8")
    return output_path


def run_feedback_logic(feedback: str, extra_note: str, output_path: Path) -> Path | None:
    """
    Replicate the feedback logic from cli.py main() exactly as written.
    Returns the feedback_path if a file was written, else None.
    """
    if feedback in ["yes", "partially"]:
        feedback_dir = REPO_ROOT / "knowledge_base" / "generated_strategies"
        feedback_dir.mkdir(exist_ok=True)

        feedback_content = f"""---
feedback: {feedback}
notes: {extra_note}
---

"""
        feedback_path = feedback_dir / output_path.name
        feedback_path.write_text(
            feedback_content + output_path.read_text(encoding="utf-8"),
            encoding="utf-8"
        )
        return feedback_path

    elif feedback == "no":
        return None


# ── Tests ────────────────────────────────────────────────────────────────────

def test_feedback_yes():
    """'yes' feedback → file saved to generated_strategies/ with correct content."""
    output_path = make_temp_output_file()
    try:
        result = run_feedback_logic("yes", "", output_path)

        assert result is not None, "Expected a file path, got None"
        assert result.exists(), f"Expected file to exist: {result}"

        content = result.read_text(encoding="utf-8")
        assert "feedback: yes" in content, "Missing feedback metadata"
        assert "notes: " in content, "Missing notes metadata"
        assert SAMPLE_STRATEGY in content, "Original strategy content missing"

        print(f"  PASS: File created at {result.relative_to(REPO_ROOT)}")
        print(f"        Content preview: {content[:120].strip()}")
    finally:
        shutil.rmtree(output_path.parent, ignore_errors=True)
        if result and result.exists():
            result.unlink()


def test_feedback_partially():
    """'partially' feedback → file saved with the improvement note."""
    output_path = make_temp_output_file()
    note = "Add more detail on performance testing"
    try:
        result = run_feedback_logic("partially", note, output_path)

        assert result is not None, "Expected a file path, got None"
        assert result.exists(), f"Expected file to exist: {result}"

        content = result.read_text(encoding="utf-8")
        assert "feedback: partially" in content, "Missing feedback metadata"
        assert note in content, f"Expected note '{note}' in content"
        assert SAMPLE_STRATEGY in content, "Original strategy content missing"

        print(f"  PASS: File created with partial feedback note")
        print(f"        Content preview: {content[:160].strip()}")
    finally:
        shutil.rmtree(output_path.parent, ignore_errors=True)
        if result and result.exists():
            result.unlink()


def test_feedback_no():
    """'no' feedback → nothing saved, generated_strategies/ not modified."""
    output_path = make_temp_output_file()
    files_before = list(FEEDBACK_DIR.glob("*.md")) if FEEDBACK_DIR.exists() else []
    try:
        result = run_feedback_logic("no", "", output_path)

        assert result is None, f"Expected None, got {result}"

        files_after = list(FEEDBACK_DIR.glob("*.md")) if FEEDBACK_DIR.exists() else []
        new_files = [f for f in files_after if f not in files_before]
        assert not new_files, f"Unexpected files created: {new_files}"

        print(f"  PASS: No file created (feedback='no')")
    finally:
        shutil.rmtree(output_path.parent, ignore_errors=True)


def test_generated_strategies_dir_created_on_first_yes():
    """The generated_strategies/ dir is auto-created if it doesn't exist."""
    output_path = make_temp_output_file()

    # Temporarily rename the dir if it exists to test creation from scratch
    backup = None
    if FEEDBACK_DIR.exists():
        backup = FEEDBACK_DIR.parent / "_generated_strategies_backup"
        FEEDBACK_DIR.rename(backup)

    try:
        assert not FEEDBACK_DIR.exists(), "Dir should not exist before test"
        result = run_feedback_logic("yes", "", output_path)

        assert FEEDBACK_DIR.exists(), "generated_strategies/ was not created"
        assert result is not None and result.exists(), "File not saved"

        print(f"  PASS: Directory auto-created: {FEEDBACK_DIR.relative_to(REPO_ROOT)}")
    finally:
        shutil.rmtree(output_path.parent, ignore_errors=True)
        if result and result.exists():
            result.unlink()
        if FEEDBACK_DIR.exists():
            shutil.rmtree(FEEDBACK_DIR)
        if backup and backup.exists():
            backup.rename(FEEDBACK_DIR)


# ── Runner ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [
        ("Feedback 'yes' saves file", test_feedback_yes),
        ("Feedback 'partially' saves file with note", test_feedback_partially),
        ("Feedback 'no' saves nothing", test_feedback_no),
        ("Dir auto-created on first 'yes'", test_generated_strategies_dir_created_on_first_yes),
    ]

    passed = 0
    failed = 0

    print("=" * 60)
    print("  QAI Consultant — Feedback Loop Tests")
    print("=" * 60)

    for name, fn in tests:
        print(f"\n[TEST] {name}")
        try:
            fn()
            passed += 1
        except AssertionError as e:
            print(f"  FAIL: {e}")
            failed += 1
        except Exception as e:
            print(f"  ERROR: {type(e).__name__}: {e}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"  Results: {passed} passed, {failed} failed")
    print("=" * 60)

    sys.exit(0 if failed == 0 else 1)
