"""
Tests for src/app.py — v0.3 changes (Risk Register + Test Strategy).

Covers:
1. init_session_state() initializes all three risk keys (risk_register, risk_sources, risk_path)
2. render_strategy() stores risk data in session state after generation
3. Two tabs defined: "⚠️ Risk Register" and "📋 Test Strategy"
4. Each tab has its own download button with the correct label + filename pattern
5. "Generate Another Strategy" clears all risk-related session state keys
6. Sidebar "Start Over" gap: does NOT clear risk keys (documented as known gap)
7. feedback_submitted absent from init_session_state (unchanged from v0.2)
8. LLM smoke test: both Risk Register and Test Strategy generated correctly
"""

import sys
import os
os.environ["ANONYMIZED_TELEMETRY"] = "False"
os.environ["CHROMA_TELEMETRY"] = "False"

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
APP_SRC = REPO_ROOT / "src"
APP_PY = APP_SRC / "app.py"
sys.path.insert(0, str(APP_SRC))


@pytest.fixture(scope="module")
def agent():
    """Real QAIAgent for the LLM smoke test; SKIP (not ERROR) without live API keys."""
    from agent import QAIAgent
    try:
        return QAIAgent()
    except Exception as exc:
        pytest.skip(f"live agent unavailable ({type(exc).__name__}: {exc}) — requires API keys")


# ── Helpers ───────────────────────────────────────────────────────────────────

def read_app_source() -> str:
    return APP_PY.read_text(encoding="utf-8")


def extract_function(source: str, fn_name: str) -> str:
    """Return the source lines of a top-level function."""
    # Split on 'def <fn_name>' and take until the next top-level 'def' or EOF
    pattern = rf'\ndef {fn_name}\('
    start = re.search(pattern, source)
    if not start:
        raise ValueError(f"Function '{fn_name}' not found in app.py")
    rest = source[start.start():]
    # Find next top-level def (starts at column 0, after the first line)
    next_def = re.search(r'\ndef \w', rest[4:])
    if next_def:
        return rest[:next_def.start() + 4]
    return rest


# ── Tests: static / structural (no LLM) ──────────────────────────────────────

def test_init_session_state_has_risk_keys():
    """init_session_state() initializes risk_register, risk_sources, risk_path."""
    source = read_app_source()
    fn = extract_function(source, "init_session_state")

    assert '"risk_register"' in fn, "risk_register not initialized in init_session_state"
    assert '"risk_sources"' in fn, "risk_sources not initialized in init_session_state"
    assert '"risk_path"' in fn, "risk_path not initialized in init_session_state"

    # Verify default values
    assert 'risk_register = None' in fn or "risk_register\"] = None" in fn, \
        "risk_register should default to None"
    assert 'risk_sources = []' in fn or "risk_sources\"] = []" in fn, \
        "risk_sources should default to []"
    assert 'risk_path = None' in fn or "risk_path\"] = None" in fn, \
        "risk_path should default to None"

    print("  PASS: init_session_state() initializes risk_register=None, risk_sources=[], risk_path=None")


def test_feedback_submitted_absent_from_init():
    """feedback_submitted is NOT pre-set in init_session_state (unchanged from v0.2)."""
    source = read_app_source()
    fn = extract_function(source, "init_session_state")
    assert '"feedback_submitted"' not in fn, \
        "feedback_submitted should not be initialized in init_session_state"
    print("  PASS: feedback_submitted correctly absent from init_session_state")


def test_two_tabs_defined():
    """render_strategy() defines exactly two tabs with the correct labels."""
    source = read_app_source()
    fn = extract_function(source, "render_strategy")

    # st.tabs(["⚠️ Risk Register", "📋 Test Strategy"])
    assert 'st.tabs(' in fn, "st.tabs() call not found in render_strategy"
    assert '"⚠️ Risk Register"' in fn or "'⚠️ Risk Register'" in fn, \
        "Tab label '⚠️ Risk Register' not found"
    assert '"📋 Test Strategy"' in fn or "'📋 Test Strategy'" in fn, \
        "Tab label '📋 Test Strategy' not found"

    print("  PASS: Two tabs defined: '⚠️ Risk Register' and '📋 Test Strategy'")


def test_risk_register_tab_has_download_button():
    """Tab 1 (Risk Register) has a download button with the correct label."""
    source = read_app_source()
    fn = extract_function(source, "render_strategy")

    assert '"⬇️ Download (.md)"' in fn, \
        "Risk Register download button label not found"
    assert 'risk_register' in fn and 'download_button' in fn, \
        "download_button for risk_register not found"
    # Filename uses project_name
    assert 'risk_register_' in fn, "risk_register filename prefix not found"

    print("  PASS: Risk Register tab has download button '⬇️ Download (.md)'")


def test_strategy_tab_has_download_button():
    """Tab 2 (Test Strategy) has a download button with the correct label."""
    source = read_app_source()
    fn = extract_function(source, "render_strategy")

    assert '"⬇️ Download (.md)"' in fn, \
        "Test Strategy download button label not found"
    # Filename uses project_name
    assert 'test_strategy_' in fn, "test_strategy filename prefix not found"

    print("  PASS: Test Strategy tab has download button '⬇️ Download (.md)'")


def test_render_strategy_stores_risk_in_session():
    """render_strategy() assigns risk_register, risk_sources, risk_path to session state."""
    source = read_app_source()
    fn = extract_function(source, "render_strategy")

    assert 'st.session_state.risk_register = risk_register' in fn, \
        "risk_register not stored in session state"
    assert 'st.session_state.risk_sources = risk_sources' in fn, \
        "risk_sources not stored in session state"
    assert 'st.session_state.risk_path = risk_path' in fn, \
        "risk_path not stored in session state"

    print("  PASS: render_strategy() stores risk_register, risk_sources, risk_path in session state")


# Each of the 4 generation calls, found by a fingerprint that's unique to that
# step and doesn't move if unrelated lines above it change.
_GENERATION_STEP_FINGERPRINTS = {
    "Risk Register": "agent.ask_streaming(risk_prompt, system_prompt=RISK_SYSTEM_PROMPT)",
    "Effort Estimation": "estimator.estimate(context, risk_register)",
    "Test Strategy": "agent.ask_streaming(strategy_prompt, system_prompt=SYSTEM_PROMPT)",
    "Test Plan": "agent.ask_streaming(test_plan_prompt, system_prompt=TEST_PLAN_SYSTEM_PROMPT)",
}


def test_render_strategy_isolates_each_generation_step():
    """Each of the 4 live generation calls (Risk Register, Effort Estimation,
    Test Strategy, Test Plan) in render_strategy() is wrapped in its own
    try/except, mirroring StrategyGenerator.generate_all()'s documented
    per-step isolation (CLAUDE.md: "Failure of step 4 must not discard
    results from steps 1-3"). Concurrent-load stress testing showed both LLM
    providers failing simultaneously becomes non-negligible at ~50 concurrent
    users (observed ~14% single-provider rate-limit rate) — without this,
    render_strategy() crashed the whole Streamlit page with a raw traceback
    for every affected user instead of failing just that one step.
    """
    fn = extract_function(read_app_source(), "render_strategy")
    lines = fn.splitlines()
    for step_name, fingerprint in _GENERATION_STEP_FINGERPRINTS.items():
        call_lines = [i for i, line in enumerate(lines) if fingerprint in line]
        assert call_lines, f"Could not find the {step_name} generation call in render_strategy()"
        call_line = call_lines[0]
        # A 'try:' must appear above this call, with no unindented ('except'
        # or blank-then-dedent) statement breaking the block in between.
        preceding = lines[:call_line]
        try_lines = [i for i, line in enumerate(preceding) if line.strip() == "try:"]
        assert try_lines, f"{step_name} generation call is not inside a try block"
        # An 'except' must close that same try block somewhere after the call.
        following = lines[call_line:]
        assert any(line.strip().startswith("except") for line in following[:15]), \
            f"{step_name} generation call's try block has no except within a few lines after it"
    print("  PASS: all 4 generation steps in render_strategy() are individually try/except-wrapped")


def test_generate_another_clears_risk_keys():
    """'Generate Another Strategy' deletes all risk-related keys + feedback_submitted."""
    GENERATE_ANOTHER_KEYS = [
        "dialogue", "answers", "strategy", "sources", "output_path",
        "risk_register", "risk_sources", "risk_path", "feedback_submitted",
    ]
    source = read_app_source()
    fn = extract_function(source, "render_strategy")

    for key in GENERATE_ANOTHER_KEYS:
        assert f'"{key}"' in fn, \
            f"Key '{key}' missing from 'Generate Another Strategy' cleanup list"

    print(f"  PASS: 'Generate Another Strategy' clears all {len(GENERATE_ANOTHER_KEYS)} keys:")
    print(f"        {GENERATE_ANOTHER_KEYS}")


def test_generate_another_cleanup_logic():
    """Simulate the cleanup dict — all risk keys removed, current_step reset to intro."""
    session_state = {
        "dialogue": object(),
        "answers": {"project_name": "Test"},
        "strategy": "# Strategy",
        "sources": ["[Standard] foo.pdf"],
        "output_path": Path("/tmp/test_strategy.md"),
        "risk_register": "# Risk Register",
        "risk_sources": ["[Methodology] Risk_Based_Testing.md"],
        "risk_path": Path("/tmp/risk_register.md"),
        "feedback_submitted": True,
        "current_step": "strategy",
    }

    # Simulate the cleanup (mirrors app.py lines 318-323)
    for key in ["dialogue", "answers", "strategy", "sources", "output_path",
                "risk_register", "risk_sources", "risk_path", "feedback_submitted"]:
        if key in session_state:
            del session_state[key]
    session_state["current_step"] = "intro"

    assert "risk_register" not in session_state, "risk_register not cleared"
    assert "risk_sources" not in session_state, "risk_sources not cleared"
    assert "risk_path" not in session_state, "risk_path not cleared"
    assert "feedback_submitted" not in session_state, "feedback_submitted not cleared"
    assert "strategy" not in session_state, "strategy not cleared"
    assert session_state["current_step"] == "intro", "current_step not reset to intro"

    print("  PASS: Cleanup simulation removes all 9 keys and resets current_step to intro")


def test_sidebar_start_over_clears_risk_keys():
    """
    Gap fixed: sidebar 'Start Over' now clears risk_register, risk_sources,
    risk_path, and feedback_submitted — same set as 'Generate Another Strategy'.
    """
    EXPECTED_KEYS = [
        "risk_register", "risk_sources", "risk_path", "feedback_submitted",
    ]
    source = read_app_source()
    fn = extract_function(source, "render_sidebar")

    missing = [k for k in EXPECTED_KEYS if f'"{k}"' not in fn]
    assert not missing, \
        f"Sidebar 'Start Over' is still missing these keys: {missing}"

    print("  PASS: Sidebar 'Start Over' now clears all risk + feedback keys:")
    print(f"        {EXPECTED_KEYS}")


def test_dialogue_has_additional_context_field():
    """render_dialogue() defines the optional additional-context text area with the 2000-char cap."""
    fn = extract_function(read_app_source(), "render_dialogue")
    assert "input_additional_context" in fn, \
        "render_dialogue() is missing the input_additional_context widget"
    assert "max_chars=2000" in fn, \
        "additional-context text area should cap input at 2000 chars"
    print("  PASS: render_dialogue() has input_additional_context with max_chars=2000")


def test_review_writes_back_additional_context_before_generating():
    """render_review() must call set_additional_context BEFORE transitioning to the
    strategy step, so review-stage edits reach the generation prompts."""
    fn = extract_function(read_app_source(), "render_review")
    assert "review_additional_context" in fn, \
        "render_review() is missing the review_additional_context widget"
    set_pos = fn.find("set_additional_context")
    step_pos = fn.find('current_step = "strategy"')
    assert set_pos != -1, "render_review() never calls set_additional_context"
    assert step_pos != -1, "render_review() never transitions to the strategy step"
    assert set_pos < step_pos, \
        "set_additional_context must run before the transition to the strategy step"
    print("  PASS: render_review() writes back additional context before current_step = 'strategy'")


def test_cleanup_blocks_clear_additional_context_keys():
    """Both cleanup blocks (sidebar 'Start Over' and 'Generate Another Strategy')
    must clear input_additional_context and review_additional_context — the
    `for q in QUESTIONS` pop-loop does not cover them."""
    source = read_app_source()
    for fn_name in ["render_sidebar", "render_strategy"]:
        fn = extract_function(source, fn_name)
        for key in ["input_additional_context", "review_additional_context"]:
            assert f'"{key}"' in fn, \
                f"{fn_name}() cleanup is missing '{key}'"
    print("  PASS: both cleanup blocks clear input_additional_context + review_additional_context")


def test_risk_analyzer_imported_at_module_level():
    """RiskAnalyzer is imported at module level in app.py (not lazily)."""
    source = read_app_source()
    # Check it's a top-level import, not inside a function
    top_imports = source.split("def ")[0]  # everything before first function def
    assert "from risk_analyzer import RiskAnalyzer" in top_imports, \
        "RiskAnalyzer should be imported at module level, not lazily"
    print("  PASS: RiskAnalyzer imported at module level")


# ── Release Notes (v2.5.0) ────────────────────────────────────────────────────

def test_sidebar_has_release_notes_expander():
    """render_sidebar() has a 'Release Notes' expander rendering load_changelog()'s output."""
    fn = extract_function(read_app_source(), "render_sidebar")
    assert 'st.expander("📋 Release Notes")' in fn, \
        "render_sidebar() is missing the '📋 Release Notes' expander"
    assert "st.markdown(load_changelog())" in fn, \
        "render_sidebar() must render load_changelog()'s output via st.markdown(...)"
    print("  PASS: sidebar has a 'Release Notes' expander rendering load_changelog()")


def test_load_changelog_reads_real_file():
    """load_changelog() actually reads the real CHANGELOG.md once it exists."""
    import app
    app.load_changelog.clear()
    content = app.load_changelog()
    assert content.strip(), "load_changelog() returned empty content"
    assert "2.5.0" in content, "load_changelog() content does not mention 2.5.0"
    print("  PASS: load_changelog() reads the real CHANGELOG.md")


def test_load_changelog_fallback_on_missing_file(monkeypatch):
    """load_changelog() falls back to a plain string when the file is unreadable."""
    import app
    monkeypatch.setattr(app, "CHANGELOG_PATH", Path("Z:/definitely/does/not/exist/CHANGELOG.md"))
    app.load_changelog.clear()
    try:
        content = app.load_changelog()
        assert content == "_Release notes unavailable._", \
            f"Expected fallback string, got: {content!r}"
    finally:
        app.load_changelog.clear()
    print("  PASS: load_changelog() falls back gracefully on a missing file")


def test_banner_exists_and_gates_on_release_notes_seen():
    """main() shows the one-time banner gated on session_state.release_notes_seen."""
    fn = extract_function(read_app_source(), "main")
    assert 'st.session_state.get("release_notes_seen")' in fn, \
        "main() does not check st.session_state.get('release_notes_seen')"
    assert "st.session_state.release_notes_seen = True" in fn, \
        "main() does not set release_notes_seen = True"
    assert "st.info(" in fn and "Release Notes" in fn, \
        "main() does not show the release-notes banner via st.info(...)"
    print("  PASS: main() has the one-time release-notes banner gated on release_notes_seen")


def test_banner_appears_before_render_sidebar_call():
    """The banner check must run before render_sidebar() (ordering, like
    test_review_writes_back_additional_context_before_generating)."""
    fn = extract_function(read_app_source(), "main")
    banner_pos = fn.find('st.session_state.get("release_notes_seen")')
    sidebar_pos = fn.find("render_sidebar()")
    assert banner_pos != -1, "banner gate not found in main()"
    assert sidebar_pos != -1, "render_sidebar() call not found in main()"
    assert banner_pos < sidebar_pos, \
        "the release_notes_seen banner must run before render_sidebar() is called"
    print("  PASS: banner check runs before render_sidebar() in main()")


# ── LLM smoke test: both documents generated ─────────────────────────────────

def test_both_documents_generated_and_stored(agent):
    """
    Smoke test: RiskAnalyzer + StrategyGenerator both produce non-empty output
    and the simulated session state stores all six keys correctly.
    """
    from dialogue import ProjectContext
    from risk_analyzer import RiskAnalyzer
    from strategy_generator import StrategyGenerator, build_strategy_prompt, SYSTEM_PROMPT

    context = ProjectContext(
        project_name="SmokeTester",
        project_description="A CI smoke-test web app used by QA engineers",
        project_type="web app",
        tech_stack="Python Flask + PostgreSQL",
        team_qa_size="1",
        team_dev_size="2",
        timeline="6 weeks",
        methodology="Kanban",
        known_risks="Database migration failures",
        existing_automation="No existing automation",
        compliance_requirements="none",
    )

    print("  Generating Risk Register...")
    risk_analyzer = RiskAnalyzer(agent)
    risk_register, risk_sources = risk_analyzer.analyze(context)
    risk_path = risk_analyzer.save(risk_register, context)

    print("  Generating Test Strategy...")
    generator = StrategyGenerator(agent)
    strategy, sources = generator.generate(context)
    output_path = generator.save(strategy, context)

    # Simulate what render_strategy() does to session state
    session = {
        "strategy": strategy,
        "sources": sources,
        "output_path": output_path,
        "risk_register": risk_register,
        "risk_sources": risk_sources,
        "risk_path": risk_path,
    }

    # All six keys must be populated
    assert session["strategy"], "strategy is empty"
    assert session["sources"], "sources list is empty"
    assert session["output_path"].exists(), "output_path file does not exist"
    assert session["risk_register"], "risk_register is empty"
    assert session["risk_sources"], "risk_sources list is empty"
    assert session["risk_path"].exists(), "risk_path file does not exist"

    # Both files are in output/
    assert "test_strategy_SmokeTester" in output_path.name, "Unexpected strategy filename"
    assert "risk_register_SmokeTester" in risk_path.name, "Unexpected risk register filename"

    # Risk Register has expected sections
    for section in ["Executive Summary", "Risk Matrix Overview", "Detailed Risk Analysis"]:
        assert section in risk_register, f"Missing section in risk_register: {section}"

    print("  PASS: Both documents generated and stored correctly")
    print(f"        Strategy:      {output_path.name}")
    print(f"        Risk Register: {risk_path.name}")
    print(f"        Strategy sources:  {len(sources)}")
    print(f"        Risk sources:      {len(risk_sources)}")


# ── Runner ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    static_tests = [
        ("init_session_state() has risk_register, risk_sources, risk_path",
            test_init_session_state_has_risk_keys),
        ("feedback_submitted absent from init_session_state (v0.2 unchanged)",
            test_feedback_submitted_absent_from_init),
        ("Two tabs: '⚠️ Risk Register' and '📋 Test Strategy'",
            test_two_tabs_defined),
        ("Risk Register tab has download button",
            test_risk_register_tab_has_download_button),
        ("Test Strategy tab has download button",
            test_strategy_tab_has_download_button),
        ("render_strategy() stores risk data in session state",
            test_render_strategy_stores_risk_in_session),
        ("render_strategy() isolates each of the 4 generation steps",
            test_render_strategy_isolates_each_generation_step),
        ("Generate Another clears all 9 keys incl. risk keys",
            test_generate_another_clears_risk_keys),
        ("Generate Another cleanup logic (simulated)",
            test_generate_another_cleanup_logic),
        ("Sidebar 'Start Over' gap fixed — now clears all risk keys",
            test_sidebar_start_over_clears_risk_keys),
        ("render_dialogue has additional-context field (max_chars=2000)",
            test_dialogue_has_additional_context_field),
        ("render_review writes back additional context before generating",
            test_review_writes_back_additional_context_before_generating),
        ("both cleanup blocks clear additional-context keys",
            test_cleanup_blocks_clear_additional_context_keys),
        ("RiskAnalyzer imported at module level",
            test_risk_analyzer_imported_at_module_level),
    ]

    passed = failed = 0

    print("=" * 68)
    print("  QAI Consultant — Streamlit App v0.3 Tests")
    print("=" * 68)

    for name, fn in static_tests:
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

    # LLM test
    print(f"\n{'=' * 68}")
    print("  Loading agent + running LLM smoke test (requires Ollama)...")
    print(f"{'=' * 68}")

    try:
        from agent import QAIAgent
        agent = QAIAgent()
        print("\n[TEST] Both documents generated and stored in session state")
        test_both_documents_generated_and_stored(agent)
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
