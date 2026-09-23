# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

QAI Consultant is a Python-based AI agent that acts as a senior QA Architect. It collects project context via a structured 11-question dialogue, then generates Test Strategies grounded in ISTQB, OWASP, IEEE, and ISO standards using a cloud LLM (Mistral API, with OpenRouter fallback) and RAG over a Pinecone vector knowledge base.

**Deployed:** https://quality-ai-consultant.streamlit.app
**Latest GitHub release:** [v3.5.2](https://github.com/gvasile29/qai-consultant/releases/tag/v3.5.2) (2026-09-15, tagged on `master`). v3.4/v3.4.1 (and v2.0.0–v2.5.0) shipped without an individual tag/release; v3.5.0/v3.5.1 never got a tag or GitHub release either (v3.5.0's PyPI publish step was skipped entirely, and v3.5.1 was published then yanked the same day for being unresolvable — see the Gotchas entry on the `[tool.uv.sources]` incident). Treat `version.py` as the source of truth for "what's actually on `master`", not the latest tag, when in doubt.

## Development Commands

```bash
pip install -r requirements.txt          # Runtime dependencies
pip install -r requirements-dev.txt      # + ruff + pytest (for development)

# Prerequisites: copy .env.example → .env and fill in the 4 API keys
cp .env.example .env

python src/ingest.py                     # Build/rebuild Pinecone index from knowledge_base/
python src/cli.py                        # Run terminal UI (Rich-based)
streamlit run src/app.py                 # Run browser UI at http://localhost:8501
python src/mcp_server.py                 # Run the MCP server locally (stdio, fully keyless)

ruff check src/ tests/                   # Lint (config in ruff.toml)
```

Required environment variables (`.env` or Streamlit Cloud secrets):
```
MISTRAL_API_KEY=...
OPENROUTER_API_KEY=...
PINECONE_API_KEY=...
PINECONE_INDEX_NAME=qai-consultant
```

## Browser / UI Testing

See the `browser-ui-testing` skill (`.claude/skills/browser-ui-testing/`) before verifying any Streamlit UI change — it covers the Playwright-CLI-over-MCP-tools default and how to scale review process to change risk.

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
| `kb_config.py` | (v3.0) Dependency-free (stdlib only) shared KB constants — `EMBEDDING_MODEL`, `CHUNK_SIZE`/`CHUNK_OVERLAP`, `SOURCE_CATEGORIES`/`get_source_category()`. Single source of truth `agent.py`, `ingest.py`, `evals/rag.py`, and `local_index.py` all import instead of each carrying their own copy; kept free of third-party imports specifically so it's importable from the keyless MCP server path (`ingest.py` imports `pinecone` at module level, `agent.py` pulls in Streamlit-adjacent code — neither can be) |
| `kb_manifest.py` | `KB_MANIFEST` — single source of truth for the Streamlit sidebar's "Knowledge Base" panel: maps curated display groups (emoji + label) to real paths under `knowledge_base/`; `app.py` checks each path's existence before rendering a bullet, so the UI can never advertise content that isn't actually there. `tests/test_kb_manifest.py` guards that every real top-level KB subfolder (except `generated_strategies/`) is represented. Streamlit-only — not in the MCP package's `py-modules` whitelist |
| `dialogue.py` | `DialogueManager` + `ProjectContext` dataclass — collects 11 project fields; `to_rag_query()` builds the retrieval query |
| `templates.py` | `TEMPLATES` dict — quick-start project profiles (e.g. `web_app`) that pre-fill all 11 dialogue fields at once; consumed by `app.py`'s template picker. See the "Streamlit widget state" gotcha below for the two-layer session-state update this requires |
| `strategy_generator.py` | `StrategyGenerator` — `generate_all(results_summary=None)` prefetches RAG chunks in parallel (ThreadPoolExecutor) then runs Risk → Effort → Strategy sequentially, passing `results_summary` through to the Risk step (v3.1 F2); `generate(chunks=None)` accepts pre-fetched chunks |
| `test_plan_generator.py` | `TestPlanGenerator` — the 4th `generate_all()` stage; builds an IEEE 829-aligned Test Plan via RAG + LLM (`ask_streaming`), taking the Risk Register as input to prioritize test cases and resource allocation. Same `generate(chunks=None)`/`save()` shape as `risk_analyzer.py`/`strategy_generator.py` |
| `risk_analyzer.py` | `RiskAnalyzer` — analyzes project context, builds risk-focused RAG query, generates Risk Register; `analyze(chunks=None, results_summary=None)` accepts pre-fetched chunks and an optional execution-data summary (v3.1 F2); `append_execution_data_appendix()` deterministically appends it regardless of what the LLM wrote |
| `effort_core.py` | (v3.0) The deterministic PERT/multiplier/confidence pipeline extracted out of `EffortEstimator`, zero agent/LLM dependency in its import graph — what the MCP server's `estimate_qa_effort` tool calls directly, so that path never needs `agent.py` (Pinecone/Mistral/OpenAI/Streamlit). `EffortEstimator` delegates here for the numbers and adds the LLM narrative on top for the Streamlit/CLI report; tests call effort_core's functions directly (the wrapper methods that used to exist purely for tests were deleted 2026-09-17) |
| `effort_estimator.py` | `EffortEstimator` — deterministic baseline + multipliers + PERT calculation (delegates to `effort_core.py`); LLM used only for narrative sections (no RAG) |
| `review_core.py` | (v3.1 F1) Deterministic, dependency-free QA Document Quality Review: `review_document(text, doc_type="auto")` scores an existing Test Plan/Strategy/test case list 0-100 across 6 weighted dimensions, returns `ReviewResult` (findings carry `citation_queries`, resolved to KB citations by the caller — MCP via `LocalIndex`, Streamlit/CLI via `retrieve_knowledge()`). No LLM, no agent import — same import-graph tier as `effort_core.py` |
| `results_core.py` | (v3.1 F2) Deterministic, dependency-free test-results health analysis: `parse_junit_xml()`/`parse_results_csv()` → `TestRecord` list → `analyze()` computes flaky/ever-failing/never-run/slowest/failure-clustering into `ResultsAnalysis`; `summarize_for_prompt()` builds the bounded text block that grounds the Risk Register. No file I/O, no LLM |
| `maturity_core.py` | (v3.5) Deterministic, dependency-free QA process-maturity assessment: `assess_maturity(text)` scores 10 TMMi Level 2/3 process areas from a free-text description or pasted document, returning an indicative TMMi level (1-3, never 4-5 per TMMi's own no-skip/no-certification rule) plus a conditional 7-check EU AI Act Articles 9-15 readiness dimension (only scored when the input signals an AI/ML system — otherwise omitted, not scored as a false 0). Findings carry `citation_queries`, resolved to KB citations by the caller (MCP via `LocalIndex`, Streamlit/CLI via `retrieve_knowledge()`). No LLM, no agent import — same import-graph tier as `review_core.py`/`results_core.py` |
| `maturity_generator.py` | (v3.5) LLM narrative + save() for `maturity_core.py`'s output — mirrors `review_generator.py`'s shape (`build_maturity_prompt()`, `build_maturity_report_markdown()`, `save_maturity_report()`) so `cli.py --maturity` and `app.py`'s maturity mode share one prompt/save path. Streamlit/CLI only, not in the MCP server's import graph |
| `review_generator.py` | (v3.1 F1) LLM narrative + save() for `review_core.py`'s output — mirrors `risk_analyzer.py`/`strategy_generator.py`'s shape (`build_review_prompt()`, `build_review_report_markdown()`, `save_review_report()`) so `cli.py --review` and `app.py`'s review mode share one prompt/save path. Streamlit/CLI only, not in the MCP server's import graph |
| `ai_disclosure.py` | Dependency-free EU AI Act Article 50 transparency notices: `AI_INTERACTION_NOTICE` (sidebar, Art 50(1)), `with_ai_footer()` (visible "AI-generated" document footer, Art 50(2)), `build_front_matter()`/`pdf_meta_html()` (machine-readable marking), and (v3.3) `pdf_icon_html()` — a base64 data-URI `<img>` tag embedding the EU Code of Practice's "Fully AI-Generated" icon (Art 50(4)) into a PDF export's `<body>` via `pdf_export.py`'s `extra_body_html` param; the Streamlit sidebar embeds the same icon's SVG variants directly instead (`app.py`) |
| `pdf_export.py` | `markdown_to_pdf()` — converts a generated document's markdown to styled PDF bytes via `xhtml2pdf`, for `app.py`'s PDF download buttons; `extra_body_html` param (v3.3) injects `ai_disclosure.py`'s `pdf_icon_html()` badge. Renders raster images (PNG) via base64 data URIs but not SVG — see the Gotchas entry below. Slow (1-5s); see the "PDF caching" gotcha for why it must never run inside the tab render loop |
| `version.py` | `__version__` — version string displayed in CLI banner and Streamlit sidebar (see `src/version.py` for the current value; kept in lockstep with `pyproject.toml` per the Release Checklist below) |
| `theme.py` | (v3.4) "Calibration Bench" visual identity system — `LIGHT_TOKENS`/`DARK_TOKENS` (surface/ink/line/accent + `pass_`/`hold`/`fail` signal colors, WCAG AA-verified), `build_css(tokens)` (pure function → `<style>` block, unit-testable without a Streamlit runtime — see `tests/test_theme.py`), `inject_theme_css()` (picks tokens via `st.context.theme.type`, same mechanism `app.py`'s `st.logo()` already used). `build_css()`'s output includes the pre-existing `.st-key-header-logo [data-testid="stImage"]` centering rule (carried over verbatim, not reintroduced) plus the new `.ledger-card`, `.signal-ledger`, and `table.risk-ledger` component styles |
| `_theme_fonts.py` | (v3.4, generated) IBM Plex Mono (400/500), Plex Sans (400/600), Plex Sans Condensed (700) embedded as base64 `woff2` data URIs — no client-side font CDN call. Consumed only by `theme.py`'s `build_css()` |
| `components.py` | (consolidated 2026-09-17 from `ledger_components.py`/`landing_hero.py`/`interactive_flow_style.py`/`output_screen_style.py`) Reusable Streamlit HTML/CSS component builders — Signal Ledger + Risk Ledger table (`score_tier`, `signal_ledger_html`, `risk_ledger_table_html`), the landing hero + "How it works"/"What you get" cards (`build_landing_hero_html`, `build_landing_deliverables_html`), dialogue/review/sidebar styling (`build_dialogue_header_html`, `build_review_summary_html`, `build_sidebar_polish_css`), and output-screen styling (`build_output_eyebrow_html`, `build_stage_sequence_html`, `build_content_polish_css`, `build_doc_review_input_tray_css`). All pure functions (token dict [+ plain args] → HTML string), no Streamlit dependency, directly unit-testable — see `tests/test_components.py`. The four source modules were split by which "Power-On Sequence" redesign PR touched them (v3.4-v3.4.3), not by functional boundary; consolidated per `docs/superpowers/plans/2026-09-17-architecture-cleanup.md`. `theme.py`/`_theme_fonts.py` are untouched and stay separate (tokens/base CSS, and generated font data respectively) |
| `risk_ledger.py` | (v3.4) Deterministic, dependency-free parser for the "Risk Matrix Overview" markdown table `risk_analyzer.py`'s prompt forces the LLM to emit: `parse_risk_matrix(markdown_text)` → list of `{risk_id, description, likelihood, impact, risk_level, priority}` dicts, `severity_tier(risk_level)` (Low→`pass`, Medium→`hold`, High/Critical→`fail`). `_strip_markdown_emphasis()` strips stray `**bold**`/`*italic*` markdown that real Mistral output routinely wraps table cells in (found via live browser QA, not by any prompt requirement) before `components.risk_ledger_table_html()` HTML-escapes the cells — otherwise literal asterisks render in the browser. Never raises; same tier as `results_core.py`/`review_core.py` |
| `logger.py` | `get_logger()` + `setup_logging()` — centralized logging to `logs/qai_consultant.log`; file handler (DEBUG) + console handler (WARNING+) |
| `visit_counter.py` | (v3.1.1, fixed v3.1.2/v3.1.3) `get_and_increment_visit_count()` — Streamlit-only visit counter persisted in Pinecone's `app-metrics` namespace (isolated from the RAG `knowledge-base` namespace), fixed vector ID `visit_counter`, `{"count": <int>}` metadata; fetch→increment→upsert, wrapped in `try/except Exception: return None` so it never crashes the app. The upserted placeholder vector (`DUMMY_VECTOR`) must not be all-zero — see the Gotchas entry below |
| `mcp_server.py` | (v3.0) The MCP server itself (FastMCP, local stdio, fully keyless — no Pinecone/Mistral/OpenRouter/Streamlit in its import graph). 6 `@mcp.tool()`s: `retrieve_qa_knowledge`, `list_kb_sources` (both via `local_index.py`), `estimate_qa_effort` (via `effort_core.py`), `review_qa_document` (v3.1 F1, via `review_core.py`), `analyze_test_results` (v3.1 F2, via `results_core.py`), and `assess_qa_maturity` (v3.5, deterministic TMMi + conditional EU AI Act readiness assessment, resolves `citation_queries` via `LocalIndex`) — plus 4 `@mcp.prompt()`s from `prompts.py`. `main()` calls `index.warmup_embedder()` before `mcp.run()`; never move that back to lazy/first-call — see the Windows deadlock Gotchas entry below. Packaged as `qai-consultant-mcp` on PyPI; run directly with `python src/mcp_server.py` |
| `local_index.py` | (v3.0) `LocalIndex` — fully local, keyless, in-memory cosine-similarity index over `knowledge_base/**/*.md` only (no PDFs — see the licensing gate below), chunked 1000/200 like `ingest.py` (via `kb_config.py`) so served results match production RAG, disk-cached embeddings. `warmup_embedder()` (v3.1.6, cheap — model construction + one `embed_query()`) is separate from the expensive lazy `_ensure_built()` (full corpus embed, deferred to the first real `search()`/`list_sources()` call) — see the two MCP-attach-timeout Gotchas entries below for why they were split. As of v3.5.3, embeddings come from `fastembed` (ONNX Runtime) instead of `sentence-transformers`/`torch` via `HuggingFaceEmbeddings` — see the embedding-backend-simplification spec. |
| `prompts.py` | (v3.0) Static, parameter-free MCP `@mcp.prompt()` templates extracted from this project's own generators' structural sections (not the LLM-call plumbing, which stays Streamlit/CLI-only): `qa_project_interview` (the 11-question intake) plus `*_structure` prompts so an MCP client can produce Risk Register/Test Strategy/Test Plan documents shaped like the app's own output, grounded via `retrieve_qa_knowledge`/`estimate_qa_effort` instead of a second internal LLM call |
| `telemetry.py` | (v3.0) Opt-in MCP usage telemetry, disabled unless `QAI_TELEMETRY=1`. Single plain HTTPS POST per event to PostHog (no SDK), fire-and-forget from a daemon thread, 2s timeout, every exception swallowed, no retries/disk buffering, no free-text payloads — a telemetry failure must never break or slow a tool call |
| `cli.py` | Terminal UI using `rich` — parallel RAG prefetch → Risk Register (streaming via `rich.live.Live`) → Effort spinner → Strategy (streaming via `rich.live.Live`) → feedback loop. `--review PATH [--doc-type ...]` (v3.1 F1) and `--results PATH ...` (v3.1 F2) argparse flags: `--review` runs `run_review_mode()` and exits without the interactive dialogue; `--results` threads a `results_summary` into the normal flow's Risk Register step. `--maturity path/to/description.txt` (v3.5) mirrors `--review`'s shape for the QA Maturity Assessment |
| `app.py` | Streamlit web UI — state machine: `intro → dialogue → review → strategy` plus `doc_review` (v3.1 F1, `render_doc_review()`); Risk + Strategy + Test Plan stream via `st.write_stream()`; results shown in 4 tabs; PDF bytes cached in session state after generation; uses `@st.cache_resource` for agent. `render_review()` has an optional "Attach test execution results" expander (v3.1 F2) storing `st.session_state.results_analysis`, consumed by the Risk Register step. `REVIEW_MODE_STATE_KEYS` is the single list of doc_review's session-state keys, consumed by both "Start Over" and "Generate Another Strategy" plus the mode's own reset buttons; v3.5 adds a `maturity` step (`render_maturity_assessment()`) with its own `MATURITY_MODE_STATE_KEYS` cleanup list wired the same way as `REVIEW_MODE_STATE_KEYS` |

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

`tests/test_changelog.py` also guards the release checklist itself: `test_pyproject_version_matches_version_py` fails if `pyproject.toml`'s version drifts from `src/version.py`'s `__version__`, and `test_changelog_top_entry_has_content` fails if a version bump adds a bare CHANGELOG heading with no actual bullet content underneath it.

> **Rule:** After every code change, run relevant tests before committing. Add new tests for every new feature.

> **Baseline (v3.0.0):** 317 passed, 0 known errors. The `test_full_estimate_bmw` / `test_risk_analyzer` live-`agent`-fixture tests documented as errors as of v2.0.1 now pass directly (SKIP without API keys, per their own fixtures) rather than erroring — this baseline note had drifted stale relative to the growing suite well before v3.0; the table above is similarly incomplete (many test files added since v2.0.1/v2.5.x/v3.0 aren't listed) and due for a fuller audit, out of scope for this release.

## Evals (`evals/` — release gate)

A release gate that treats the app like a model under test ("are the numbers and documents it produces honest?"), separate from `tests/`. The former tier-1 deterministic checks (estimate, review, results, maturity integrity) migrated to ordinary pytest test modules in `tests/` on 2026-09-17, leaving one remaining tier: rag/local_index_parity. The remaining eval functions (`rag`, `local_index_parity`) are still standalone module-level runners — there is no `tests/` wrapper for them by design; the 4 former tier-1 modules moved to ordinary pytest tests instead (see below).

```bash
pytest tests/test_estimate_integrity.py         # tier 1 (formerly evals-det): estimate checks
pytest tests/test_review_integrity.py           # tier 1 (formerly evals-det): v3.1 F1 rubric checks
pytest tests/test_results_integrity.py          # tier 1 (formerly evals-det): v3.1 F2 results-analysis checks
pytest tests/test_maturity_integrity.py         # tier 1 (formerly evals-det): v3.5 maturity checks
python -m evals.run                  # tier 2 only (rag/local_index_parity)
```

**Tier 1 (deterministic, keyless, CI-safe — 4 modules, now ordinary pytest tests as of 2026-09-17):**
- `estimate_integrity`: runs the *real shipped* `InputValidator` / `EffortEstimator` (stubs only the heavy `agent` module) on golden inputs. 5 metrics: `duration_bounds`, `team_restatement_invariance`, `name_display_fidelity`, `confidence_magnitude_sanity`, `no_fabricated_versions`.
- `review_integrity` (v3.1): runs the real shipped `review_core.review_document()` (no stub needed — dependency-free). 4 metrics: `score_ordering`, `dimension_attribution`, `determinism`, `insufficient_content_handling`.
- `results_integrity` (v3.1): runs the real shipped `results_core.analyze()`/parsers (no stub needed). 4 metrics: `flaky_and_ever_failing_boundaries`, `cluster_count`, `malformed_input_never_crashes`, `csv_xml_parity`.
- `maturity_integrity` (v3.5): runs the real shipped `maturity_core.assess_maturity()` (no stub needed — dependency-free). 6 metrics: `level_ordering`, `no_level_skip`, `ai_act_gating`, `determinism`, `negation_not_counted_as_evidence`, `insufficient_content_handling`.

No LLM, no API keys in any of the four; a red row names a real defect in the shipped logic.

**Tier 2 — `rag` (classical RAG metrics, fully local):** builds an in-memory cosine index over `knowledge_base/*.md` with the app's own embedding model (`all-MiniLM-L6-v2`, same `langchain_community` import as `src/agent.py`) — no Pinecone, no keys. 5 metrics. Keyless: `context_recall@k` + `context_precision_mrr` (reuse the `expects` labels). Need a generated answer, so they go through the app's own `LLMClient` (`judge.py`) — the production Mistral model: `faithfulness` + `answer_relevance` (LLM-judged) and `source_attribution` (regex over `[Source N]` citations). They need `MISTRAL_API_KEY`; judged metrics SKIP, never fail, when the keys are absent or the provider is unreachable, and SKIP below a half-of-cases quorum.

| File | Role |
|------|------|
| `estimate_integrity.py` | Tier 1 checks + runner; `golden.jsonl` = cases, `captured_test_plan.md` = fixture for the version check |
| `review_integrity.py` | (v3.1) Tier 1 checks + runner; `review_golden.jsonl` = cases, `fixtures/review/*.md` = document fixtures (strong/weak/vague-measurability) |
| `results_integrity.py` | (v3.1) Tier 1 checks + runner; `results_golden.jsonl` = cases, `fixtures/results/*.xml`/`.csv` = JUnit/CSV fixtures (3-run flaky/ever-failing set, failure-cluster set, malformed XML, XML/CSV parity pair) |
| `maturity_integrity.py` | (v3.5) Tier 1 checks + runner; `maturity_golden.jsonl` = cases, `fixtures/maturity/*.txt` = description fixtures |
| `rag.py` | Tier 2 metrics + local index; `rag_golden.jsonl` = (query → expected source) cases |
| `local_index_parity.py` | Tier 2, keyless but not dependency-free (needs the embedding stack): reruns `rag.py`'s Context Recall@k / MRR metrics against the real `src/local_index.LocalIndex` (chunked 1000/200, what the MCP server actually serves) instead of `rag.py`'s coarser doc-level 4000-char index, so a chunking/category/cache regression that only shows up at chunk granularity doesn't slip past the doc-level eval. `python -m evals.local_index_parity` |
| `judge.py` | LLM judge/generator for the judged metrics, via the app's `LLMClient` (production Mistral) |
| `thresholds.py` | The gate spec — every floor + one line of rationale |
| `run.py` | Aggregate gate over the single remaining tier (rag/local_index_parity); tier-1 pytest tests are now invoked directly by CI, not via this runner |

> **Skip semantics:** judged metrics SKIP (never fail) when the judge backend is unreachable; the whole RAG tier SKIPs when `sentence-transformers` is absent — so a bare CI box still gets the deterministic checks via `pytest tests/`, independent of whether the RAG tier can run. Add a case by appending a line to the relevant `*.jsonl`; the datasets *are* the suites.

## CI

GitHub Actions (`.github/workflows/ci.yml`) runs on every push/PR to `main`/`master`:

| Job | Blocking? | What it checks |
|-----|-----------|-----------------|
| `test` | Yes | `pytest tests/` on Python 3.11 (single version as of 2026-09-17 — see Gotchas; this also runs the former evals-det tier-1 checks, now ordinary pytest tests) |
| `quality` | Yes | `ruff check src/ tests/`, `mypy src/`, `bandit -r src/ -ll` — merged into one job as of 2026-09-17 (was 3 separate jobs: `lint`, `typecheck`, `security-bandit`) |
| `security-pip-audit` | **No** | `pip-audit -r requirements.txt --desc` — non-blocking. The 10-CVE backlog (langchain/nltk/transformers family) was cleared in PR #62, but this job stays non-blocking on purpose: a new CVE can land in a transitive dependency with no fixed version yet published, which would block unrelated PRs with no way out. Promote once there's an allowlist/waiver mechanism for exactly that case. |
| `coverage` | Yes | `pytest --cov=src --cov-fail-under=60` — the coverage floor is the measured `ubuntu-latest` baseline (60.88%) at the time this gate was added, rounded down; it can only be raised over time, never silently regress. Measured locally on Windows first (61.36%) — the two platforms differ enough (fewer tests execute on Linux; some skip there) that the floor had to be set from the CI runner's own number, not the dev machine's. |

`security-pip-audit` uses `continue-on-error: true` (not a shell-level `|| true`) so its findings stay visible as a neutral/warning status in the PR checks list and in the job's `$GITHUB_STEP_SUMMARY`, without blocking merge. The `quality` job (which replaced the three separate `lint`/`typecheck`/`security-bandit` jobs as of 2026-09-17) does not use `continue-on-error` — a failure there now fails the job for real, same as `test`.

A separate workflow, `.github/workflows/live-contract-tests.yml`, runs nightly (`0 3 * * *`) and via manual `workflow_dispatch` against real Pinecone/Mistral/OpenRouter — `tests/test_live_contracts.py`'s `test_pinecone_roundtrip`/`test_mistral_completion`/`test_openrouter_fallback`. It never triggers on `push`/`pull_request`, so it can never block a PR by construction. It needs `MISTRAL_API_KEY`/`OPENROUTER_API_KEY`/`PINECONE_API_KEY`/`PINECONE_INDEX_NAME` configured as GitHub Actions repository secrets (separate from Streamlit Cloud's own secrets store) — until they're added, every test in it SKIPs silently rather than failing. The Pinecone test writes only to a dedicated `ci-contract-tests` namespace, isolated from `knowledge-base` and `app-metrics`, and cleans up after itself; the fetch retries up to 3 times (1.5s apart) to absorb serverless-index eventual consistency without masking a real contract break. The Mistral and OpenRouter tests go through the real `agent.LLMClient` code path (not raw SDK calls) — `test_openrouter_fallback` mocks `llm_client._mistral.chat.complete` to raise, forcing the real Mistral-to-OpenRouter fallback branch to execute against the real OpenRouter API — so a break in message-building, response extraction, or the fallback logic itself is caught here too, not just an auth/model-name/endpoint break. The workflow's `run:` block starts with `set -o pipefail`, per the `tee`-swallows-exit-code gotcha documented below — without it, this job would report green even on a real contract break.

**Removed in v3.5.3:** the weekly Dependency Drift Canary workflow (`.github/workflows/dependency-drift-check.yml`) existed to manage a ~99-entry fully-pinned transitive lock; once the fastembed backend switch (v3.5.3) removed torch/sentence-transformers/langchain-community and shrank that list by roughly a third of its former size, re-running `uv pip compile` by hand before each MCP release became sufficient, and the workflow (plus its auto-close-every-Dependabot-PR side effect) was deleted. Historical design spec: `docs/superpowers/specs/2026-09-03-dependency-drift-canary-design.md`.

## Roadmap

Full version history and rationale lives in `CHANGELOG.md` — this is a condensed index, not the source of truth.

- **v0.1–v1.0** ✅ Core agent, CLI, Streamlit UI, feedback loop, Risk Register, Effort Estimation, confidence scoring, MVP hardening (error handling, tests, docs)
- **v2.0–v2.0.2** ✅ Cloud migration (Ollama→Mistral+OpenRouter, ChromaDB→Pinecone, Streamlit Cloud) + stability/eval hardening
- **v2.5.0–v2.6** ✅ In-app Release Notes; `evaluation_audit/` KB pillar; EU AI Act Article 50 transparency (notices, footers, machine-readable marking) + KB pillar
- **v3.0** ✅ MCP server MVP (`qai-consultant-mcp` on PyPI) — keyless local stdio server (`src/mcp_server.py` + `src/local_index.py` + `src/kb_config.py`), tools `retrieve_qa_knowledge`/`list_kb_sources`/`estimate_qa_effort`, `src/prompts.py` MCP prompts, licensing gate in `tests/test_packaging.py` (zero PDFs/HTML in the wheel). Design rationale (the "MCP lens"): `MCP_PLAN.md`.
- **v3.1–v3.1.6** ✅ Evaluation Package — `review_qa_document` + `analyze_test_results` MCP tools, Streamlit doc-review/results modes, CLI flags — plus visit counter (see the Pinecone all-zero-vector Gotcha) and MCP registry/distribution fixes (`mcp>=2.0` breaking upgrade, cold-start attach timeout — see the MCP warmup Gotcha).
- **v3.2** ✅ CI quality gates completion — nightly `live-contract-tests.yml` against real Pinecone/Mistral/OpenRouter, SKIPs without secrets, never blocks a PR.
- **v3.3–v3.3.1** ✅ EU AI Act "Fully AI-Generated" icon (sidebar SVG + PDF PNG badge) + an MCP attach-reliability fix (dependency-pinning saga, see Gotchas).
- **v3.4–v3.4.4** ✅ "Calibration Bench" visual redesign in 3 phases (landing → interactive flow → output screens, each via `superpowers:subagent-driven-development` with independent implementer+reviewer per task plus a final whole-branch review) + further MCP dependency-pinning fixes. Full incident history: `docs/postmortems/2026-09-mcp-dependency-pinning-saga.md`.
- **v3.5.0–v3.5.3** ✅ QA Maturity Assessment (`assess_qa_maturity` tool, TMMi-based, `src/maturity_core.py`) + keyword-matching fixes (see the QA Maturity Gotcha) + MCP embedding backend switched to `fastembed`, dropping torch/sentence-transformers/langchain-community.
- **v4.0** Remote MCP + distribution: hosted Streamable HTTP server connectable from claude.ai, registry submissions, server-side usage metrics.

> **MCP lens (governs all v3.x scope):** the client LLM is stronger than the internal one, so the server never exposes LLM generation — only what the client can't do alone (standards-grounded retrieval, deterministic estimation, validated QA process templates). `ask()`/`ask_streaming()`/document generation stay in Streamlit/CLI. Rationale: `MCP_PLAN.md`.

Keep each version's scope tight — implement incrementally in this order, and consult `CHANGELOG.md` for full detail on any entry above.

## Release Checklist

See the `release-checklist` skill (`.claude/skills/release-checklist/`) whenever bumping `__version__` — it lists every file to update together and the merge gate, and ends by running the `claude-md-hygiene` skill so CLAUDE.md doesn't bloat back up release over release.

## Gotchas

> This section is condensed to the actionable rule + why. Where a full incident writeup exists, it's linked — read that before touching the related code for real.

- **PERT normalization:** `ACTIVITY_BREAKDOWN` percentages sum to 106–121% raw. `_pert_breakdown()` normalizes at runtime via `norm_scale`. Never remove this step when adding/editing activities.
- **Streamlit widget state:** `st.session_state["input_{key}"]` and `st.session_state.answers[key]` are separate layers. Both must be updated together when pre-filling fields (e.g. template application).
- **PDF caching:** `markdown_to_pdf()` is slow (1–5s). Results are cached in `st.session_state.*_pdf_bytes`. Never call it inside the tab rendering block.
- **Session state cleanup:** "Start Over" and "Generate Another Strategy" must clear answers, widget input keys, PDF byte caches, `_feedback_partial`, `run_count`, plus the F1/F2/maturity mode keys (`REVIEW_MODE_STATE_KEYS`, `results_analysis`+`results_uploader`, `MATURITY_MODE_STATE_KEYS`). Missing any key causes stale data or broken run limits.
- **Filename sanitization:** All `save()` methods apply `re.sub(r'[^\w\-.]', '_', ...)` before constructing file paths — Windows disallows `:`, `*`, `?`, `<`, `>`, `|`.
- **RAG futures:** All three `ThreadPoolExecutor` future `.result()` calls are wrapped in `try/except` with fallback to `[]`. A Pinecone timeout must not abort the pipeline.
- **Pinecone rejects all-zero dense vectors:** `index.upsert()` raises `[400] Dense vectors must contain at least one non-zero value` if every component is `0.0`. Root cause of the v3.1.1 visit counter silently never incrementing (`DUMMY_VECTOR` was `[0.0]*384`, and the swallowing `except Exception: return None` hid it) — fixed in v3.1.2 with a non-zero placeholder + a `logger.warning()` on the caught exception. Any future placeholder/dummy vector upserted to Pinecone must not be all-zero.
- **Per-step isolation:** `generate_all()` wraps each of the 4 steps (Risk, Effort, Strategy, Plan) in its own `try/except`. Failure of step 4 must not discard results from steps 1–3. (Had zero test coverage of the actual `except` branches until the 2026-09-22 gap review — see `tests/test_strategy_generator.py`.)
- **MCP server: embedding-model warmup must happen before `mcp.run()`**, not lazily on first call — a Windows-specific deadlock between the `mcp` SDK's stdin-reader thread and the embedding backend's native runtime first-init. Full incident history: `docs/postmortems/2026-07-30-mcp-windows-stdio-deadlock.md`. Re-verified against fastembed/onnxruntime before the v3.5.3 backend switch — the hazard is about any native runtime's first init, not torch specifically.
- **FastMCP `pre_parse_json` silently coerces JSON-array-shaped string arguments into real lists.** It runs on every string argument before Pydantic validation, so a parameter typed plain `str` fails the moment a client sends the JSON-array form. Fix: type it `Optional[Union[str, list]]` (a real `Union`) and branch on `isinstance(value, list)` in the tool body. (`analyze_test_results`'s multi-run `junit_xml` argument.)
- **`render_strategy()` resumability:** gated by an explicit `results_complete` flag (set only after the final PDF-bytes precompute), not by any single stage's output — a mid-pipeline Streamlit rerun (e.g. websocket reconnect) must not treat an incomplete run as done. `generation_started` gates the `run_count` increment so a rerun doesn't re-burn quota; each of the 4 stages has its own `if st.session_state.get(X) is None: ... else: reuse` guard. Both flags must stay in the cleanup lists.
- **Never let a bare `except Exception` swallow `StopException`/`RerunException`** — Streamlit raises one of these to legitimately stop/rerun the script. Any `try/except Exception` around `st.*` calls needs `except (StopException, RerunException): raise` first. Fixed by the `streamlit==1.59.1` pin (these now inherit from `BaseException`) — import via the public `streamlit.runtime.scriptrunner` path. Full incident history: `docs/postmortems/2026-08-streamlit-scriptcontrolexception-swallowed.md`.
- **Streamlit Cloud deploy lag:** a merge to `master` can serve stale code for 10+ minutes despite the deploy log saying `Updated app!`. "Reboot app" restarts the process but doesn't always force a fresh `git pull` (a stale `CHANGELOG.md` read straight off disk once survived a reboot + hard refresh). The only reliable fix is pushing a new commit to the tracked branch, which fires the GitHub webhook and forces a real fresh clone.
- **`command | tee -a "$GITHUB_STEP_SUMMARY"` silently swallows the command's real exit code** — every "blocking" CI job needs `set -o pipefail` as the first line of its `run:` block. Full incident history: `docs/postmortems/2026-08-tee-pipefail-ci-gate.md`.
- **Every CI job must install dev tools via `pip install -r requirements-dev.txt`, never a bespoke unpinned `pip install <tool>`** — an unpinned `pip install ruff` once picked up a much newer ruff with a larger default rule set and failed CI on a docs-only push, purely from tooling drift.
- **Streamlit CSS scoping via `st.container(key=...)`:** a blanket `[data-testid="stImage"]` rule applies to every `st.image()` call in the app. Scope per-instance via `st.container(key="...")`, which generates a `st-key-<key>` class (used for the header logo vs. the EU AI icon).
- **xhtml2pdf renders raster images (PNG) via base64 data URIs but not SVG** — any image added to a PDF export (`pdf_export.py`'s `extra_body_html`) needs a PNG, not SVG.
- **A module-level import allowlist test can silently block a legitimate stdlib addition** — `tests/test_ai_act_marking.py` AST-walks `ai_disclosure.py` and asserts every import's top-level name is allowlisted. The test's job is blocking third-party/heavy imports, not stdlib ones; update the allowlist when adding a stdlib import there.
- **Every entry in `pyproject.toml`'s `[project] dependencies` must be exact-pinned (`==`), never a loose bound** — enforced by `tests/test_packaging.py::test_all_dependencies_are_exact_pinned`. `uvx qai-consultant-mcp` resolves against PyPI's live index on every launch, so a loose bound can push cold-start past Claude Desktop's ~60s timeout. Full incident history: `docs/postmortems/2026-09-mcp-dependency-pinning-saga.md`.
- **`page.screenshot(full_page=True)` silently crops a Streamlit page** when it has independently-scrolling containers (`stMain`/`stSidebarContent` scroll within a fixed-height `stApp`). Use the `full_screenshot()` helper in `scripts/verify_visual_common.py` (measures true content height via `page.evaluate()`, grows the viewport, captures, restores) instead of `page.screenshot(full_page=True)` directly.
- **Hover CSS on real Streamlit buttons must exclude primary buttons from `color` overrides** — Streamlit's default primary button is a red fill with a white label; overriding just the label color on hover can drop contrast far below WCAG AA while the fill stays red. Scope `color` changes to `button:not([data-testid$="-primary"]):hover`; `border-color` is safe unscoped.
- **A pinned-but-unupgradeable `transformers` version can carry known CVEs that are still safe to accept** if the vulnerable code path (attacker-controlled model repo ID) is unreachable — this project always calls `HuggingFaceEmbeddings` with a hardcoded model name. Superseded in v3.5.3: the fastembed switch removed `transformers`/`sentence-transformers`/`torch` from the MCP package's dependencies entirely.
- **A single-package Dependabot security-update PR against `pyproject.toml` can desynchronize the fully-resolved transitive lock** — `[project] dependencies` there is one `uv pip compile` run's mutually-consistent output; close such a PR manually and regenerate the whole array instead of merging it. Design spec: `docs/superpowers/specs/2026-09-03-dependency-drift-canary-design.md`.
- **A version bump merged to `master` is not the same as a version published to PyPI** — check `pypi.org/pypi/qai-consultant-mcp/json`'s `info.version` before assuming an MCP-surface change is live; the `twine upload` step is human-gated and has been skipped before (v3.5.0 sat un-published for days with no error anywhere).
- **QA Maturity's keyword-based evidence detection will keep missing paraphrased practices** — `maturity_core.py`'s checks are fixed keyword/phrase lists by design (dependency-free, no LLM). Treat each false-negative report as a data point and weigh false-positive risk before broadening any keyword list.
- **A project-local `[tool.uv.sources]`/`[[tool.uv.index]]` index scoping is invisible to real `uvx`/`pip` consumers** — it only applies when `uv` resolves this repo's own `pyproject.toml` directly. Verify any per-package index scoping via `uvx --from <published-package>==<version> ...` from a directory with no ambient project files. Full incident history: `docs/postmortems/2026-09-mcp-dependency-pinning-saga.md`.
- **Renaming/merging a CI job's `name:` requires updating branch protection's required status checks FIRST**, before the job-name change lands — otherwise the old required check names stop reporting forever and block every future PR.
- **The eval/CI gates don't catch every gap — a periodic senior-architect review still finds real ones.** The 2026-09-22 pass closed 8 findings not caught by any automated gate: untested per-step-isolation `except` branches, a fixable CVE backlog in `requirements.txt`, unguarded file-upload sizes, an unbounded query cache, non-rotating logs, a stale index cache with no eviction, and unsanitized YAML front-matter fields. See PR #95 for the full list.
