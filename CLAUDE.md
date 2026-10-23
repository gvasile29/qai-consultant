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
python scripts/usage_report.py           # Visits, runs, downloads, feedback (Pinecone) + MCP installs (PyPI)

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

### Source Files (`src/qai_consultant/`)

**Package layout.** `src/app.py` stays a real Streamlit script (a shim would freeze the UI); `src/{cli,ingest,mcp_server}.py` are 5-line shims for the documented commands. Dependency direction is strict, and only the first three tiers ship in the wheel; `tests/system/release/test_package_layout.py` enforces both:

| Tier | Modules | Wheel |
|------|---------|-------|
| `common/` | version, logger, kb_config, telemetry, text_checks | yes |
| `core/` | dialogue, effort_core, review_core, results_core, maturity_core, risk_ledger | yes (may import `common`) |
| `mcp/` | server, prompts, local_index | yes (may import `common`, `core`) |
| `rag/`, `generation/`, `compliance/`, `ui/`, `observability/` | app side (agent, ingest, generators, guards, theme, counters) | no |

Table paths below are relative to `src/qai_consultant/`. The table lists only modules with constraints the code doesn't show (rationale, import-tier rules); other modules are discoverable from the tree.

| File | Role |
|------|------|
| `rag/agent.py` | `QAIAgent` — connects to Pinecone + HuggingFace embeddings; `LLMClient` wraps Mistral API (primary) + OpenRouter (fallback); exposes `retrieve_knowledge()`, `ask()`, `ask_streaming()`, `ask_with_rag()`; `_get_secret()` reads from `.env` or Streamlit secrets |
| `common/kb_config.py` | (v3.0) Dependency-free (stdlib only) shared KB constants — `EMBEDDING_MODEL`, `CHUNK_SIZE`/`CHUNK_OVERLAP`, `SOURCE_CATEGORIES`/`get_source_category()`. Single source of truth `agent.py`, `ingest.py`, `evals/rag.py`, and `local_index.py` all import instead of each carrying their own copy; kept free of third-party imports specifically so it's importable from the keyless MCP server path (`ingest.py` imports `pinecone` at module level, `agent.py` pulls in Streamlit-adjacent code — neither can be) |
| `core/effort_core.py` | (v3.0) The deterministic PERT/multiplier/confidence pipeline extracted out of `EffortEstimator`, zero agent/LLM dependency in its import graph — what the MCP server's `estimate_qa_effort` tool calls directly, so that path never needs `agent.py` (Pinecone/Mistral/OpenAI/Streamlit). `EffortEstimator` delegates here for the numbers and adds the LLM narrative on top for the Streamlit/CLI report; tests call effort_core's functions directly (the wrapper methods that used to exist purely for tests were deleted 2026-09-17) |
| `core/review_core.py` | (v3.1 F1) Deterministic, dependency-free QA Document Quality Review: `review_document(text, doc_type="auto")` scores an existing Test Plan/Strategy/test case list 0-100 across 6 weighted dimensions, returns `ReviewResult` (findings carry `citation_queries`, resolved to KB citations by the caller — MCP via `LocalIndex`, Streamlit/CLI via `retrieve_knowledge()`). No LLM, no agent import — same import-graph tier as `effort_core.py` |
| `core/results_core.py` | (v3.1 F2) Deterministic, dependency-free test-results health analysis: `parse_junit_xml()`/`parse_results_csv()` → `TestRecord` list → `analyze()` computes flaky/ever-failing/never-run/slowest/failure-clustering into `ResultsAnalysis`; `summarize_for_prompt()` builds the bounded text block that grounds the Risk Register. No file I/O, no LLM |
| `core/maturity_core.py` | (v3.5) Deterministic, dependency-free QA process-maturity assessment: `assess_maturity(text)` scores 10 TMMi Level 2/3 process areas from a free-text description or pasted document, returning an indicative TMMi level (1-3, never 4-5 per TMMi's own no-skip/no-certification rule) plus a conditional 7-check EU AI Act Articles 9-15 readiness dimension (only scored when the input signals an AI/ML system — otherwise omitted, not scored as a false 0). Findings carry `citation_queries`, resolved to KB citations by the caller (MCP via `LocalIndex`, Streamlit/CLI via `retrieve_knowledge()`). No LLM, no agent import — same import-graph tier as `review_core.py`/`results_core.py` |
| `compliance/ai_disclosure.py` | Dependency-free EU AI Act Article 50 transparency notices: `AI_INTERACTION_NOTICE` (sidebar, Art 50(1)), `with_ai_footer()` (visible "AI-generated" document footer, Art 50(2)), `build_front_matter()`/`pdf_meta_html()` (machine-readable marking), and (v3.3) `pdf_icon_html()` — a base64 data-URI `<img>` tag embedding the EU Code of Practice's "Fully AI-Generated" icon (Art 50(4)) into a PDF export's `<body>` via `pdf_export.py`'s `extra_body_html` param; the Streamlit sidebar embeds the same icon's SVG variants directly instead (`app.py`) |
| `compliance/output_guards.py` | Dependency-free honesty guards for LLM documents: prompt rule blocks (`GROUNDING_RULES` no invented project facts, `CITATION_RULES` no unverifiable section numbers/quotes, `STANDARDS_RULES` no "ISTQB-mandated") embedded by every generator prompt, plus `sanitize_llm_markdown()` (lone `**`, standards overstatements, section refs absent from the prompt) applied inside `agent.clean_markdown_html(text, source_text=prompt)` at every sink. From the 2026-10 exploratory QA pass; guarded by `tests/unit/compliance/test_output_guards.py` |
| `core/risk_ledger.py` | (v3.4) Deterministic, dependency-free parser for the "Risk Matrix Overview" markdown table `risk_analyzer.py`'s prompt forces the LLM to emit: `parse_risk_matrix(markdown_text)` → list of `{risk_id, description, likelihood, impact, risk_level, priority}` dicts, `severity_tier(risk_level)` (Low→`pass`, Medium→`hold`, High/Critical→`fail`). `_strip_markdown_emphasis()` strips stray `**bold**`/`*italic*` markdown that real Mistral output routinely wraps table cells in (found via live browser QA, not by any prompt requirement) before `components.risk_ledger_table_html()` HTML-escapes the cells — otherwise literal asterisks render in the browser. Never raises; same tier as `results_core.py`/`review_core.py`. As of v3.5.4 also used by `effort_core.risk_buffer()` (count Risk Level per row), so it ships in the MCP wheel |
| `observability/usage_guard.py` | (v3.6.0) Server-side daily run limits that survive a new session (unlike `run_count`): a global daily cap + a best-effort per-client cap keyed on a date-salted SHA-256 of the client IP (raw IP never stored; skipped for private/loopback addresses so users behind one proxy can't lock each other out). Counters live in Pinecone's `app-metrics` namespace. Fails open on any store error. Limits overridable via `QAI_GLOBAL_DAILY_RUN_LIMIT` / `QAI_CLIENT_DAILY_RUN_LIMIT` (defaults 100 / 10). `app.py`'s `_enforce_daily_quota()` calls it at all 3 run-consuming sites |
| `observability/visit_counter.py` | (v3.1.1; generalized v3.7.0) Streamlit-only usage counters in Pinecone's `app-metrics` namespace, one vector per counter (`{"count": n}`): `visit_counter`, `download_<doc>_<md|pdf>` (every `st.download_button` needs `on_click=_track_download` — guarded by `tests/unit/observability/test_visit_counter.py`), `feedback_<yes|partially|no>`. Never raises; `record_event()` increments on a daemon thread. `DUMMY_VECTOR` must not be all-zero — see Gotchas |
| `mcp/server.py` | (v3.0) The MCP server itself (FastMCP, local stdio, fully keyless — no Pinecone/Mistral/OpenRouter/Streamlit in its import graph). 6 `@mcp.tool()`s: `retrieve_qa_knowledge`, `list_kb_sources` (both via `local_index.py`), `estimate_qa_effort` (via `effort_core.py`), `review_qa_document` (v3.1 F1, via `review_core.py`), `analyze_test_results` (v3.1 F2, via `results_core.py`), and `assess_qa_maturity` (v3.5, deterministic TMMi + conditional EU AI Act readiness assessment, resolves `citation_queries` via `LocalIndex`) — plus 4 `@mcp.prompt()`s from `prompts.py`. `main()` calls `index.warmup_embedder()` before `mcp.run()`; never move that back to lazy/first-call — see the Windows deadlock Gotchas entry below. Packaged as `qai-consultant-mcp` on PyPI; run directly with `python src/mcp_server.py` (a shim for `qai_consultant.mcp.server`) |
| `mcp/local_index.py` | (v3.0) `LocalIndex` — fully local, keyless, in-memory cosine-similarity index over `knowledge_base/**/*.md` only (no PDFs — see the licensing gate in `tests/system/release/test_packaging.py`), chunked 1000/200 like `ingest.py` (via `kb_config.py`) so served results match production RAG, disk-cached embeddings. `warmup_embedder()` (v3.1.6, cheap — model construction + one `embed_query()`) is separate from the expensive lazy `_ensure_built()` (full corpus embed, deferred to the first real `search()`/`list_sources()` call) — see the two MCP-attach-timeout Gotchas entries below for why they were split. As of v3.5.3, embeddings come from `fastembed` (ONNX Runtime) instead of `sentence-transformers`/`torch` via `HuggingFaceEmbeddings` — see the embedding-backend-simplification spec. |
| `mcp/prompts.py` | (v3.0) Static, parameter-free MCP `@mcp.prompt()` templates extracted from this project's own generators' structural sections (not the LLM-call plumbing, which stays Streamlit/CLI-only): `qa_project_interview` (the 11-question intake) plus `*_structure` prompts so an MCP client can produce Risk Register/Test Strategy/Test Plan documents shaped like the app's own output, grounded via `retrieve_qa_knowledge`/`estimate_qa_effort` instead of a second internal LLM call |
| `common/telemetry.py` | (v3.0; default-on since v3.7.0) MCP usage telemetry, off via `QAI_TELEMETRY=0`/`DO_NOT_TRACK=1`, stderr notice at startup, per-process id never persisted (ePrivacy). Single HTTPS POST to PostHog, daemon thread, 2s timeout, all exceptions swallowed, no free-text. `tests/conftest.py` + CI `env:` keep tests/CI from reporting |
| `../app.py` (at `src/app.py`) | Streamlit web UI — state machine: `intro → dialogue → review → strategy` plus `doc_review` (v3.1 F1, `render_doc_review()`); Risk + Strategy + Test Plan stream via `st.write_stream()`; results shown in 4 tabs; PDF bytes cached in session state after generation; uses `@st.cache_resource` for agent. `render_review()` has an optional "Attach test execution results" expander (v3.1 F2) storing `st.session_state.results_analysis`, consumed by the Risk Register step. `REVIEW_MODE_STATE_KEYS` is the single list of doc_review's session-state keys, consumed by both "Start Over" and "Generate Another Strategy" plus the mode's own reset buttons; v3.5 adds a `maturity` step (`render_maturity_assessment()`) with its own `MATURITY_MODE_STATE_KEYS` cleanup list wired the same way as `REVIEW_MODE_STATE_KEYS` |

### Key Configuration (`src/qai_consultant/rag/agent.py` config block)

`PINECONE_NAMESPACE` (`knowledge-base`) must equal the one in `rag/ingest.py`; `EMBEDDING_MODEL` is shared via `common/kb_config.py`. Other constants (`TOP_K_RESULTS`, `LLM_NUM_PREDICT`, ...) are in the config block itself.

> **LLMClient fallback:** Mistral API is tried first. On any exception, OpenRouter is used automatically, sending `OPENROUTER_MODELS` as OpenRouter's `models` fallback array (max 3 entries). Both failing raises `QAIConnectionError`. The OpenRouter account has no credits: every entry must stay `:free` and never an `openrouter/*` auto-router (live, `openrouter/free` routed a Risk Register to a content-safety classifier that answered "User Safety: safe") — enforced by `tests/unit/rag/test_llm_client.py::test_openrouter_fallback_chain_uses_only_free_models`. Free tier = 50 requests/day (~12 full generations) until a one-time $10 credit purchase lifts it to 1,000/day.

## Knowledge Base

All agent outputs are grounded in documents from `knowledge_base/`. Re-run `ingest.py` after adding new files.

## Testing

Tests live in `tests/<level>/<feature>/test_*.py`. The level folder is also a pytest marker (applied automatically in `tests/conftest.py`, registered in `pyproject.toml`), so `pytest tests/unit` and `pytest -m unit` select the same files. Keep test file basenames unique across the tree (no `__init__.py`, so duplicates collide).

| Level | What belongs there |
|-------|--------------------|
| `unit/` | One module, collaborators mocked, no network |
| `integration/` | Several real modules together with a mocked LLM/Pinecone; includes the former evals tier-1 `*_integrity` checks |
| `system/` | A whole surface driven end to end without live services: Streamlit (`ui/`, AppTest), CLI flags, the MCP server, packaging/changelog/skill-doc guards (`release/`) |
| `e2e/` | Live Pinecone/Mistral/OpenRouter or real model downloads; SKIP without secrets (nightly `live-contract-tests.yml`) |

Feature folders: `estimation`, `review`, `results`, `maturity`, `generation` (risk/strategy/test plan), `dialogue`, `rag` (agent, LLM client, local index, KB), `ui`, `cli`, `mcp`, `compliance` (AI Act, output guards, PDF), `observability` (telemetry, usage, visits, logging), `release`. A feature folder exists only under the levels that have files for it. New tests go in the matching `<level>/<feature>/` folder.

```bash
python -m pytest tests/ -v                                   # all tests
python -m pytest tests/unit -v                               # one level (or: -m unit)
python -m pytest tests/unit/rag/test_agent.py -v             # single file
python -m pytest tests/unit/rag/test_agent.py::test_kb_missing_raises_error -v
```

`tests/system/release/test_changelog.py` also guards the release checklist itself: `test_pyproject_version_matches_version_py` fails if `pyproject.toml`'s version drifts from `common/version.py`'s `__version__`, and `test_changelog_top_entry_has_content` fails if a version bump adds a bare CHANGELOG heading with no actual bullet content underneath it.

> **Rule:** After every code change, run relevant tests before committing. Add new tests for every new feature.

## Evals (`evals/` — release gate)

A release gate that treats the app like a model under test ("are the numbers and documents it produces honest?"), separate from `tests/`. The former tier-1 deterministic checks (estimate, review, results, maturity integrity) migrated to ordinary pytest test modules in `tests/` on 2026-09-17, leaving one remaining tier: rag/local_index_parity. The remaining eval functions (`rag`, `local_index_parity`) are still standalone module-level runners — there is no `tests/` wrapper for them by design; the 4 former tier-1 modules moved to ordinary pytest tests instead (see below).

```bash
pytest tests/integration/estimation/test_estimate_integrity.py         # tier 1 (formerly evals-det): estimate checks
pytest tests/integration/review/test_review_integrity.py           # tier 1 (formerly evals-det): v3.1 F1 rubric checks
pytest tests/integration/results/test_results_integrity.py          # tier 1 (formerly evals-det): v3.1 F2 results-analysis checks
pytest tests/integration/maturity/test_maturity_integrity.py         # tier 1 (formerly evals-det): v3.5 maturity checks
python -m evals.run                  # tier 2 only (rag/local_index_parity)
```

**Tier 1 (deterministic, keyless, CI-safe — 4 modules, now ordinary pytest tests as of 2026-09-17):**
- `estimate_integrity`: runs the *real shipped* `InputValidator` / `EffortEstimator` (stubs only the heavy `agent` module) on golden inputs. 5 metrics: `duration_bounds`, `team_restatement_invariance`, `name_display_fidelity`, `confidence_magnitude_sanity`, `no_fabricated_versions`.
- `review_integrity` (v3.1): runs the real shipped `review_core.review_document()` (no stub needed — dependency-free). 4 metrics: `score_ordering`, `dimension_attribution`, `determinism`, `insufficient_content_handling`.
- `results_integrity` (v3.1): runs the real shipped `results_core.analyze()`/parsers (no stub needed). 4 metrics: `flaky_and_ever_failing_boundaries`, `cluster_count`, `malformed_input_never_crashes`, `csv_xml_parity`.
- `maturity_integrity` (v3.5): runs the real shipped `maturity_core.assess_maturity()` (no stub needed — dependency-free). 6 metrics: `level_ordering`, `no_level_skip`, `ai_act_gating`, `determinism`, `negation_not_counted_as_evidence`, `insufficient_content_handling`.

No LLM, no API keys in any of the four; a red row names a real defect in the shipped logic.

**Tier 2 — `rag` (classical RAG metrics, fully local):** builds an in-memory cosine index over `knowledge_base/*.md` with the app's own embedding model (`all-MiniLM-L6-v2`, same `langchain_community` import as `rag/agent.py`) — no Pinecone, no keys. 5 metrics. Keyless: `context_recall@k` + `context_precision_mrr` (reuse the `expects` labels). Need a generated answer, so they go through the app's own `LLMClient` (`judge.py`) — the production Mistral model: `faithfulness` + `answer_relevance` (LLM-judged) and `source_attribution` (regex over `[Source N]` citations). They need `MISTRAL_API_KEY`; judged metrics SKIP, never fail, when the keys are absent or the provider is unreachable, and SKIP below a half-of-cases quorum.

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

A separate workflow, `.github/workflows/live-contract-tests.yml`, runs nightly (`0 3 * * *`) and via `workflow_dispatch` against real Pinecone/Mistral/OpenRouter (`tests/e2e/rag/test_live_contracts.py`: `test_pinecone_roundtrip`/`test_mistral_completion`/`test_openrouter_fallback`). It never triggers on `push`/`pull_request`, so it can never block a PR. It needs the 4 API keys as GitHub Actions repository secrets (separate from Streamlit Cloud's); without them every test SKIPs. The Pinecone test writes only to the `ci-contract-tests` namespace and cleans up (fetch retries 3x for eventual consistency). The LLM tests go through the real `agent.LLMClient` path; `test_openrouter_fallback` forces the Mistral-to-OpenRouter branch against the real OpenRouter API. The `run:` block starts with `set -o pipefail` (see the `tee` gotcha below).

**Removed in v3.5.3:** the weekly Dependency Drift Canary workflow (`dependency-drift-check.yml`); after the fastembed switch shrank the pinned transitive lock, re-running `uv pip compile` by hand before each MCP release is enough. Spec: `docs/superpowers/specs/2026-09-03-dependency-drift-canary-design.md`.

## Roadmap

Full version history and rationale lives in `CHANGELOG.md` — this is a condensed index, not the source of truth.

- **v0.1–v3.9.3** ✅ shipped; version history and rationale live in `CHANGELOG.md` (git log has the PRs).
- **v4.0** Remote MCP + distribution: hosted Streamable HTTP server connectable from claude.ai, registry submissions, server-side usage metrics.

> **MCP lens (governs all v3.x scope):** the client LLM is stronger than the internal one, so the server never exposes LLM generation — only what the client can't do alone (standards-grounded retrieval, deterministic estimation, validated QA process templates). `ask()`/`ask_streaming()`/document generation stay in Streamlit/CLI. Rationale: `MCP_PLAN.md`.

Keep each version's scope tight — implement incrementally in this order, and consult `CHANGELOG.md` for full detail on any entry above.

## Release Checklist

See the `release-checklist` skill (`.claude/skills/release-checklist/`) whenever bumping `__version__` — it lists every file to update together and the merge gate, and ends by running the `claude-md-hygiene` skill so CLAUDE.md doesn't bloat back up release over release.

## Gotchas

> This section is condensed to the actionable rule + why. Where a full incident writeup exists, it's linked — read that before touching the related code for real.

- **PERT normalization:** `ACTIVITY_BREAKDOWN` percentages sum to 106–121% raw. `_pert_breakdown()` normalizes at runtime via `norm_scale`. Never remove this step when adding/editing activities.
- **Streamlit/PDF/session-state gotchas** (widget-state layers, PDF caching, session cleanup lists, `render_strategy()` resumability, xhtml2pdf images, hover CSS, screenshots) live in the `streamlit-gotchas` skill — load it before editing `src/app.py`, `ui/` or `compliance/pdf_export.py`.
- **Filename sanitization:** All `save()` methods apply `re.sub(r'[^\w\-.]', '_', ...)` before constructing file paths — Windows disallows `:`, `*`, `?`, `<`, `>`, `|`.
- **RAG futures:** All three `ThreadPoolExecutor` future `.result()` calls are wrapped in `try/except` with fallback to `[]`. A Pinecone timeout must not abort the pipeline.
- **Pinecone rejects all-zero dense vectors** (`[400] Dense vectors must contain at least one non-zero value`): the v3.1.1 visit counter silently never incremented because `DUMMY_VECTOR` was all zeros and a swallowing `except` hid it. Any placeholder vector must be non-zero.
- **`LLMClient._chat_stream()` may only fall back to OpenRouter before the first chunk is yielded** — OpenRouter restarts the document from scratch, so a mid-stream fallback duplicates the already-shown opening; after the first chunk it raises `QAIConnectionError` instead.
- **Per-step isolation:** `generate_all()` wraps each of the 4 steps (Risk, Effort, Strategy, Plan) in its own `try/except`. Failure of step 4 must not discard results from steps 1–3. (Had zero test coverage of the actual `except` branches until the 2026-09-22 gap review — see `tests/unit/generation/test_strategy_generator.py`.)
- **MCP server: embedding-model warmup must happen before `mcp.run()`**, not lazily on first call — a Windows deadlock between the `mcp` SDK's stdin-reader thread and any native runtime's first init (also true for fastembed/onnxruntime). Postmortem: `docs/postmortems/2026-07-30-mcp-windows-stdio-deadlock.md`.
- **FastMCP `pre_parse_json` silently coerces JSON-array-shaped string arguments into real lists.** It runs on every string argument before Pydantic validation, so a parameter typed plain `str` fails the moment a client sends the JSON-array form. Fix: type it `Optional[Union[str, list]]` (a real `Union`) and branch on `isinstance(value, list)` in the tool body. (`analyze_test_results`'s multi-run `junit_xml` argument.)
- **Never let a bare `except Exception` swallow `StopException`/`RerunException`** — any `try/except Exception` around `st.*` calls needs `except (StopException, RerunException): raise` first (import via `streamlit.runtime.scriptrunner`). Postmortem: `docs/postmortems/2026-08-streamlit-scriptcontrolexception-swallowed.md`.
- **Streamlit Cloud deploy lag:** a merge to `master` can serve stale code for 10+ minutes despite `Updated app!`; "Reboot app" doesn't always re-pull. Only pushing a new commit to the tracked branch forces a fresh clone.
- **`command | tee -a "$GITHUB_STEP_SUMMARY"` silently swallows the command's real exit code** — every "blocking" CI job needs `set -o pipefail` as the first line of its `run:` block. Full incident history: `docs/postmortems/2026-08-tee-pipefail-ci-gate.md`.
- **Every CI job must install dev tools via `pip install -r requirements-dev.txt`, never a bespoke unpinned `pip install <tool>`** — an unpinned `pip install ruff` once picked up a much newer ruff with a larger default rule set and failed CI on a docs-only push, purely from tooling drift.
- **Never use `st.image()` in `app.py`** — its media-file-manager entries can expire into a broken image (alt text `0`). Inline base64 data URIs via `components.header_logo_html()`/`inline_image_html()`; `tests/unit/compliance/test_output_guards.py` fails if `st.image` returns.
- **A module-level import allowlist test can silently block a legitimate stdlib addition** — `tests/unit/compliance/test_ai_act_marking.py` AST-walks `ai_disclosure.py` and asserts every import's top-level name is allowlisted. The test's job is blocking third-party/heavy imports, not stdlib ones; update the allowlist when adding a stdlib import there.
- **Every entry in `pyproject.toml`'s `[project] dependencies` must be exact-pinned (`==`), never a loose bound** — enforced by `tests/system/release/test_packaging.py::test_all_dependencies_are_exact_pinned`. `uvx qai-consultant-mcp` resolves against PyPI's live index on every launch, so a loose bound can push cold-start past Claude Desktop's ~60s timeout. Full incident history: `docs/postmortems/2026-09-mcp-dependency-pinning-saga.md`.
- **A single-package Dependabot security-update PR against `pyproject.toml` can desynchronize the fully-resolved transitive lock** — `[project] dependencies` there is one `uv pip compile` run's mutually-consistent output; close such a PR manually and regenerate the whole array instead of merging it. Design spec: `docs/superpowers/specs/2026-09-03-dependency-drift-canary-design.md`.
- **A version bump merged to `master` is not the same as a version published to PyPI** — check `pypi.org/pypi/qai-consultant-mcp/json`'s `info.version` before assuming an MCP-surface change is live; the `twine upload` step is human-gated and has been skipped before (v3.5.0 sat un-published for days with no error anywhere).
- **QA Maturity's keyword-based evidence detection will keep missing paraphrased practices** — `maturity_core.py`'s checks are fixed keyword/phrase lists by design (dependency-free, no LLM). Treat each false-negative report as a data point and weigh false-positive risk before broadening any keyword list.
- **A project-local `[tool.uv.sources]`/`[[tool.uv.index]]` index scoping is invisible to real `uvx`/`pip` consumers.** Verify via `uvx --from <published-package>==<version> ...` from a directory with no project files. Postmortem: `docs/postmortems/2026-09-mcp-dependency-pinning-saga.md`.
- **Renaming/merging a CI job's `name:` requires updating branch protection's required status checks FIRST**, before the job-name change lands — otherwise the old required check names stop reporting forever and block every future PR.
- **Mistral's Free plan 429s `mistral-small`/`medium`/`magistral` (code 1300) at near-zero usage while serving the Ministral family** — a plan/tier block, not rate limiting; probe several models. It went unnoticed ~3 weeks (from ~2026-09-03) because `LLMClient` silently fell back to OpenRouter; check OpenRouter's Activity page for fallback spikes (local logs only go back to 2026-09-22).
- **Exact-pinned packages don't pin the embedding model's files** — fastembed downloads `Qdrant/all-MiniLM-L6-v2-onnx` from HF `main` into `%TEMP%/fastembed_cache`, so an upstream model-repo edit can break installs with no package change (#105). When a KB-tool bug won't reproduce, check the HF commit history and test with `FASTEMBED_CACHE_PATH` + `HF_HUB_OFFLINE=1`.
- **Generated documents must pass through `output_guards.sanitize_llm_markdown()` and new generator prompts must embed `GROUNDING_RULES`/`CITATION_RULES`** — prompt rules alone failed in live runs; `scripts/llm_e2e_smoke.py`'s `lint_output` is the gate. Also: no `st.form` in the dialogue (first-Enter race), match effort keywords as whole words ("CANoe" contains "no"). PR #121.
- **Word overlap can't validate that a `[Source N]` citation supports its sentence** (tried 2026-10-19: both flagged citations were valid). A real check needs an LLM judge or a human; `output_guards` only drops markers whose N isn't in the prompt and unquotes non-verbatim quotes.
- **`src/ingest.py` (and `qai_consultant.rag.ingest.main`) has no argparse: ANY invocation, including `--help`, deletes and re-uploads the production Pinecone `knowledge-base` namespace.** Verify the entry point only by import or mocks, never by running it.
- **The wheel excludes `qai_consultant/cli.py` via `setup.py`'s `build_py` override** (`packages.find` cannot exclude a single module); `test_packaging.py` forbids it. New wheel code goes into `common/`, `core/` or `mcp/` only.
- **A periodic senior-architect review still finds gaps no automated gate catches** (the 2026-09-22 pass closed 8: untested `except` branches, a CVE backlog, unguarded uploads, unbounded caches, non-rotating logs, unsanitized YAML fields); see PR #95.
