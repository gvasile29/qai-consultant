# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

QAI Consultant is a Python-based AI agent that acts as a senior QA Architect. It collects project context via a structured 11-question dialogue, then generates Test Strategies grounded in ISTQB, OWASP, IEEE, and ISO standards using a cloud LLM (Mistral API, with OpenRouter fallback) and RAG over a Pinecone vector knowledge base.

**Deployed:** https://appi-consultant-esodgczvwpmozzybuhdhek.streamlit.app
**Latest GitHub release:** [v2.5.1](https://github.com/gvasile29/qai-consultant/releases/tag/v2.5.1) (2026-07-13, tagged on `master`) — catches up the release history to `version.py`/`CHANGELOG.md`; v2.0.0–v2.5.0 were never individually tagged.

## Development Commands

```bash
pip install -r requirements.txt          # Runtime dependencies
pip install -r requirements-dev.txt      # + ruff + pytest (for development)

# Prerequisites: copy .env.example → .env and fill in the 4 API keys
cp .env.example .env

python src/ingest.py                     # Build/rebuild Pinecone index from knowledge_base/
python src/cli.py                        # Run terminal UI (Rich-based)
streamlit run src/app.py                 # Run browser UI at http://localhost:8501

ruff check src/ tests/                   # Lint (config in ruff.toml)
```

Required environment variables (`.env` or Streamlit Cloud secrets):
```
MISTRAL_API_KEY=...
OPENROUTER_API_KEY=...
PINECONE_API_KEY=...
PINECONE_INDEX_NAME=qai-consultant
```

## Architecture

**Data flow:**
```
User Input
  → DialogueManager (11 questions → ProjectContext)
  → generate_all() — parallel RAG prefetch (ThreadPoolExecutor, 3 workers)
      → [parallel] _build_risk_query()          → retrieve_knowledge(k=5) → Pinecone
      → [parallel] context.to_rag_query()       → retrieve_knowledge(k=5) → Pinecone
      → [parallel] _build_test_plan_query()     → retrieve_knowledge(k=5) → Pinecone
      (each future wrapped in try/except → falls back to [] on Pinecone error)
  → RiskAnalyzer.analyze(context, chunks=prefetched)   [per-step try/except in generate_all()]
      → build_risk_prompt(context, knowledge_context)
      → agent.ask_streaming(prompt) → Mistral API / OpenRouter (streamed)
      → Risk Register saved to output/  [filename sanitized via regex, mkdir parents=True]
  → EffortEstimator.estimate(context, risk_register)   [per-step try/except in generate_all()]
      → deterministic PERT + multipliers (normalized to 100%) + confidence score
      → agent.ask(narrative_prompt) → Mistral API (short, ~600 char prompt)
      → Effort Report saved to output/
  → StrategyGenerator.generate(context, chunks=prefetched)  [per-step try/except]
      → build_strategy_prompt(context, knowledge_context)
      → agent.ask_streaming(prompt) → Mistral API / OpenRouter (streamed)
      → raises ValueError if LLM returns empty string
      → Test Strategy saved to output/
  → TestPlanGenerator.generate(context, risk_register, chunks=prefetched)  [per-step try/except]
      → build_test_plan_prompt(context, risk_register, knowledge_context)
      → agent.ask_streaming(prompt) → Mistral API / OpenRouter (streamed)
      → Test Plan saved to output/
  → Feedback prompt → if yes/partially → saved to knowledge_base/generated_strategies/
      (existing YAML front matter stripped before prepending feedback block)
```

### Source Files (`src/`)

| File | Role |
|------|------|
| `agent.py` | `QAIAgent` — connects to Pinecone + HuggingFace embeddings; `LLMClient` wraps Mistral API (primary) + OpenRouter (fallback); exposes `retrieve_knowledge()`, `ask()`, `ask_streaming()`, `ask_with_rag()`; `_get_secret()` reads from `.env` or Streamlit secrets |
| `ingest.py` | One-time pipeline: load PDFs/Markdowns → chunk (1000 chars, 200 overlap) → embed (all-MiniLM-L6-v2) → upsert to Pinecone |
| `dialogue.py` | `DialogueManager` + `ProjectContext` dataclass — collects 11 project fields; `to_rag_query()` builds the retrieval query |
| `strategy_generator.py` | `StrategyGenerator` — `generate_all()` prefetches RAG chunks in parallel (ThreadPoolExecutor) then runs Risk → Effort → Strategy sequentially; `generate(chunks=None)` accepts pre-fetched chunks |
| `risk_analyzer.py` | `RiskAnalyzer` — analyzes project context, builds risk-focused RAG query, generates Risk Register; `analyze(chunks=None)` accepts pre-fetched chunks |
| `effort_estimator.py` | `EffortEstimator` — deterministic baseline + multipliers + PERT calculation; LLM used only for narrative sections (no RAG) |
| `ai_disclosure.py` | Dependency-free EU AI Act Article 50 transparency notices: `AI_INTERACTION_NOTICE` (sidebar, Art 50(1)) and `with_ai_footer()` (visible "AI-generated" document footer, Art 50(2)) |
| `version.py` | `__version__` = "2.0.0" — version string displayed in CLI banner and Streamlit sidebar |
| `logger.py` | `get_logger()` + `setup_logging()` — centralized logging to `logs/qai_consultant.log`; file handler (DEBUG) + console handler (WARNING+) |
| `cli.py` | Terminal UI using `rich` — parallel RAG prefetch → Risk Register (streaming via `rich.live.Live`) → Effort spinner → Strategy (streaming via `rich.live.Live`) → feedback loop |
| `app.py` | Streamlit web UI — 4-step state machine: `intro → dialogue → review → strategy`; Risk + Strategy + Test Plan stream via `st.write_stream()`; results shown in 4 tabs; PDF bytes cached in session state after generation; uses `@st.cache_resource` for agent |

### Key Configuration (`src/agent.py` config block)

```python
MISTRAL_MODEL    = "mistral-small-latest"          # primary LLM provider
OPENROUTER_MODEL = "mistralai/mistral-small-3.2-24b-instruct"  # fallback
EMBEDDING_MODEL  = "sentence-transformers/all-MiniLM-L6-v2"   # must match ingest.py
TOP_K_RESULTS    = 5          # default k for retrieve_knowledge()
RAG_K_GENERATION = 5          # k for Risk + Strategy prompts
PINECONE_NAMESPACE = "knowledge-base"   # must match ingest.py

LLM_NUM_PREDICT = 1500        # max output tokens — prevents runaway generation
LLM_TEMPERATURE = 0.1         # near-deterministic sampling
```

> **LLMClient fallback:** Mistral API is tried first. On any exception, OpenRouter is used automatically. Both failing raises `QAIConnectionError`.

### Generated Output

- `output/` — gitignored; timestamped markdown files:
  - `test_strategy_ProjectName_TIMESTAMP.md` — Test Strategy
  - `risk_register_ProjectName_TIMESTAMP.md` — Risk Register
  - `effort_estimation_ProjectName_TIMESTAMP.md` — Effort Estimation Report
- `knowledge_base/generated_strategies/` — validated strategies from user feedback (yes/partially); ingested on next `ingest.py` run

## Knowledge Base

All agent outputs are grounded in documents from `knowledge_base/`. Re-run `ingest.py` after adding new files.

### Ingestion source categories (mapped by folder path)

| Folder | Category tag in metadata |
|--------|--------------------------|
| `standards/` | `"Standard"` |
| `methodologies/` | `"Methodology"` |
| `articles/` | `"Article"` |
| `expert_knowledge/` | `"Expert Knowledge"` |
| `evaluation_audit/` | `"Audit/Evaluation"` |

### Contents

- **`standards/istqb/`** — 14 ISTQB certification PDFs (CTFL, CTAL-TA, CTAL-TM, CTAL-TAE, CT-AI, CT-GenAI, CT-MBT, CT-ATLaS, CT-MAT, CTel-ITP, and more)
- **`standards/owasp/`** — WSTG v4.2 PDF, MASTG PDF, OWASP Top 10 2021 (HTML + MD)
- **`standards/`** — IEEE 829, ISO/IEC 25010, ISO 26262, A-SPICE (all Markdown)
- **`methodologies/`** — 5 guides (Agile, BDD/TDD, Exploratory, Risk-Based, Test Pyramid); each ends with a "QAI Consultant application" section
- **`expert_knowledge/`** — Contribution framework with PROMPT files for AI-assisted knowledge extraction interviews; `Scenario_TeamAlignment.md` is the first real scenario
- **`articles/`** — 10 real-world AI QA case studies with quantified outcomes
- **`evaluation_audit/`** — 11 docs covering process/test maturity models (TMMi, CMMI, ISO/IEC 33002), audit methodology (ISO 19011, gap analysis, audit report structure), security/compliance audit (OWASP ASVS, ISO 27001, SOC 2), and 3 real public failure case studies (Knight Capital, Boeing 737 MAX MCAS, CrowdStrike 2024 outage) illustrating process/audit gaps

### RAG indexing priority
Index OWASP Top 10 MD + methodology MDs + evaluation_audit/ MDs first (structured), then ISTQB/OWASP PDFs, then expert knowledge and articles as supplementary.

## Testing

Tests are in `tests/`. Run with:
```bash
python -m pytest tests/ -v                                      # all tests
python -m pytest tests/test_agent.py -v                         # single file
python -m pytest tests/test_agent.py::test_kb_missing_raises_error -v  # single test
```

**Test files:**
| File | Coverage |
|------|----------|
| `test_llm_client.py` | LLMClient — Mistral primary, OpenRouter fallback, streaming, QAIConnectionError when both fail — 8 tests |
| `test_agent.py` | QAIAgent error handling + ask_streaming() — QAIKnowledgeBaseError, QAIConnectionError, streaming — 7 tests |
| `test_performance_config.py` | Config regression guards — LLM_NUM_PREDICT, RAG_K_GENERATION, MISTRAL_MODEL, OPENROUTER_MODEL, LLMClient, temperature — 6 tests |
| `test_dialogue.py` | InputValidator + DialogueManager — validation rules, submit flow, reset — 21 tests |
| `test_confidence_v06.py` | Confidence score algorithm — PERT spread, capacity gap, data quality, multiplier magnitude, boundary conditions — 24 tests |
| `test_effort_estimator.py` | EffortEstimator — deterministic calculations, PERT, CLI/Streamlit integration — 26 tests |
| `test_feedback_loop.py` | CLI feedback loop — 4 tests |
| `test_app_feedback_loop.py` | Streamlit feedback loop — 9 tests |
| `test_risk_analyzer.py` | RiskAnalyzer module — 7 tests |
| `test_app_v03.py` | Streamlit v0.3 Risk Register integration — 11 tests |
| `test_integration.py` | End-to-end pipeline — dialogue → Risk Register + Effort Report + Test Strategy — 5 tests |

> **Rule:** After every code change, run relevant tests before committing. Add new tests for every new feature.

> **Baseline (v2.0.1):** 104 passed, 7 pre-existing fixture errors (`test_full_estimate_bmw`, `test_risk_analyzer` — require live `agent` fixture, run only with valid API keys).

## Evals (`evals/` — release gate)

A release gate that treats the app like a model under test ("are the numbers and documents it produces honest?"), separate from `tests/`. Two independent tiers; exits non-zero if either fails. The eval functions **are** the assertions — there is no `tests/` wrapper for this module by design.

```bash
python -m evals.run                  # both tiers
python -m evals.run --det            # tier 1 only (keyless, no LLM)
python -m evals.estimate_integrity   # tier 1 standalone
python -m evals.rag                  # tier 2 standalone
```

**Tier 1 — `estimate_integrity` (deterministic, keyless):** runs the *real shipped* `InputValidator` / `EffortEstimator` (stubs only the heavy `agent` module) on golden inputs. 5 metrics: `duration_bounds`, `team_restatement_invariance`, `name_display_fidelity`, `confidence_magnitude_sanity`, `no_fabricated_versions`. No LLM, no API keys; CI-safe. A red row names a real defect in the shipped logic.

**Tier 2 — `rag` (classical RAG metrics, fully local):** builds an in-memory cosine index over `knowledge_base/*.md` with the app's own embedding model (`all-MiniLM-L6-v2`, same `langchain_community` import as `src/agent.py`) — no Pinecone, no keys. 5 metrics. Keyless: `context_recall@k` + `context_precision_mrr` (reuse the `expects` labels). Need a generated answer, so they go through the app's own `LLMClient` (`judge.py`) — the production Mistral model: `faithfulness` + `answer_relevance` (LLM-judged) and `source_attribution` (regex over `[Source N]` citations). They need `MISTRAL_API_KEY`; judged metrics SKIP, never fail, when the keys are absent or the provider is unreachable, and SKIP below a half-of-cases quorum.

| File | Role |
|------|------|
| `estimate_integrity.py` | Tier 1 checks + runner; `golden.jsonl` = cases, `captured_test_plan.md` = fixture for the version check |
| `rag.py` | Tier 2 metrics + local index; `rag_golden.jsonl` = (query → expected source) cases |
| `judge.py` | LLM judge/generator for the judged metrics, via the app's `LLMClient` (production Mistral) |
| `thresholds.py` | The gate spec — every floor + one line of rationale |
| `run.py` | Aggregate gate over both tiers |

> **Skip semantics:** judged metrics SKIP (never fail) when the judge backend is unreachable; the whole RAG tier SKIPs when `sentence-transformers` is absent — so a bare CI box still runs the full deterministic tier. Add a case by appending a line to the relevant `*.jsonl`; the datasets *are* the suites.

## Roadmap

- **v0.1** ✅ Core agent + CLI + Streamlit Web UI
- **v0.2** ✅ Feedback loop — validated strategies saved to knowledge base
- **v0.3** ✅ Risk Register generation (automatic, alongside Test Strategy)
- **v0.4** ✅ Effort Estimation Report (deterministic baseline + PERT + team capacity)
- **v0.5** ✅ Auto re-ingest — file watcher, incremental ingest, manifest tracking
- **v0.6** ✅ Confidence level algorithm — score-based (0-100) with 4 factors
- **v1.0** ✅ MVP — error handling, input validation, logging, docstrings, tests, INSTALL.md, CONTRIBUTING.md, version display
- **v2.0** ✅ Cloud migration — Ollama → Mistral API + OpenRouter fallback; ChromaDB → Pinecone; deployed to Streamlit Cloud
- **v2.0.1** ✅ Stability — 27 bugs fixed across 8 files: PERT normalization, template no-op, PDF freeze, run_count bypass, session state cleanup, filename sanitization, RAG fallback, per-step exception isolation, None guards
- **v2.0.2** ✅ Stability — release-gate evals added (`evals/` — estimate integrity + RAG metrics, judged via the app's own `LLMClient`); 5 estimation/validation defects fixed (duration bounds, team restatement, name fidelity, confidence magnitude sanity, fabricated versions in Test Plan); session-state `AttributeError` crash fix; narrative duplication + truncation fixes; `LLM_NUM_PREDICT` raised to 4000; per-step generation isolation from LLM outages
- **v2.5.0** ✅ In-app Release Notes — sidebar "📋 Release Notes" panel renders CHANGELOG.md (cached via `load_changelog()`); one-time session banner on load pointing users to it
- **v2.5.1** ✅ Knowledge base — new `evaluation_audit/` content pillar (11 docs): TMMi/CMMI/ISO-IEC-33002 process maturity, ISO 19011 audit methodology + gap analysis + audit report structure, OWASP ASVS/ISO 27001/SOC 2 security-compliance audit, and 3 real public failure case studies (Knight Capital, Boeing 737 MAX MCAS, CrowdStrike 2024 outage); `ingest.py` category mapping + RAG indexing priority updated; 11 new `evals/rag_golden.jsonl` cases (context_recall@k=1.00, context_precision_mrr=0.79). First version tagged as a [GitHub release](https://github.com/gvasile29/qai-consultant/releases/tag/v2.5.1) since v1.0.0 — v2.0.0–v2.5.0 exist in `CHANGELOG.md`/`version.py` but were never individually tagged
- **v2.5.2** ✅ EU AI Act transparency patch (Article 50, deadline 2026-08-02): `src/ai_disclosure.py` (new, dependency-free) — `AI_INTERACTION_NOTICE` shown as a persistent sidebar `st.info()` (Article 50(1), not a one-time dismissible banner — the disclosure obligation doesn't lapse after first viewing); `with_ai_footer()` appends a visible "AI-generated content" label to the 4 generators' `save()` output (Risk Register, Effort Estimation, Test Strategy, Test Plan) plus, in `app.py`, to the `.md` download button data and the `markdown_to_pdf()` input for each document (Article 50(2)) — CLI coverage comes for free since `cli.py` calls the same `save()` methods. Machine-readable marking (YAML front matter, PDF metadata) stays v3.0 scope (Omnibus grace period until 2026-12-02). Assessment in `MCP_PLAN.md` section 12
- **v2.6** ✅ EU AI Act KB pillar (content-only): `knowledge_base/standards/eu_ai_act/` self-authored summaries (risk tiers, provider/deployer obligations, Article 50 transparency, Articles 9-15 testing implications for high-risk AI systems, conformity assessment, timeline); no `ingest.py` changes needed (`standards/` category mapping applies); new `evals/rag_golden.jsonl` cases; feeds the live app now, the MCP index in v3.0, and the audit tool in v3.1
- **v3.0** MCP server MVP (local stdio, fully keyless), PyPI package `qai-consultant-mcp`: `src/mcp_server.py` (FastMCP) + `src/local_index.py` (chunked in-memory cosine index over self-authored KB `.md` files, disk-cached embeddings, no Pinecone/LLM keys) + `src/kb_config.py` (dependency-free shared constants — required because `ingest.py` imports `pinecone` at module level) + `src/telemetry.py` (opt-in via `QAI_TELEMETRY=1`, PostHog, fire-and-forget, no free-text payloads; passive monitoring via PyPI/GitHub stats); tools `retrieve_qa_knowledge`, `list_kb_sources`, `estimate_qa_effort` (deterministic effort core extracted from `EffortEstimator`, no narrative); MCP prompts for the 11-question interview + Risk Register / Test Strategy / Test Plan structures; licensing gate automated in packaging tests (zero PDFs in wheel); Streamlit in-app MCP announcement (sidebar panel + one-time banner, v2.5.0 Release Notes pattern) and EU AI Act Article 50(2) machine-readable output marking (YAML front matter + PDF metadata, deadline 2026-12-02) shipping in the same release. Full spec with pinned tool contracts, per-step test suites, and 10-step build order: `MCP_PLAN.md`. Same repo as the app: isolation is architectural (separate modules, no cross-imports), not a separate repository
- **v3.1** QA maturity audit tool: `assess_qa_maturity` combining `evaluation_audit/` retrieval with a deterministic TMMi-inspired scoring rubric; gap summary JSON with cited KB sources
- **v3.2** Remote MCP + distribution: hosted Streamable HTTP server connectable from claude.ai, MCP registry submissions, server-side usage metrics complementing the opt-in client telemetry

> **MCP lens (governs all v3.x scope):** the client LLM is stronger than the internal one, so the server never exposes LLM generation. It exposes what the client cannot do alone: standards-grounded retrieval, deterministic estimation, and validated QA process templates. `ask()`/`ask_streaming()`/document generation stay in Streamlit/CLI. Former roadmap items v2.1/v2.2/v3.0-hosted/v4.0 were deleted 2026-07-14; rationale and absorbed intent in `MCP_PLAN.md`.

Keep each version's scope tight — implement incrementally in this order.

## Gotchas

- **PERT normalization:** `ACTIVITY_BREAKDOWN` percentages sum to 106–121% raw. `_pert_breakdown()` normalizes at runtime via `norm_scale`. Never remove this step when adding/editing activities.
- **Streamlit widget state:** `st.session_state["input_{key}"]` and `st.session_state.answers[key]` are separate layers. Both must be updated together when pre-filling fields (e.g. template application). Updating only `answers` leaves widgets unchanged on re-render.
- **PDF caching:** `markdown_to_pdf()` is slow (1–5s). Results are cached in `st.session_state.*_pdf_bytes` after generation. Never call it inside the tab rendering block — it re-executes on every re-render.
- **Session state cleanup:** Both "Start Over" and "Generate Another Strategy" must clear: answers, widget input keys, PDF byte caches, `_feedback_partial`, and `run_count`. Missing any key causes stale data or broken run limits across sessions.
- **Filename sanitization:** All `save()` methods apply `re.sub(r'[^\w\-.]', '_', ...)` before constructing file paths. Windows does not allow `:`, `*`, `?`, `<`, `>`, `|` in filenames — project names with these chars will crash without this guard.
- **RAG futures:** All three `ThreadPoolExecutor` future `.result()` calls are wrapped in `try/except` with fallback to `[]`. A Pinecone timeout must not abort the entire pipeline.
- **Per-step isolation:** `generate_all()` wraps each of the 4 steps (Risk, Effort, Strategy, Plan) in its own `try/except`. Failure of step 4 must not discard results from steps 1–3.
- **`render_strategy()` resumability:** the 4-stage generation pipeline is gated by an explicit `results_complete` flag (set `True` only after the PDF-bytes precompute — the final step), not by any single stage's output like `strategy`. A Streamlit rerun mid-pipeline (e.g. a websocket reconnect during the multi-minute streamed generation) re-enters the same script; gating on `strategy is None` alone let a rerun landing after stage 3 slip through as "already done" while stage 4/PDF bytes stayed unset forever. `generation_started` (set once, before any stage runs) gates the `run_count` increment so a mid-pipeline rerun doesn't re-burn the user's quota, and each of the 4 stages has its own `if st.session_state.get(X) is None: ... else: reuse` guard so a resumed run skips already-completed stages. Both `generation_started` and `results_complete` must stay in the "Start Over" and "Generate Another Strategy" cleanup lists so a genuinely new attempt is treated as fresh.
- **Never let a bare `except Exception` swallow `StopException`/`RerunException`:** Streamlit raises one of them into the running script at the next `st.*` call whenever it needs to legitimately stop or rerun (most commonly a websocket disconnect/reconnect — a long-standing Streamlit client-side race, see `streamlit/streamlit#9767` and `#11500`). On Streamlit 1.37 (this app's pin at the time this bug was found) both inherited from `Exception`, so a bare `except Exception` swallowed them — logged as an empty-message "generation failed", execution then barreled into the remaining stages on a dead session, producing bursts of empty-message failures and endless non-deterministic regeneration even after the `results_complete` resumability fix above. Each of `render_strategy()`'s 4 per-stage try/excepts has `except (StopException, RerunException): raise` BEFORE the generic `except Exception as exc:` as explicit defense against this. `streamlit==1.59.1` (current pin) already moved `ScriptControlException` to inherit from `BaseException` instead, so a bare `except Exception` can no longer catch it regardless — but keep the explicit re-raise clause anyway (belt-and-suspenders against a future downgrade or an upstream regression), and any new `try/except Exception` wrapped around `st.*` calls in this file needs the same guard.
- **`streamlit==1.59.1` pin (upgraded from 1.37.0):** the upgrade was specifically to pick up the upstream fix moving `ScriptControlException` (`StopException`/`RerunException`) to inherit from `BaseException` — see the gotcha above. No breaking API changes affected this app's Streamlit usage (`st.write_stream`, `st.tabs`, `st.form`, `st.cache_data`/`st.cache_resource`, `st.rerun`, `st.session_state`, `st.secrets` — all stable across the range). `from streamlit.runtime.scriptrunner import RerunException, StopException` still re-exports correctly at this version even though the concrete classes live in `streamlit.runtime.scriptrunner_utils.exceptions` internally — import via the public `streamlit.runtime.scriptrunner` path, not the internal module.
- **Streamlit Cloud deploy lag:** after merging to `master`, the live app's own deploy log can say `Updated app!` within seconds while the running process keeps serving the old code for 10+ minutes (observed during the v2.5.0 rollout — hard refresh, a fresh browser session, and an in-app `Rerun` all still showed the stale version). Verify the live app directly rather than trusting the log; if stale, use "Manage app" → ⋮ → **Reboot app** to force a real restart (this disrupts current users — confirm before doing it on the production URL).
