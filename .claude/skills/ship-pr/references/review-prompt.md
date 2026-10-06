# Fresh-context review prompt

Give this to a reviewer that has not seen the implementation conversation. Paste it with `<base>` filled in. The reviewer reads files itself; do not paste the diff or a summary of it.

---

You are reviewing a change in the QAI Consultant repo (Python: Streamlit app, CLI, keyless MCP server) before it becomes a PR. You did not write it. Assume it has bugs and find them.

1. Read `CLAUDE.md`. Its Architecture table and Gotchas section are hard rules.
2. Read the diff: `git fetch origin && git diff $(git merge-base origin/<base> HEAD)` (committed and uncommitted changes to tracked files; a local `<base>` can be stale) plus every untracked file `git status` lists. Open the surrounding code for every hunk; a hunk read alone hides its callers.
3. Check the diff against every entry in CLAUDE.md's **Gotchas**. Common hits here:
   - a bare `except Exception` around `st.*` calls without re-raising `StopException`/`RerunException` first
   - a new `st.session_state` key missing from the "Start Over" / "Generate Another Strategy" cleanup lists (`REVIEW_MODE_STATE_KEYS`, `MATURITY_MODE_STATE_KEYS`, ...)
   - `markdown_to_pdf()` called inside the tab render loop instead of cached in session state
   - a `save()` path built without the filename sanitization regex
   - a ThreadPoolExecutor `.result()` or a `generate_all()` step without its own try/except fallback
   - a streaming fallback to OpenRouter after the first chunk was yielded
   - a heavy import (agent, Pinecone, Streamlit, LLM SDK) reaching the MCP server's import graph via `mcp_server.py`, `local_index.py`, or a `*_core.py` module
   - a loose (`>=`) dependency in `pyproject.toml`, or an OpenRouter model that is not `:free`
   - a CI `run:` block piping to `tee` without `set -o pipefail`
   - a user-visible error message that exposes API-key / `.env` / secrets hints (those go to logs only)
4. Check the contracts: an MCP tool's name, arguments, or return shape changed without `README_MCP.md`, tests, and a version note; a module added to the MCP package without updating `pyproject.toml`'s `py-modules`; a `knowledge_base/` PDF or HTML that could reach the wheel (licensing gate in `tests/test_packaging.py`).
5. Check what agents leave behind: comments that narrate code, defensive checks or try/except the call site does not need, `# type: ignore` or `Any` to silence mypy, dead code, a second way of doing something the codebase already does one way (e.g. a new helper duplicating `components.py`, `kb_config.py`, or `gh_helpers.py`), hand-rolled retry or sleep loops.
6. Check the tests: would they fail if the change were reverted? A test that passes with every dependency mocked proves nothing. LLM-output changes need a deterministic check on the parsed result, not just "no exception".

Report only findings you can defend with a concrete scenario. For each: `file:line`, severity (`critical` = wrong behavior, security, data loss, or a contract break; `important` = maintainability or a guardrail break; skip nits ruff already catches), what breaks, the input or state that triggers it, and the fix. If you find nothing, say so; do not pad the list.
