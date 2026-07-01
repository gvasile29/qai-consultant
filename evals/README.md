# evals

A release gate that treats QAI Consultant like a model under test, not just code that runs: it asks *are the numbers and documents it produces honest?* Two independent tiers, one non-zero exit if either fails.

```bash
python -m evals.run         # both tiers
python -m evals.run --det   # keyless deterministic tier only (no LLM, no keys)
```

## Tier 1 — `estimate_integrity` (deterministic, keyless)

Runs the **real shipped functions** (`InputValidator`, `EffortEstimator`) on golden inputs and asserts they round-trip honestly — re-implements nothing. No LLM, no API keys, instant; drops straight into CI.

| Metric | Catches |
|--------|---------|
| `duration_bounds` | a 4-digit year parsed as a duration (`"June 2026"` → 42,546 days) |
| `team_restatement_invariance` | restated headcount double-counted (`"3+2, or 5"` → 10 people) |
| `name_display_fidelity` | project name silently mangled (spaces → `_`) in the deliverable title |
| `confidence_magnitude_sanity` | a physically-impossible estimate labelled "High" confidence |
| `no_fabricated_versions` | version numbers in a deliverable that no user ever supplied |

A red row names a real defect in the shipped logic — the tier *is* the issue list.

## Tier 2 — `rag` (classical RAG metrics, fully local)

Builds an in-memory index over `knowledge_base/*.md` with the app's own embedding model (`all-MiniLM-L6-v2`) — **no Pinecone, no keys, no Docker** — then measures the classical RAG triad.

| Metric | Type | Floor |
|--------|------|-------|
| `context_recall@k` | keyless (does retrieval surface a labelled source doc?) | 0.80 |
| `context_precision_mrr` | keyless (how *highly* is the labelled source ranked? — MRR) | 0.70 |
| `faithfulness` | LLM judge (are the answer's claims grounded in the context?) | 0.70 |
| `answer_relevance` | LLM judge (does the answer address the query?) | 0.70 |
| `source_attribution` | regex over a generated answer (do its `[Source N]` cites point at retrieved chunks?) | 0.90 |

Recall and precision are keyless and deterministic. The other three need a generated answer, so they go through the app's own `LLMClient` (`judge.py`) — the production Mistral model, the same one the app ships. Set `MISTRAL_API_KEY` (and `OPENROUTER_API_KEY` for the fallback) to run them. They **SKIP — never fail** — when the keys are absent or the provider is unreachable (and SKIP below a half-of-cases quorum rather than score thin data). The whole tier SKIPs if the embedding stack is unavailable, so a bare CI box still gets the full deterministic tier plus the keyless retrieval metrics.

## Layout

```
estimate_integrity.py  golden.jsonl  captured_test_plan.md   # tier 1
rag.py  rag_golden.jsonl  judge.py                           # tier 2 (judge.py = LLMClient adapter)
thresholds.py                                                # the gate spec (every floor + why)
run.py                                                       # aggregate gate
```

Add a case by appending a line to `golden.jsonl` (tier 1) or `rag_golden.jsonl` (tier 2) — the datasets *are* the suites; no new test files.
