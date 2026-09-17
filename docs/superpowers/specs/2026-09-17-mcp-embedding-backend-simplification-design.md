# MCP Embedding Backend Simplification — Design Spec

## Context

A 4-angle over-engineering audit (2026-09-16, four independent subagent reviews of
module architecture, dependency/release engineering, CI/evals, and process/docs)
converged independently on the same root cause across three of its findings:

> The `qai-consultant-mcp` package's cold-start time (`sentence-transformers` +
> `torch` import, ~15-25s depending on machine) sits uncomfortably close to Claude
> Desktop's ~60s `initialize` handshake timeout. Every dependency-pinning incident
> from v3.1.5 through v3.5.2 (unbounded `mcp` floor, transitive `scipy` surprise
> download, `torch` CPU-index scoping breaking real consumers) was "fixed" by
> adding *more* pinning rigor around this fact, never by addressing the fact
> itself. The current `pyproject.toml` fully exact-pins the entire resolved
> transitive dependency tree (~99 entries) specifically to prevent any of those
> ~99 packages from updating unnoticed between two `uvx` launches and forcing a
> slow reinstall — itself made necessary largely by how much torch/sentence-
> transformers/scikit-learn pull in.

This spec addresses that root cause directly: swap the embedding backend used by
the MCP server's local retrieval index (`src/local_index.py`) from
`sentence-transformers`/`torch` (via `langchain_community`'s `HuggingFaceEmbeddings`)
to `fastembed` (ONNX Runtime-based, no torch).

**Validated, not assumed:** a pre-design spike ran the project's own existing
retrieval-quality gate (`evals/local_index_parity.py` — real chunked
`LocalIndex`, real `rag_golden.jsonl`, 23 cases) against both backends:

| Backend | recall@5 | MRR | Cold import time (this machine) |
|---|---|---|---|
| sentence-transformers (current) | 0.91 | 0.86 | 15.85s |
| fastembed (proposed) | 0.91 | 0.86 | 5.02s |

Identical retrieval quality (same 21/23 hits, same 2 misses), ~3x faster cold
import. An earlier ad-hoc 3-query/25-chunk comparison had shown per-vector cosine
similarity between the two backends varying from 0.77–1.0, raising a real concern
(there's a documented 2023 fastembed GitHub issue reporting much worse embedding
fidelity for this exact model) — but that concern did not survive contact with
the real golden dataset and real chunking. The full quality gate is what should be
trusted here, not the raw vector-similarity number.

## Scope

**In scope:**
- `src/local_index.py` — the embedding backend it constructs
- `pyproject.toml` — the MCP package's dependency list (direct + full transitive
  regeneration)
- `.github/workflows/dependency-drift-check.yml` — deleted (see Decisions below)
- `requirements-dev.txt` — add `fastembed` so CI/dev can run
  `evals/local_index_parity.py` and `tests/test_local_index.py` against the real
  backend
- `tests/test_local_index.py` — mock target updates
- `mcp_server.py` — comment/docstring updates only (the `warmup_embedder()`
  call site and its rationale change from "torch/MKL native init" to "onnxruntime
  native init"; the actual code path is unchanged)
- `CLAUDE.md`, `CHANGELOG.md`, `README.md`, `README_MCP.md`, `src/version.py` —
  per the existing Release Checklist

**Out of scope (deliberately untouched):**
- `src/agent.py`, `src/ingest.py`, `requirements.txt` — the Streamlit/CLI app's
  Pinecone-backed RAG path. It has no `uvx` cold-start constraint (Streamlit Cloud
  runs a persistent process) and stays on `sentence-transformers`/`torch` exactly
  as it is today. This is a genuinely separate system from the MCP server's local
  index — they already use different indices (Pinecone vs. in-memory cosine) built
  from the same `knowledge_base/*.md` source files.
- `evals/rag.py`'s own `_Index` class, which intentionally hardcodes
  `HuggingFaceEmbeddings` to test the doc-level, Pinecone-equivalent baseline
  (its own docstring: "Deliberately different from... too coarse for real
  retrieval" — measuring something else on purpose).

## Design

### 1. `local_index.py`: adapter class, not a rewrite

Replace the direct `HuggingFaceEmbeddings` construction with a small adapter that
exposes the same two methods `LocalIndex` already calls (`embed_documents`,
`embed_query`), so the rest of the class — chunking, the disk cache, the
`warmup_embedder()`/`_ensure_built()` split, `search()`, `list_sources()` — is
untouched:

```python
class _FastEmbedEmbeddings:
    """Adapter matching HuggingFaceEmbeddings' two methods LocalIndex calls,
    backed by fastembed's ONNX Runtime instead of sentence-transformers/torch —
    see docs/superpowers/specs/2026-09-17-mcp-embedding-backend-simplification-design.md."""

    def __init__(self, model_name: str):
        from fastembed import TextEmbedding
        self._model = TextEmbedding(model_name=model_name)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [v.tolist() for v in self._model.embed(texts)]

    def embed_query(self, text: str) -> list[float]:
        return next(iter(self._model.embed([text]))).tolist()
```

`_embedding_model()` constructs `_FastEmbedEmbeddings(EMBEDDING_MODEL)` instead of
`HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)`. `EMBEDDING_MODEL` itself
(`kb_config.py`'s `"sentence-transformers/all-MiniLM-L6-v2"`) does not change —
fastembed resolves that exact model string to its own ONNX conversion
(`qdrant/all-MiniLM-L6-v2-onnx` under the hood), confirmed during the spike.

### 2. Disk cache: version bump, not a migration

`_CACHE_FORMAT_VERSION` goes from `1` to `2`. Cache filenames already embed this
version (`index_v{version}_{kb_version}.json`), so an existing user's on-disk
cache — built with sentence-transformers vectors — is never read as if it were
fastembed output; it's simply treated as absent, and `_ensure_built()`'s existing
fallback path (already handles "missing" alongside "corrupted") rebuilds fresh.
No new migration code needed; this is exactly the mechanism the version field
already exists for.

### 3. `pyproject.toml`: direct dependency change + full regeneration

Remove from `dependencies`: `torch`, `sentence-transformers`, `langchain-community`
(confirmed via grep: no other module in the MCP package's `py-modules` whitelist —
`mcp_server`, `dialogue`, `effort_core`, `telemetry`, `prompts`, `kb_config`,
`logger`, `version`, `review_core`, `results_core`, `maturity_core` — imports
`langchain`/`torch`/`sentence_transformers`/`sklearn`/`scipy` in any form).
Add: `fastembed`.

Regenerate the full transitive lock with the already-documented command
(`uv pip compile pyproject.toml --universal --python-version 3.10`, no
`--extra-index-url` — see the existing comment block above `dependencies`).
Removing `torch` also removes its own transitive chain (`networkx`, `sympy`,
`mpmath`); removing `sentence-transformers` also removes `scikit-learn`, `scipy`,
`joblib`, `threadpoolctl`; removing `langchain-community` also removes
`langchain-classic`, `langchain-core`, `langchain-protocol`,
`langchain-text-splitters`, `langsmith`, and whatever else was only reachable
through it. The exact resulting count isn't hand-predicted here — the compile
command is authoritative — but every one of those packages' *only* reason for
being in this file is the backend being removed.

**Exact-pinning is kept**, on the new (much smaller) resolved list. This isn't a
reversal of the pinning discipline that fixed real past incidents (v3.1.5,
v3.3.1, v3.4.4) — it's the same discipline applied to a much smaller surface,
which is what actually shrinks the maintenance burden the over-engineering audit
flagged, without reopening the "no version of X exists" failure mode.

### 4. Decision: delete `dependency-drift-check.yml`

With the dependency list shrunk by roughly two-thirds, the weekly canary
workflow's original justification (a large, hand-tracked lock rotting silently)
is much weaker, and its side effects (auto-closing every Dependabot PR touching
`pyproject.toml`, including genuine CVE fixes) were flagged by the audit as
themselves a cost. **Decision (user-confirmed): delete the workflow and its
`scripts/check_dependency_drift.py` + `tests/test_check_dependency_drift.py`
support code entirely.** Re-running the documented `uv pip compile` command by
hand before each MCP release (already a step implied by the comment above
`dependencies`) is sufficient at this smaller scale. Ordinary Dependabot PRs
against `pyproject.toml` are no longer auto-closed — a human reviews them,
same as any other dependency PR, and re-runs the full-tree compile if one is
merged (a note to this effect belongs in the Release Checklist).

### 5. Windows deadlock protection: pattern preserved, cause re-verified

The existing `main()` warmup-before-`mcp.run()` pattern in `mcp_server.py` is
**not specific to torch** — the deadlock it prevents is about *any* native
library's first initialization racing the stdio-reader thread's blocking
`ReadFile()` on Windows (confirmed by rereading the current code comment: "native
torch/MKL thread and DLL init"). `onnxruntime` (fastembed's backend) is also a
compiled native library, so the same race is structurally possible. The code
path doesn't change — `index.warmup_embedder()` still runs on the main thread
before `mcp.run()` — but the comments describing *why* need updating from
torch/MKL-specific language to the general "any native runtime's first init"
framing, and this needs the same category of verification the original fix got:
**a real subprocess-with-piped-stdio E2E check** (this was a one-off manual
verification in v3.0.2/v3.1.6 per `CLAUDE.md`, never committed as an automated
test — confirmed by searching `tests/` for `stdio_client`, found only in
`CLAUDE.md` and old plan docs). The implementation plan includes re-running that
same style of check against the fastembed-backed server before shipping, since a
different native library could in principle behave differently even though the
threading hazard is the same shape.

### 6. Testing

- `tests/test_local_index.py` currently mocks `local_index.HuggingFaceEmbeddings`
  directly (6 call sites: cache hit/miss, KB-edit invalidation, embedding-model
  mismatch invalidation, etc.). These become `patch("local_index._FastEmbedEmbeddings", ...)`
  — same fake object shape (`embed_documents`/`embed_query`), same assertions.
- A new test asserts `_CACHE_FORMAT_VERSION == 2` and that a cache file written
  under format version 1 is treated as a miss (rebuild triggered), covering the
  upgrade path for existing installs.
- `evals/local_index_parity.py` needs no code change — it already exercises the
  real `LocalIndex` end-to-end. Its pass/fail against `thresholds.py`'s existing
  `LOCAL_INDEX_RECALL_AT_K_MIN`/`LOCAL_INDEX_MRR_MIN` floors (0.8/0.7) is the
  permanent regression gate for retrieval quality — already proven to pass at
  0.91/0.86 in the spike, and it runs in the `evals-det` CI job on every PR.
- `requirements-dev.txt` gets `fastembed` added (pinned to the version verified
  during implementation) so both the above run for real in CI, not skipped.

## Error Handling

No new error-handling design is needed: `_ensure_built()`'s existing
try/except-around-cache-load (any exception → treat as miss, rebuild) already
covers a corrupted or wrong-version cache, and `LocalIndex.__init__`/`search()`'s
existing exception handling in `mcp_server.py`'s callers is backend-agnostic —
neither cares which library raised. `fastembed.TextEmbedding`'s construction
failure (missing model files, no network on first download) surfaces the same
way `HuggingFaceEmbeddings`'s did: as an exception `_ensure_built()`/callers
already handle as "index unavailable."

## Migration for existing installs

Fully automatic. An existing `qai-consultant-mcp` user upgrading gets: a new
`fastembed` dependency resolved by `uvx`/`pip` on next launch (one-time, like any
version bump), and their old on-disk index cache silently ignored in favor of a
fresh fastembed-backed rebuild on first real tool call (via the cache version
bump in point 2) — no user action, no data loss (the cache is a pure
performance optimization, never a source of truth).
