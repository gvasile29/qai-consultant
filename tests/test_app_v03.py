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

REPO_ROOT = Path(__file__).resolve().parent.parent
APP_SRC = REPO_ROOT / "src"
APP_PY = APP_SRC / "app.py"
sys.path.insert(0, str(APP_SRC))


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

    assert '"⬇️ Download Risk Register (.md)"' in fn, \
        "Risk Register download button label not found"
    assert 'risk_register' in fn and 'download_button' in fn, \
        "download_button for risk_register not found"
    # Filename uses project_name
    assert 'risk_register_' in fn, "risk_register filename prefix not found"

    print("  PASS: Risk Register tab has download button '⬇️ Download Risk Register (.md)'")


def test_strategy_tab_has_download_button():
    """Tab 2 (Test Strategy) has a download button with the correct label."""
    source = read_app_source()
    fn = extract_function(source, "render_strategy")

    assert '"⬇️ Download Test Strategy (.md)"' in fn, \
        "Test Strategy download button label not found"
    # Filename uses project_name
    assert 'test_strategy_' in fn, "test_strategy filename prefix not found"

    print("  PASS: Test Strategy tab has download button '⬇️ Download Test Strategy (.md)'")


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


def test_risk_analyzer_imported_at_module_level():
    """RiskAnalyzer is imported at module level in app.py (not lazily)."""
    source = read_app_source()
    # Check it's a top-level import, not inside a function
    top_imports = source.split("def ")[0]  # everything before first function def
    assert "from risk_analyzer import RiskAnalyzer" in top_imports, \
        "RiskAnalyzer should be imported at module level, not lazily"
    print("  PASS: RiskAnalyzer imported at module level")


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
        ("Generate Another clears all 9 keys incl. risk keys",
            test_generate_another_clears_risk_keys),
        ("Generate Another cleanup logic (simulated)",
            test_generate_another_cleanup_logic),
        ("Sidebar 'Start Over' gap fixed — now clears all risk keys",
            test_sidebar_start_over_clears_risk_keys),
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
