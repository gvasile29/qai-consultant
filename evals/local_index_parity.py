"""Retrieval-parity gate: the MCP server's served LocalIndex vs. rag_golden.jsonl.

``evals/rag.py`` measures a doc-level (4000-char) index — adequate for labelling
which topic a query belongs to, but coarser than what the app/MCP server actually
serve (1000/200-char chunks, same as ``ingest.py``). This module runs the same
Context Recall@k / MRR metrics against the REAL ``src/local_index.LocalIndex`` —
the class the MCP server's ``retrieve_qa_knowledge`` tool calls directly — so a
regression in chunking, category tagging, or the cache layer that only shows up
at chunk granularity doesn't slip past the doc-level eval.

Keyless but NOT dependency-free — needs the embedding stack (sentence-transformers/
torch, installed via requirements.txt), same caveat as evals/rag.py. SKIPs (not
fails) when that stack or its model weights are unavailable.

    python -m evals.local_index_parity
"""

from __future__ import annotations

import sys
from pathlib import Path

from . import ensure_src_on_path
from . import thresholds as T
from .rag import Metric, _golden  # shared golden dataset + result type

_METRICS = [
    ("local_index_recall@k", T.LOCAL_INDEX_RECALL_AT_K_MIN),
    ("local_index_precision_mrr", T.LOCAL_INDEX_MRR_MIN),
]


def _skip_all(note: str) -> list[Metric]:
    return [Metric(n, None, t, note=note) for n, t in _METRICS]


def run_all() -> list[Metric]:
    try:
        ensure_src_on_path()
        from local_index import LocalIndex  # noqa: PLC0415
        index = LocalIndex()
    except Exception as exc:  # noqa: BLE001 — missing deps, uncached model, offline download, torch
        return _skip_all(f"SKIP (index unavailable: {type(exc).__name__})")

    cases = _golden()
    if not cases:
        return [Metric(n, 0.0, t, note="FAIL: no golden cases (missing/empty/corrupt rag_golden.jsonl)")
                for n, t in _METRICS]

    hits, rrs = 0, []
    for c in cases:
        result = index.search(c["query"], k=T.RAG_K)
        sources = [chunk["source"] for chunk in result.get("chunks", [])]
        rank = next((i + 1 for i, s in enumerate(sources) if any(e in s for e in c["expects"])), 0)
        hits += 1 if rank else 0
        rrs.append(1.0 / rank if rank else 0.0)

    n = len(cases)
    return [
        Metric("local_index_recall@k", hits / n, T.LOCAL_INDEX_RECALL_AT_K_MIN,
               note=f"{hits}/{n} golden queries retrieved a labelled source via the served LocalIndex"),
        Metric("local_index_precision_mrr", sum(rrs) / n, T.LOCAL_INDEX_MRR_MIN,
               note=f"mean reciprocal rank over {n} queries via the served LocalIndex"),
    ]


def format_table(metrics: list[Metric]) -> str:
    lines = ["", f"{'Metric':<26} Score   Floor   Result", f"{'-' * 26} ------  ------  ------"]
    for m in metrics:
        score = "  -  " if m.skipped else f"{m.value:.2f}"
        result = "SKIP" if m.skipped else ("pass" if m.passed else "FAIL")
        lines.append(f"{m.name:<26} {score:<7} {m.threshold:<7.2f} {result:<6} {m.note}")
    return "\n".join(lines)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        metrics = run_all()
    except Exception as exc:  # noqa: BLE001 — report a clean failure, not a traceback
        print(f"\nlocal_index_parity tier errored (did not run): {type(exc).__name__}: {exc}")
        return 1
    print(format_table(metrics))
    ok = all(m.passed for m in metrics)
    print(f"\nlocal_index_parity: {'PASS' if ok else 'FAIL'} "
          f"({sum(1 for m in metrics if not m.passed)} below floor, "
          f"{sum(1 for m in metrics if m.skipped)} skipped)")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
