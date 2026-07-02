"""
Tests for src/app.py — session_state AttributeError regression (live-stress-test finding).

Reproduced live on the deployed app: typing into the first dialogue field and then
blurring it crashed the whole app with
    AttributeError: st.session_state has no attribute "agent"
even though init_session_state() unconditionally sets st.session_state.agent as its
first statement in main(). Streamlit's own session_state proxy raises AttributeError
(not KeyError-with-default) for a missing key accessed via attribute syntax, so any
`st.session_state.<key> is None` check executed before that key is guaranteed set for
THIS run is one dropped/late init away from crashing the whole app for every user.

Covers (5 tests):
1.  main(): the "agent" sentinel check uses st.session_state.get(...), not attribute access
2.  main(): current_step is read via st.session_state.get(...) with an "intro" default
3.  render_strategy(): run_count is read via st.session_state.get(...) with a 0 default
4.  render_strategy(): the "agent" sentinel check uses st.session_state.get(...)
5.  render_strategy(): the "strategy" sentinel check uses st.session_state.get(...)
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


# ── Helpers (same pattern as test_app_v03.py) ─────────────────────────────────

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


# ── Tests ──────────────────────────────────────────────────────────────────────

def test_main_agent_check_uses_safe_get():
    """main()'s agent sentinel check must not use bare attribute access (crashes if
    the key is momentarily absent — reproduced live on the deployed app)."""
    fn = extract_function(read_app_source(), "main")
    assert "st.session_state.agent is None" not in fn, \
        "main() still checks st.session_state.agent via bare attribute access"
    assert 'st.session_state.get("agent")' in fn, \
        "main() should read agent via st.session_state.get(\"agent\")"
    print("  PASS: main()'s agent check uses st.session_state.get(...)")


def test_main_current_step_uses_safe_get():
    """main()'s current_step read must not use bare attribute access."""
    fn = extract_function(read_app_source(), "main")
    assert "st.session_state.current_step" not in fn, \
        "main() still reads st.session_state.current_step via bare attribute access"
    assert 'st.session_state.get("current_step", "intro")' in fn, \
        "main() should read current_step via st.session_state.get(\"current_step\", \"intro\")"
    print("  PASS: main()'s current_step read uses st.session_state.get(...) with an 'intro' default")


def test_render_strategy_run_count_uses_safe_get():
    """render_strategy()'s run_count check must not use bare attribute access."""
    fn = extract_function(read_app_source(), "render_strategy")
    assert "st.session_state.run_count >=" not in fn, \
        "render_strategy() still checks st.session_state.run_count via bare attribute access"
    assert 'st.session_state.get("run_count", 0)' in fn, \
        "render_strategy() should read run_count via st.session_state.get(\"run_count\", 0)"
    print("  PASS: render_strategy()'s run_count check uses st.session_state.get(...)")


def test_render_strategy_agent_check_uses_safe_get():
    """render_strategy()'s agent sentinel check must not use bare attribute access."""
    fn = extract_function(read_app_source(), "render_strategy")
    assert "agent = st.session_state.agent" not in fn, \
        "render_strategy() still reads st.session_state.agent via bare attribute access"
    assert 'agent = st.session_state.get("agent")' in fn, \
        "render_strategy() should read agent via st.session_state.get(\"agent\")"
    print("  PASS: render_strategy()'s agent check uses st.session_state.get(...)")


def test_render_strategy_strategy_check_uses_safe_get():
    """render_strategy()'s strategy sentinel check must not use bare attribute access."""
    fn = extract_function(read_app_source(), "render_strategy")
    assert "st.session_state.strategy is None" not in fn, \
        "render_strategy() still checks st.session_state.strategy via bare attribute access"
    assert 'st.session_state.get("strategy") is None' in fn, \
        "render_strategy() should check strategy via st.session_state.get(\"strategy\")"
    print("  PASS: render_strategy()'s strategy check uses st.session_state.get(...)")


# ── Runner ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [
        ("main(): agent check uses safe .get()", test_main_agent_check_uses_safe_get),
        ("main(): current_step read uses safe .get()", test_main_current_step_uses_safe_get),
        ("render_strategy(): run_count check uses safe .get()", test_render_strategy_run_count_uses_safe_get),
        ("render_strategy(): agent check uses safe .get()", test_render_strategy_agent_check_uses_safe_get),
        ("render_strategy(): strategy check uses safe .get()", test_render_strategy_strategy_check_uses_safe_get),
    ]
    passed = failed = 0
    for name, test_fn in tests:
        try:
            test_fn()
            passed += 1
        except AssertionError as e:
            print(f"  FAIL: {name} — {e}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
    raise SystemExit(1 if failed else 0)
