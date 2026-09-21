# evals

A release gate that treats QAI Consultant like a model under test, not just code that runs: it asks *are the numbers and documents it produces honest?* The evals suite runs two RAG-quality metrics checks via `evals.run`, exits non-zero if either fails.

```bash
python -m evals.run   # rag + local_index_parity
```

## `rag` — classical RAG metrics (fully local)

Builds an in-memory index over `knowledge_base/*.md` with the app's own embedding model (`all-MiniLM-L6-v2`) — **no Pinecone, no keys, no Docker** — then measures the classical RAG triad.

| Metric | Type | Floor |
|--------|------|-------|
| `context_recall@k` | keyless (does retrieval surface a labelled source doc?) | 0.80 |
| `context_precision_mrr` | keyless (how *highly* is the labelled source ranked? — MRR) | 0.70 |
| `faithfulness` | LLM judge (are the answer's claims grounded in the context?) | 0.70 |
| `answer_relevance` | LLM judge (does the answer address the query?) | 0.70 |
| `source_attribution` | regex over a generated answer (do its `[Source N]` cites point at retrieved chunks?) | 0.90 |

Recall and precision are keyless and deterministic. The other three need a generated answer, so they go through the app's own `LLMClient` (`judge.py`) — the production Mistral model, the same one the app ships. Set `MISTRAL_API_KEY` (and `OPENROUTER_API_KEY` for the fallback) to run them. They **SKIP — never fail** — when the keys are absent or the provider is unreachable (and SKIP below a half-of-cases quorum rather than score thin data). Recall/MRR are keyless but still need the embedding stack (installed via `requirements.txt`); if it's absent the whole RAG tier SKIPs.

## `local_index_parity` — served LocalIndex parity

Runs the same Context Recall@k and Precision (MRR) metrics as `rag`, but against the MCP server's actual served `LocalIndex` (chunk-level, 1000/200 overlap — matches production retrieval granularity). This ensures the chunking/embedding/ranking behavior of the live-served index matches `rag`'s coarser doc-level index at the retrieval quality level. Keyless; no LLM needed. Both SKIP (not fail) without the embedding stack.

## Archived — Deterministic checks (moved to pytest)

The four deterministic "tier-1" modules (`estimate_integrity`, `review_integrity`, `results_integrity`, `maturity_integrity`) moved to ordinary pytest tests in `tests/` as of 2026-09-17 (Task 2 and Task 3 of the CI/evals simplification). The `pytest tests/` suite (run by the CI `test` job) now covers them. They are no longer part of `evals.run` — see `tests/test_estimate_integrity.py` et al. and CLAUDE.md's Evals section. **Their check logic and fixtures were not deleted** — only the CLI entry point (`python -m evals.<module>`) moved to pytest; the modules, golden files, and fixtures below still live in `evals/` and are what `tests/test_*.py` imports and runs against.

## Layout

```
rag.py  rag_golden.jsonl  judge.py          # RAG eval (judge.py = LLMClient adapter)
local_index_parity.py                       # LocalIndex parity eval
thresholds.py                               # the gate spec (every floor + why)
run.py                                      # aggregate gate over rag + local_index_parity

estimate_integrity.py  golden.jsonl  captured_test_plan.md     # invoked via pytest tests/test_estimate_integrity.py
review_integrity.py    review_golden.jsonl  fixtures/review/*.md    # invoked via pytest tests/test_review_integrity.py
results_integrity.py   results_golden.jsonl fixtures/results/*      # invoked via pytest tests/test_results_integrity.py
maturity_integrity.py  maturity_golden.jsonl fixtures/maturity/*.txt # invoked via pytest tests/test_maturity_integrity.py
```

Add a case to `rag`/`local_index_parity` by appending a line to `rag_golden.jsonl` — the dataset *is* the suite; no new test files. The four migrated modules' golden/fixture files above work the same way — append a case to the relevant `*_golden.jsonl` and it's picked up by the corresponding `tests/test_*.py` (see the Archived section above).
