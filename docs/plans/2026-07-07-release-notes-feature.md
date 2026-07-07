# Release Notes in the Streamlit App — Design

**Date:** 2026-07-07
**Ships as:** v2.5.0

## Goal

Let QAI Consultant users see what changed/was added with every version update, from inside the Streamlit app — no need to read CHANGELOG.md on GitHub or CLAUDE.md's dev-facing Roadmap.

## Components

### 1. Version bump & changelog file
- `src/version.py`: `__version__ = "2.5.0"`, `__release_date__ = "2026-07-07"`.
- New `CHANGELOG.md` at the repo root, Keep-a-Changelog style, newest first:
  - `v2.5.0` — this release-notes feature itself.
  - Backfilled entries for `v2.0.2` down through `v0.1`, rewritten in end-user language from CLAUDE.md's Roadmap section (stripped of internal file/commit references — end users don't need to know about `PERT normalization` internals, just what changed for them).
- CLAUDE.md's Roadmap section gets a matching `v2.5.0` line, consistent with every prior version bump recorded there.

### 2. Sidebar — persistent "Release Notes" access
In `render_sidebar()` (`src/app.py:143`), directly under the `v{__version__}` caption, add an `st.expander("📋 Release Notes")`. It reads `CHANGELOG.md` via a small `@st.cache_data`-wrapped helper (file content doesn't change during a running session) and renders it with `st.markdown(...)` — the whole file, no parsing/pagination needed. Always present regardless of banner state; this is the permanent, discoverable way to see history at any time.

### 3. One-time "what's new" banner
At the top of `main()` (`src/app.py:869`), after the agent loads successfully (so it doesn't clutter the API-key-missing troubleshooting screen) and before `render_sidebar()`:

```python
if not st.session_state.get("release_notes_seen"):
    st.session_state.release_notes_seen = True
    st.info(f"✨ Updated to v{__version__} — see the sidebar's Release Notes for what's new.")
```

Because the flag is set immediately, the banner renders exactly once per browser session, on whichever step the user is on when they first load the app, and never reappears for the rest of that session — even across intro → dialogue → review → strategy navigation. A hard page refresh that starts a new Streamlit session shows it again; this is the accepted trade-off of session-only tracking (no user accounts, no localStorage/cookie dependency).

## Data flow

```
CHANGELOG.md (repo root, git-tracked)
   → read once per session, cached (@st.cache_data)
   → sidebar expander: st.markdown(full file content)

version.__version__
   → sidebar caption (existing)
   → banner text (new)
```

No new dependencies, no RAG/Pinecone involvement, no LLM calls.

## Error handling & edge cases
- Reading `CHANGELOG.md` is wrapped in try/except; if missing/unreadable at runtime, the sidebar expander shows a graceful fallback ("Release notes unavailable") instead of crashing the app.
- `release_notes_seen` is a session-wide flag, not tied to a specific project run — it must **not** be added to the "Start Over" (`src/app.py:172-186`) or "Generate Another Strategy" cleanup key lists, so starting a new strategy within the same browser session doesn't re-trigger the banner.

## Testing
- `CHANGELOG.md` sanity check: file exists, non-empty, contains a `v2.5.0` heading and headings for all backfilled versions (`v2.0.2`, `v2.0.1`, `v2.0`, `v1.0`, `v0.6`, `v0.5`, `v0.4`, `v0.3`, `v0.2`, `v0.1`).
- Cross-check regression guard: the top `CHANGELOG.md` version heading matches `version.__version__` exactly — catches bumping one but forgetting the other, without hardcoding "2.5.0" as a second magic string in the test.
- Extend `tests/test_app_v03.py` (Streamlit `AppTest`):
  - sidebar contains a "Release Notes" expander with non-empty content.
  - the banner renders on a fresh `AppTest` run referencing the current version.
  - it does not reappear after a subsequent rerun in the same `AppTest` session.
  - "Start Over" does not reset/reshow it (flag survives the cleanup block).

## Out of scope
- CLI (`src/cli.py`) release notes display — goal is specifically the Streamlit app.
- Cross-session/cross-device persistence (localStorage, cookies, user accounts) — explicitly deferred per the session-only decision.
- Structured/parsed changelog data model — plain markdown file rendered as-is.
