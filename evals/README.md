# evals

A release gate that treats QAI Consultant like a model under test, not just code that runs: it asks *are the numbers and documents it produces honest?* The evals suite runs two independent metrics tiers via `evals.run`, exit non-zero if either fails.

```bash
python -m evals.run   # both tiers
```

## Tier 1 — `rag` (classical RAG metrics, fully local)

Builds an in-memory index over `knowledge_base/*.md` with the app's own embedding model (`all-MiniLM-L6-v2`) — **no Pinecone, no keys, no Docker** — then measures the classical RAG triad.

| Metric | Type | Floor |
|--------|------|-------|
| `context_recall@k` | keyless (does retrieval surface a labelled source doc?) | 0.80 |
| `context_precision_mrr` | keyless (how *highly* is the labelled source ranked? — MRR) | 0.70 |
| `faithfulness` | LLM judge (are the answer's claims grounded in the context?) | 0.70 |
| `answer_relevance` | LLM judge (does the answer address the query?) | 0.70 |
| `source_attribution` | regex over a generated answer (do its `[Source N]` cites point at retrieved chunks?) | 0.90 |

Recall and precision are keyless and deterministic. The other three need a generated answer, so they go through the app's own `LLMClient` (`judge.py`) — the production Mistral model, the same one the app ships. Set `MISTRAL_API_KEY` (and `OPENROUTER_API_KEY` for the fallback) to run them. They **SKIP — never fail** — when the keys are absent or the provider is unreachable (and SKIP below a half-of-cases quorum rather than score thin data). Recall/MRR are keyless but still need the embedding stack (installed via `requirements.txt`); if it's absent the whole RAG tier SKIPs.

## Tier 2 — `local_index_parity` (served LocalIndex vs. rag_golden.jsonl)

Runs the same Context Recall@k and Precision (MRR) metrics as Tier 1's `rag`, but against the MCP server's actual served `LocalIndex` (chunk-level, 1000/200 overlap — matches production retrieval granularity). This ensures the chunking/embedding/ranking behavior of the live-served index matches the `rag` tier's coarser doc-level index at the retrieval quality level. Keyless; no LLM needed. Both tiers SKIP (not fail) without the embedding stack.

## Archived — Deterministic checks (moved to pytest)

The four deterministic "tier-1" modules (`estimate_integrity`, `review_integrity`, `results_integrity`, `maturity_integrity`) moved to ordinary pytest tests in `tests/` as of 2026-09-17 (Task 2 and Task 3 of the CI/evals simplification). The `pytest tests/` suite (run by the CI `test` job) now covers them. They are no longer part of `evals.run` — see `tests/test_estimate_integrity.py` et al. and CLAUDE.md's Evals section.

## Layout

```
rag.py  rag_golden.jsonl  judge.py          # tier 1 RAG eval (judge.py = LLMClient adapter)
local_index_parity.py                        # tier 2 LocalIndex parity eval
thresholds.py                                # the gate spec (every floor + why)
run.py                                       # aggregate gate
```

Add a case by appending a line to `rag_golden.jsonl` — the dataset *is* the suite; no new test files. Deterministic checks moved to `tests/test_*.py` (see Archived section above).
