# Docs & Process Trim Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce CLAUDE.md's bulk by extracting its longest incident post-mortems into `docs/postmortems/*.md` (linked, not duplicated), eliminate duplicated Playwright verification-script plumbing by backfilling a real bug fix (`full_screenshot()`) into the two scripts that still lack it, and record a lighter-weight process convention for future cosmetic-only changes so they don't default to the heaviest review ritual this repo has used.

**Architecture:** No application code changes — this plan touches only `CLAUDE.md`, new files under `docs/postmortems/`, and the three `scripts/verify_*_visual.py` files plus a new shared `scripts/verify_visual_common.py`. Each postmortem extraction keeps the *actionable rule* inline in `CLAUDE.md` (trimmed to 1-3 sentences) and moves the full incident forensics to its own dated file; CLAUDE.md links to it. The three visual-verification scripts keep their screen-specific click/selector/wait logic exactly as-is — only the genuinely duplicated (or, in two cases, missing-where-needed) helper functions move into the shared module.

**Tech Stack:** Markdown (docs), Python (`playwright.sync_api`, for the scripts).

## Global Constraints

- CLAUDE.md is loaded into every Claude Code session in this repo — trimming it is only a net win if the *rule* a session needs survives inline; only the *forensics* (repro steps, timestamps, dead-end investigation paths) move out.
- Nothing in `tests/` currently imports from `scripts/verify_*_visual.py` (confirmed: these are manual-only, not part of `pytest`/CI) — this plan's script changes carry no test-suite risk, but Task 2 still ends by actually running the scripts against a live `streamlit run src/app.py`, since they have no automated coverage otherwise.
- Scope is deliberately smaller than "every CLAUDE.md Gotcha/Roadmap entry" — see Task 1's "Explicitly out of scope" note. Do not expand scope to additional entries without going back to the user; over-extracting into a sprawling `docs/postmortems/` tree would reproduce the exact over-engineering pattern this plan exists to fix.

---

## File Structure

| File | Change |
|---|---|
| `docs/postmortems/2026-07-30-mcp-windows-stdio-deadlock.md` | New — full narrative from the "MCP server: embedding-model warmup" Gotcha + the v3.1.6 Roadmap entry |
| `docs/postmortems/2026-09-mcp-dependency-pinning-saga.md` | New — full narrative from 3 chained Gotchas (v3.3.1 exact-pinning, v3.4.4 transitive scipy, v3.5.1/v3.5.2 uv.sources) + their matching Roadmap entries |
| `docs/postmortems/2026-08-tee-pipefail-ci-gate.md` | New — full narrative from the `tee`/pipefail Gotcha |
| `docs/postmortems/2026-08-streamlit-scriptcontrolexception-swallowed.md` | New — full narrative from the "Never let a bare except Exception swallow StopException/RerunException" Gotcha |
| `CLAUDE.md` | 4 Gotchas entries + ~6 Roadmap entries trimmed to summary+link; new process-scale paragraph added to "Browser / UI Testing" section |
| `scripts/verify_visual_common.py` | New — `URL`, `full_screenshot()`, `reveal()` shared helpers |
| `scripts/verify_landing_visual.py` | Import shared helpers; replace 2 raw `page.screenshot(full_page=True)` calls with `full_screenshot()` |
| `scripts/verify_interactive_flow_visual.py` | Import shared helpers; replace 6 raw `page.screenshot(full_page=True)` calls with `full_screenshot()`; delete local `_reveal()`, use shared `reveal()` |
| `scripts/verify_output_screens_visual.py` | Import shared helpers; delete local `full_screenshot()` definition (lines 26-56) |

---

### Task 1: Extract 4 largest incident post-mortems out of CLAUDE.md

**Files:**
- Create: `docs/postmortems/2026-07-30-mcp-windows-stdio-deadlock.md`
- Create: `docs/postmortems/2026-09-mcp-dependency-pinning-saga.md`
- Create: `docs/postmortems/2026-08-tee-pipefail-ci-gate.md`
- Create: `docs/postmortems/2026-08-streamlit-scriptcontrolexception-swallowed.md`
- Modify: `CLAUDE.md` (Gotchas section, Roadmap section)

**Interfaces:** None (documentation only).

- [ ] **Step 1: Create the postmortems directory and the first file**

Run: `mkdir -p docs/postmortems` (or `New-Item -ItemType Directory -Force docs/postmortems` on Windows PowerShell).

Create `docs/postmortems/2026-07-30-mcp-windows-stdio-deadlock.md`:

```markdown
# Postmortem: MCP server deadlock on Windows stdio (v3.0.0/v3.0.1, fixed v3.0.2; cold-start regression fixed v3.1.6)

**Status:** Fixed. **Affected releases:** qai-consultant-mcp 3.0.0, 3.0.1 (deadlock); 3.1.0-3.1.5 (cold-start timeout regression). **Linked from:** CLAUDE.md's "MCP server: embedding-model warmup must happen before `mcp.run()`" Gotcha.

## Incident 1: indefinite deadlock on the first real tool call (v3.0.0/v3.0.1)

`mcp_server.py`'s `main()` calls `index.warmup_embedder()` on the main thread right after `_get_index()`, before starting the stdio server. Found via a real end-to-end test (v3.0.2) of the *published* `uvx qai-consultant-mcp` subprocess over real stdio: without the warmup, the server deadlocks indefinitely on the first `retrieve_qa_knowledge` call — happens even with a warm on-disk index cache (where `list_kb_sources` never touches the embedding model at all, so it's genuinely the *first* real model call that triggers it).

Root cause is Windows-specific: the `mcp` SDK's `stdio_server()` runs a concurrent `stdin_reader()` task blocked in `ReadFile()` on the piped stdin; when the embedding model's first real inference call (`HuggingFaceEmbeddings` construction + `encode()`, native torch/MKL thread + DLL init) instead happens lazily inside a FastMCP-dispatched worker thread — i.e. concurrently with that reader — the two threads deadlock on the process loader lock.

Confirmed via 7 isolated repros: plain sequential calls, a bare `ThreadPoolExecutor` worker, and `anyio.to_thread.run_sync` inside an asyncio loop all worked fine in-process; only the genuine subprocess-with-piped-stdio server loop hung, and only until the warmup call was moved before `mcp.run()`. `OMP_NUM_THREADS=1`/`MKL_NUM_THREADS=1`/`KMP_DUPLICATE_LIB_OK=TRUE`/`HF_HUB_OFFLINE=1` were all tried and did **not** fix it — the warmup ordering is the actual fix.

This affected the live PyPI package (3.0.0 and 3.0.1) for every real client (Claude Code, Claude Desktop, claude.ai) — any session that called a knowledge-retrieval tool would hang forever with no error.

**Fix:** move the embedding model's first real inference to the main thread, before `mcp.run()` starts `stdio_server()`'s concurrent stdin-reader task.

**Rule that survives in CLAUDE.md:** never move the model's first real inference back to being lazy/first-call-triggered without re-verifying this via a real subprocess-with-piped-stdio test.

## Incident 2: the warmup fix itself caused a cold-start "could not attach" (v3.1.0-v3.1.5, fixed v3.1.6)

The original warmup call was `index.search("warmup", k=1)`, which went through `LocalIndex`'s ordinary search path — on a cache miss, this synchronously embedded the *entire* KB corpus (`embed_documents()` over every chunk of every document) before the server could respond to even the first `initialize` message. Combined with Claude Desktop being MSIX-sandboxed (its own virtualized `%LOCALAPPDATA%`, confirmed via a duplicate `uv` package cache path under `AppData\Local\Packages\Claude_<id>\LocalCache\Local\`, completely separate from the system-wide cache), every attach attempt started from a genuinely cold on-disk index cache with no way to pre-warm it from outside. Claude Desktop's `initialize` request gives up after ~60s and cancels — this looked to users like "could not attach," not a crash.

**Fix (v3.1.6):** split `LocalIndex` into a new cheap `warmup_embedder()` (constructs the embedding model + one `embed_query()` call — the minimum needed to satisfy Incident 1's fix, which is about the *native runtime's first initialization* racing the stdin-reader thread, not about every subsequent call) and the expensive `_ensure_built()` (full corpus embed), now lazy and deferred to the first real `search()`/`list_sources()` call. Verified via a real subprocess-with-piped-stdio E2E test (`mcp.client.stdio.stdio_client`, matching exactly how Claude Desktop/Claude Code launch the server) with the on-disk index cache forced cold: no hang on the first real tool call.

**Residual, not fixed by v3.1.6:** even with everything fully cached, `initialize` still took roughly 20-25 seconds on a typical Windows machine — isolated to `import sentence_transformers` alone taking ~15s (torch adds another ~5s), not network calls or embedding time. Uncomfortably close to a 60s client budget on a slower machine. **This is the root cause later addressed directly in v3.5.3's fastembed backend switch** (see `docs/superpowers/specs/2026-09-17-mcp-embedding-backend-simplification-design.md`) rather than continuing to work around it.

**Trade-off accepted:** a corrupted/unreadable KB file no longer fails the server at startup, only lazily on the first real tool call — acceptable since the shipped KB is package content, not user-editable, and the more common startup failure (embedding model unavailable) still fails fast via `warmup_embedder()`.
```

- [ ] **Step 2: Replace the two CLAUDE.md entries with trimmed summaries + link**

In `CLAUDE.md`'s Gotchas section, find the entry starting `- **MCP server: embedding-model warmup must happen before \`mcp.run()\`.**` (the full text is the long paragraph beginning with that bold lead-in and ending `...it did not change *where* that first call happens.`). Replace the entire bullet with:

```markdown
- **MCP server: embedding-model warmup must happen before `mcp.run()`.** `mcp_server.py`'s `main()` calls `index.warmup_embedder()` on the main thread right after `_get_index()`, before starting the stdio server — never move the embedding model's first real inference back to being lazy/first-call-triggered without re-verifying this via a real subprocess-with-piped-stdio test. Root cause: a Windows-specific deadlock between the `mcp` SDK's stdin-reader thread and the embedding backend's native runtime first-init, both racing for the process loader lock. Full incident history (both the original v3.0.0/v3.0.1 deadlock and the v3.1.0-v3.1.5 cold-start regression it caused): `docs/postmortems/2026-07-30-mcp-windows-stdio-deadlock.md`.
```

In `CLAUDE.md`'s Roadmap section, find the `- **v3.1.6** ✅ Fix: \`qai-consultant-mcp\` could show "could not attach"...` bullet (ends `...still fails fast via \`warmup_embedder()\`.`). Replace it with:

```markdown
- **v3.1.6** ✅ Fix: `qai-consultant-mcp` could show "could not attach" in Claude Desktop on a cold cache — a client-side `initialize` handshake timeout caused by the original warmup call synchronously embedding the entire KB corpus. Split `LocalIndex` into a cheap `warmup_embedder()` (main-thread, before `mcp.run()`) and a lazy `_ensure_built()` (deferred to first real use). Full incident history: `docs/postmortems/2026-07-30-mcp-windows-stdio-deadlock.md`.
```

- [ ] **Step 3: Create the dependency-pinning-saga postmortem**

Create `docs/postmortems/2026-09-mcp-dependency-pinning-saga.md`:

```markdown
# Postmortem: the MCP dependency-pinning saga (v3.3.1 -> v3.4.4 -> v3.5.1/v3.5.2)

**Status:** Fixed (v3.5.2), then structurally addressed (v3.5.3 fastembed switch — see `docs/superpowers/specs/2026-09-17-mcp-embedding-backend-simplification-design.md`). **Linked from:** CLAUDE.md's "Every entry in pyproject.toml's dependencies must be exact-pinned" and "project-local [tool.uv.sources] index scoping" Gotchas.

Three chained incidents, each caused by the previous fix's blind spot, all rooted in the same fact: `uvx qai-consultant-mcp` resolves against PyPI's live index on every launch, so nothing committed to this repo (a `uv.lock`, a `[tool.uv.sources]` block) travels to a real end user's install.

## Incident 1 (v3.3.1): loose transitive bounds let upstream releases reinstall the whole environment

Found in real Claude Desktop logs: 4 of the package's 6 runtime dependencies (`mcp`, `langchain-community`, `platformdirs`, `defusedxml`) had loose version bounds. Whenever any of them — or a transitive dependency uv's resolver picks — published a new PyPI release between two launches, `uvx qai-consultant-mcp` re-resolved and reinstalled all ~88 packages (~26-30s), regardless of which `qai-consultant-mcp` version a user had pinned. Stacked with the ~20-25s `sentence-transformers`/`torch` import cost, this routinely approached or exceeded Claude Desktop's ~60s `initialize` timeout — one observed launch got a response at 59.1s, another was cancelled at 59.9s.

**Fix:** exact-pin all 6 direct dependencies (`mcp==1.28.1`, `langchain-community==0.4.2`, `sentence-transformers==2.7.0`, `platformdirs==4.11.0`, `torch==2.13.0`, `defusedxml==0.7.1`), plus a regression test (`tests/test_packaging.py::test_all_dependencies_are_exact_pinned`). A `uv.lock` in the repo was considered and ruled out: it never reaches `uvx`'s resolver for a published package.

**Residual, explicitly flagged at the time:** exact-pinning the 6 direct dependencies does not pin *their* transitive dependencies (`mcp`'s own `pydantic`/`anyio`/`httpx`, `sentence-transformers`'s `transformers`/`huggingface-hub`, etc.) — known limitation, not yet closed.

## Incident 2 (v3.4.4, 2026-08-31): the residual risk materialized for real

Three consecutive Claude Desktop attach attempts each logged `Downloading scipy (35.0MiB)` immediately after `initialize`, then a `notifications/cancelled` ~60s later. `scipy` is not a direct dependency — pulled in transitively by `scikit-learn`, which `sentence-transformers==2.7.0` requires; it resolved to `scipy==1.18.1`, a release not yet present in Claude Desktop's own sandboxed `uv` cache. Worse than a one-time slow launch: because the client cancels *during* the install, the wheel is extracted into a fresh `.tmp*` directory that never gets promoted to the permanent cache — 17 orphaned `.tmp*` directories were found, each a different abandoned attempt, all re-downloading the identical wheel. Self-sustaining: no amount of retrying cleared it.

**Fix:** exact-pin the *entire resolved dependency tree* (~99 entries, via `uv pip compile pyproject.toml --universal --python-version 3.10`), including per-Python-version variants (numpy/scipy/scikit-learn each need a different exact pin on 3.10 vs 3.11 vs 3.12+) and per-platform markers (`pywin32`/`colorama` on `win32` only). `--universal` is required — a platform-specific compile would silently break installs on other platforms.

## Incident 3 (v3.5.1, 2026-09-15, yanked same day; fixed v3.5.2): a project-local index scoping broke every real install

`pyproject.toml` had scoped `torch` to a CPU-only wheel index (`download.pytorch.org/whl/cpu`) via `[tool.uv.sources]`/`[[tool.uv.index]]` since v3.0, verified only by running `uv sync`/`uv pip install .` *from inside the checked-out repo* — which reads `[tool.uv.*]` config because it's ambient project context, not because a real consumer would see it. `[tool.uv.*]` is project-local config: it is never distributed as part of a built wheel/sdist's metadata. The weekly Dependency Drift Canary correctly resolved `torch==2.13.0+cpu` *for the project's own compile step*, baked that exact string into `dependencies`, and it shipped as `3.5.1` — which then failed immediately for every real consumer with "no version of torch==2.13.0+cpu" (plain PyPI has no `+cpu`-tagged build).

**Fix:** reverted `torch` to a plain `torch==2.13.0` pin (matching the last known-working 3.4.4) and removed the `[tool.uv.sources]`/`[[tool.uv.index]]` block entirely, so local tooling and real consumers resolve identically.

## The pattern

All three incidents were "fixed" by adding *more* pinning rigor around the same underlying cost (`sentence-transformers`/`torch`'s heavy, slow-importing dependency chain), never by questioning whether that cost needed to be there at all. v3.5.3 addressed the root cause directly instead — see `docs/superpowers/specs/2026-09-17-mcp-embedding-backend-simplification-design.md`.
```

- [ ] **Step 4: Replace the three chained CLAUDE.md Gotchas entries with trimmed summaries + link**

In `CLAUDE.md`'s Gotchas section, find and replace these three bullets (each currently a long paragraph):

Entry starting `- **Every entry in \`pyproject.toml\`'s \`[project] dependencies\` must be exact-pinned...**` → replace with:

```markdown
- **Every entry in `pyproject.toml`'s `[project] dependencies` must be exact-pinned (`==`), never a loose bound.** Enforced by `tests/test_packaging.py::test_all_dependencies_are_exact_pinned`. `uvx qai-consultant-mcp` resolves against PyPI's live index on every launch — nothing committed to this repo travels to a real end user's install, so a loose bound anywhere in the resolved tree can trigger an unexpected reinstall that pushes cold-start past Claude Desktop's ~60s `initialize` timeout. Full incident history (v3.3.1 → v3.4.4 → v3.5.1/v3.5.2): `docs/postmortems/2026-09-mcp-dependency-pinning-saga.md`.
```

Entry starting `- **The v3.3.1 residual risk above materialized for real on 2026-08-31...**` → delete entirely (fully absorbed into the postmortem's Incident 2 and the entry above).

Entry starting `- **A project-local \`[tool.uv.sources]\`/\`[[tool.uv.index]]\` index scoping is invisible to real \`uvx\`/\`pip\` consumers...**` → replace with:

```markdown
- **A project-local `[tool.uv.sources]`/`[[tool.uv.index]]` index scoping is invisible to real `uvx`/`pip` consumers.** `[tool.uv.*]` config only applies when `uv` resolves this repo's own `pyproject.toml` directly — it is never distributed as part of a built wheel/sdist, so it cannot verify anything about what a real downstream consumer sees. Any future per-package index scoping in this file must be verified via `uvx --from <published-package>==<version> ...` run from a directory with no ambient project files, not via `uv sync`/`uv pip install .` from inside the checked-out repo. Full incident history: `docs/postmortems/2026-09-mcp-dependency-pinning-saga.md`.
```

In `CLAUDE.md`'s Roadmap section, trim the `v3.3.1`, `v3.4.4`, `v3.5.1`, and `v3.5.2` bullets (each currently a long paragraph with full incident forensics) to keep only: the version, a one-sentence description of the user-visible fix, and a link to the postmortem. For each, keep the bullet's opening clause (version, checkmark/no-checkmark status, one-line summary already present at the start of each bullet — e.g. `**v3.3.1** ✅ Fix: \`qai-consultant-mcp\` could intermittently fail to attach...`) up through the first sentence, delete the rest of that bullet's body, and append: `` Full incident history: `docs/postmortems/2026-09-mcp-dependency-pinning-saga.md`. `` Do this for all 4 Roadmap bullets (v3.3.1, v3.4.4, v3.5.1, v3.5.2) individually — read each one's actual current first sentence in the file before trimming, since "keep the opening clause" must produce a grammatically complete sentence for each, not a mechanically identical cut point across all 4.

- [ ] **Step 5: Create the tee/pipefail postmortem**

Create `docs/postmortems/2026-08-tee-pipefail-ci-gate.md`:

```markdown
# Postmortem: `tee` silently swallowed CI gate failures (PR #67)

**Status:** Fixed. **Linked from:** CLAUDE.md's "`command | tee -a` silently swallows exit codes" Gotcha.

`command | tee -a "$GITHUB_STEP_SUMMARY"` silently swallows the command's real exit code — every "blocking" CI job needed `set -o pipefail` as the first line of its `run:` block, or it wasn't actually blocking.

Discovered in PR #67 (Phase 3's coverage gate): bash's default pipe exit status is the *last* command's — here always `tee`'s, which is 0 — so `python -m pytest ... --cov-fail-under=60 | tee -a ...` reported job status "success" even when the log's own last line read `FAIL Required test coverage of 61% not reached`. GitHub Actions' default shell for `run:` steps does **not** set `pipefail` on its own; it must be set explicitly inside the script.

This affected every "blocking" job added since PR #63/#66 (`typecheck`, `security-bandit`, `evals-det`) — none of them had actually been capable of failing a PR, they simply hadn't had a real finding to prove it yet.

**Fix:** add `set -o pipefail` to all `run:` blocks that pipe to `tee` (including the intentionally-non-blocking `security-pip-audit`, so its neutral/warning status displays correctly too). The coverage floor itself also moved from 61% (Windows-measured) to 60% (the real Linux number, 60.88%, is lower because fewer tests run there) as part of the same fix.

**How it was caught:** actually reading a real `ubuntu-latest` job's log line-by-line after it reported "pass" instead of trusting the green checkmark.

**Rule that survives in CLAUDE.md:** any future CI job that pipes to `tee` (or any command whose exit code must propagate through a pipe) needs `set -o pipefail` as the first line of its `run:` block.
```

- [ ] **Step 6: Replace the CLAUDE.md tee/pipefail Gotcha with a trimmed summary + link**

Find the entry starting `- **\`command | tee -a "$GITHUB_STEP_SUMMARY"\` silently swallows the command's real exit code...**` and replace it with:

```markdown
- **`command | tee -a "$GITHUB_STEP_SUMMARY"` silently swallows the command's real exit code — every "blocking" CI job needs `set -o pipefail` as the first line of its `run:` block, or it isn't actually blocking.** GitHub Actions' default shell does not set `pipefail` on its own. Found in PR #67 when a coverage gate reported "pass" despite its own log's last line reading `FAIL`. Full incident history: `docs/postmortems/2026-08-tee-pipefail-ci-gate.md`.
```

- [ ] **Step 7: Create the StopException/RerunException postmortem**

Create `docs/postmortems/2026-08-streamlit-scriptcontrolexception-swallowed.md`:

```markdown
# Postmortem: bare `except Exception` swallowed Streamlit's control-flow exceptions

**Status:** Fixed. **Linked from:** CLAUDE.md's "Never let a bare except Exception swallow StopException/RerunException" Gotcha.

Streamlit raises `StopException`/`RerunException` into the running script at the next `st.*` call whenever it needs to legitimately stop or rerun (most commonly a websocket disconnect/reconnect — a long-standing Streamlit client-side race, see `streamlit/streamlit#9767` and `#11500`).

On Streamlit 1.37 (this app's pin at the time this bug was found) both inherited from `Exception`, so a bare `except Exception` in `render_strategy()`'s per-stage try/excepts swallowed them — logged as an empty-message "generation failed", execution then barreled into the remaining stages on a dead session, producing bursts of empty-message failures and endless non-deterministic regeneration even after the `results_complete` resumability fix (a separate, earlier fix for a related but distinct mid-pipeline-rerun bug).

**Fix:** each of `render_strategy()`'s 4 per-stage try/excepts got `except (StopException, RerunException): raise` before the generic `except Exception as exc:`, as explicit defense.

**Follow-up:** `streamlit==1.59.1` (upgraded from 1.37.0) moved `ScriptControlException` to inherit from `BaseException` instead, so a bare `except Exception` can no longer catch it regardless of this fix — but the explicit re-raise clause was kept anyway (belt-and-suspenders against a future downgrade or an upstream regression). `from streamlit.runtime.scriptrunner import RerunException, StopException` still re-exports correctly at 1.59.1 even though the concrete classes live in `streamlit.runtime.scriptrunner_utils.exceptions` internally.

**Rule that survives in CLAUDE.md:** any new `try/except Exception` wrapped around `st.*` calls in `app.py` needs the same `except (StopException, RerunException): raise` guard before the generic clause.
```

- [ ] **Step 8: Replace the two related CLAUDE.md Gotchas with trimmed summaries + link**

Find the entry starting `- **Never let a bare \`except Exception\` swallow \`StopException\`/\`RerunException\`:**` and replace it with:

```markdown
- **Never let a bare `except Exception` swallow `StopException`/`RerunException`.** Streamlit raises one of these into the running script whenever it needs to legitimately stop or rerun (most commonly a websocket disconnect/reconnect). Any `try/except Exception` wrapped around `st.*` calls in `app.py` needs `except (StopException, RerunException): raise` before the generic clause. Full incident history: `docs/postmortems/2026-08-streamlit-scriptcontrolexception-swallowed.md`.
```

Find the entry starting `- **\`streamlit==1.59.1\` pin (upgraded from 1.37.0):**` and replace it with:

```markdown
- **`streamlit==1.59.1` pin (upgraded from 1.37.0):** picked up an upstream fix moving `ScriptControlException` (`StopException`/`RerunException`) to inherit from `BaseException` instead of `Exception` — see `docs/postmortems/2026-08-streamlit-scriptcontrolexception-swallowed.md`. No breaking API changes affected this app's Streamlit usage across the range. Import `RerunException`/`StopException` via the public `streamlit.runtime.scriptrunner` path, not the internal module they actually live in.
```

- [ ] **Step 9: Verify the extraction didn't break any cross-reference and commit**

Run: `grep -rn "docs/postmortems/" CLAUDE.md` — expect exactly 4 distinct postmortem filenames referenced, each from at least one Gotcha or Roadmap entry.

```bash
git add docs/postmortems/ CLAUDE.md
git commit -m "$(cat <<'EOF'
docs: extract 4 largest CLAUDE.md incident postmortems into docs/postmortems/

Moves full incident forensics (Windows stdio deadlock, the 3-incident
dependency-pinning saga, the tee/pipefail CI bug, and the Streamlit
ScriptControlException bug) out of CLAUDE.md into dated postmortem
files, keeping only the actionable rule + a link inline. CLAUDE.md is
loaded into every session in this repo; the forensics were valuable
history but not something every session needs to re-read.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_013xJEqRuCdtixjGy8hpg3jB
EOF
)"
```

**Explicitly out of scope for this task (a deliberate scope decision, not an oversight):** several other Gotchas/Roadmap entries are also long (e.g. "Streamlit Cloud deploy lag," the "Every CI job must install dev tools via requirements-dev.txt" ruff-drift incident, the "v3.4.4 transitive-dependency lock surfaced CVEs" entry, the "module-level import allowlist test" entry). These were deliberately left in place: extracting every long entry in one pass risks turning `docs/postmortems/` into its own sprawling, unmaintained archive — the same over-engineering-by-accumulation pattern this whole audit exists to push back on. If CLAUDE.md's length becomes a problem again, treat that as a signal to revisit this list, not a reason to have extracted everything up front.

---

### Task 2: Consolidate Playwright verification script plumbing

**Files:**
- Create: `scripts/verify_visual_common.py`
- Modify: `scripts/verify_landing_visual.py`
- Modify: `scripts/verify_interactive_flow_visual.py`
- Modify: `scripts/verify_output_screens_visual.py`

**Interfaces:**
- Produces: `verify_visual_common.URL: str`, `verify_visual_common.full_screenshot(page: Page, path: str, viewport: dict) -> None`, `verify_visual_common.reveal(page: Page, locator, max_scrolls: int = 40, step: int = 1200, pause: int = 100) -> None`.
- Consumes: `playwright.sync_api.Page` (all three scripts already depend on this).

- [ ] **Step 1: Write the shared module**

```python
"""Shared helpers for the manual Playwright visual-verification scripts
(scripts/verify_*_visual.py). Not part of pytest/CI — these scripts are
run manually against a live `streamlit run src/app.py`.
"""
from playwright.sync_api import Page

URL = "http://localhost:8501"


def full_screenshot(page: Page, path: str, viewport: dict) -> None:
    """Streamlit's [data-testid="stMain"] and [data-testid="stSidebarContent"]
    scroll independently of the document -- stApp/stAppViewContainer are
    height:100vh + overflow:hidden, and stMain/stSidebarContent are each
    overflow-y:auto with their own clientHeight capped at the viewport.
    Plain page.screenshot(full_page=True) only captures document scroll
    height, which Streamlit pins to exactly the viewport height, so it
    silently crops anything below the fold in either region (confirmed via
    a live DOM probe: stMain.scrollHeight=1736 vs clientHeight=1400 on a
    real Risk Register tab). Fix: measure the true content height, grow the
    viewport to fit it (stApp's 100vh math then gives every region enough
    room to render without internal scrolling), screenshot, then restore the
    original viewport so subsequent interactions see consistent geometry.

    `viewport` is the caller's normal viewport dict (e.g. {"width": 1280,
    "height": 1400}) to restore afterward — pass whatever you constructed
    the page with, since different scripts use different sizes."""
    needed = page.evaluate(
        """
        () => {
            const main = document.querySelector('[data-testid="stMain"]');
            const sidebar = document.querySelector('[data-testid="stSidebarContent"]');
            return Math.max(
                main ? main.scrollHeight : 0,
                sidebar ? sidebar.scrollHeight : 0,
                window.innerHeight,
            );
        }
        """
    )
    page.set_viewport_size({"width": viewport["width"], "height": needed + 40})
    page.wait_for_timeout(150)
    page.screenshot(path=path, full_page=True)
    page.set_viewport_size(viewport)
    page.wait_for_timeout(150)


def reveal(page: Page, locator, max_scrolls: int = 40, step: int = 1200, pause: int = 100) -> None:
    """Streamlit lazy-mounts elements far below the fold (IntersectionObserver-
    gated rendering -- confirmed by inspecting document.querySelectorAll('button')
    before/after scrolling: a button can be absent from the DOM entirely until
    scrolled near view, not just off-screen). Scroll incrementally until
    `locator` is attached before interacting with it; a no-op if it's already
    present."""
    for _ in range(max_scrolls):
        if locator.count() > 0:
            return
        page.mouse.wheel(0, step)
        page.wait_for_timeout(pause)
```

- [ ] **Step 2: Update `verify_landing_visual.py`**

Replace the import block (lines 10-16):

```python
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

URL = "http://localhost:8501"
```

with:

```python
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

from verify_visual_common import URL, full_screenshot

VIEWPORT = {"width": 1280, "height": 900}
```

Replace both raw screenshot calls. Line 24 + line 31 together (first browser block):

```python
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(URL, timeout=30000, wait_until="networkidle")
        # "networkidle" only tracks HTTP -- Streamlit renders the actual DOM
        # over a websocket after that, so wait for the hero itself before
        # timing the entrance animations against it.
        page.wait_for_selector(".pom-hero", timeout=30000)
        page.wait_for_timeout(2500)  # let the one-shot entrance animations finish
        page.screenshot(path=str(out_dir / "landing_normal_motion.png"), full_page=True)
```

becomes:

```python
        page = browser.new_page(viewport=VIEWPORT)
        page.goto(URL, timeout=30000, wait_until="networkidle")
        # "networkidle" only tracks HTTP -- Streamlit renders the actual DOM
        # over a websocket after that, so wait for the hero itself before
        # timing the entrance animations against it.
        page.wait_for_selector(".pom-hero", timeout=30000)
        page.wait_for_timeout(2500)  # let the one-shot entrance animations finish
        full_screenshot(page, str(out_dir / "landing_normal_motion.png"), VIEWPORT)
```

Line 39 + line 43 together (second browser block):

```python
        page = browser.new_page(viewport={"width": 1280, "height": 900}, reduced_motion="reduce")
        page.goto(URL, timeout=30000, wait_until="networkidle")
        page.wait_for_selector(".pom-hero", timeout=30000)
        page.wait_for_timeout(300)  # should already be at resting state almost immediately
        page.screenshot(path=str(out_dir / "landing_reduced_motion.png"), full_page=True)
```

becomes:

```python
        page = browser.new_page(viewport=VIEWPORT, reduced_motion="reduce")
        page.goto(URL, timeout=30000, wait_until="networkidle")
        page.wait_for_selector(".pom-hero", timeout=30000)
        page.wait_for_timeout(300)  # should already be at resting state almost immediately
        full_screenshot(page, str(out_dir / "landing_reduced_motion.png"), VIEWPORT)
```

- [ ] **Step 3: Update `verify_interactive_flow_visual.py`**

Replace the import block and delete the local `_reveal()` definition (lines 11-31):

```python
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

URL = "http://localhost:8501"


def _reveal(page, locator, max_scrolls=40, step=1200, pause=100):
    """Streamlit lazy-mounts elements far below the fold (IntersectionObserver-
    gated rendering -- confirmed by inspecting document.querySelectorAll('button')
    before/after scrolling: the intro screen's "Start" button and the dialogue
    form's submit button are absent from the DOM entirely until scrolled near
    view, not just off-screen). Scroll incrementally until `locator` is
    attached before interacting with it; a no-op if it's already present."""
    for _ in range(max_scrolls):
        if locator.count() > 0:
            return
        page.mouse.wheel(0, step)
        page.wait_for_timeout(pause)
```

with:

```python
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

from verify_visual_common import URL, full_screenshot, reveal

VIEWPORT = {"width": 1280, "height": 1400}
```

Replace all 4 call sites of `_reveal(page, ...)` (lines 44, 84, 118, 134) with `reveal(page, ...)` (same arguments, just drop the leading underscore).

Replace all 6 raw `page.screenshot(path=str(out_dir / "<name>.png"), full_page=True)` calls with `full_screenshot(page, str(out_dir / "<name>.png"), VIEWPORT)`, keeping each call's original filename:
- Line 48: `dialogue_empty.png`
- Line 67: `dialogue_filled.png`
- Line 76: `dialogue_card_hover.png`
- Line 81: `sidebar_button_hover.png`
- Line 93: `review_first_visit.png`
- Line 108: `review_after_edit.png`
- Line 138: `review_reduced_motion.png` (7 total — this one was miscounted as 6 in this task's header; verify the actual count when editing and adjust the commit message if it differs)

Also replace both `new_page(viewport={"width": 1280, "height": 1400}, ...)` calls (lines 39 and 114) with `new_page(viewport=VIEWPORT, ...)`.

- [ ] **Step 4: Update `verify_output_screens_visual.py`**

Replace the import block and delete the local `full_screenshot()` definition (lines 16-56):

```python
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

URL = "http://localhost:8501"
VIEWPORT = {"width": 1280, "height": 1400}


def full_screenshot(page: Page, path: str) -> None:
    """Streamlit's [data-testid="stMain"] and [data-testid="stSidebarContent"]
    scroll independently of the document -- stApp/stAppViewContainer are
    height:100vh + overflow:hidden, and stMain/stSidebarContent are each
    overflow-y:auto with their own clientHeight capped at the viewport.
    Plain page.screenshot(full_page=True) only captures document scroll
    height, which Streamlit pins to exactly the viewport height, so it
    silently crops anything below the fold in either region (confirmed via
    a live DOM probe: stMain.scrollHeight=1736 vs clientHeight=1400 on the
    real Risk Register tab). Fix: measure the true content height, grow the
    viewport to fit it (stApp's 100vh math then gives every region enough
    room to render without internal scrolling), screenshot, then restore the
    original viewport so subsequent interactions see consistent geometry."""
    needed = page.evaluate(
        """
        () => {
            const main = document.querySelector('[data-testid="stMain"]');
            const sidebar = document.querySelector('[data-testid="stSidebarContent"]');
            return Math.max(
                main ? main.scrollHeight : 0,
                sidebar ? sidebar.scrollHeight : 0,
                window.innerHeight,
            );
        }
        """
    )
    page.set_viewport_size({"width": VIEWPORT["width"], "height": needed + 40})
    page.wait_for_timeout(150)
    page.screenshot(path=path, full_page=True)
    page.set_viewport_size(VIEWPORT)
    page.wait_for_timeout(150)
```

with:

```python
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

from verify_visual_common import URL, full_screenshot

VIEWPORT = {"width": 1280, "height": 1400}
```

This script's 8 existing `full_screenshot(page, str(out_dir / "<name>.png"))` call sites now need a third argument. Add `, VIEWPORT` before the closing paren of each: `full_screenshot(page, str(out_dir / "landing_deliverables.png"), VIEWPORT)`, `full_screenshot(page, str(out_dir / "strategy_stage_active.png"), VIEWPORT)`, `full_screenshot(page, str(out_dir / "strategy_tab1_risk.png"), VIEWPORT)`, `full_screenshot(page, str(out_dir / "strategy_tab2_effort.png"), VIEWPORT)`, `full_screenshot(page, str(out_dir / "doc_review_input_tray.png"), VIEWPORT)`, `full_screenshot(page, str(out_dir / "doc_review_results.png"), VIEWPORT)`, `full_screenshot(page, str(out_dir / "landing_deliverables_reduced_motion.png"), VIEWPORT)`, `full_screenshot(page, str(out_dir / "doc_review_results_reduced_motion.png"), VIEWPORT)`.

- [ ] **Step 5: Run all 3 scripts against a live app to confirm nothing broke**

Run: `streamlit run src/app.py` in one terminal (leave running), then in another:

```bash
python scripts/verify_landing_visual.py
python scripts/verify_interactive_flow_visual.py
python scripts/verify_output_screens_visual.py
```

Expected: all 3 exit 0, print their existing console assertions (fill widths, class names, hover colors) as before, and produce screenshots in their respective temp directories — this time with `landing_normal_motion.png`/`landing_reduced_motion.png` and all 7 of the interactive-flow script's screenshots correctly capturing the full page height instead of the pre-existing (per CLAUDE.md's own gotcha) silent crop. `verify_output_screens_visual.py` runs one real Mistral/Pinecone generation (per its own docstring) — budget a few minutes and 1 of the session's free runs.

- [ ] **Step 6: Commit**

```bash
git add scripts/verify_visual_common.py scripts/verify_landing_visual.py scripts/verify_interactive_flow_visual.py scripts/verify_output_screens_visual.py
git commit -m "$(cat <<'EOF'
refactor: consolidate Playwright visual-verification script helpers

Extracts full_screenshot() (the Streamlit independent-scroll-region
screenshot fix, previously only in verify_output_screens_visual.py)
and reveal() (previously only in verify_interactive_flow_visual.py)
into a shared scripts/verify_visual_common.py, and backfills
full_screenshot() into the landing and interactive-flow scripts —
CLAUDE.md documented both as still silently producing cropped
screenshots. Screen-specific click/selector/wait logic is unchanged
in all 3 scripts.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_013xJEqRuCdtixjGy8hpg3jB
EOF
)"
```

---

### Task 3: Record a lighter-weight process convention for cosmetic-only changes

**Files:**
- Modify: `CLAUDE.md` (end of the "## Browser / UI Testing" section)

**Interfaces:** None (documentation only).

- [ ] **Step 1: Add the process-scale paragraph**

At the end of the existing `## Browser / UI Testing` section in `CLAUDE.md` (after the paragraph ending `...Playwright is installed (\`playwright==1.62.0\`, pinned in \`requirements-dev.txt\`) with the Chromium browser binary already downloaded locally — no setup needed before writing a script.`), add:

```markdown

**Process scale for visual/CSS-only changes:** the 3-phase "Power-On Sequence" redesign (v3.4.1-v3.4.3) used `superpowers:subagent-driven-development` with an independent implementer + reviewer per task, plus a separate final whole-branch review, for each phase. That level of process is proportionate for a multi-task redesign spanning several screens, but it is not the default for a small, single-screen, cosmetic-only CSS/styling change with no logic, security, or data-handling surface — those can go through the normal direct-implementation workflow (write the change, verify visually per the section above, commit) without a dedicated multi-agent review pass. Reserve the heavier process for changes that touch application logic, security-sensitive code, or anything with a real behavioral surface to get wrong.
```

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "$(cat <<'EOF'
docs: record process-scale convention for cosmetic-only visual changes

The 3-phase Power-On Sequence redesign's full subagent-driven-
development treatment (per-task implementer+reviewer, final whole-
branch review) is disproportionate for a small single-screen CSS
change with no logic/security surface. Records this as an explicit
convention so future small visual work doesn't default to the
heaviest process this repo has used.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_013xJEqRuCdtixjGy8hpg3jB
EOF
)"
```
