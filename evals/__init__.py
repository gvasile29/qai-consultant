"""Evals for QAI Consultant — a release gate over classical RAG metrics.

  - rag (classical RAG metrics, local) — over a local doc-level embedding index of
    ``knowledge_base/*.md`` (no Pinecone). Context Recall@k and Precision (MRR) are
    keyless; Faithfulness, Answer Relevance and Source Attribution need a generated
    answer via the app's LLMClient (production Mistral) and SKIP without a key.
  - local_index_parity (keyless) — the same Recall@k/MRR metrics against the
    MCP server's actual served ``LocalIndex`` (chunk-level, 1000/200 — matches
    production retrieval granularity, unlike rag's coarser doc-level index).

    python -m evals.run                  # both
    python -m evals.rag                  # RAG (doc-level eval index) only
    python -m evals.local_index_parity   # served LocalIndex parity only

``thresholds.py`` is the gate spec; ``rag_golden.jsonl`` is the shared dataset
(append a line to add a case).

Note: the deterministic "tier-1" checks that used to live here (estimate_integrity,
review_integrity, results_integrity, maturity_integrity) moved to ordinary pytest
tests in tests/ as of 2026-09-17 — see CLAUDE.md's Evals section.
"""

import sys
from pathlib import Path


def ensure_src_on_path() -> None:
    """Put the app's ``src/`` on sys.path (idempotent) so the eval can import the real
    modules. Deliberately not removed afterwards — later lazy imports still need it."""
    src = str(Path(__file__).resolve().parent.parent / "src")
    if src not in sys.path:
        sys.path.insert(0, src)
