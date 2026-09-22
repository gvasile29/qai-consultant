# Postmortem: the MCP dependency-pinning saga (v3.3.1 -> v3.4.4 -> v3.5.1/v3.5.2)

**Status:** Fixed (v3.5.2). A proposed structural fix (swapping the embedding backend to fastembed/ONNX) is specced and shipped in v3.5.3 — see `docs/superpowers/specs/2026-09-17-mcp-embedding-backend-simplification-design.md`. **Linked from:** CLAUDE.md's "Every entry in pyproject.toml's dependencies must be exact-pinned" and "project-local [tool.uv.sources] index scoping" Gotchas.

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

All three incidents were "fixed" by adding *more* pinning rigor around the same underlying cost (`sentence-transformers`/`torch`'s heavy, slow-importing dependency chain), never by questioning whether that cost needed to be there at all. A fastembed/ONNX backend swap addresses the root cause directly — shipped in v3.5.3: `docs/superpowers/specs/2026-09-17-mcp-embedding-backend-simplification-design.md`.
