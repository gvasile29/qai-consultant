"""
Regression tests for src/app.py — run_count / generation_started /
results_complete fix.

BUG #1 (production, Streamlit Cloud): render_strategy() gated the 4-stage
generation pipeline (Risk Register -> Effort Estimation -> Test Strategy ->
Test Plan) with `if st.session_state.get("strategy") is None:`, and only
wrote `strategy` to session state near the END of the pipeline (after stage
3). A Streamlit rerun mid-pipeline (e.g. a websocket reconnect during the
multi-minute streamed generation) re-entered the same "is None" branch,
restarting the ENTIRE pipeline from scratch AND incrementing run_count
again. With MAX_RUNS_PER_SESSION = 3, three such reruns silently burned all
3 allowed runs before the user ever saw a completed result, then the
top-of-function lockout check permanently blocked them with "refresh the
page".

BUG #2 (found by adversarial review of the first fix attempt): gating the
outer "needs_generation" check on `strategy is None` is itself unsafe, even
with per-stage resume guards, because `strategy` is written by STAGE 3 of 4
— stage 4 (Test Plan) and the PDF-bytes precompute both run AFTER it, still
inside the same block. A rerun landing in that window sees `strategy` already
non-None, so `needs_generation` becomes False and the whole resume block is
skipped forever — `test_plan` stays None permanently, and
`st.download_button(data=None, ...)` in tab 4 raises uncaught.

THE FIX (src/app.py, render_strategy() + render_sidebar()):
1. `needs_generation` is now gated on an explicit `results_complete` flag,
   set True only at the very end of the block — after ALL 4 stages AND the
   PDF-bytes precompute finish — never on any single stage's output.
2. A `generation_started` flag is set True (and run_count incremented) only
   the FIRST time the pipeline is entered for a generation attempt.
3. The top-of-function run-cap check only fires for a brand-new attempt
   (`needs_generation and not generation_started`) — never blocks resuming
   an already-in-progress attempt.
4. Each of the 4 generation stages (risk_register, effort_report, strategy,
   test_plan) is individually guarded so a resumed run skips any stage a
   prior (interrupted) rerun already completed.
5. `generation_started` and `results_complete` were added to both
   session-state cleanup lists ("Start Over" in render_sidebar(),
   "Generate Another Strategy" in render_strategy()).

Covers:
1. The run_count increment is guarded by "if not generation_started:" (structural).
2. The top-of-function MAX_RUNS_PER_SESSION lockout condition includes
   generation_started (structural fingerprint).
3. needs_generation is gated on results_complete, not on strategy (structural).
4. results_complete is set True only after the PDF-bytes precompute (position check).
5. Each of the 4 generation stages has a resume-skip guard:
   "if st.session_state.get(X) is None:" ... else: reuse stored value.
6. generation_started AND results_complete are in BOTH cleanup key lists
   (Start Over + Generate Another).
7. Behavioral simulation: two reruns of an interrupted pipeline charge
   run_count exactly once and the second rerun is never locked out, even
   when run_count reaches the cap on the first call.
8. Behavioral simulation of BUG #2 specifically: a rerun landing after
   `strategy` is set but before `results_complete` is set must still resume
   (not fall through as "already done").
9. Sanity re-check that the existing per-step try/except isolation
   (test_app_v03.py::test_render_strategy_isolates_each_generation_step)
   still structurally holds against the new code.
"""

import sys
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
APP_SRC = REPO_ROOT / "src"
APP_PY = APP_SRC / "app.py"
sys.path.insert(0, str(APP_SRC))


# ── Helpers (mirrors tests/test_app_v03.py) ──────────────────────────────────

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


# ── Tests: static / structural (no LLM) ──────────────────────────────────────

def test_run_count_increment_guarded_by_generation_started():
    """The `st.session_state.run_count += 1` line inside render_strategy() must
    be preceded (within a few lines, same indent block) by
    `if not generation_started:` — not unconditional — so a mid-pipeline
    rerun that re-enters the branch does not charge a second run."""
    fn = extract_function(read_app_source(), "render_strategy")
    lines = fn.splitlines()

    increment_lines = [i for i, line in enumerate(lines) if "run_count += 1" in line]
    assert increment_lines, "st.session_state.run_count += 1 not found in render_strategy()"
    increment_line = increment_lines[0]

    window = lines[max(0, increment_line - 5):increment_line]
    assert any("if not generation_started:" in line for line in window), \
        "run_count increment is not guarded by 'if not generation_started:'"
    assert any("generation_started = True" in line for line in window), \
        "generation_started is not set True alongside the run_count increment guard"

    print("  PASS: run_count increment is guarded by 'if not generation_started:'")


def test_run_count_increment_not_unconditional():
    """Negative check: the increment line must be nested two levels deep
    (def -> if needs_generation -> if not generation_started), not sitting
    directly under `if needs_generation:` as an unconditional statement."""
    fn = extract_function(read_app_source(), "render_strategy")
    lines = fn.splitlines()

    increment_lines = [line for line in lines if "run_count += 1" in line]
    assert increment_lines, "run_count increment not found"
    increment_line = increment_lines[0]
    indent = len(increment_line) - len(increment_line.lstrip(" "))
    assert indent >= 12, \
        f"run_count increment indentation ({indent}) suggests it is not nested " \
        f"under the 'if not generation_started:' guard"

    print("  PASS: run_count increment is nested under the generation_started guard, not unconditional")


def test_lockout_condition_includes_generation_started():
    """The top-of-function MAX_RUNS_PER_SESSION lockout check must include
    `generation_started` in its condition, so it only blocks brand-new
    generation attempts, never a resumed (interrupted) one."""
    fn = extract_function(read_app_source(), "render_strategy")

    lockout_lines = [
        line for line in fn.splitlines()
        if "MAX_RUNS_PER_SESSION" in line and "if " in line
    ]
    assert lockout_lines, "Could not find the MAX_RUNS_PER_SESSION lockout 'if' line"
    lockout_line = lockout_lines[0]

    assert "generation_started" in lockout_line, \
        f"Lockout condition does not reference generation_started: {lockout_line!r}"
    assert "needs_generation" in lockout_line, \
        f"Lockout condition does not reference needs_generation: {lockout_line!r}"
    assert "not generation_started" in lockout_line, \
        f"Lockout condition must require 'not generation_started': {lockout_line!r}"

    print("  PASS: lockout condition requires needs_generation AND not generation_started")


def test_needs_generation_gated_on_results_complete_not_strategy():
    """needs_generation must be derived from an explicit `results_complete`
    flag, NOT from `strategy is None`. Gating on `strategy` alone is unsafe:
    `strategy` is written by stage 3 of 4, so a rerun landing between stage 3
    and the end of the pipeline (stage 4 + PDF-bytes precompute) would see
    `strategy` already set and skip the resume block forever, permanently
    stranding stage 4 / PDF bytes as None."""
    fn = extract_function(read_app_source(), "render_strategy")
    lines = fn.splitlines()

    assign_lines = [
        i for i, line in enumerate(lines)
        if line.strip().startswith("needs_generation = ")
    ]
    assert assign_lines, "needs_generation assignment not found in render_strategy()"
    assign_line = lines[assign_lines[0]].strip()

    assert 'results_complete' in assign_line, \
        f"needs_generation must be derived from results_complete: {assign_line!r}"
    assert '"strategy") is None' not in assign_line, \
        f"needs_generation must NOT be gated directly on strategy (BUG #2): {assign_line!r}"

    print("  PASS: needs_generation is gated on results_complete, not on 'strategy is None'")


def test_results_complete_set_after_pdf_bytes_precompute():
    """`results_complete = True` must be set AFTER the PDF-bytes precompute
    block (the last step of the pipeline), so a rerun landing anywhere before
    that — including after `strategy` is set but before Test Plan or PDF
    bytes finish — still sees needs_generation == True and resumes."""
    fn = extract_function(read_app_source(), "render_strategy")
    lines = fn.splitlines()

    pdf_lines = [i for i, line in enumerate(lines) if "test_plan_pdf_bytes = markdown_to_pdf" in line]
    assert pdf_lines, "PDF-bytes precompute (test_plan_pdf_bytes) not found"

    complete_lines = [i for i, line in enumerate(lines) if "results_complete = True" in line]
    assert complete_lines, "'st.session_state.results_complete = True' not found"

    assert complete_lines[0] > pdf_lines[0], \
        "results_complete must be set AFTER the PDF-bytes precompute, not before/interleaved"

    print("  PASS: results_complete is set only after the PDF-bytes precompute completes")


# Fingerprint: session-state key -> the "is None" resume-skip guard we expect
_STAGE_RESUME_GUARDS = {
    "risk_register": 'st.session_state.get("risk_register") is None',
    "effort_report": 'st.session_state.get("effort_report") is None',
    "strategy": 'st.session_state.get("strategy") is None',
    "test_plan": 'st.session_state.get("test_plan") is None',
}


def test_each_stage_has_resume_skip_guard():
    """Each of the 4 generation stages is individually guarded by
    `if st.session_state.get(X) is None:` with an `else:` branch that reuses
    the already-stored value — so a resumed run skips stages a prior
    (interrupted) rerun already completed."""
    fn = extract_function(read_app_source(), "render_strategy")

    for key, guard in _STAGE_RESUME_GUARDS.items():
        assert guard in fn, f"Resume-skip guard for '{key}' not found: {guard!r}"

    print("  PASS: all 4 stages (risk_register, effort_report, strategy, test_plan) "
          "have 'is None' resume-skip guards")


def test_each_stage_guard_has_else_reusing_stored_value():
    """For each stage guard, an `else:` branch must exist nearby that assigns
    the local variable from the already-stored session_state value (proving
    a resumed run reuses it instead of regenerating)."""
    fn = extract_function(read_app_source(), "render_strategy")
    lines = fn.splitlines()

    expected_reuse = {
        "risk_register": "risk_register = st.session_state.risk_register",
        "effort_report": "effort_report = st.session_state.effort_report",
        "strategy": "strategy = st.session_state.strategy",
        "test_plan": "test_plan = st.session_state.test_plan",
    }

    for key, guard in _STAGE_RESUME_GUARDS.items():
        # Restrict to actual "if ..." guard statements — for 'strategy' this
        # also excludes the unrelated `needs_generation = ...` assignment at
        # the top of the function, which no longer even contains this
        # substring post-fix, but keep the guard for robustness.
        guard_lines = [
            i for i, line in enumerate(lines)
            if guard in line and line.strip().startswith("if ")
        ]
        assert guard_lines, f"Guard for '{key}' not found"
        guard_line = guard_lines[0]
        following = lines[guard_line:guard_line + 60]
        assert any(line.strip() == "else:" for line in following), \
            f"No 'else:' branch found after the '{key}' resume-skip guard"
        assert any(expected_reuse[key] in line for line in following), \
            f"Reuse assignment {expected_reuse[key]!r} not found after the '{key}' guard"

    print("  PASS: each stage's 'else:' branch reuses the stored session_state value")


def test_generation_started_in_start_over_cleanup():
    """render_sidebar()'s 'Start Over' cleanup list includes generation_started."""
    fn = extract_function(read_app_source(), "render_sidebar")
    assert '"generation_started"' in fn, \
        "'Start Over' cleanup list is missing 'generation_started'"
    print("  PASS: 'Start Over' (render_sidebar) cleanup list includes generation_started")


def test_generation_started_in_generate_another_cleanup():
    """render_strategy()'s 'Generate Another Strategy' cleanup list includes
    generation_started."""
    fn = extract_function(read_app_source(), "render_strategy")
    assert '"generation_started"' in fn, \
        "'Generate Another Strategy' cleanup list is missing 'generation_started'"
    print("  PASS: 'Generate Another Strategy' cleanup list includes generation_started")


def test_results_complete_in_start_over_cleanup():
    """render_sidebar()'s 'Start Over' cleanup list includes results_complete
    (otherwise a stale True would make the next generation attempt skip
    entirely)."""
    fn = extract_function(read_app_source(), "render_sidebar")
    assert '"results_complete"' in fn, \
        "'Start Over' cleanup list is missing 'results_complete'"
    print("  PASS: 'Start Over' (render_sidebar) cleanup list includes results_complete")


def test_results_complete_in_generate_another_cleanup():
    """render_strategy()'s 'Generate Another Strategy' cleanup list includes
    results_complete."""
    fn = extract_function(read_app_source(), "render_strategy")
    assert '"results_complete"' in fn, \
        "'Generate Another Strategy' cleanup list is missing 'results_complete'"
    print("  PASS: 'Generate Another Strategy' cleanup list includes results_complete")


def test_generation_started_initialized_or_defaulted():
    """generation_started is read via .get(..., False) in render_strategy()
    (it doesn't need to be in init_session_state, but must default safely)."""
    fn = extract_function(read_app_source(), "render_strategy")
    assert 'st.session_state.get("generation_started", False)' in fn, \
        "generation_started must be read with a safe False default"
    print("  PASS: generation_started defaults to False via st.session_state.get(...)")


def test_results_complete_initialized_or_defaulted():
    """results_complete is read via .get(..., False) in render_strategy()."""
    fn = extract_function(read_app_source(), "render_strategy")
    assert 'st.session_state.get("results_complete", False)' in fn, \
        "results_complete must be read with a safe False default"
    print("  PASS: results_complete defaults to False via st.session_state.get(...)")


# ── Behavioral simulation ─────────────────────────────────────────────────────
#
# Replicates the exact guard logic from render_strategy() (app.py, the top-of
# -function lockout check + the generation_started-gated run_count increment,
# now keyed off results_complete) operating on a plain dict session_state,
# per the established convention in test_app_feedback_loop.py / test_app_v03.py
# (Streamlit can't be driven headlessly).

MAX_RUNS_PER_SESSION = 3


def simulate_render_strategy_entry(session_state: dict) -> str:
    """
    Mirrors app.py render_strategy()'s entry guard:

        needs_generation = not st.session_state.get("results_complete", False)
        generation_started = st.session_state.get("generation_started", False)

        if needs_generation and not generation_started and st.session_state.get("run_count", 0) >= MAX_RUNS_PER_SESSION:
            <locked out>

        if needs_generation:
            if not generation_started:
                st.session_state.generation_started = True
                st.session_state.run_count += 1
            <... pipeline runs, may or may not finish ...>

    Returns one of: "locked_out", "generation_entered".
    Does NOT simulate the pipeline body itself (stage generation) — only the
    entry guard + run_count bookkeeping, which is what the bug affected.
    """
    needs_generation = not session_state.get("results_complete", False)
    generation_started = session_state.get("generation_started", False)

    if (
        needs_generation
        and not generation_started
        and session_state.get("run_count", 0) >= MAX_RUNS_PER_SESSION
    ):
        return "locked_out"

    if needs_generation:
        if not generation_started:
            session_state["generation_started"] = True
            session_state["run_count"] = session_state.get("run_count", 0) + 1
        # Pipeline body would run here; in the interrupted-rerun scenarios
        # being simulated, it does NOT reach `st.session_state.results_complete
        # = True` before the script reruns (websocket reconnect mid-stream).

    return "generation_entered"


def test_interrupted_rerun_charges_run_count_exactly_once():
    """Two reruns of the SAME interrupted generation attempt (results_complete
    stays False both times, simulating a rerun that hit before the pipeline
    finished) must increment run_count only ONCE — the exact bug this fix
    addresses (BUG #1)."""
    session_state = {"run_count": 0}
    # results_complete / generation_started absent — first entry

    result_1 = simulate_render_strategy_entry(session_state)
    assert result_1 == "generation_entered"
    assert session_state["run_count"] == 1, \
        f"Expected run_count == 1 after first entry, got {session_state['run_count']}"
    assert session_state["generation_started"] is True

    # Simulate a rerun (e.g. websocket reconnect) — results_complete is STILL
    # False because the pipeline never finished before the rerun.
    result_2 = simulate_render_strategy_entry(session_state)
    assert result_2 == "generation_entered", \
        "Second (resumed) entry must not be locked out"
    assert session_state["run_count"] == 1, \
        f"run_count must stay at 1 across the interrupted rerun, got {session_state['run_count']}"

    print("  PASS: run_count incremented exactly once across two reruns of an "
          "interrupted generation attempt")


def test_resume_after_strategy_set_but_before_pipeline_complete():
    """Regression test for BUG #2 (adversarial review finding): a rerun
    landing AFTER stage 3 (`strategy`) is set but BEFORE the pipeline is
    fully done (results_complete still False) must still resume — not fall
    through as 'already done'. This is exactly the gap the first fix attempt
    had: gating needs_generation on `strategy is None` instead of an explicit
    completion flag would have returned 'generation_entered' as False-ish
    (needs_generation False) here, permanently stranding stage 4 / PDF bytes."""
    session_state = {
        "run_count": 1,
        "generation_started": True,
        # 'strategy' would be set in the real session_state by this point,
        # but the entry guard must NOT depend on it — only results_complete
        # (still absent/False here) determines whether to resume.
        "results_complete": False,
    }

    result = simulate_render_strategy_entry(session_state)
    assert result == "generation_entered", \
        "A rerun after 'strategy' is set but before results_complete must still resume"
    assert session_state["run_count"] == 1, \
        "run_count must not increment again on this resumed rerun"

    print("  PASS: a rerun landing after 'strategy' is set but before the pipeline "
          "is fully complete still resumes (BUG #2 regression covered)")


def test_resumed_rerun_not_locked_out_even_at_cap():
    """If run_count reaches MAX_RUNS_PER_SESSION exactly on the call that
    starts generation, a SECOND rerun of that same (still-interrupted)
    attempt must NOT be locked out — because generation_started is True,
    the lockout condition (needs_generation AND NOT generation_started AND
    run_count >= cap) does not fire."""
    session_state = {"run_count": MAX_RUNS_PER_SESSION - 1}  # one below the cap

    # Call 1: starts a new generation attempt, reaching the cap exactly.
    result_1 = simulate_render_strategy_entry(session_state)
    assert result_1 == "generation_entered", \
        "First call must be allowed to start (run_count was below the cap)"
    assert session_state["run_count"] == MAX_RUNS_PER_SESSION, \
        f"run_count should now equal the cap, got {session_state['run_count']}"
    assert session_state["generation_started"] is True

    # Call 2: a rerun of the SAME (interrupted) attempt. results_complete is
    # still False, run_count already == cap. Without the fix this would be
    # locked out ("refresh the page") even though the user never got a result.
    result_2 = simulate_render_strategy_entry(session_state)
    assert result_2 == "generation_entered", \
        "Resumed rerun must NOT be locked out even though run_count == cap, " \
        "because generation_started is True"
    assert session_state["run_count"] == MAX_RUNS_PER_SESSION, \
        "run_count must not increment again on the resumed rerun"

    print("  PASS: resumed rerun proceeds even when run_count already equals the cap "
          "(generation_started prevents false lockout)")


def test_brand_new_attempt_still_locked_out_at_cap():
    """Sanity counterpart: once a generation attempt actually COMPLETES
    (results_complete True, then cleared by Start Over / Generate Another
    along with generation_started) and run_count is already at the cap, a
    genuinely NEW attempt must still be locked out. Confirms the fix doesn't
    remove the cap entirely."""
    session_state = {
        "run_count": MAX_RUNS_PER_SESSION,
        "generation_started": False,  # fresh attempt (post Start Over / Generate Another)
        "results_complete": False,    # fresh attempt, nothing generated yet
    }

    result = simulate_render_strategy_entry(session_state)
    assert result == "locked_out", \
        "A brand-new generation attempt at the run cap must still be locked out"
    assert session_state["run_count"] == MAX_RUNS_PER_SESSION, \
        "run_count must not change when locked out"

    print("  PASS: a genuinely NEW attempt at the cap is still locked out (cap not bypassed)")


# ── Sanity re-check of the pre-existing per-step isolation test ─────────────

_GENERATION_STEP_FINGERPRINTS = {
    "Risk Register": "agent.ask_streaming(risk_prompt, system_prompt=RISK_SYSTEM_PROMPT)",
    "Effort Estimation": "estimator.estimate(context, risk_register)",
    "Test Strategy": "agent.ask_streaming(strategy_prompt, system_prompt=SYSTEM_PROMPT)",
    "Test Plan": "agent.ask_streaming(test_plan_prompt, system_prompt=TEST_PLAN_SYSTEM_PROMPT)",
}


def test_per_step_isolation_still_holds_with_resume_guards():
    """Re-verifies test_app_v03.py::test_render_strategy_isolates_each_generation_step's
    fingerprint check still structurally holds now that each stage is also
    wrapped in an outer 'if st.session_state.get(X) is None:' resume guard —
    the try/except must still directly wrap each LLM call."""
    fn = extract_function(read_app_source(), "render_strategy")
    lines = fn.splitlines()
    for step_name, fingerprint in _GENERATION_STEP_FINGERPRINTS.items():
        call_lines = [i for i, line in enumerate(lines) if fingerprint in line]
        assert call_lines, f"Could not find the {step_name} generation call in render_strategy()"
        call_line = call_lines[0]
        preceding = lines[:call_line]
        try_lines = [i for i, line in enumerate(preceding) if line.strip() == "try:"]
        assert try_lines, f"{step_name} generation call is not inside a try block"
        following = lines[call_line:]
        assert any(line.strip().startswith("except") for line in following[:15]), \
            f"{step_name} generation call's try block has no except within a few lines after it"
    print("  PASS: per-step try/except isolation still holds alongside the new resume guards")


# ── Runner ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [
        ("run_count increment guarded by 'if not generation_started:'",
            test_run_count_increment_guarded_by_generation_started),
        ("run_count increment is not unconditional (nesting check)",
            test_run_count_increment_not_unconditional),
        ("lockout condition includes generation_started",
            test_lockout_condition_includes_generation_started),
        ("needs_generation is gated on results_complete, not 'strategy is None'",
            test_needs_generation_gated_on_results_complete_not_strategy),
        ("results_complete is set only after the PDF-bytes precompute",
            test_results_complete_set_after_pdf_bytes_precompute),
        ("each of the 4 stages has a resume-skip 'is None' guard",
            test_each_stage_has_resume_skip_guard),
        ("each stage guard has an 'else:' branch reusing the stored value",
            test_each_stage_guard_has_else_reusing_stored_value),
        ("'Start Over' cleanup clears generation_started",
            test_generation_started_in_start_over_cleanup),
        ("'Generate Another Strategy' cleanup clears generation_started",
            test_generation_started_in_generate_another_cleanup),
        ("'Start Over' cleanup clears results_complete",
            test_results_complete_in_start_over_cleanup),
        ("'Generate Another Strategy' cleanup clears results_complete",
            test_results_complete_in_generate_another_cleanup),
        ("generation_started defaults safely via .get(..., False)",
            test_generation_started_initialized_or_defaulted),
        ("results_complete defaults safely via .get(..., False)",
            test_results_complete_initialized_or_defaulted),
        ("behavioral: interrupted rerun charges run_count exactly once",
            test_interrupted_rerun_charges_run_count_exactly_once),
        ("behavioral: rerun after 'strategy' set but before pipeline complete still resumes (BUG #2)",
            test_resume_after_strategy_set_but_before_pipeline_complete),
        ("behavioral: resumed rerun not locked out even at cap",
            test_resumed_rerun_not_locked_out_even_at_cap),
        ("behavioral: brand-new attempt still locked out at cap",
            test_brand_new_attempt_still_locked_out_at_cap),
        ("sanity: per-step try/except isolation still holds",
            test_per_step_isolation_still_holds_with_resume_guards),
    ]

    passed = failed = 0

    print("=" * 68)
    print("  QAI Consultant — run_count / generation_started / results_complete tests")
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

    sys.exit(0 if failed == 0 else 1)
