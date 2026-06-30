"""Evals for QAI Consultant — a release gate in two tiers.

  - estimate_integrity (keyless, deterministic) — checks over the *real shipped logic*
    (``InputValidator``, ``EffortEstimator``): duration/team parsing, name fidelity,
    confidence sanity, fabricated versions. No LLM, no API keys; runs in any CI.
  - rag (classical RAG metrics, fully local) — over a local embedding index of
    ``knowledge_base/*.md`` (no Pinecone, no keys): Context Recall@k, Context Precision
    (MRR) and Source Attribution are judge-free; Faithfulness and Answer Relevance use a
    local Ollama judge. Judged metrics SKIP if Ollama is absent.

    python -m evals.run                 # both tiers
    python -m evals.estimate_integrity  # keyless tier only
    python -m evals.rag                 # RAG tier only

``thresholds.py`` is the gate spec; ``golden.jsonl`` / ``rag_golden.jsonl`` are the
datasets (append a line to add a case).
"""
