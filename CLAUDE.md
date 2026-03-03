# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

QAI Consultant is a Python-based AI agent that acts as a senior QA Architect. It collects project context via a structured 11-question dialogue, then generates Test Strategies grounded in ISTQB, OWASP, IEEE, and ISO standards using a local LLM (Mistral via Ollama) with RAG over the knowledge base.

## Development Commands

```bash
pip install -r requirements.txt          # Install dependencies

# Prerequisites: Ollama must be running with the quantized Mistral model
ollama serve
ollama pull mistral:7b-instruct-q4_0    # 4-bit quantized — ~3x faster on CPU than float16

python src/ingest.py                     # Build/rebuild ChromaDB vector store from knowledge_base/
python src/cli.py                        # Run terminal UI (Rich-based)
streamlit run src/app.py                 # Run browser UI at http://localhost:8501
```

> `chroma_db/` is gitignored — it is generated locally by `ingest.py` and must exist before running the agent.

## Architecture

**Data flow:**
```
User Input
  → DialogueManager (11 questions → ProjectContext)
  → generate_all() — parallel RAG prefetch (ThreadPoolExecutor, 2 workers)
      → [parallel] _build_risk_query()  → retrieve_knowledge(k=5) → ChromaDB
      → [parallel] context.to_rag_query() → retrieve_knowledge(k=5) → ChromaDB
  → RiskAnalyzer.analyze(context, chunks=prefetched)
      → build_risk_prompt(context, knowledge_context)
      → agent.ask_streaming(prompt) → Ollama mistral:7b-instruct-q4_0 (streamed)
      → Risk Register saved to output/
  → EffortEstimator.estimate(context, risk_register)
      → deterministic PERT + multipliers + confidence score
      → agent.ask(narrative_prompt) → Ollama (short, ~600 char prompt)
      → Effort Report saved to output/
  → StrategyGenerator.generate(context, chunks=prefetched)
      → build_strategy_prompt(context, knowledge_context)
      → agent.ask_streaming(prompt) → Ollama mistral:7b-instruct-q4_0 (streamed)
      → Test Strategy saved to output/
  → Feedback prompt → if yes/partially → saved to knowledge_base/generated_strategies/
```

### Source Files (`src/`)

| File | Role |
|------|------|
| `agent.py` | `QAIAgent` — loads ChromaDB + HuggingFace embeddings, exposes `retrieve_knowledge()`, `ask()`, `ask_streaming()`, `ask_with_rag()`; all LLM params in one config block |
| `ingest.py` | One-time pipeline: load PDFs/Markdowns → chunk (1000 chars, 200 overlap) → embed (all-MiniLM-L6-v2) → persist to `chroma_db/` |
| `dialogue.py` | `DialogueManager` + `ProjectContext` dataclass — collects 11 project fields; `to_rag_query()` builds the retrieval query |
| `strategy_generator.py` | `StrategyGenerator` — `generate_all()` prefetches RAG chunks in parallel (ThreadPoolExecutor) then runs Risk → Effort → Strategy sequentially; `generate(chunks=None)` accepts pre-fetched chunks |
| `risk_analyzer.py` | `RiskAnalyzer` — analyzes project context, builds risk-focused RAG query, generates Risk Register; `analyze(chunks=None)` accepts pre-fetched chunks |
| `effort_estimator.py` | `EffortEstimator` — deterministic baseline + multipliers + PERT calculation; LLM used only for narrative sections (no RAG) |
| `version.py` | `__version__` = "1.0.0" — version string displayed in CLI banner and Streamlit sidebar |
| `logger.py` | `get_logger()` + `setup_logging()` — centralized logging to `logs/qai_consultant.log`; file handler (DEBUG) + console handler (WARNING+) |
| `knowledge_watcher.py` | `KnowledgeBaseWatcher` + `IngestManager` + `IngestManifest` — watches `knowledge_base/` for new/changed files and incrementally re-ingests them; singleton via `get_watcher()` |
| `cli.py` | Terminal UI using `rich` — parallel RAG prefetch → Risk Register (streaming via `rich.live.Live`) → Effort spinner → Strategy (streaming via `rich.live.Live`) → feedback loop |
| `app.py` | Streamlit web UI — 4-step state machine: `intro → dialogue → review → strategy`; Risk + Strategy stream via `st.write_stream()`; results shown in 3 tabs; uses `@st.cache_resource` for agent |

### Key Configuration (`src/agent.py` config block)

```python
OLLAMA_MODEL     = "mistral:7b-instruct-q4_0"  # quantized model — change here to switch
EMBEDDING_MODEL  = "sentence-transformers/all-MiniLM-L6-v2"  # must match ingest.py
TOP_K_RESULTS    = 5          # default k for retrieve_knowledge()
RAG_K_GENERATION = 5          # k for Risk + Strategy prompts (imported by risk_analyzer, strategy_generator)
GENERATION_TIMEOUT = 300      # HTTP wall-clock timeout (seconds) — set via OllamaClient(timeout=N)

LLM_NUM_CTX     = 4096        # context window — Mistral default 32768 causes CPU hangs
LLM_NUM_PREDICT = 1500        # max output tokens — prevents runaway generation
LLM_TEMPERATURE = 0.1         # near-deterministic sampling

_ollama_client = OllamaClient(timeout=GENERATION_TIMEOUT)  # real HTTP timeout
```

> **Performance note:** `options={"timeout": N}` in `ollama.chat()` is silently ignored by Ollama.
> The real HTTP timeout must be set via `OllamaClient(timeout=N)`.
>
> `CHROMA_DIR` — absolute path to `chroma_db/` resolved from `agent.py` location.

### Generated Output

- `output/` — gitignored; timestamped markdown files:
  - `test_strategy_ProjectName_TIMESTAMP.md` — Test Strategy
  - `risk_register_ProjectName_TIMESTAMP.md` — Risk Register (v0.3)
  - `effort_estimation_ProjectName_TIMESTAMP.md` — Effort Estimation Report (v0.4)
- `chroma_db/ingest_manifest.json` — tracks ingested files with timestamps; used by auto re-ingest to detect new/changed files (v0.5)
- `knowledge_base/generated_strategies/` — validated strategies from user feedback (yes/partially); ingested on next `ingest.py` run (NEW v0.2)
- `chroma_db/` — gitignored; rebuilt by running `python src/ingest.py`

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
python -m pytest tests/ -v
```

**Test files:**
| File | Coverage |
|------|----------|
| `test_feedback_loop.py` | CLI feedback loop — 4 tests |
| `test_app_feedback_loop.py` | Streamlit feedback loop — 9 tests |
| `test_risk_analyzer.py` | RiskAnalyzer module — 7 tests |
| `test_app_v03.py` | Streamlit v0.3 Risk Register integration — 11 tests |
| `test_effort_estimator.py` | EffortEstimator — deterministic calculations, PERT, CLI/Streamlit integration — 26 tests |
| `test_knowledge_watcher.py` | KnowledgeBaseWatcher, IngestManager, IngestManifest — file detection, debounce, singleton, CLI/Streamlit integration — 23 tests |
| `test_confidence_v06.py` | Confidence score algorithm — PERT spread, capacity gap, data quality, multiplier magnitude, boundary conditions — 24 tests |
| `test_agent.py` | QAIAgent error handling + ask_streaming() — QAIKnowledgeBaseError, QAIConnectionError, QAIModelError, streaming — 8 tests |
| `test_dialogue.py` | InputValidator + DialogueManager — validation rules, submit flow, reset — 21 tests |
| `test_ollama_check.py` | Ollama connectivity checks — running/not running, model present/missing — 5 tests |
| `test_integration.py` | End-to-end pipeline — dialogue → Risk Register + Effort Report + Test Strategy — 5 tests |
| `test_performance_config.py` | Performance regression guards — LLM_NUM_CTX, LLM_NUM_PREDICT, GENERATION_TIMEOUT, RAG_K_GENERATION, OllamaClient instance, model tag — 6 tests |

> **Rule:** After every code change, run relevant tests before committing. Add new tests for every new feature.

## Roadmap

- **v0.1** ✅ Core agent + CLI + Streamlit Web UI
- **v0.2** ✅ Feedback loop — validated strategies saved to knowledge base
- **v0.3** ✅ Risk Register generation (automatic, alongside Test Strategy)
- **v0.4** ✅ Effort Estimation Report (deterministic baseline + PERT + team capacity)
- **v0.5** ✅ Auto re-ingest — watches `knowledge_base/` with file watcher, incremental ingest, manifest tracking, post-feedback immediate ingest
- **v0.6** ✅ Confidence level algorithm — score-based (0-100) with 4 factors: PERT spread, capacity gap, data quality, multiplier magnitude
- **v0.7** HuggingFace integration — `download_knowledge_base.py` so users don't need to build KB manually
- **v0.8** Community knowledge — launch LinkedIn Poll Series (10 polls ready) + run expert knowledge extraction sessions using prompts in `knowledge_base/expert_knowledge/`
- **v1.0** ✅ MVP — error handling, input validation, logging, docstrings, tests, INSTALL.md, CONTRIBUTING.md, version display
- **v2.0** HuggingFace integration — easy KB download for new users
- **v2.1** Community knowledge — LinkedIn Poll Series + expert knowledge extraction sessions
- **v3.0** Hosted version — shared KB, quality gate, VPS deployment
- **v4.0** Multi-LLM support (OpenAI, Claude API, Gemini, and more)

Keep each version's scope tight — implement incrementally in this order.
