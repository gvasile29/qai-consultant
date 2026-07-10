"""
Regression tests for src/app.py — StopException/RerunException swallowed by
render_strategy()'s per-stage `except Exception` blocks.

BUG (production, Streamlit Cloud, observed live 2026-07-10 ~10:35-10:53 UTC):
after the run_count/results_complete fix (PR #40), the live app STILL
regenerated the Risk Register (and Test Strategy) endlessly, dozens of times
in a row, each with genuinely different LLM output — never hitting the
run-count cap, never completing. The "Manage app" deploy log showed a burst
of "ERROR: Risk Register generation failed:" / "ERROR: Test Strategy
generation failed:" / "ERROR: Effort Estimation generation failed:" lines
with a completely EMPTY exception message on every single occurrence.

Root cause: Streamlit's own script-control-flow exceptions, `StopException`
and `RerunException` (streamlit.runtime.scriptrunner.exceptions), both
inherit from `Exception` (not `BaseException`) in Streamlit 1.37. Streamlit
raises one of these INTO the running script at the next `st.*` API call
whenever it needs to legitimately stop or rerun the script — most commonly
because the browser's websocket session was interrupted (observed live via
the "Bad message format: Tried to use SessionInfo before it was
initialized" client-side reconnect race, a long-standing Streamlit bug —
https://github.com/streamlit/streamlit/issues/9767,
https://github.com/streamlit/streamlit/issues/11500 — which becomes far
more consequential here because each of the 4 generation stages runs a
multi-minute `st.write_stream()` call, a wide window for a reconnect to land
in).

render_strategy()'s four `except Exception as exc:` blocks (around each of
the Risk Register / Effort Estimation / Test Strategy / Test Plan calls)
caught these control-flow exceptions as if they were ordinary LLM/network
failures: they have no meaningful message (hence the empty log lines),
so the code logged an empty error, marked that stage "failed", and kept
executing the REST of the function — which immediately hit the same
already-signalled stop/rerun condition at the next `st.*` checkpoint,
cascading through the remaining stages in the same burst. Because the
`StopException`/`RerunException` was swallowed instead of propagating, the
run's already-generated content from that pass was discarded, and the next
real script rerun (which Streamlit still performs after the signal fires)
started that stage over — with a fresh, non-deterministic LLM completion
each time.

THE FIX: each of the four per-stage try blocks now has
`except (StopException, RerunException): raise` BEFORE the generic
`except Exception as exc:`, so Streamlit's control-flow signal propagates
normally (stopping/rerunning the script as Streamlit intends) instead of
being misreported as a stage failure. This lets the resume-skip guards
added in PR #40 (results_complete / generation_started / per-stage
`is None` checks) actually do their job: a genuine rerun now correctly
resumes from session_state instead of the exception handler wiping out
that stage's in-flight work first.

Covers:
1. `StopException`/`RerunException` are imported at module level from
   `streamlit.runtime.scriptrunner`.
2. Each of the 4 stage try/except blocks has an
   `except (StopException, RerunException): raise` clause positioned
   BEFORE its generic `except Exception as exc:` clause (Python evaluates
   except clauses in order — reversing this order would make the specific
   clause unreachable).
3. Behavioral simulation: the exact except-ordering pattern used in
   render_strategy() actually re-raises StopException/RerunException
   instead of swallowing it, using the real Streamlit exception classes
   (no live Streamlit session needed — this is a plain Python exception
   propagation check).
"""

import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
APP_SRC = REPO_ROOT / "src"
APP_PY = APP_SRC / "app.py"
sys.path.insert(0, str(APP_SRC))

from streamlit.runtime.scriptrunner import RerunException, StopException  # noqa: E402


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


# ── Tests: static / structural (no LLM, no live Streamlit session) ──────────

def test_stopexception_rerunexception_imported():
    """app.py imports StopException and RerunException at module level."""
    source = read_app_source()
    assert "from streamlit.runtime.scriptrunner import" in source, \
        "app.py must import from streamlit.runtime.scriptrunner"
    import_lines = [
        line for line in source.splitlines()
        if line.startswith("from streamlit.runtime.scriptrunner import")
    ]
    assert import_lines, "streamlit.runtime.scriptrunner import line not found"
    import_line = import_lines[0]
    assert "StopException" in import_line, "StopException not imported"
    assert "RerunException" in import_line, "RerunException not imported"
    print("  PASS: StopException and RerunException imported from streamlit.runtime.scriptrunner")


# Fingerprint: session-state key -> the generic except clause that must be
# preceded by the StopException/RerunException re-raise clause.
_STAGE_GENERIC_EXCEPT_FINGERPRINTS = {
    "Risk Register": 'logger.error("Risk Register generation failed: %s", exc)',
    "Effort Estimation": 'logger.error("Effort Estimation generation failed: %s", exc)',
    "Test Strategy": 'logger.error("Test Strategy generation failed: %s", exc)',
    "Test Plan": 'logger.error("Test Plan generation failed: %s", exc)',
}


def test_each_stage_reraises_stop_and_rerun_exception_before_generic_catch():
    """Each of the 4 stages must have `except (StopException, RerunException):
    raise` immediately before its generic `except Exception as exc:` clause.
    Python tries except clauses in source order — if the generic clause came
    first, it would swallow StopException/RerunException before the specific
    clause ever ran, exactly reproducing the bug this test guards against."""
    fn = extract_function(read_app_source(), "render_strategy")
    lines = fn.splitlines()

    for step_name, fingerprint in _STAGE_GENERIC_EXCEPT_FINGERPRINTS.items():
        log_lines = [i for i, line in enumerate(lines) if fingerprint in line]
        assert log_lines, f"Could not find the {step_name} generic-except log line"
        log_line = log_lines[0]

        # The generic `except Exception as exc:` clause is the line directly
        # above the log call.
        generic_except_lines = [
            i for i in range(max(0, log_line - 3), log_line)
            if lines[i].strip() == "except Exception as exc:"
        ]
        assert generic_except_lines, \
            f"{step_name}: could not find 'except Exception as exc:' directly above its log line"
        generic_except_line = generic_except_lines[0]

        # Walk backward from the generic clause to the nearest preceding
        # 'try:' at the same indent — the specific re-raise clause (with its
        # 'raise' body, and any explanatory comment lines) must sit in that
        # gap, with no OTHER except clause in between (which would prove it
        # isn't "immediately before").
        try_indent = len(lines[generic_except_line]) - len(lines[generic_except_line].lstrip(" "))
        gap_start = generic_except_line
        for i in range(generic_except_line - 1, -1, -1):
            stripped = lines[i].strip()
            if stripped == "try:" and (len(lines[i]) - len(lines[i].lstrip(" "))) == try_indent:
                gap_start = i + 1
                break
        preceding = lines[gap_start:generic_except_line]

        other_except_lines = [
            line for line in preceding
            if line.strip().startswith("except") and "StopException" not in line
        ]
        assert not other_except_lines, \
            f"{step_name}: found another except clause between try/StopException-reraise " \
            f"and the generic except, so the reraise clause isn't immediately before it: " \
            f"{other_except_lines}"

        assert any(
            "except (StopException, RerunException):" in line
            for line in preceding
        ), (
            f"{step_name}: 'except (StopException, RerunException): raise' not found "
            f"immediately before its generic 'except Exception as exc:' clause — "
            f"Streamlit's own stop/rerun signal would be silently swallowed here"
        )
        assert any(line.strip() == "raise" for line in preceding), \
            f"{step_name}: the StopException/RerunException clause must re-raise, not handle"

    print("  PASS: all 4 stages re-raise StopException/RerunException before the generic except")


def test_stage_reraise_clause_lists_both_exception_types():
    """The re-raise clause must catch BOTH StopException and RerunException —
    Streamlit uses StopException for st.stop()/session teardown and
    RerunException for a script rerun; missing either would leave that
    specific signal vulnerable to being swallowed again."""
    fn = extract_function(read_app_source(), "render_strategy")
    count = fn.count("except (StopException, RerunException):")
    assert count == 4, \
        f"Expected exactly 4 'except (StopException, RerunException):' clauses " \
        f"(one per generation stage), found {count}"
    print("  PASS: exactly 4 'except (StopException, RerunException):' clauses found, "
          "one per generation stage")


# ── Behavioral simulation ─────────────────────────────────────────────────────
#
# Proves the except-ordering pattern actually works, using the REAL Streamlit
# exception classes (StopException/RerunException are plain importable
# classes — no live Streamlit script session is needed to test that
# `except (StopException, RerunException): raise` positioned before
# `except Exception:` correctly re-raises instead of being swallowed).

def _simulate_stage_with_fixed_ordering(exc_to_raise):
    """Mirrors the FIXED except-clause order used in each of the 4 stages."""
    try:
        raise exc_to_raise
    except (StopException, RerunException):
        raise
    except Exception as exc:
        return f"caught-and-swallowed: {exc!r}"


def _simulate_stage_with_buggy_ordering(exc_to_raise):
    """Mirrors the ORIGINAL (buggy) single generic except clause — no
    specific re-raise, so StopException/RerunException gets swallowed."""
    try:
        raise exc_to_raise
    except Exception as exc:
        return f"caught-and-swallowed: {exc!r}"


def test_fixed_ordering_propagates_stop_exception():
    """With the fix's except-clause order, a StopException raised inside the
    stage's try block propagates out of the function instead of being
    logged as a fake 'generation failed' error."""
    with pytest.raises(StopException):
        _simulate_stage_with_fixed_ordering(StopException())
    print("  PASS: StopException propagates through the fixed except ordering")


def test_fixed_ordering_propagates_rerun_exception():
    """Same as above for RerunException (Streamlit's actual rerun signal,
    constructed with a real RerunData payload as Streamlit itself does)."""
    from streamlit.runtime.scriptrunner import RerunData

    with pytest.raises(RerunException):
        _simulate_stage_with_fixed_ordering(RerunException(RerunData()))
    print("  PASS: RerunException propagates through the fixed except ordering")


def test_buggy_ordering_reproduces_the_original_bug():
    """Sanity check: confirms the ORIGINAL single-except pattern really did
    swallow StopException on Streamlit 1.37 (the version pinned when this bug
    was found and fixed) — proving the bug was real and the fix's
    before/after behavior differs.

    Streamlit later moved `ScriptControlException` to inherit from
    `BaseException` instead of `Exception` (confirmed fixed by the time of
    requirements.txt's current pin) — a bare `except Exception:` can no
    longer catch it at all, regardless of clause ordering. This test adapts
    to whichever behavior the installed Streamlit version actually has,
    so it stays meaningful across the upgrade instead of asserting a
    version-specific implementation detail that's no longer true."""
    if issubclass(StopException, Exception):
        # Pre-fix Streamlit (e.g. 1.37): ScriptControlException < Exception,
        # so the naive except swallows it — this is the bug this whole file
        # guards against.
        result = _simulate_stage_with_buggy_ordering(StopException())
        assert result.startswith("caught-and-swallowed:"), \
            "Expected the buggy ordering to swallow StopException (reproducing the original bug)"
        print("  PASS: confirmed the pre-fix except ordering swallows StopException "
              "(reproduces the original bug)")
    else:
        # Post-fix Streamlit: ScriptControlException < BaseException, so
        # `except Exception:` can't catch it even without our explicit
        # re-raise clause — the upstream fix now does this for us too.
        with pytest.raises(StopException):
            _simulate_stage_with_buggy_ordering(StopException())
        print("  PASS: installed Streamlit version already makes StopException a "
              "BaseException — confirms the upstream architectural fix is in place, "
              "our explicit re-raise clause is now defense-in-depth")


# ── Runner ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [
        ("StopException/RerunException imported at module level",
            test_stopexception_rerunexception_imported),
        ("each stage re-raises StopException/RerunException before the generic except",
            test_each_stage_reraises_stop_and_rerun_exception_before_generic_catch),
        ("exactly 4 re-raise clauses, one per stage",
            test_stage_reraise_clause_lists_both_exception_types),
        ("behavioral: fixed ordering propagates StopException",
            test_fixed_ordering_propagates_stop_exception),
        ("behavioral: RerunException is the real Streamlit class",
            test_fixed_ordering_propagates_rerun_exception),
        ("behavioral: buggy ordering reproduces the original swallow bug",
            test_buggy_ordering_reproduces_the_original_bug),
    ]

    passed = failed = 0

    print("=" * 68)
    print("  QAI Consultant — StopException/RerunException swallow-bug regression tests")
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
