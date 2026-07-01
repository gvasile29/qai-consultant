"""Classical RAG metrics over a fully-local index — no Pinecone, no API keys.

Builds an in-memory index from ``knowledge_base/*.md`` using the SAME embedding model
the app ships (``all-MiniLM-L6-v2``), then measures five metrics:

  - Context Recall@k       (judge-free)  — does retrieval surface a labelled source doc?
  - Context Precision (MRR) (judge-free)  — how highly is the labelled source ranked?
  - Source Attribution      (regex)       — do the answer's [Source N] cites point at real chunks?
  - Faithfulness            (Ollama judge) — are the answer's claims grounded in the context?
  - Answer Relevance        (Ollama judge) — does the answer address the query?

Retrieval is keyless and deterministic (local embeddings). The judged metrics
(faithfulness, answer relevance, source attribution — the last needs a generated
answer) SKIP, never fail, when Ollama is unreachable. The whole suite SKIPs if the
embedding stack is unavailable — so it stays CI-safe.

    python -m evals.rag

Note: a local cosine index over the markdown KB tests embedding/retrieval *quality*,
not the production Pinecone wiring. For "local Pinecone" instead, run the Pinecone
Local emulator and ingest the KB; the metrics below are independent of that choice.
"""

from __future__ import annotations

import functools
import heapq
import json
import math
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from . import ollama
from . import thresholds as T

_DIR = Path(__file__).resolve().parent
_KB = _DIR.parent / "knowledge_base"
_SRC = _DIR.parent / "src"
_EMBEDDING_MODEL_DEFAULT = "sentence-transformers/all-MiniLM-L6-v2"  # vendored fallback
_DOC_CHARS = 4000   # per-file text embedded; enough to characterise a topic doc


def _embedding_model() -> str:
    """The app's embedding model. Imported from src/agent.py so the eval can never
    drift from what ingest.py used; falls back to the vendored default when src (with
    its heavy pinecone/mistral/openai imports) is not installed in the eval env."""
    try:
        if str(_SRC) not in sys.path:
            sys.path.insert(0, str(_SRC))
        from agent import EMBEDDING_MODEL  # noqa: PLC0415
        return EMBEDDING_MODEL
    except Exception:  # noqa: BLE001 — src not importable here → use the vendored default
        return _EMBEDDING_MODEL_DEFAULT
_SRC_CHARS = 1500   # per-source text shown to the model AND the faithfulness judge
_ANS_CHARS = 3000   # answer text shown to the judges

# Canonical (name, threshold) wiring — single source for live and skipped Metrics.
_METRICS = [
    ("context_recall@k", T.RECALL_AT_K_MIN),
    ("context_precision_mrr", T.MRR_MIN),
    ("faithfulness", T.FAITHFULNESS_MIN),
    ("answer_relevance", T.ANSWER_RELEVANCE_MIN),
    ("source_attribution", T.SOURCE_ATTRIBUTION_MIN),
]


@dataclass(frozen=True)
class Metric:
    name: str
    value: float | None      # None = skipped
    threshold: float
    note: str = ""

    @property
    def skipped(self) -> bool:
        return self.value is None

    @property
    def passed(self) -> bool:
        return self.skipped or self.value >= self.threshold


def _skip_all(note: str) -> list[Metric]:
    return [Metric(n, None, t, note=note) for n, t in _METRICS]


def _judged_skip(note: str) -> list[Metric]:
    return [Metric(n, None, t, note=note) for n, t in _METRICS[2:]]


# ── Local index (app's embedding model, cosine, no Pinecone) ─────────────────────

def _kb_docs() -> list[tuple[str, str]]:
    """(relative-path, text) for every markdown file in the knowledge base. The path is
    relative to the KB root (not just p.name) so same-named files in different
    subdirectories stay distinct."""
    return [(str(p.relative_to(_KB)), p.read_text(encoding="utf-8")[:_DOC_CHARS])
            for p in sorted(_KB.rglob("*.md"))]


class _Index:
    """Lazy in-memory index. ``__init__`` may raise if the embedding stack or model
    weights are unavailable; callers treat any failure as SKIP."""

    def __init__(self) -> None:
        from langchain_huggingface import HuggingFaceEmbeddings  # noqa: PLC0415
        self._emb = HuggingFaceEmbeddings(model_name=_embedding_model())
        self._docs = _kb_docs()
        self._vecs = self._emb.embed_documents([t for _, t in self._docs])
        self._norms = [math.sqrt(sum(x * x for x in v)) for v in self._vecs]  # precomputed once
        self._qcache: dict[str, list[float]] = {}

    def _qvec(self, query: str) -> list[float]:
        if query not in self._qcache:                       # embed each query at most once
            self._qcache[query] = self._emb.embed_query(query)
        return self._qcache[query]

    def _rank(self, query: str, k: int) -> list[int]:
        qv = self._qvec(query)
        qn = math.sqrt(sum(x * x for x in qv)) or 1.0        # query norm computed once
        def cos(i: int) -> float:
            nb = self._norms[i]
            return sum(a * b for a, b in zip(qv, self._vecs[i])) / (qn * nb) if nb else 0.0
        return heapq.nlargest(k, range(len(self._docs)), key=cos)  # O(N log k), only top-k

    def retrieve(self, query: str, k: int) -> list[str]:
        """Top-k filenames by cosine similarity."""
        return [self._docs[i][0] for i in self._rank(query, k)]

    def chunks(self, query: str, k: int) -> list[str]:
        """Top-k document texts, in rank order."""
        return [self._docs[i][1] for i in self._rank(query, k)]


@functools.lru_cache(maxsize=1)
def _golden() -> list[dict]:
    """Parse rag_golden.jsonl once; skip blank and malformed lines rather than crash."""
    cases = []
    for line in (_DIR / "rag_golden.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and "query" in obj and "expects" in obj:
            if isinstance(obj["expects"], str):   # tolerate a bare string; a str would
                obj["expects"] = [obj["expects"]]  # otherwise iterate as chars and inflate recall
            if isinstance(obj["expects"], list):
                cases.append(obj)
    return cases


# ── Metrics 1 & 2: Context Recall@k + Precision (MRR), judge-free ────────────────

def retrieval_metrics(index: _Index) -> list[Metric]:
    """Recall@k (does a labelled source appear in top-k) and MRR (how highly the first
    labelled source ranks), in one retrieval pass per query. ``expects`` is a list so
    a query legitimately served by more than one doc is not under-counted."""
    cases = _golden()
    if not cases:
        return [Metric(n, None, t, note="SKIP (no golden cases)") for n, t in _METRICS[:2]]
    hits, rrs = 0, []
    for c in cases:
        files = index.retrieve(c["query"], T.RAG_K)
        rank = next((i + 1 for i, f in enumerate(files) if any(e in f for e in c["expects"])), 0)
        hits += 1 if rank else 0
        rrs.append(1.0 / rank if rank else 0.0)
    n = len(cases)
    return [
        Metric("context_recall@k", hits / n, T.RECALL_AT_K_MIN,
               note=f"{hits}/{n} golden queries retrieved a labelled source"),
        Metric("context_precision_mrr", sum(rrs) / n, T.MRR_MIN,
               note=f"mean reciprocal rank of the labelled source over {n} queries"),
    ]


# ── Metrics 3-5: Faithfulness + Answer Relevance + Source Attribution ────────────

_QA_SYS = (
    "You are a senior QA architect. Answer the query using ONLY the numbered SOURCES. "
    "After each recommendation, cite the supporting source inline as [Source N]."
)
_FAITH_SYS = (
    "Grade FAITHFULNESS: the fraction of the ANSWER's factual claims that are supported "
    "by the CONTEXT. Return JSON {\"score\": <0..1>, \"unsupported\": [\"...\"]}."
)
_RELEVANCE_SYS = (
    "Grade ANSWER RELEVANCE: does the ANSWER directly address the QUERY (not generic "
    'filler)? Return JSON {"score": <0..1>}.'
)
_CITE = re.compile(r"\[\s*Source\s*(\d+)\s*\]", re.IGNORECASE)


def _score(verdict: dict) -> float:
    """Coerce a judge 'score' to a clamped [0,1] float. Non-numeric, boolean, and
    non-finite (NaN/inf) values are invalid → 0.0, never a silent perfect 1.0."""
    v = verdict.get("score", 0.0)
    if isinstance(v, bool):          # bool is an int subclass; a boolean score is malformed
        return 0.0
    try:
        f = float(v)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(f):         # NaN/inf would otherwise clamp to 1.0
        return 0.0
    return max(0.0, min(1.0, f))


def _attr_counts(answer: str, k: int) -> tuple[int, int]:
    """(valid, total) [Source N] citations in the answer; valid = 1 <= N <= k."""
    nums = [int(n) for n in _CITE.findall(answer)]
    return sum(1 for n in nums if 1 <= n <= k), len(nums)


def _grade_case(index: _Index, case: dict) -> tuple[float, float, int, int]:
    """Generate one answer over numbered sources and grade it. The faithfulness judge
    sees the SAME sources string the model saw (no extra truncation), so claims are
    not spuriously marked unsupported. Raises on a failed generation/judge call."""
    chunks = index.chunks(case["query"], T.RAG_K)
    sources = "\n\n".join(f"[Source {i + 1}] {t[:_SRC_CHARS]}" for i, t in enumerate(chunks))
    answer = ollama.chat([
        {"role": "system", "content": _QA_SYS},
        {"role": "user", "content": f"SOURCES:\n{sources}\n\nQUERY:\n{case['query']}"},
    ], temperature=0.0, max_tokens=2500)  # temp 0 → deterministic answer, less run-to-run score variance;
    #                                       max_tokens headroom for reasoning models' think trace
    faith = _score(ollama.judge_json(_FAITH_SYS, f"CONTEXT:\n{sources}\n\nANSWER:\n{answer[:_ANS_CHARS]}"))
    rel = _score(ollama.judge_json(_RELEVANCE_SYS, f"QUERY:\n{case['query']}\n\nANSWER:\n{answer[:_ANS_CHARS]}"))
    valid, total = _attr_counts(answer, len(chunks))
    return faith, rel, valid, total


def judged_quality(index: _Index) -> list[Metric]:
    """Generate an answer per judged query over numbered sources, then score
    faithfulness + answer relevance (Ollama judge) and source attribution (regex).
    SKIPs all three if Ollama is unreachable. A case that errors is dropped (any
    exception isolated to that case); if fewer than a quorum survive, the metrics
    SKIP rather than report a mean over too-thin data."""
    if not ollama.reachable():
        return _judged_skip(f"SKIP (no Ollama at {ollama.BASE})")
    cases = [c for c in _golden() if c.get("judge")]
    if not cases:
        return _judged_skip("SKIP (no judged golden cases)")
    faith, rel = [], []
    valid_cites = total_cites = failed = 0
    for c in cases:
        try:
            f, r, v, t = _grade_case(index, c)
        except Exception:  # noqa: BLE001 — isolate ANY per-case failure (transport, JSON, key)
            failed += 1
            continue
        faith.append(f)
        rel.append(r)
        valid_cites += v
        total_cites += t
    n = len(faith)
    quorum = math.ceil(T.JUDGED_QUORUM_MIN * len(cases))
    if n < quorum:
        return _judged_skip(f"SKIP (only {n}/{len(cases)} cases graded, below quorum {quorum})")
    tail = f" ({failed} errored)" if failed else ""
    if total_cites:
        attr = Metric("source_attribution", valid_cites / total_cites, T.SOURCE_ATTRIBUTION_MIN,
                      note=f"{valid_cites}/{total_cites} citations valid over {n} answer(s){tail}")
    else:  # a model that never cites cannot demonstrate provenance — not a free pass
        attr = Metric("source_attribution", 0.0, T.SOURCE_ATTRIBUTION_MIN,
                      note=f"no [Source N] citations emitted over {n} answer(s){tail} — provenance unverifiable")
    return [
        Metric("faithfulness", sum(faith) / n, T.FAITHFULNESS_MIN, note=f"mean over {n} answer(s){tail}"),
        Metric("answer_relevance", sum(rel) / n, T.ANSWER_RELEVANCE_MIN, note=f"mean over {n} answer(s){tail}"),
        attr,
    ]


# ── Runner ───────────────────────────────────────────────────────────────────────

def run_all() -> list[Metric]:
    try:
        index = _Index()
    except Exception as exc:  # noqa: BLE001 — missing deps, uncached model, offline download, torch
        return _skip_all(f"SKIP (index unavailable: {type(exc).__name__})")
    return [*retrieval_metrics(index), *judged_quality(index)]


def format_table(metrics: list[Metric]) -> str:
    lines = ["", f"{'Metric':<22} Score   Floor   Result", f"{'-' * 22} ------  ------  ------"]
    for m in metrics:
        score = "  -  " if m.skipped else f"{m.value:.2f}"
        result = "SKIP" if m.skipped else ("pass" if m.passed else "FAIL")
        lines.append(f"{m.name:<22} {score:<7} {m.threshold:<7.2f} {result:<6} {m.note}")
    return "\n".join(lines)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # gate output contains non-ASCII; don't crash on cp1252/ascii
    metrics = run_all()
    print(format_table(metrics))
    ok = all(m.passed for m in metrics)
    print(f"\nRAG metrics: {'PASS' if ok else 'FAIL'} "
          f"({sum(1 for m in metrics if not m.passed)} below floor, "
          f"{sum(1 for m in metrics if m.skipped)} skipped)")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
