"""Evals for QAI Consultant — a release gate in two tiers.

  - estimate_integrity (keyless, deterministic) — checks over the real shipped logic
    (``InputValidator``, ``EffortEstimator``): duration/team parsing, name fidelity,
    confidence sanity, fabricated versions. No LLM, no keys; runs in any CI.
  - rag (classical RAG metrics, local) — over a local embedding index of
    ``knowledge_base/*.md`` (no Pinecone). Context Recall@k and Precision (MRR) are
    keyless; Faithfulness, Answer Relevance and Source Attribution need a generated
    answer via the app's LLMClient (production Mistral) and SKIP without a key.

    python -m evals.run                 # both tiers
    python -m evals.estimate_integrity  # keyless tier only
    python -m evals.rag                 # RAG tier only

``thresholds.py`` is the gate spec; ``golden.jsonl`` / ``rag_golden.jsonl`` are the
datasets (append a line to add a case).
"""

import sys
from pathlib import Path


def ensure_src_on_path() -> None:
    """Put the app's ``src/`` on sys.path (idempotent) so the eval can import the real
    modules. Deliberately not removed afterwards — later lazy imports still need it."""
    src = str(Path(__file__).resolve().parent.parent / "src")
    if src not in sys.path:
        sys.path.insert(0, src)
