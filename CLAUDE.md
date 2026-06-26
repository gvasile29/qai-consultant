# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

QAI Consultant is a Python-based AI agent that acts as a senior QA Architect. It collects project context via a structured 11-question dialogue, then generates Test Strategies grounded in ISTQB, OWASP, IEEE, and ISO standards using a cloud LLM (Mistral API, with OpenRouter fallback) and RAG over a Pinecone vector knowledge base.

**Deployed:** https://appi-consultant-esodgczvwpmozzybuhdhek.streamlit.app

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
  → generate_all() — parallel RAG prefetch (ThreadPoolExecutor, 2 workers)
      → [parallel] _build_risk_query()  → retrieve_knowledge(k=5) → Pinecone
      → [parallel] context.to_rag_query() → retrieve_knowledge(k=5) → Pinecone
  → RiskAnalyzer.analyze(context, chunks=prefetched)
      → build_risk_prompt(context, knowledge_context)
      → agent.ask_streaming(prompt) → Mistral API / OpenRouter (streamed)
      → Risk Register saved to output/
  → EffortEstimator.estimate(context, risk_register)
      → deterministic PERT + multipliers + confidence score
      → agent.ask(narrative_prompt) → Mistral API (short, ~600 char prompt)
      → Effort Report saved to output/
  → StrategyGenerator.generate(context, chunks=prefetched)
      → build_strategy_prompt(context, knowledge_context)
      → agent.ask_streaming(prompt) → Mistral API / OpenRouter (streamed)
      → Test Strategy saved to output/
  → Feedback prompt → if yes/partially → saved to knowledge_base/generated_strategies/
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
| `version.py` | `__version__` = "2.0.0" — version string displayed in CLI banner and Streamlit sidebar |
| `logger.py` | `get_logger()` + `setup_logging()` — centralized logging to `logs/qai_consultant.log`; file handler (DEBUG) + console handler (WARNING+) |
| `cli.py` | Terminal UI using `rich` — parallel RAG prefetch → Risk Register (streaming via `rich.live.Live`) → Effort spinner → Strategy (streaming via `rich.live.Live`) → feedback loop |
| `app.py` | Streamlit web UI — 4-step state machine: `intro → dialogue → review → strategy`; Risk + Strategy stream via `st.write_stream()`; results shown in 3 tabs; uses `@st.cache_resource` for agent |

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

### Contents

- **`standards/istqb/`** — 14 ISTQB certification PDFs (CTFL, CTAL-TA, CTAL-TM, CTAL-TAE, CT-AI, CT-GenAI, CT-MBT, CT-ATLaS, CT-MAT, CTel-ITP, and more)
- **`standards/owasp/`** — WSTG v4.2 PDF, MASTG PDF, OWASP Top 10 2021 (HTML + MD)
- **`standards/`** — IEEE 829, ISO/IEC 25010, ISO 26262, A-SPICE (all Markdown)
- **`methodologies/`** — 5 guides (Agile, BDD/TDD, Exploratory, Risk-Based, Test Pyramid); each ends with a "QAI Consultant application" section
- **`expert_knowledge/`** — Contribution framework with PROMPT files for AI-assisted knowledge extraction interviews; `Scenario_TeamAlignment.md` is the first real scenario
- **`articles/`** — 10 real-world AI QA case studies with quantified outcomes

### RAG indexing priority
Index OWASP Top 10 MD + methodology MDs first (structured), then ISTQB/OWASP PDFs, then expert knowledge and articles as supplementary.

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

## Roadmap

- **v0.1** ✅ Core agent + CLI + Streamlit Web UI
- **v0.2** ✅ Feedback loop — validated strategies saved to knowledge base
- **v0.3** ✅ Risk Register generation (automatic, alongside Test Strategy)
- **v0.4** ✅ Effort Estimation Report (deterministic baseline + PERT + team capacity)
- **v0.5** ✅ Auto re-ingest — file watcher, incremental ingest, manifest tracking
- **v0.6** ✅ Confidence level algorithm — score-based (0-100) with 4 factors
- **v1.0** ✅ MVP — error handling, input validation, logging, docstrings, tests, INSTALL.md, CONTRIBUTING.md, version display
- **v2.0** ✅ Cloud migration — Ollama → Mistral API + OpenRouter fallback; ChromaDB → Pinecone; deployed to Streamlit Cloud
- **v2.1** HuggingFace KB — `download_knowledge_base.py` so new users don't need to build the KB manually
- **v2.2** Community knowledge — LinkedIn Poll Series + expert knowledge extraction sessions
- **v3.0** Hosted version — shared KB, quality gate, VPS deployment
- **v4.0** Multi-LLM support (OpenAI, Claude API, Gemini, and more)

Keep each version's scope tight — implement incrementally in this order.
