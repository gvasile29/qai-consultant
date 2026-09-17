# Postmortem: bare `except Exception` swallowed Streamlit's control-flow exceptions

**Status:** Fixed. **Linked from:** CLAUDE.md's "Never let a bare except Exception swallow StopException/RerunException" Gotcha.

Streamlit raises `StopException`/`RerunException` into the running script at the next `st.*` call whenever it needs to legitimately stop or rerun (most commonly a websocket disconnect/reconnect — a long-standing Streamlit client-side race, see `streamlit/streamlit#9767` and `#11500`).

On Streamlit 1.37 (this app's pin at the time this bug was found) both inherited from `Exception`, so a bare `except Exception` in `render_strategy()`'s per-stage try/excepts swallowed them — logged as an empty-message "generation failed", execution then barreled into the remaining stages on a dead session, producing bursts of empty-message failures and endless non-deterministic regeneration even after the `results_complete` resumability fix (a separate, earlier fix for a related but distinct mid-pipeline-rerun bug).

**Fix:** each of `render_strategy()`'s 4 per-stage try/excepts got `except (StopException, RerunException): raise` before the generic `except Exception as exc:`, as explicit defense.

**Follow-up:** `streamlit==1.59.1` (upgraded from 1.37.0) moved `ScriptControlException` to inherit from `BaseException` instead, so a bare `except Exception` can no longer catch it regardless of this fix — but the explicit re-raise clause was kept anyway (belt-and-suspenders against a future downgrade or an upstream regression). `from streamlit.runtime.scriptrunner import RerunException, StopException` still re-exports correctly at 1.59.1 even though the concrete classes live in `streamlit.runtime.scriptrunner_utils.exceptions` internally.

**Rule that survives in CLAUDE.md:** any new `try/except Exception` wrapped around `st.*` calls in `app.py` needs the same `except (StopException, RerunException): raise` guard before the generic clause.
