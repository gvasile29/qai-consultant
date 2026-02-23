"""
Tests for the feedback loop in src/app.py (Streamlit Web UI).

Strategy: Streamlit can't be driven headlessly, so we test the logic
directly by replicating or importing the exact code paths from app.py.

Covers:
1. feedback='yes'        → file saved to generated_strategies/ with correct frontmatter
2. feedback='partially'  → file saved with improvement note in frontmatter
3. feedback='no'         → nothing saved
4. feedback_submitted    → guard prevents double submission
5. Generate Another      → 'feedback_submitted' cleared from session state
6. Dir auto-created      → generated_strategies/ created if absent
7. Partially UX fix      → note field shown immediately; save triggered once note filled
"""

import sys
import shutil
import tempfile
from pathlib import Path
from types import SimpleNamespace

# ── Project paths ────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parent.parent
APP_SRC = REPO_ROOT / "src"
FEEDBACK_DIR = REPO_ROOT / "knowledge_base" / "generated_strategies"

# ── Sample data ───────────────────────────────────────────────────────────────
SAMPLE_STRATEGY = "# Test Strategy — SampleProject\n\nGenerated strategy body."


def make_temp_output_file() -> Path:
    """Simulate a saved output/ file (what generator.save() produces)."""
    tmp = Path(tempfile.mkdtemp())
    p = tmp / "test_strategy_SampleProject_20260223_140000.md"
    p.write_text(SAMPLE_STRATEGY, encoding="utf-8")
    return p


# ── Extracted feedback logic from app.py render_strategy() ──────────────────
# Mirrors lines 314-347 of app.py exactly, but with session_state as a dict
# and without Streamlit UI calls.

def run_app_feedback_logic(feedback: str, extra_note: str, output_path: Path, session_state: dict) -> Path | None:
    """
    Mirrors the feedback block in render_strategy() (app.py lines 314-349).
    Returns the feedback_path if a file was written, else None.

    Updated to match the UX fix:
      - 'partially' with no note → st.stop() path: nothing saved, feedback_submitted stays unset
      - 'partially' with note    → save triggered immediately (same render cycle)
      - save condition: `if yes or (partially and extra_note)`
    """
    yes = (feedback == "yes")
    partially = (feedback == "partially")
    no = (feedback == "no")

    feedback_path = None

    # Mirror: if partially and no note → st.stop() (nothing happens)
    if partially and not extra_note:
        return None  # st.stop() equivalent — feedback_submitted not set

    # Mirror: extra_note is set from input when partially, else ""
    note = extra_note if partially else ""

    if yes or (partially and extra_note):
        feedback_dir = REPO_ROOT / "knowledge_base" / "generated_strategies"
        feedback_dir.mkdir(exist_ok=True)

        feedback_value = "yes" if yes else "partially"

        feedback_content = f"""---
feedback: {feedback_value}
notes: {note}
---

"""
        feedback_path = feedback_dir / output_path.name
        feedback_path.write_text(
            feedback_content + output_path.read_text(encoding="utf-8"),
            encoding="utf-8",
        )

        session_state["feedback_submitted"] = True

    if no:
        session_state["feedback_submitted"] = True
        # No file written

    return feedback_path


def run_generate_another_cleanup(session_state: dict):
    """Mirrors the 'Generate Another Strategy' button handler (app.py lines 293-298)."""
    for key in ["dialogue", "answers", "strategy", "sources", "output_path", "feedback_submitted"]:
        if key in session_state:
            del session_state[key]
    session_state["current_step"] = "intro"


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_feedback_yes():
    """'yes' → file saved with 'feedback: yes' frontmatter, feedback_submitted=True."""
    output_path = make_temp_output_file()
    session_state = {}
    result = None
    try:
        result = run_app_feedback_logic("yes", "", output_path, session_state)

        assert result is not None, "Expected a file path, got None"
        assert result.exists(), f"File not found: {result}"

        content = result.read_text(encoding="utf-8")
        assert "feedback: yes" in content, "Missing 'feedback: yes' in frontmatter"
        assert "notes: " in content, "Missing 'notes:' key"
        assert SAMPLE_STRATEGY in content, "Original strategy body missing"
        assert session_state.get("feedback_submitted") is True, "feedback_submitted not set"

        print(f"  PASS: File at {result.relative_to(REPO_ROOT)}")
        print(f"        Frontmatter: {content[:80].strip()}")
    finally:
        shutil.rmtree(output_path.parent, ignore_errors=True)
        if result and result.exists():
            result.unlink()


def test_feedback_partially():
    """'partially' → file saved with improvement note, feedback_submitted=True."""
    output_path = make_temp_output_file()
    note = "Add more coverage on security testing for OWASP Top 10"
    session_state = {}
    result = None
    try:
        result = run_app_feedback_logic("partially", note, output_path, session_state)

        assert result is not None, "Expected a file path, got None"
        assert result.exists(), f"File not found: {result}"

        content = result.read_text(encoding="utf-8")
        assert "feedback: partially" in content, "Missing 'feedback: partially'"
        assert note in content, f"Improvement note missing from saved file"
        assert SAMPLE_STRATEGY in content, "Original strategy body missing"
        assert session_state.get("feedback_submitted") is True, "feedback_submitted not set"

        print(f"  PASS: File with partial note saved")
        print(f"        Frontmatter: {content[:120].strip()}")
    finally:
        shutil.rmtree(output_path.parent, ignore_errors=True)
        if result and result.exists():
            result.unlink()


def test_feedback_no():
    """'no' → no file written, feedback_submitted=True."""
    output_path = make_temp_output_file()
    files_before = set(FEEDBACK_DIR.glob("*.md")) if FEEDBACK_DIR.exists() else set()
    session_state = {}
    try:
        result = run_app_feedback_logic("no", "", output_path, session_state)

        assert result is None, f"Expected None, got {result}"
        assert session_state.get("feedback_submitted") is True, "feedback_submitted not set"

        files_after = set(FEEDBACK_DIR.glob("*.md")) if FEEDBACK_DIR.exists() else set()
        new_files = files_after - files_before
        assert not new_files, f"Unexpected files created: {new_files}"

        print(f"  PASS: No file written, feedback_submitted=True")
    finally:
        shutil.rmtree(output_path.parent, ignore_errors=True)


def test_feedback_submitted_guard():
    """
    When feedback_submitted=True, the button row is not shown in the UI.
    We verify the guard condition: `not session_state.get('feedback_submitted', False)`.
    """
    # Simulate state BEFORE submission
    session_before = {}
    guard_before = not session_before.get("feedback_submitted", False)
    assert guard_before is True, "Buttons should be shown before submission"

    # Simulate state AFTER submission
    session_after = {"feedback_submitted": True}
    guard_after = not session_after.get("feedback_submitted", False)
    assert guard_after is False, "Buttons should be hidden after submission"

    print(f"  PASS: Guard correctly shows buttons only when feedback not yet submitted")


def test_feedback_submitted_not_set_by_default():
    """feedback_submitted is absent from session state by default (init_session_state doesn't set it)."""
    # Read init_session_state from app.py and verify feedback_submitted is not initialized
    app_source = (APP_SRC / "app.py").read_text(encoding="utf-8")

    # The function should NOT initialize feedback_submitted (it should be absent by default)
    # It IS used as: st.session_state.get("feedback_submitted", False)
    assert '"feedback_submitted"' not in app_source.split("def init_session_state")[1].split("def load_agent")[0], \
        "feedback_submitted should NOT be initialized in init_session_state — it must default to absent"

    print(f"  PASS: feedback_submitted is not pre-set in init_session_state (defaults to absent/False)")


def test_generate_another_clears_feedback_submitted():
    """'Generate Another Strategy' deletes feedback_submitted from session state."""
    session_state = {
        "dialogue": object(),
        "answers": {"project_name": "Test"},
        "strategy": "# Strategy",
        "sources": ["[Standard] foo.pdf"],
        "output_path": Path("/tmp/test.md"),
        "feedback_submitted": True,
        "current_step": "strategy",
    }

    run_generate_another_cleanup(session_state)

    assert "feedback_submitted" not in session_state, \
        "feedback_submitted should be removed after Generate Another"
    assert "strategy" not in session_state, "strategy should be cleared"
    assert "dialogue" not in session_state, "dialogue should be cleared"
    assert session_state.get("current_step") == "intro", "Should return to intro step"

    print(f"  PASS: 'Generate Another' clears feedback_submitted and resets to intro")


def test_generate_another_works_even_without_feedback_submitted():
    """Cleanup is safe even if user never gave feedback (feedback_submitted absent)."""
    session_state = {
        "dialogue": object(),
        "answers": {},
        "strategy": "# Strategy",
        "sources": [],
        "output_path": Path("/tmp/test.md"),
        # feedback_submitted intentionally absent
        "current_step": "strategy",
    }

    run_generate_another_cleanup(session_state)  # must not raise

    assert "feedback_submitted" not in session_state, "Should still be absent"
    assert session_state.get("current_step") == "intro"

    print(f"  PASS: Cleanup is safe when feedback_submitted was never set")


def test_generated_strategies_dir_autocreated():
    """generated_strategies/ is auto-created when first 'yes'/'partially' feedback is given."""
    output_path = make_temp_output_file()
    backup = None
    result = None

    # Temporarily hide the dir to simulate first run
    if FEEDBACK_DIR.exists():
        backup = FEEDBACK_DIR.parent / "_generated_strategies_backup"
        FEEDBACK_DIR.rename(backup)

    session_state = {}
    try:
        assert not FEEDBACK_DIR.exists(), "Dir should be absent before test"
        result = run_app_feedback_logic("yes", "", output_path, session_state)

        assert FEEDBACK_DIR.exists(), "generated_strategies/ was NOT auto-created"
        assert result is not None and result.exists(), "File was not saved"

        print(f"  PASS: generated_strategies/ auto-created on first 'yes'")
    finally:
        shutil.rmtree(output_path.parent, ignore_errors=True)
        if result and result.exists():
            result.unlink()
        if FEEDBACK_DIR.exists():
            shutil.rmtree(FEEDBACK_DIR)
        if backup and backup.exists():
            backup.rename(FEEDBACK_DIR)


def test_partially_ux_fix_one_interaction():
    """
    UX fix: 'partially' clicked → text input shown immediately → note filled → save in one render.

    Sub-case A: partially clicked, note empty → st.stop() path:
                nothing saved, feedback_submitted NOT set.
    Sub-case B: partially clicked, note filled → save triggered at once:
                file written, feedback: partially frontmatter, feedback_submitted=True.
    """
    output_path = make_temp_output_file()
    result_a = result_b = None
    try:
        # ── Sub-case A: partially with empty note → st.stop(), nothing saved ──
        session_a = {}
        result_a = run_app_feedback_logic("partially", "", output_path, session_a)

        assert result_a is None, \
            "Sub-case A: expected None (st.stop() path), file should NOT be written"
        assert "feedback_submitted" not in session_a, \
            "Sub-case A: feedback_submitted must NOT be set when note is empty"

        print("  PASS Sub-case A: empty note -> st.stop() path, nothing saved, "
              "feedback_submitted not set")

        # ── Sub-case B: partially with note → save triggered immediately ──────
        note = "Risk coverage section needs OWASP Top 10 breakdown"
        session_b = {}
        result_b = run_app_feedback_logic("partially", note, output_path, session_b)

        assert result_b is not None, "Sub-case B: expected file path, got None"
        assert result_b.exists(), f"Sub-case B: file not found: {result_b}"

        content = result_b.read_text(encoding="utf-8")
        assert "feedback: partially" in content, \
            "Sub-case B: missing 'feedback: partially' in frontmatter"
        assert note in content, \
            f"Sub-case B: improvement note missing from saved file"
        assert SAMPLE_STRATEGY in content, \
            "Sub-case B: original strategy body missing"
        assert session_b.get("feedback_submitted") is True, \
            "Sub-case B: feedback_submitted not set after save"

        print(f"  PASS Sub-case B: note filled -> file saved immediately in same render")
        print(f"        Frontmatter: {content[:130].strip()}")

    finally:
        shutil.rmtree(output_path.parent, ignore_errors=True)
        if result_b and result_b.exists():
            result_b.unlink()


# ── Runner ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [
        ("Feedback 'yes' saves file with frontmatter",       test_feedback_yes),
        ("Feedback 'partially' saves file with note",        test_feedback_partially),
        ("Feedback 'no' saves nothing",                      test_feedback_no),
        ("feedback_submitted guard prevents double submit",  test_feedback_submitted_guard),
        ("feedback_submitted absent from init_session_state",test_feedback_submitted_not_set_by_default),
        ("Generate Another clears feedback_submitted",       test_generate_another_clears_feedback_submitted),
        ("Generate Another safe when no feedback given",     test_generate_another_works_even_without_feedback_submitted),
        ("generated_strategies/ auto-created on first yes",  test_generated_strategies_dir_autocreated),
        ("Partially UX fix: note shown immediately, saves in one render",
                                                              test_partially_ux_fix_one_interaction),
    ]

    passed = 0
    failed = 0

    print("=" * 65)
    print("  QAI Consultant — Streamlit App Feedback Loop Tests")
    print("=" * 65)

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

    print("\n" + "=" * 65)
    print(f"  Results: {passed} passed, {failed} failed")
    print("=" * 65)

    sys.exit(0 if failed == 0 else 1)
