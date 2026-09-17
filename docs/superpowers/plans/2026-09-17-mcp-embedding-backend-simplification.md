# MCP Embedding Backend Simplification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the MCP server's local retrieval index (`src/local_index.py`) embedding backend from `sentence-transformers`/`torch` (via `langchain_community.embeddings.HuggingFaceEmbeddings`) with `fastembed` (ONNX Runtime, no torch), then shrink `pyproject.toml`'s dependency list and delete the dependency-drift-canary automation that existed to manage the old, much larger list.

**Architecture:** `LocalIndex._embedding_model()` constructs a new thin adapter class (`_FastEmbedEmbeddings`) instead of `HuggingFaceEmbeddings`, exposing the same two methods (`embed_documents`, `embed_query`) so nothing else in `LocalIndex` changes. The on-disk cache format version is bumped so old sentence-transformers-built caches are treated as absent rather than misread. `pyproject.toml`'s direct dependencies drop `torch`/`sentence-transformers`/`langchain-community` and gain `fastembed`; the full transitive lock is regenerated via the already-documented `uv pip compile` command. `.github/workflows/dependency-drift-check.yml` and its support script/test are deleted.

**Tech Stack:** Python 3.10+, `fastembed` (ONNX Runtime-based embeddings), `uv` (dependency compilation), `pytest`, `mcp` SDK (stdio client, for the manual verification script).

**Spec:** `docs/superpowers/specs/2026-09-17-mcp-embedding-backend-simplification-design.md`

## Global Constraints

- Every entry in `pyproject.toml`'s `[project] dependencies` must be exact-pinned (`==`), enforced by `tests/test_packaging.py::test_all_dependencies_are_exact_pinned`.
- `requires-python = ">=3.10"` — the regenerated lock must cover 3.10/3.11/3.12 via `--universal`.
- `kb_config.EMBEDDING_MODEL` (`"sentence-transformers/all-MiniLM-L6-v2"`) does not change — fastembed resolves this exact string itself.
- Retrieval quality floor: `evals/local_index_parity.py` must keep passing against `thresholds.py`'s `LOCAL_INDEX_RECALL_AT_K_MIN` (0.8) / `LOCAL_INDEX_MRR_MIN` (0.7) — already verified at 0.91/0.86 with fastembed in the pre-design spike.
- Release Checklist: any version bump updates `src/version.py`, `pyproject.toml`, `CHANGELOG.md`, `README.md`, `README_MCP.md`, `CLAUDE.md` together in the same change.
- No `--extra-index-url` in the `uv pip compile` regeneration command — see the existing comment block above `pyproject.toml`'s `dependencies` (the v3.5.1 incident).

---

## File Structure

| File | Change |
|---|---|
| `src/local_index.py` | New `_FastEmbedEmbeddings` adapter class; `_embedding_model()` uses it; `_CACHE_FORMAT_VERSION` bumped 1→2 |
| `tests/test_local_index.py` | 6 mock-target updates (`local_index.HuggingFaceEmbeddings` → `local_index._FastEmbedEmbeddings`); new cache-version-upgrade test |
| `src/mcp_server.py` | Comment-only update in `main()`: torch/MKL language → general native-runtime language |
| `pyproject.toml` | Remove `torch`/`sentence-transformers`/`langchain-community` direct deps, add `fastembed`, regenerate full `dependencies` array |
| `requirements-dev.txt` | Add `fastembed==0.8.0` |
| `.github/workflows/dependency-drift-check.yml` | Deleted |
| `scripts/check_dependency_drift.py` | Deleted |
| `tests/test_check_dependency_drift.py` | Deleted |
| `scripts/verify_mcp_stdio_no_deadlock.py` | New — manual real-subprocess E2E check |
| `src/version.py`, `CHANGELOG.md`, `README.md`, `README_MCP.md`, `CLAUDE.md` | Release Checklist updates for v3.5.3 |

---

### Task 1: Swap `local_index.py`'s embedding backend to fastembed

**Files:**
- Modify: `src/local_index.py:22-35` (imports, `_CACHE_FORMAT_VERSION`), `src/local_index.py:175-178` (`_embedding_model`)
- Test: `tests/test_local_index.py`

**Interfaces:**
- Produces: `local_index._FastEmbedEmbeddings` — a class with `__init__(self, model_name: str)`, `embed_documents(self, texts: list[str]) -> list[list[float]]`, `embed_query(self, text: str) -> list[float]`. `tests/test_local_index.py`'s mocks target this class name.
- Consumes: `kb_config.EMBEDDING_MODEL` (unchanged), `fastembed.TextEmbedding` (new third-party import).

- [ ] **Step 1: Write the failing test for the new cache-version behavior**

Add to `tests/test_local_index.py`, in the "Corrupted cache recovery" section (after `test_cache_with_wrong_embedding_model_falls_back_to_rebuild`, before the `list_sources()` section):

```python
def test_cache_format_version_is_2():
    from local_index import _CACHE_FORMAT_VERSION
    assert _CACHE_FORMAT_VERSION == 2, (
        "Bumped for the fastembed backend switch — an old format-1 cache (built "
        "with sentence-transformers vectors) must never be read as if it were "
        "fastembed output; see docs/superpowers/specs/"
        "2026-09-17-mcp-embedding-backend-simplification-design.md"
    )


def test_cache_written_under_old_format_version_is_treated_as_miss(tmp_path):
    kb = tmp_path / "kb"
    cache_dir = tmp_path / "cache"
    _write_kb(kb, {"standards/std.md": "# Std\n\nrisk testing content"})

    idx1 = _build_index(kb, cache_dir)
    cache_files = list(cache_dir.glob("*.json"))
    assert len(cache_files) == 1
    payload = json.loads(cache_files[0].read_text(encoding="utf-8"))
    payload["format_version"] = 1  # simulate a pre-upgrade, sentence-transformers-era cache
    cache_files[0].write_text(json.dumps(payload), encoding="utf-8")

    with patch("local_index._FastEmbedEmbeddings", return_value=_FakeEmbeddings()) as mock_cls:
        idx2 = LocalIndex(kb_dir=kb, cache_dir=cache_dir)
        idx2._ensure_built()
        assert mock_cls.called, "A format-1 cache must not be trusted after the format-2 bump"

    assert idx2.kb_version == idx1.kb_version
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `python -m pytest tests/test_local_index.py::test_cache_format_version_is_2 tests/test_local_index.py::test_cache_written_under_old_format_version_is_treated_as_miss -v`
Expected: FAIL — `test_cache_format_version_is_2` fails because `_CACHE_FORMAT_VERSION` is still `1`; `test_cache_written_under_old_format_version_is_treated_as_miss` fails with `AttributeError` because `local_index._FastEmbedEmbeddings` doesn't exist yet.

- [ ] **Step 3: Implement the adapter class and wire it in**

In `src/local_index.py`, replace the import at line 30:

```python
from langchain_community.embeddings import HuggingFaceEmbeddings
```

with:

```python
from fastembed import TextEmbedding
```

Bump the format version at line 35:

```python
_CACHE_FORMAT_VERSION = 2  # bumped for the fastembed backend switch (was 1: sentence-transformers)
```

Add the adapter class right after the `Chunk` dataclass (after line 73, before `_simple_chunk_splits`):

```python
class _FastEmbedEmbeddings:
    """Adapter matching HuggingFaceEmbeddings' two methods LocalIndex calls,
    backed by fastembed's ONNX Runtime instead of sentence-transformers/torch —
    see docs/superpowers/specs/2026-09-17-mcp-embedding-backend-simplification-design.md.
    Cuts cold-start import time roughly 3x (no torch), which is what actually
    matters for the MCP server's uvx-launched cold start."""

    def __init__(self, model_name: str):
        self._model = TextEmbedding(model_name=model_name)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [v.tolist() for v in self._model.embed(texts)]

    def embed_query(self, text: str) -> list[float]:
        return next(iter(self._model.embed([text]))).tolist()
```

Update `_embedding_model()` (currently lines 175-178):

```python
def _embedding_model(self):
    if self._embedder is None:
        self._embedder = _FastEmbedEmbeddings(EMBEDDING_MODEL)
    return self._embedder
```

- [ ] **Step 4: Update the existing test file's mock targets**

In `tests/test_local_index.py`, replace every occurrence of `local_index.HuggingFaceEmbeddings` with `local_index._FastEmbedEmbeddings` (6 occurrences: lines 59, 164, 169, 189, 219, 241). The fake object (`_FakeEmbeddings`, lines 30-44) already matches the adapter's two-method interface and needs no change.

Also update the module docstring (lines 4-9) to stop naming the old backend specifically:

```python
"""
Tests for src/local_index.py — the MCP server's local, keyless KB index.

Uses a small synthetic knowledge_base/ (tmp_path) and a deterministic fake
embedder (bag-of-words over a fixed vocabulary) instead of the real fastembed
model, so these tests are fast and don't depend on model-download
availability. The real model is exercised by evals/local_index_parity.py
against the actual knowledge_base/.

Covers: chunk counts/boundaries, category filtering, disk-cache round-trip,
cache invalidation on KB edits, corrupted-cache recovery, and k clamping.
"""
```

- [ ] **Step 5: Run the full test file to verify everything passes**

Run: `python -m pytest tests/test_local_index.py -v`
Expected: PASS — all tests including the 2 new ones.

- [ ] **Step 6: Run the real retrieval-quality gate**

Run: `python -m evals.local_index_parity`
Expected: PASS, `local_index_recall@k` and `local_index_precision_mrr` both `pass` against their floors (0.80/0.70) — this exercises the real `fastembed` package against the real `knowledge_base/` corpus and `rag_golden.jsonl`, not a mock. (`fastembed` must be installed locally to run this — see Task 2 for adding it to `requirements-dev.txt`; install it ad hoc first with `pip install fastembed` if running this step before Task 2.)

- [ ] **Step 7: Update `mcp_server.py`'s warmup comment**

In `src/mcp_server.py`'s `main()` (around lines 508-536), replace the torch/MKL-specific language in the comment block. Change:

```python
        # Force the FIRST real embedding-model inference (constructing
        # HuggingFaceEmbeddings + one embed_query() call — native torch/MKL
        # thread and DLL init) to happen here, on the main thread, before
        # mcp.run() starts stdio_server()'s concurrent stdin-reader task.
        # Deferring this to the first retrieve_qa_knowledge call (which
        # FastMCP dispatches to an anyio worker thread) deadlocks on Windows:
        # that worker thread's torch/MKL native thread creation races the
        # stdin-reader thread's blocking ReadFile() on the piped stdin for
        # the process loader lock, and neither ever proceeds. Confirmed via
        # a real `uvx qai-consultant-mcp` stdio subprocess (v3.0/v3.0.1 E2E
        # test) hanging indefinitely on the second tool call.
```

to:

```python
        # Force the FIRST real embedding-model inference (constructing the
        # embedding backend + one embed_query() call — native runtime thread
        # and DLL init) to happen here, on the main thread, before mcp.run()
        # starts stdio_server()'s concurrent stdin-reader task. Deferring this
        # to the first retrieve_qa_knowledge call (which FastMCP dispatches to
        # an anyio worker thread) deadlocks on Windows: that worker thread's
        # native thread creation races the stdin-reader thread's blocking
        # ReadFile() on the piped stdin for the process loader lock, and
        # neither ever proceeds. Originally found with torch/MKL (v3.0/v3.0.1
        # E2E test, hanging indefinitely on the second tool call); the hazard
        # is about ANY native runtime's first init, not torch specifically —
        # re-verified against fastembed's onnxruntime backend via
        # scripts/verify_mcp_stdio_no_deadlock.py (Task 4 of the 2026-09-17
        # embedding-backend-simplification plan) before this backend switch shipped.
```

- [ ] **Step 8: Commit**

```bash
git add src/local_index.py tests/test_local_index.py src/mcp_server.py
git commit -m "$(cat <<'EOF'
refactor: swap MCP local index embedding backend to fastembed

Replaces sentence-transformers/torch (via langchain_community's
HuggingFaceEmbeddings) with fastembed (ONNX Runtime, no torch) in
local_index.py. Validated via evals/local_index_parity.py against the
real golden dataset: identical recall@5/MRR (0.91/0.86) to the old
backend, ~3x faster cold import — the actual bottleneck behind the
uvx/Claude-Desktop cold-start timeout risk documented in CLAUDE.md.

Cache format version bumped 1->2 so existing on-disk caches (built
with sentence-transformers vectors) are treated as absent rather than
misread, per LocalIndex's existing miss/rebuild fallback.

See docs/superpowers/specs/2026-09-17-mcp-embedding-backend-simplification-design.md

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_013xJEqRuCdtixjGy8hpg3jB
EOF
)"
```

---

### Task 2: Shrink `pyproject.toml`'s dependencies and add fastembed to dev tooling

**Files:**
- Modify: `pyproject.toml:44-144` (`dependencies` array)
- Modify: `requirements-dev.txt`

**Interfaces:**
- Consumes: Task 1's `local_index.py` (must no longer import `langchain_community`/`torch`/`sentence_transformers` for this task's dependency removal to be correct).
- Produces: a `pyproject.toml` `dependencies` array that still passes `tests/test_packaging.py::test_all_dependencies_are_exact_pinned` and the wheel-build packaging test.

- [ ] **Step 1: Confirm no other MCP-whitelisted module needs the packages being removed**

Run: `grep -rn "langchain\|torch\|sentence_transformers\|sklearn\|scipy" src/mcp_server.py src/dialogue.py src/effort_core.py src/telemetry.py src/prompts.py src/kb_config.py src/logger.py src/version.py src/review_core.py src/results_core.py src/maturity_core.py`
Expected: no matches (or only comment references, which Task 1 Step 7 already updated) — confirms `torch`/`sentence-transformers`/`langchain-community` are safe to remove from the MCP package's dependencies.

- [ ] **Step 2: Edit `pyproject.toml`'s direct dependency lines**

In the `dependencies` array (`pyproject.toml:44-144`), remove these lines:

```toml
    "langchain-classic==1.0.8",
    "langchain-community==0.4.2",
    "langchain-core==1.6.1",
    "langchain-protocol==0.0.19",
    "langchain-text-splitters==1.1.2",
    "langsmith==0.11.2",
```

```toml
    "scikit-learn==1.7.2 ; python_full_version < '3.11'",
    "scikit-learn==1.9.0 ; python_full_version >= '3.11'",
    "scipy==1.15.3 ; python_full_version < '3.11'",
    "scipy==1.17.1 ; python_full_version == '3.11.*'",
    "scipy==1.18.1 ; python_full_version >= '3.12'",
    "sentence-transformers==2.7.0",
```

```toml
    "torch==2.13.0",
```

and (only if nothing else needs them after the compile in Step 3 — confirm in Step 3, don't hand-remove speculatively): `joblib`, `threadpoolctl`, `networkx` (both markers), `sympy`, `mpmath`.

Add, alphabetically positioned:

```toml
    "fastembed==0.8.0",
```

- [ ] **Step 3: Regenerate the full transitive lock**

Run: `uv pip compile pyproject.toml --universal --python-version 3.10`
Replace the entire `dependencies = [...]` array with the command's output, keeping the existing comment block above it (lines 24-43) unchanged. Do not add `--extra-index-url` (see Global Constraints).

- [ ] **Step 4: Add fastembed to dev tooling**

In `requirements-dev.txt`, add a new line after the existing MCP-server comment block (after line 18, before the Playwright section):

```
# fastembed (v3.5.3) -- the MCP server's local_index.py embedding backend;
# needed to run tests/test_local_index.py's real-package assertions and
# evals/local_index_parity.py locally/in CI against the real backend, not a
# mock. Pinned to match pyproject.toml's exact-pinned MCP package dependency.
fastembed==0.8.0
```

- [ ] **Step 5: Verify packaging tests still pass**

Run: `python -m pytest tests/test_packaging.py -v`
Expected: PASS, including `test_all_dependencies_are_exact_pinned` and the wheel-build test (confirms the wheel still builds cleanly with the new dependency set and ships no PDFs/HTML).

- [ ] **Step 6: Re-run the full local_index test suite and eval gate with the trimmed dependency set installed**

Run: `pip install -r requirements-dev.txt && python -m pytest tests/test_local_index.py -v && python -m evals.local_index_parity`
Expected: all PASS — confirms nothing else in the dev/CI environment was silently relying on `sentence-transformers`/`torch`/`langchain-community` being importable via this path.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml requirements-dev.txt
git commit -m "$(cat <<'EOF'
build: drop torch/sentence-transformers/langchain-community from MCP package deps

Removes the packages only reachable through the sentence-transformers/
torch embedding backend replaced in the previous commit, and their own
transitive chains (scikit-learn, scipy, networkx, sympy, mpmath,
langchain-core/-classic/-protocol/-text-splitters, langsmith). Adds
fastembed. Regenerated via the documented `uv pip compile` command.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_013xJEqRuCdtixjGy8hpg3jB
EOF
)"
```

---

### Task 3: Delete the dependency-drift-canary workflow and its support code

**Files:**
- Delete: `.github/workflows/dependency-drift-check.yml`
- Delete: `scripts/check_dependency_drift.py`
- Delete: `tests/test_check_dependency_drift.py`

**Interfaces:**
- Consumes: nothing from Tasks 1-2 (independent deletion, sequenced here per the spec's narrative — the shrunk dependency list is *why* this is being deleted now, not a technical dependency).
- Produces: nothing consumed by later tasks.

- [ ] **Step 1: Confirm nothing else references the files being deleted**

Run: `grep -rln "check_dependency_drift\|dependency-drift-check" .github/ scripts/ tests/ docs/ CLAUDE.md README.md 2>/dev/null`
Expected: only the three files themselves and `CLAUDE.md` (its CI section and Gotchas — updated in Task 4).

- [ ] **Step 2: Delete the workflow and its support code**

```bash
git rm .github/workflows/dependency-drift-check.yml scripts/check_dependency_drift.py tests/test_check_dependency_drift.py
```

- [ ] **Step 3: Run the full test suite to confirm nothing else depended on the deleted test file's fixtures**

Run: `python -m pytest tests/ -v --ignore=tests/test_check_dependency_drift.py`
Expected: PASS (the `--ignore` flag is redundant after `git rm` but harmless — confirms no collection error from a dangling reference elsewhere).

- [ ] **Step 4: Commit**

```bash
git commit -m "$(cat <<'EOF'
chore: delete dependency-drift-canary workflow

The weekly drift-canary existed to manage a ~99-entry fully-pinned
transitive lock; with torch/sentence-transformers/langchain-community
removed (previous commit), the resolved dependency list is roughly a
third of that size. Re-running the documented `uv pip compile` command
by hand before each MCP release is sufficient at this smaller scale,
and removes the auto-close-every-Dependabot-PR side effect that was
closing genuine CVE-fix PRs along with routine drift.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_013xJEqRuCdtixjGy8hpg3jB
EOF
)"
```

---

### Task 4: Real stdio E2E verification, version bump, and release docs

**Files:**
- Create: `scripts/verify_mcp_stdio_no_deadlock.py`
- Modify: `src/version.py`
- Modify: `pyproject.toml:7` (version)
- Modify: `CHANGELOG.md`
- Modify: `README.md`
- Modify: `README_MCP.md`
- Modify: `CLAUDE.md`

**Interfaces:**
- Consumes: Tasks 1-3's completed, committed changes (this task validates and documents the finished state).

- [ ] **Step 1: Write the real subprocess-with-piped-stdio verification script**

```python
"""Manual pre-release check: does the MCP server's first real tool call
deadlock on Windows? (See mcp_server.py's main() comment and
docs/superpowers/specs/2026-09-17-mcp-embedding-backend-simplification-design.md,
section 5.) Launches the real server as a subprocess over piped stdio —
exactly how Claude Desktop/Claude Code launch it — and calls a real tool.
A hang past the timeouts below means the warmup-before-mcp.run() fix is
broken for the current embedding backend.

Run manually before every MCP release:
    python scripts/verify_mcp_stdio_no_deadlock.py
"""
import asyncio
import sys
import time
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SERVER = _REPO_ROOT / "src" / "mcp_server.py"


async def main() -> int:
    params = StdioServerParameters(command=sys.executable, args=[str(_SERVER)])
    start = time.monotonic()

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await asyncio.wait_for(session.initialize(), timeout=90)
            print(f"initialize() returned in {time.monotonic() - start:.1f}s")

            result = await asyncio.wait_for(
                session.call_tool("retrieve_qa_knowledge", {"query": "risk-based testing", "k": 3}),
                timeout=60,
            )
            total = time.monotonic() - start
            if result.isError:
                print(f"FAIL: tool call returned isError=True after {total:.1f}s: {result}")
                return 1
            print(f"first retrieve_qa_knowledge call succeeded in {total:.1f}s total")

    print("PASS: no deadlock on first real tool call")
    return 0


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
    except asyncio.TimeoutError:
        print("FAIL: timed out waiting for a response — likely the loader-lock deadlock")
        exit_code = 1
    raise SystemExit(exit_code)
```

- [ ] **Step 2: Run it against the fastembed-backed server**

Run: `python scripts/verify_mcp_stdio_no_deadlock.py`
Expected: `PASS: no deadlock on first real tool call`, with both `initialize()` and the tool call completing well under their timeouts (the pre-design spike measured ~5s cold import for fastembed vs. ~16-25s for the old backend, so `initialize()` should return noticeably faster than before).

- [ ] **Step 3: Bump the version**

In `src/version.py`, update `__version__` to `"3.5.3"` and `__release_date__` to today's date. In `pyproject.toml:7`, update `version = "3.5.3"`.

- [ ] **Step 4: Add the CHANGELOG entry**

At the top of `CHANGELOG.md`, add:

```markdown
## [3.5.3] - <today's date>

### Changed
- `qai-consultant-mcp`'s local knowledge-base index (`local_index.py`) now uses `fastembed` (ONNX Runtime) instead of `sentence-transformers`/`torch` for embeddings. This removes the single largest contributor to the package's cold-start time — the root cause behind the v3.1.5/v3.3.1/v3.4.4/v3.5.1 dependency-pinning incidents, all of which were fixed by adding more pinning rigor around this cost rather than addressing it directly. Retrieval quality is unchanged (`evals/local_index_parity.py`: recall@5=0.91, MRR=0.86, identical to the previous backend); cold import time is roughly 3x faster.
- `pyproject.toml`'s dependency list shrank from ~99 to a much smaller resolved set with `torch`, `sentence-transformers`, `langchain-community`, and their transitive chains (`scikit-learn`, `scipy`, `networkx`, `sympy`, `mpmath`, `langchain-core`/`-classic`/`-protocol`/`-text-splitters`, `langsmith`) removed.
- Removed the weekly dependency-drift-canary workflow (`.github/workflows/dependency-drift-check.yml`) — no longer justified at the smaller dependency scale; re-run `uv pip compile` by hand before each MCP release instead.

### Notes
- The Streamlit app / CLI (`agent.py`, `ingest.py`, `requirements.txt`) are unaffected — they keep using `sentence-transformers`/`torch` via the Pinecone-backed RAG path, a separate system with no `uvx` cold-start constraint.
```

- [ ] **Step 5: Update README.md**

In `README.md:21`, change:

```markdown
![Version](https://img.shields.io/badge/version-3.5.2-green.svg)
```

to:

```markdown
![Version](https://img.shields.io/badge/version-3.5.3-green.svg)
```

Add a new roadmap bullet after the existing `v3.5.2` entry (around line 286), matching the existing bullet style:

```markdown
- **v3.5.3** ✅ `qai-consultant-mcp`'s local index switched from `sentence-transformers`/`torch` to `fastembed` (ONNX Runtime) for embeddings — same retrieval quality (`evals/local_index_parity.py`: recall@5=0.91, MRR=0.86, unchanged), ~3x faster cold import, and a much smaller dependency list. Removed the weekly dependency-drift-canary workflow, no longer justified at the smaller scale. See `CHANGELOG.md` for details.
```

The tools table itself is unchanged (no tool surface change in this release).

- [ ] **Step 6: Update README_MCP.md**

In `README_MCP.md:44`, change:

```markdown
First run downloads the embedding model (`sentence-transformers/all-MiniLM-L6-v2`, CPU-only) and builds a local index — this takes a minute or two the first time, then it's cached.
```

to:

```markdown
First run downloads the embedding model (`sentence-transformers/all-MiniLM-L6-v2`, served via `fastembed`'s ONNX Runtime) and builds a local index — this now takes a few seconds to a minute the first time (previously a minute or two, before the v3.5.3 backend switch), then it's cached.
```

No tools table change (tool surface unchanged).

- [ ] **Step 7: Update CLAUDE.md**

Locate each anchor with `grep -n "<anchor text>" CLAUDE.md` first, since line numbers shift as earlier steps in this plan and prior sessions edit the file.

1. **Architecture table, `local_index.py` row** (anchor: `` | `local_index.py` | (v3.0) `LocalIndex` ``). Append a sentence to the end of the existing cell (before the closing ` |`): `` As of v3.5.3, embeddings come from `fastembed` (ONNX Runtime) instead of `sentence-transformers`/`torch` via `HuggingFaceEmbeddings` — see the embedding-backend-simplification spec. ``

2. **Gotcha: "MCP server: embedding-model warmup must happen before `mcp.run()`."** (anchor: that exact sentence, bolded, near the start of the Gotchas section). Append one sentence to the end of that gotcha's paragraph (do not remove or alter the existing torch/MKL incident narrative — it remains accurate history for why the pattern exists): `` Re-verified against the fastembed/onnxruntime backend on <today's date> via a real subprocess-with-piped-stdio check (`scripts/verify_mcp_stdio_no_deadlock.py`) before the v3.5.3 backend switch shipped — no regression: the hazard is about any native runtime's first init racing the stdin-reader thread, not torch specifically. ``

3. **CI section paragraph describing `dependency-drift-check.yml`** (anchor: `` Another separate workflow, `.github/workflows/dependency-drift-check.yml`, runs weekly ``). Delete this entire paragraph and replace it with: `` **Removed in v3.5.3:** the weekly Dependency Drift Canary workflow (`.github/workflows/dependency-drift-check.yml`) existed to manage a ~99-entry fully-pinned transitive lock; once the fastembed backend switch (v3.5.3) removed torch/sentence-transformers/langchain-community and shrank that list to roughly a third of its former size, re-running `uv pip compile` by hand before each MCP release became sufficient, and the workflow (plus its auto-close-every-Dependabot-PR side effect) was deleted. Historical design spec: `docs/superpowers/specs/2026-09-03-dependency-drift-canary-design.md`. ``

4. **Gotcha: "A single-package Dependabot security-update PR can silently corrupt..."** (anchor: that sentence, bolded). Append to the end of that gotcha's paragraph: `` **Superseded in v3.5.3:** the drift-canary workflow this gotcha's auto-close mitigation relied on was deleted once the dependency list shrank (see the CI section above) — Dependabot PRs against `pyproject.toml` are reviewed and merged manually like any other dependency PR now; a human re-runs the full `uv pip compile` regeneration if one is merged. ``

5. **Roadmap section**, immediately after the existing `v3.5.2` bullet. Add: `` - **v3.5.3** ✅ `qai-consultant-mcp`'s local index (`local_index.py`) switched from `sentence-transformers`/`torch` to `fastembed` (ONNX Runtime) for embeddings — the root cause behind the v3.1.5/v3.3.1/v3.4.4/v3.5.1 dependency-pinning incidents, all previously "fixed" by adding pinning rigor around this cost rather than addressing it. Validated via `evals/local_index_parity.py` against the real golden dataset before and after: identical recall@5/MRR (0.91/0.86), ~3x faster cold import. `pyproject.toml`'s dependency list shrank accordingly (torch/sentence-transformers/langchain-community and their transitive chains removed), and the now-oversized weekly dependency-drift-canary workflow was deleted. Design spec: `docs/superpowers/specs/2026-09-17-mcp-embedding-backend-simplification-design.md`. ``

- [ ] **Step 8: Run the full test suite and eval gate one more time**

Run: `python -m pytest tests/ -v && python -m evals.run --det`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add scripts/verify_mcp_stdio_no_deadlock.py src/version.py pyproject.toml CHANGELOG.md README.md README_MCP.md CLAUDE.md
git commit -m "$(cat <<'EOF'
release: v3.5.3 — fastembed backend, shrunk deps, drift-canary removed

Real subprocess-with-piped-stdio check confirms no deadlock on the
first tool call with the fastembed/onnxruntime backend
(scripts/verify_mcp_stdio_no_deadlock.py). Release Checklist docs
updated together per CLAUDE.md's own rule.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_013xJEqRuCdtixjGy8hpg3jB
EOF
)"
```

**Note:** actually publishing to PyPI (`twine upload`) and tagging the release are, per this project's own established convention (see CLAUDE.md's v3.0/v3.1.4/v3.5.0 roadmap entries), deliberately left for explicit user confirmation — not part of this task's automated steps.
