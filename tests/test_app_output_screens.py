"""Tests for src/app.py's Phase 3 output-screen wiring (render_strategy(),
render_doc_review()) -- see
docs/superpowers/specs/2026-08-17-output-screens-power-on-redesign-design.md."""
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
APP_SRC = REPO_ROOT / "src"
APP_PY = APP_SRC / "app.py"
sys.path.insert(0, str(APP_SRC))


def read_app_source() -> str:
    return APP_PY.read_text(encoding="utf-8")


def extract_function(source: str, fn_name: str) -> str:
    pattern = rf'\ndef {fn_name}\('
    match = re.search(pattern, source)
    assert match, f"Could not find 'def {fn_name}(' in app.py"
    start = match.start() + 1
    next_def = re.search(r'\ndef \w+\(', source[start + len(f"def {fn_name}("):])
    end = start + len(f"def {fn_name}(") + next_def.start() if next_def else len(source)
    return source[start:end]


def test_render_strategy_uses_the_new_style_builders():
    fn = extract_function(read_app_source(), "render_strategy")
    assert "build_output_eyebrow_html" in fn
    assert "build_content_polish_css" in fn
    assert "build_stage_sequence_html" in fn


def test_render_strategy_calls_render_stages_before_and_after_each_stage():
    fn = extract_function(read_app_source(), "render_strategy")
    # fn.count("_render_stages(") would also match the helper's own
    # `def _render_stages(active_key=None):` line. That line has
    # "active_key=None" between its parens, never empty parens, so counting
    # the exact "_render_stages()" (bare call) substring cannot collide
    # with it. The active-key count, however, must match on the quote
    # character right after "=" (`_render_stages(active_key="`) rather than
    # bare "_render_stages(active_key=" -- the unquoted prefix alone also
    # matches inside the nested def's own default, `active_key=None`, which
    # inflates the count by one.
    active_calls = fn.count('_render_stages(active_key="')
    bare_calls = fn.count("_render_stages()")
    assert active_calls == 4, f"Expected 4 'active_key=\"...\"' calls (one per stage), found {active_calls}"
    assert bare_calls == 5, f"Expected 5 bare _render_stages() calls (1 initial + 1 per stage), found {bare_calls}"
    for key in ["risk_register", "effort_report", "strategy", "test_plan"]:
        assert f'_render_stages(active_key="{key}")' in fn


def test_render_stages_distinguishes_failed_from_done():
    # Regression guard: each stage's except handler sets its session-state
    # key to "" (not None) on an LLM failure. _render_stages() must not
    # treat that as "done" -- a bare `is not None` check would, since
    # "" is not None is True, showing green success next to the stage's
    # own red st.error() message during exactly the LLM-outage scenario
    # the per-stage try/except exists to survive.
    fn = extract_function(read_app_source(), "render_strategy")
    assert '"done"' in fn
    assert '"failed"' in fn
    assert "if value:" in fn, \
        "_render_stages() must branch on truthiness (`if value:`), not `is not None`, " \
        "to tell a real result apart from a failed stage's \"\" sentinel"


def test_render_strategy_sets_output_intro_animated():
    fn = extract_function(read_app_source(), "render_strategy")
    assert "st.session_state.output_intro_animated = True" in fn


def test_cleanup_blocks_do_not_clear_output_intro_animated():
    source = read_app_source()
    for fn_name in ["render_sidebar", "render_strategy"]:
        fn = extract_function(source, fn_name)
        # render_strategy() itself legitimately reads the one-shot flag via
        # st.session_state.get("output_intro_animated") right where it's
        # set -- that's the animation-gating read, not a cleanup list, so
        # strip it out before checking that no "Start Over"/"Generate
        # Another Strategy" cleanup list clears the key (same exclusion
        # precedent as review_intro_animated, per CLAUDE.md).
        fn_without_read_call = fn.replace('st.session_state.get("output_intro_animated")', "")
        assert '"output_intro_animated"' not in fn_without_read_call, \
            f"{fn_name}() must NOT clear output_intro_animated"


def test_render_doc_review_uses_the_new_style_builders():
    fn = extract_function(read_app_source(), "render_doc_review")
    assert "build_output_eyebrow_html" in fn
    assert "build_content_polish_css" in fn
    assert "build_doc_review_input_tray_css" in fn


def test_render_doc_review_wraps_intake_widgets_in_keyed_container():
    fn = extract_function(read_app_source(), "render_doc_review")
    assert 'st.container(key="doc-review-input")' in fn


def test_render_doc_review_sets_doc_review_intro_animated():
    fn = extract_function(read_app_source(), "render_doc_review")
    assert "st.session_state.doc_review_intro_animated = True" in fn


def test_doc_review_intro_animated_excluded_from_review_mode_state_keys():
    source = read_app_source()
    keys_block = re.search(r"REVIEW_MODE_STATE_KEYS = \[(.*?)\]", source, re.DOTALL)
    assert keys_block, "REVIEW_MODE_STATE_KEYS list not found"
    assert "doc_review_intro_animated" not in keys_block.group(1), \
        "doc_review_intro_animated must NOT be added to REVIEW_MODE_STATE_KEYS"

    # Mirror test_cleanup_blocks_do_not_clear_output_intro_animated's
    # approach exactly: also source-inspect render_sidebar()'s ("Start
    # Over") and render_strategy()'s ("Generate Another Strategy") own
    # inline cleanup lists directly, not just the shared
    # REVIEW_MODE_STATE_KEYS list -- doc_review_intro_animated is a
    # one-shot entrance-animation flag (same precedent as
    # review_intro_animated/output_intro_animated/mcp_announcement_seen)
    # and must never be cleared by either handler.
    for fn_name in ["render_sidebar", "render_strategy"]:
        fn = extract_function(source, fn_name)
        assert '"doc_review_intro_animated"' not in fn, \
            f"{fn_name}() must NOT clear doc_review_intro_animated"
