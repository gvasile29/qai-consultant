# Knowledge Base Expansion — EU AI Act Article 50 Content — Design

**Date:** 2026-07-14

## Goal

QAI Consultant already implements the Article 50 *transparency mechanics* (v2.5.2 — sidebar notice + document footers), but the knowledge base has no *content* on the EU AI Act itself. RAG retrieval currently can't ground a generated Test Strategy/Risk Register in the Act's risk tiers, obligations, or testing implications when a user's project happens to be a high-risk AI system.

This adds a single self-authored KB document — `standards/eu_ai_act/` — so generated output can cite the Act the same way it already cites ISO 25010 or IEEE 829. Content-only release; no `src/` code changes.

Out of scope for this pass: machine-readable Article 50(2) marking (YAML front matter / PDF metadata) — that was v3.0 scope per the Omnibus grace period (2026-12-02) and shipped there; see CLAUDE.md's v3.0 roadmap entry.

## A. Folder structure & category

New subfolder: `knowledge_base/standards/eu_ai_act/`.

No `src/ingest.py` change needed — `get_source_category()` maps by **top-level** folder name (`standards/` → `"Standard"`), the same way `standards/istqb/` and `standards/owasp/` already work as subfolders without their own `CATEGORY_MAP` entry.

## B. Document

One consolidated file, matching the granularity of `ISO_IEC_25010_Quality_Model.md` (one file per standard, `##` sections within it) rather than the one-file-per-topic granularity of `methodologies/`.

**`knowledge_base/standards/eu_ai_act/EU_AI_Act_Overview.md`** — six sections:

1. **Risk Tiers & Classification** — unacceptable / high / limited / minimal risk categories, what determines tier placement
2. **Provider & Deployer Obligations** — who is a provider vs. deployer, what each must do
3. **Article 50 Transparency Obligations** — the obligations this app's v2.5.2 patch already implements; ties the KB content back to the app's own compliance posture
4. **Articles 9–15 — Testing Implications for High-Risk AI Systems** — risk management system, data governance, technical documentation, logging, human oversight, accuracy/robustness/cybersecurity — each mapped to a concrete QA activity (this is the section that does the most work for generated Test Strategies)
5. **Conformity Assessment** — self-assessment vs. notified body involvement, CE marking, EU database registration
6. **Timeline & Deadlines** — **amended (Omnibus) dates**, with an explicit note on where they diverge from the original Regulation (EU) 2024/1689 text, so the doc doesn't read as stale next to earlier knowledge of the Act

## C. Document template

Follows the existing `standards/*.md` shape (see `ISO_IEC_25010_Quality_Model.md`):
1. Title + source/note header (self-authored public-knowledge summary, not reproduced regulatory text)
2. `##` section per topic above, `---` dividers
3. Each section closes with a **QA Focus** callout tying it to testing practice — consistent with ISO 25010/IEEE 829, and this is what makes section 4 (Art 9-15) actionable rather than just descriptive

## D. Eval coverage

Add 5–6 new cases to `evals/rag_golden.jsonl` — one query per major section, `judge: true`, `expects: ["EU_AI_Act_Overview"]` — matching the existing `{"query": ..., "expects": [...], "judge": true}` format. This is what actually exercises `context_recall@k` / `context_precision_mrr` against the new doc ("the datasets *are* the suites").

## E. Version bump

- `src/version.py`: `__version__` `2.5.2` → `2.6.0`, `__release_date__` → `2026-07-14`
- `CHANGELOG.md`: new `## [2.6.0]` entry, end-user phrasing matching existing entries (e.g. 2.5.1's KB-expansion entry)
- `CLAUDE.md`: mark `v2.6` ✅ in the Roadmap section with the same short summary style as v2.5.1/v2.5.2; no other CLAUDE.md sections need changes (no ingestion category table row needed, since `eu_ai_act/` isn't a new top-level folder)

## F. Verification

- `python -m evals.run` — both tiers. RAG tier's recall/MRR metrics run keyless (local `sentence-transformers` index); judged metrics (`faithfulness`, `answer_relevance`) skip gracefully without `MISTRAL_API_KEY` per existing skip semantics — either way is fine for confirming the new doc doesn't regress the gate
- `python -m pytest tests/ -v` — confirm no regression (this release touches no `src/` code, so this is a smoke check)
- Optionally: `python src/ingest.py` locally against a non-production index to confirm the new doc chunks/ingests cleanly, per the same caveat as the v2.5.1 design doc (production ingest left to the user's judgment)
