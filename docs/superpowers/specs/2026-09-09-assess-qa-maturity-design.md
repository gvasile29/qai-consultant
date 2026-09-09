# assess_qa_maturity — Design

**Date:** 2026-09-09
**Status:** Approved by user, pending spec review

## Problem

`MCP_PLAN.md` §2 deferred `assess_qa_maturity(project_description, focus_areas=None)`
in v3.1 because its rubric was never specified beyond a one-line sketch
("retrieval over `evaluation_audit/` + a deterministic TMMi-inspired
scoring rubric; returns gap summary JSON with cited sources") — the v3.1
plan scoped F1 (`review_qa_document`) and F2 (`analyze_test_results`) in
full detail and deliberately left this one unscheduled rather than build
an under-specified rubric.

Two knowledge-base documents added since then make the rubric fully
specifiable now:

- `knowledge_base/evaluation_audit/TMMi_Test_Maturity_Model.md` already
  contains a "QAI Consultant Application" section spelling out exactly
  how this tool should behave: treat answers/descriptions as an
  *informal* TMMi level signal, never claim or imply a certified level,
  and recommend the next level's process areas as concrete next steps.
- `knowledge_base/standards/eu_ai_act/EU_AI_Act_Overview.md`'s "Articles
  9–15 — Testing Implications for High-Risk AI Systems" section maps
  seven articles directly onto seven checkable QA activities (risk
  management, data governance, technical documentation, record-keeping,
  transparency, human oversight, accuracy/robustness/security) — a
  second, independent rubric dimension for AI-system projects.

This spec turns both into one deterministic, dependency-free core module
plus a generator and three call surfaces (MCP, Streamlit, CLI), matching
the architecture F1/F2 already established.

## Alternatives considered

- **Input: a typed `project_description` vs. accepting either a free-text
  narrative or a pasted existing document (Test Strategy/Risk Register),
  undistinguished** — chose the latter (user decision). No `doc_type`
  classifier is needed (unlike `review_core.py`'s `_detect_doc_type()`):
  the rubric scans for process-area evidence anywhere in the text
  regardless of whether it's a dialogue-style narrative or a formal
  document; distinguishing the two would add a classification step with
  no effect on scoring.
- **Rubric scope: TMMi-only vs. TMMi + EU AI Act readiness as a second,
  independent dimension** — chose the dual rubric (user decision),
  matching the original `MCP_PLAN.md` sketch which named both KB folders.
  Rejected merging them into one blended score: TMMi process maturity
  and AI Act compliance readiness are orthogonal (a mature test process
  says nothing about Article 9–15 readiness and vice versa), so they are
  reported as two separate sections, not combined into a single number.
- **AI Act dimension always scored vs. gated on AI/ML relevance** — chose
  gated. Scoring "AI Act readiness: 20/100" for a plain CRUD project
  would be noise, not a finding — the dimension is omitted entirely
  (`ai_act_relevant: false` in `stats`) unless the text signals an AI/ML
  system.
- **Surfaces: MCP-only (matching the original one-line sketch's minimal
  framing) vs. full MCP + Streamlit + CLI parity with F1/F2** — chose
  full parity (user decision), since the tool produces a standalone
  assessment result analogous to Document Review, not a pure automation
  primitive.
- **Deterministic-only output vs. an LLM narrative layer on top** — chose
  narrative (user decision): `maturity_generator.py` mirrors
  `review_generator.py`'s shape (deterministic core + LLM narrative +
  `save()`) so Streamlit/CLI get a downloadable "QA Maturity Report",
  consistent with how Document Review works. The MCP tool bypasses the
  generator entirely and returns only the deterministic
  `maturity_core` output — no LLM call in the MCP path, per the
  "MCP lens" (`MCP_PLAN.md` §1): the client LLM already writes prose
  better than ours.

## Design

### 1. `src/maturity_core.py` (new, dependency-free: `re`, `dataclasses`, `typing`)

Same import-graph tier as `effort_core.py`/`review_core.py`/`results_core.py`
— no `agent.py`, no Pinecone, no Streamlit, no LLM. Single entry point:

```python
def assess_maturity(text: str) -> MaturityResult
```

**Input hygiene:** reuses the same `MIN_CONTENT_CHARS`/`MAX_INPUT_CHARS`
guard pattern as `review_core.py` (strip front matter/AI footer if
present via the same regexes, truncate above `MAX_INPUT_CHARS`, and
short-circuit to `status="insufficient_content"` below
`MIN_CONTENT_CHARS`) — this is the same convention, not a new one.

**Dimension 1 — TMMi (always scored).** Ten process areas, each with a
small set of keyword/phrase checks in the same style as
`review_core.py`'s `_entry_exit_criteria()`/`_risk_coverage()` (a handful
of boolean checks, score = evidence found / checks total × 100):

| Level | Process area | Illustrative evidence checks |
|---|---|---|
| 2 | Test Policy and Strategy | "test policy", "test strategy", "test objectives" |
| 2 | Test Planning | "test plan", risk-based prioritization language, estimate/schedule mention |
| 2 | Test Monitoring and Control | "defect log", "status report", "tracked against plan" |
| 2 | Test Design and Execution | test-design-technique keywords, entry/exit criteria mention, requirement-ID pattern (reuse `review_core._REQ_ID_RE`) |
| 2 | Test Environment | "test environment", "staging", "representative of production" |
| 3 | Test Organization | "test team", "independent test", "QA department" |
| 3 | Test Training Program | "training program", "certification", "onboarding" |
| 3 | Test Lifecycle and Integration | "master test plan", lifecycle-phase mentions from requirements onward |
| 3 | Non-functional Testing | performance/security/usability/reliability test mentions |
| 3 | Peer Reviews | "code review", "inspection", "walkthrough", "peer review" |

(Full keyword lists finalized during implementation, sourced from each
process area's own name/description in `TMMi_Test_Maturity_Model.md` —
same sourcing discipline `review_core.py`'s `SECTION_SYNONYMS` already
follows for IEEE 829 section names.)

**Indicative level (never 4 or 5 — TMMi.md explicitly forbids claiming a
level requiring quantitative evidence a text description cannot
substantiate):**
- Level-2 area average < 60 → indicative level **1**
- Level-2 average ≥ 60, Level-3 average < 60 → indicative level **2**
- Both ≥ 60 → indicative level **3**

`MaturityResult.disclaimer` is a fixed string always present, restating
TMMi.md's own rule: this is an informal indicative signal from a text
description, not a certified TMMi appraisal, and levels cannot be
skipped in a real appraisal.

**Dimension 2 — EU AI Act readiness (conditional).** A relevance gate
(same shape as `review_core._detect_doc_type()`'s keyword voting, but
boolean) checks for AI/ML system language ("machine learning", "AI
system", "model", "neural network", "algorithm", "LLM", "artificial
intelligence", ...). When absent: `ai_act_relevant=False`,
`ai_act_dimension_scores={}`, no AI Act findings. When present: seven
checks, one per article, mapped 1:1 to `EU_AI_Act_Overview.md`'s
"Articles 9–15" section:

| Article | Dimension key |
|---|---|
| 9 | `risk_management` |
| 10 | `data_governance` |
| 11 | `technical_documentation` |
| 12 | `record_keeping` |
| 13 | `transparency_instructions` |
| 14 | `human_oversight` |
| 15 | `accuracy_robustness_security` |

Each scored the same evidence-keyword-checks way as the TMMi areas.
Findings for `risk_management` and `human_oversight` are `critical`
severity (Articles 9 and 14 are the Act's foundational safety
mechanisms); the rest are `major`. A fixed note is attached whenever
this dimension is scored, mirroring the TMMi disclaimer: risk-tier
classification (whether a system is legally "high-risk") is a
determination this tool does not make — these checks apply *if* the
project is high-risk, which the user/team must confirm independently
(same "never claim/imply" discipline as the TMMi level).

**Data shapes:**

```python
@dataclass
class MaturityFinding:
    framework: str            # "tmmi" | "eu_ai_act"
    dimension: str            # process area / article key
    level: Optional[int]      # 2 or 3 for TMMi findings; None for AI Act
    severity: str             # "critical" | "major" | "minor"
    message: str
    evidence: str
    citation_queries: list = field(default_factory=list)

@dataclass
class MaturityResult:
    status: str                        # "ok" | "insufficient_content"
    indicative_tmmi_level: int         # 1-3, 0 if insufficient_content
    tmmi_dimension_scores: dict
    ai_act_relevant: bool
    ai_act_dimension_scores: dict      # {} if not relevant
    findings: list                     # list[MaturityFinding]
    disclaimer: str
    stats: dict                        # char_count, word_count, ai_act_relevant, reason (if insufficient)
```

### 2. `src/maturity_generator.py` (new, Streamlit/CLI only — not in the MCP import graph)

Mirrors `review_generator.py`'s shape exactly:

- `build_maturity_prompt(result: MaturityResult, knowledge_context: str) -> str`
  — a short prompt (comparable size to `effort_estimator.py`'s narrative
  prompt, not a full RAG generation prompt) asking for two sections: an
  executive summary of current maturity, and a prioritized roadmap
  toward the next indicative level / next unmet AI Act article, citing
  the resolved KB chunks.
- `MaturityGenerator.generate(text, chunks=None) -> str` — runs
  `maturity_core.assess_maturity()`, resolves `citation_queries` via
  `agent.retrieve_knowledge()` (Streamlit/CLI path — same
  caller-resolves-citations contract as `review_generator.py`), calls
  `agent.ask()` for the narrative (no streaming — same choice
  `effort_estimator.py` made for its short narrative call), and returns
  a markdown report.
- `build_maturity_report_markdown()` / `save_maturity_report()` — same
  `with_ai_footer()` + filename-sanitization + `output/` save pattern as
  every other generator.

### 3. Three surfaces

**MCP (`mcp_server.py`):** new `@mcp.tool() assess_qa_maturity(project_description: str) -> dict`.
Calls `maturity_core.assess_maturity()` directly (no LLM, no generator),
resolves each finding's `citation_queries` via `LocalIndex.search()`
(identical pattern to `review_qa_document`), returns the full
`MaturityResult` as a dict with resolved citations attached per finding.
Never raises — same never-raising contract as the other four tools.

**Streamlit (`app.py`):** new mode "Assess QA Maturity" — `render_maturity_assessment()`,
structurally parallel to `render_doc_review()`: a `st.text_area()` for
the free-text description or pasted document, a "🔍 Assess Maturity"
primary button, results rendered via `ledger_components.py`'s existing
`signal_ledger_html()`/`risk_ledger_table_html()` helpers (TMMi level as
a signal ledger tile, per-area/per-article scores as ledger rows — reuse,
not a new component), then the LLM narrative streamed via
`maturity_generator.py`, with `.md`/PDF download buttons following the
existing PDF-caching gotcha (compute once, cache in session state, never
inside the render loop). New `MATURITY_MODE_STATE_KEYS` list (own
text-area key, result cache, PDF-bytes cache), added to both "Start
Over" and "Generate Another Strategy" cleanup lists plus its own reset
button — same three-call-site pattern `REVIEW_MODE_STATE_KEYS` already
established.

**CLI (`cli.py`):** new `--maturity PATH` argparse flag (reads the file
at `PATH` as the description text, same convention as `--review PATH`),
runs `run_maturity_mode()`, prints/saves the report, exits without the
interactive dialogue.

### 4. Eval module: `evals/maturity_integrity.py` (new, tier-1 style)

Same shape as `review_integrity.py`: runs the real shipped
`maturity_core.assess_maturity()` (dependency-free, no stub needed) on
golden cases in a new `evals/maturity_golden.jsonl`. Metrics:

- `level_ordering` — a narrative with strong Level-2-and-3 evidence
  scores a higher `indicative_tmmi_level` than a narrative with none
  (monotonicity, same spirit as `review_integrity`'s `score_ordering`).
- `no_level_skip` — a case with strong Level-3-only keyword stuffing but
  no Level-2 evidence must still resolve to indicative level 1, never
  jump straight to 3 (guards the deliberate no-skip logic).
- `ai_act_gating` — an AI-relevant case populates
  `ai_act_dimension_scores`; a non-AI case leaves it empty (guards
  against false-positive compliance noise).
- `determinism` — same input twice yields byte-identical scores/findings.
- `insufficient_content_handling` — a near-empty input never crashes and
  returns `status="insufficient_content"`.

No LLM, no API keys — wired into `evals/run.py`'s always-run tier-1
section alongside `review_integrity`/`results_integrity`, which means it
runs under the existing `evals-det` CI gate automatically, no workflow
changes needed.

### 5. Documentation / versioning

This ships as **v3.5.0** (next after v3.4.4; v4.0 stays reserved for
remote MCP per the existing roadmap renumbering note). Full Release
Checklist applies: `version.py`, `pyproject.toml` (new module in the
MCP package's `py-modules` whitelist — `maturity_core.py` only;
`maturity_generator.py` stays Streamlit/CLI-only like
`review_generator.py`), `CHANGELOG.md`, `README.md` (MCP tools table +
Roadmap), `README_MCP.md` (tools table), `CLAUDE.md` (architecture table
rows for both new modules, roadmap entry marking `assess_qa_maturity` as
shipped, removal of the "deliberately deferred" note in the v3.1 roadmap
entry or a forward-pointer to this one). `tests/test_packaging.py`'s
whitelist-exact-match test will need `maturity_core.py` added to its
expected `py-modules` set.

## Testing

- `tests/test_maturity_core.py` — unit tests per TMMi area and per AI
  Act article check, the no-skip level logic, the AI-relevance gate, the
  insufficient-content path, and a determinism test (same input twice).
- `tests/test_maturity_generator.py` — prompt building, citation
  resolution wiring (mocked `retrieve_knowledge`), `save()` filename
  sanitization + AI footer, mirroring `test_review_generator.py`'s shape
  if one exists (else mirroring `test_effort_estimator.py`'s LLM-call
  mocking pattern).
- `tests/test_mcp_server.py` — new `assess_qa_maturity` tool test,
  mirroring the existing `review_qa_document`/`analyze_test_results`
  tests (never-raising contract, citation resolution via the in-memory
  `LocalIndex`).
- `tests/test_app_maturity.py` (new, mirroring `test_app_v03.py`'s
  Streamlit integration style) — session-state cleanup list membership,
  widget-key round-trip.
- `evals/maturity_integrity.py` + `evals/maturity_golden.jsonl` — see
  §4 above; run via `python -m evals.maturity_integrity` standalone and
  as part of `python -m evals.run --det`.
- Manual: one real Streamlit run through the new mode with both an
  AI-relevant and a non-AI-relevant description, confirming the AI Act
  section appears/disappears correctly and the PDF export renders.

## Release ownership

Version bump (v3.5.0), CHANGELOG entry, and all Release Checklist doc
updates land in the same PR as the code, per the existing merge gate
(`CHANGELOG.md` must have the new version's entry before merge — see
CLAUDE.md's Release Checklist section). Git tag + GitHub release +
MCP registry `server.json` sync (if the MCP tool surface changed enough
to warrant it, per the v3.1.4/v3.3.1 precedent) are left for explicit
user confirmation before those irreversible/external-facing steps, same
as every prior release in this repo.
