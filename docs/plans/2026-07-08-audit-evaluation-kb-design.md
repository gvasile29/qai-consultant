# Knowledge Base Expansion — Process Audit & Evaluation — Design

**Date:** 2026-07-08

## Goal

Today's `knowledge_base/` grounds QAI Consultant in how to **implement** a QA process (standards, methodologies, articles). It has no content on how that process gets **evaluated** afterward — maturity assessment, audit methodology, compliance audit criteria, or real-world cases where a process gap surfaced at audit time. Generated Test Strategies / Risk Registers currently can't be audit-aware because the KB has nothing to retrieve on that topic.

This adds a fourth content pillar — audit/evaluation — so RAG retrieval can ground generated output in what an auditor or maturity assessment would actually check for.

Out of scope for this pass: the separate "post-implementation audit evaluation" feature (a new dialogue/eval flow that scores an already-implemented strategy against real audit results) — that's a v3.0-level roadmap item, not a KB content task. Also out of scope: running ingest against the production Pinecone index (left to the user's judgment, separately).

## A. Folder structure & category

New top-level folder: `knowledge_base/evaluation_audit/`.

`src/ingest.py`'s `CATEGORY_MAP` (~line 55) maps top-level folder name → metadata category tag. Add:

```python
"evaluation_audit": "Audit/Evaluation",
```

`CLAUDE.md` updates to match:
- "Ingestion source categories" table gets a new row: `evaluation_audit/` → `"Audit/Evaluation"`
- "Contents" section gets a new bullet describing the folder
- "RAG indexing priority" note: new MDs are structured content, so they index in the same priority tier as the existing methodology MDs (after OWASP Top 10 MD, before ISTQB/OWASP PDFs)

## B. Documents (11 total, 4 sub-areas)

All are original Markdown written for this KB (matching how `methodologies/*.md` and the Markdown files in `standards/` are already synthesized rather than reproduced from paywalled source standards).

**B1 — Test/process maturity models (3 docs)**
- `TMMi_Test_Maturity_Model.md` — 5 maturity levels, process areas, self-assessment approach
- `CMMI_Process_Maturity.md` — CMMI applied to dev/test process maturity; cross-references the existing `ASPICE_Process_Reference_Model.md`
- `ISO_IEC_33002_Process_Assessment.md` — successor to ISO 15504/SPICE; formal process assessment methodology

**B2 — Generic audit methodology (3 docs)**
- `ISO_19011_Audit_Guidelines.md` — audit principles, audit plan, auditor/auditee roles, audit types
- `Audit_Gap_Analysis_Techniques.md` — identifying and prioritizing gaps found during an audit
- `Compliance_Audit_Report_Structure.md` — audit report structure: findings, severity, remediation, follow-up

**B3 — Security/compliance audit (2 docs)**
- `Security_Compliance_Audit_ASVS.md` — OWASP ASVS as an audit framework; complements the existing OWASP Top 10/WSTG content
- `Regulatory_Compliance_Frameworks.md` — ISO 27001, SOC 2 — what a compliance audit checks beyond functional testing

**B4 — Real, publicly documented failure case studies (3 docs)**
- `Case_Study_Knight_Capital_2012.md` — $440M lost in 45 minutes; deployment/testing process gap
- `Case_Study_Boeing_737MAX_MCAS.md` — requirements-validation process gap
- `Case_Study_CrowdStrike_2024_Outage.md` — content-update testing/rollout process gap

Each case study cites public sources (SEC filings, NTSB/FAA reports, official post-mortems) — no speculation about unpublished internal details.

## C. Document template

B1–B3 docs follow the existing `methodologies/*.md` shape:
1. Title + short intro (what it is / why it matters)
2. Key concepts / formal structure (levels, processes, criteria — tabular where it fits)
3. Practical application (checklist or steps)
4. Closing **"QAI Consultant application"** section — explicitly ties the concept to generated output (e.g., which of the 11 dialogue questions should surface this risk, which section of the generated strategy should cover it)

B4 case studies use a distinct shape: **What happened → Root cause (process gap) → What a mature process/audit would have caught → Source**.

## D. Code changes

1. `src/ingest.py` — add `"evaluation_audit": "Audit/Evaluation"` to `CATEGORY_MAP`
2. `CLAUDE.md` — update "Ingestion source categories" table, "Contents" section, "RAG indexing priority" note

## E. Verification

- Run `python src/ingest.py` locally to confirm the new documents ingest cleanly (correct category tag, reasonable chunking) — against a local/test index, not production
- Add 3–4 new cases to `evals/rag_golden.jsonl` (query → expected source) covering the new documents, per the existing pattern ("the datasets *are* the suites")
- Run `python -m evals.rag` to confirm `context_recall@k` / `context_precision_mrr` don't regress and the new docs are actually retrievable
