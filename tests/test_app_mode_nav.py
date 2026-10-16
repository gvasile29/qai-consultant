"""
Tests for src/app.py's mode navigation (landing CTAs + sidebar mode
switcher): _current_mode(), _go_to(), _generation_in_progress(), and the
narrative "pending" flag that lets the sidebar lock mode switching before
an LLM call starts.

Same convention as tests/test_app_review_mode.py: behavioral checks against
real (bare-mode) st.session_state for the pure state logic, plus static
source checks for the Streamlit wiring.
"""

import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
APP_SRC = REPO_ROOT / "src"
APP_PY = APP_SRC / "app.py"
sys.path.insert(0, str(APP_SRC))

import streamlit as st  # noqa: E402

import app  # noqa: E402
from components import APP_MODES  # noqa: E402

_NAV_KEYS = [
    "current_step", "strategy_resume_step", "results_complete", "generation_started",
    "run_count", "review_narrative_pending", "maturity_narrative_pending",
]


def extract_function(source: str, fn_name: str) -> str:
    start = re.search(rf'\ndef {fn_name}\(', source)
    if not start:
        raise ValueError(f"Function '{fn_name}' not found in app.py")
    rest = source[start.start():]
    next_def = re.search(r'\ndef \w', rest[4:])
    return rest[:next_def.start() + 4] if next_def else rest


@pytest.fixture
def state():
    for key in _NAV_KEYS:
        st.session_state.pop(key, None)
    yield st.session_state
    for key in _NAV_KEYS:
        st.session_state.pop(key, None)


# ── _current_mode() ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("step,mode", [
    ("dialogue", "strategy"), ("review", "strategy"), ("strategy", "strategy"),
    ("doc_review", "doc_review"), ("maturity", "maturity"), ("intro", None),
])
def test_current_mode_maps_every_step(step, mode):
    assert app._current_mode(step) == mode


def test_every_app_mode_has_a_landing_label():
    assert {m[0] for m in APP_MODES} == set(app._LANDING_CTA_LABELS)


# ── _go_to() ─────────────────────────────────────────────────────────────────────

def test_go_to_strategy_starts_at_dialogue_when_nothing_to_resume(state):
    state["current_step"] = "intro"
    app._go_to("strategy")
    assert state["current_step"] == "dialogue"


def test_go_to_other_mode_and_back_resumes_strategy_step(state):
    state["current_step"] = "review"
    app._go_to("maturity")
    assert state["current_step"] == "maturity"
    app._go_to("doc_review")
    assert state["current_step"] == "doc_review"
    app._go_to("strategy")
    assert state["current_step"] == "review"


def test_go_to_keeps_other_modes_state(state):
    """Switching must not wipe another mode's work (keys are disjoint)."""
    state["current_step"] = "doc_review"
    state["review_result"] = "sentinel"
    try:
        app._go_to("maturity")
        assert state.get("review_result") == "sentinel"
    finally:
        state.pop("review_result", None)


# ── _generation_in_progress() ────────────────────────────────────────────────────

def test_not_locked_on_landing(state):
    state["current_step"] = "intro"
    assert app._generation_in_progress() is False


def test_not_locked_on_strategy_step_until_the_run_is_charged(state):
    """A quota/run-cap refusal never sets generation_started, so a refused
    run must not leave the sidebar locked."""
    state["current_step"] = "strategy"
    state["run_count"] = 0
    assert app._generation_in_progress() is False


def test_locked_while_strategy_pipeline_resumes_at_run_cap(state):
    state["current_step"] = "strategy"
    state["generation_started"] = True
    state["run_count"] = app.MAX_RUNS_PER_SESSION
    assert app._generation_in_progress() is True


def test_not_locked_once_results_complete(state):
    state["current_step"] = "strategy"
    state["generation_started"] = True
    state["results_complete"] = True
    assert app._generation_in_progress() is False


@pytest.mark.parametrize("flag", ["review_narrative_pending", "maturity_narrative_pending"])
def test_locked_while_narrative_pending(state, flag):
    state["current_step"] = "doc_review"
    state[flag] = True
    assert app._generation_in_progress() is True


def test_run_cap_defined_once():
    """The lock and the three renderers must read the same cap."""
    assert APP_PY.read_text(encoding="utf-8").count("MAX_RUNS_PER_SESSION = ") == 1


def test_review_generate_charges_the_run_before_switching_to_strategy():
    body = extract_function(APP_PY.read_text(encoding="utf-8"), "render_review")
    quota = body.index("_enforce_daily_quota()")
    started = body.index("st.session_state.generation_started = True")
    switch = body.index('st.session_state.current_step = "strategy"')
    assert quota < started < switch


# ── Narrative pending flag ───────────────────────────────────────────────────────

@pytest.mark.parametrize("fn,mode", [
    ("render_doc_review", "review"), ("render_maturity_assessment", "maturity"),
])
def test_narrative_runs_from_pending_flag_popped_before_button(fn, mode):
    body = extract_function(APP_PY.read_text(encoding="utf-8"), fn)
    pop = body.index(f'st.session_state.pop("{mode}_narrative_pending", False)')
    quota = body.index("_enforce_daily_quota()", pop)
    button = body.index(f"st.session_state.{mode}_narrative_pending = True")
    assert pop < quota < button


def test_reset_helpers_clear_pending_flags(state):
    state["review_narrative_pending"] = True
    state["maturity_narrative_pending"] = True
    app._reset_review_mode_state()
    app._reset_maturity_mode_state()
    assert "review_narrative_pending" not in state
    assert "maturity_narrative_pending" not in state


# ── Wiring ───────────────────────────────────────────────────────────────────────

def test_sidebar_renders_all_modes_with_lock_and_active_state():
    fn = extract_function(APP_PY.read_text(encoding="utf-8"), "render_sidebar")
    assert "for _mode_id, _idx, _label in APP_MODES" in fn
    assert 'key=f"nav-{_mode_id}"' in fn
    assert "disabled=_nav_locked or _mode_id == _active_mode" in fn
    assert "_go_to(_mode_id)" in fn
    assert "How it works" not in fn


def test_intro_renders_all_modes_through_go_to():
    fn = extract_function(APP_PY.read_text(encoding="utf-8"), "render_intro")
    assert 'with st.container(key="landing-cta")' in fn
    assert "_go_to(_mode_id)" in fn
    assert "st.info(" not in fn


def test_both_full_reset_lists_clear_strategy_resume_step():
    source = APP_PY.read_text(encoding="utf-8")
    assert '"strategy_resume_step"' in extract_function(source, "render_sidebar")
    assert '"strategy_resume_step"' in extract_function(source, "render_strategy")


def test_strategy_reruns_after_completion_so_the_sidebar_unlocks():
    """The sidebar renders before render_strategy() finishes; without a rerun
    after results_complete is set, it stays locked until the next click."""
    body = extract_function(APP_PY.read_text(encoding="utf-8"), "render_strategy")
    done = body.index("st.session_state.results_complete = True")
    assert body[done:].lstrip().split("\n")[0].startswith("st.session_state.results_complete = True")
    following = [line.strip() for line in body[done:].split("\n")[1:] if line.strip() and not line.strip().startswith("#")]
    assert following[0] == "st.rerun()"
