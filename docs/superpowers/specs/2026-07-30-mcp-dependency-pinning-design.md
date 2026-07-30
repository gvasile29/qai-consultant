# MCP Package Dependency Pinning — Design

**Date:** 2026-07-30
**Status:** Approved by user, pending spec review

## Problem

`qai-consultant-mcp` intermittently fails to attach in Claude Desktop
("could not attach" / silent connect failure). Investigated 2026-07-30 by
reading `%APPDATA%\Claude\logs\mcp-server-qai-consultant.log` /
`mcp.log`: on several launches, `uvx` logs `Installed 88 packages in
~26-30s` before the Python process even starts, and the gap between the
client sending `initialize` and the server's response lands right at
(sometimes just over) Claude Desktop's ~60s timeout — one launch
succeeded at 59.1s, another was cancelled by the client at 59.9s before
the server replied.

Root cause: `pyproject.toml`'s `[project] dependencies` pins only 2 of 6
packages exactly (`sentence-transformers==2.7.0`, `torch==2.13.0`); the
other 4 have loose or wide bounds:

```
mcp>=1.8.0,<2.0.0
langchain-community>=0.3.30
platformdirs>=4.0.0
defusedxml>=0.7.1
```

`uvx qai-consultant-mcp` (as documented in `README_MCP.md` and used in
Claude Desktop's config) resolves the dependency graph fresh against
PyPI's live index each time it runs. Whenever `mcp`, `langchain-community`,
`platformdirs`, or `defusedxml` (or any of their transitive dependencies)
publishes a new release, the resolver picks a different version, the
resolved-environment hash changes, and uv treats it as a cache miss —
reinstalling all ~88 packages from scratch. This happens **regardless of
whether the end user has pinned `qai-consultant-mcp` itself** to a
specific version in their own Claude Desktop config, because the drift
originates from *unrelated upstream packages*, not from our own release
cadence. The ~26-30s reinstall stacks with the already-known ~20-25s
`sentence-transformers`/`torch` import cost (see the v3.1.6 gotcha in
`CLAUDE.md`), pushing total startup time close to or past the client's
~60s budget.

This is a distinct, additional root cause from the v3.1.6 fix (which
addressed *where* the embedding warmup happens, not dependency-resolution
churn) and from the v3.1.5 fix (which addressed `qai-consultant-mcp`'s own
unbounded `mcp` floor breaking on a `mcp` major bump, a one-time event —
this is about routine, recurring drift from *any* of the 4 loosely-bound
packages, at any time).

## Alternatives considered

- **`uv.lock` / constraints file in the repo** — does not work for this
  use case. `uvx qai-consultant-mcp` installs the published PyPI
  package (sdist/wheel), not a clone of the source repo, so a lockfile
  committed to the repo never reaches the resolver uv runs on an end
  user's machine. The only lever that actually reaches users is
  `[project.dependencies]` in the published package's own metadata.
- **Lighter embedding backend (fastembed/ONNX) to cut the ~20-25s import
  cost** — addresses the *other* half of the timing budget, but is a
  larger, riskier change (different embedding output characteristics,
  disk-cache format implications) already flagged as future work in the
  v3.1.6 gotcha. Explicitly out of scope here — this spec only removes
  the *reinstall* trigger, not the fixed warmup cost.

## Design

**1. Exact-pin all 6 runtime dependencies in `pyproject.toml`**, matching
the versions currently verified to work (checked via `pip show` in the
dev environment), following the pattern already used for
`sentence-transformers`/`torch`:

```
mcp==1.28.1
langchain-community==0.4.2
sentence-transformers==2.7.0
platformdirs==4.11.0
torch==2.13.0
defusedxml==0.7.1
```

This removes the re-resolution trigger from the 4 packages that
previously had loose bounds. It does not make the environment fully
deterministic: each pinned package still has its own transitive
dependencies (e.g. `langchain-community` → `langchain-core`/`langsmith`;
`sentence-transformers` → `transformers`/`huggingface-hub`; `mcp` →
`pydantic`/`anyio`/`httpx`) that remain unpinned and can still publish a
new release that changes uv's resolved environment hash, triggering a
reinstall. This fix targets the most direct, most-controllable trigger —
the package's own declared dependencies — not the full transitive
closure; see the CLAUDE.md gotcha added alongside this fix for the
residual risk and the options considered for closing it fully (full
transitive pinning via a compiled lockfile, or recommending `uv tool
install` instead of `uvx` in `README_MCP.md` so the environment isn't
re-resolved per launch).

**2. Add a regression test in `tests/test_packaging.py`**
(`test_all_dependencies_are_exact_pinned`): parses `pyproject.toml`'s
`[project] dependencies` list and asserts every entry matches
`^[A-Za-z0-9_-]+==[\w.]+$` (name, `==`, version — no `>=`, `~=`, or bare
name). Fails loudly if a future edit reintroduces a loose bound, the same
class of gap that let the v3.1.5 `mcp` incident happen unnoticed. Runs in
CI with no network dependency (pure text parsing of the already-checked-out
`pyproject.toml`).

**3. Version bump + release docs (v3.3.1)**, per the repo's standing
Release Checklist: `src/version.py`, `pyproject.toml` version (kept in
lockstep), `CHANGELOG.md` (new entry), `README.md`, `README_MCP.md`,
`CLAUDE.md` (new gotcha entry, cross-linked to the v3.1.5 and v3.1.6
gotchas since all three concern the same "MCP fails to attach" symptom
but from different causes).

**Not changed:** no runtime behavior in `mcp_server.py`, `local_index.py`,
or any other module. This is purely a packaging/dependency-metadata
change.

## Testing

- `test_all_dependencies_are_exact_pinned` runs in normal CI (`pytest
  tests/`), no network required.
- Manual verification (after the user publishes v3.3.1 to PyPI, outside
  this repo's automation): run `uvx qai-consultant-mcp` twice in a row
  from a cleared uv cache; confirm the second launch does not log an
  `Installed NN packages` line, demonstrating the resolved environment is
  now stable across launches.

## Release ownership

This spec's implementation (code + docs PR) is prepared and merged
through the repo's normal PR flow. Publishing the new version to PyPI and
creating the git tag remain explicit, user-triggered steps — same pattern
as prior MCP releases (v3.0, v3.1.4, v3.1.5, v3.1.6) — not automated as
part of this change.
