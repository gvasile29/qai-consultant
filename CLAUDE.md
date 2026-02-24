# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

QAI Consultant is a Python-based AI agent that acts as a senior QA Architect. It collects project context via a structured 11-question dialogue, then generates Test Strategies grounded in ISTQB, OWASP, IEEE, and ISO standards using a local LLM (Mistral via Ollama) with RAG over the knowledge base.

## Development Commands

```bash
pip install -r requirements.txt          # Install dependencies

# Prerequisites: Ollama must be running with Mistral
ollama serve
ollama pull mistral

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
  → RiskAnalyzer.analyze(context)          ← NEW v0.3
      → _build_risk_query() → agent.retrieve_knowledge() → ChromaDB
      → build_risk_prompt(context, knowledge_context)
      → agent.ask(prompt) → Ollama Mistral
      → Risk Register saved to output/
  → StrategyGenerator.generate(context)
      → context.to_rag_query() → agent.retrieve_knowledge() → ChromaDB similarity search
      → build_strategy_prompt(context, knowledge_context)
      → agent.ask(prompt) → Ollama Mistral
      → Test Strategy saved to output/
  → Feedback prompt → if yes/partially → saved to knowledge_base/generated_strategies/  ← NEW v0.2
```

### Source Files (`src/`)

| File | Role |
|------|------|
| `agent.py` | `QAIAgent` — loads ChromaDB + HuggingFace embeddings, exposes `retrieve_knowledge()`, `ask()`, `ask_with_rag()` |
| `ingest.py` | One-time pipeline: load PDFs/Markdowns → chunk (1000 chars, 200 overlap) → embed (all-MiniLM-L6-v2) → persist to `chroma_db/` |
| `dialogue.py` | `DialogueManager` + `ProjectContext` dataclass — collects 11 project fields; `to_rag_query()` builds the retrieval query |
| `strategy_generator.py` | `StrategyGenerator` — orchestrates retrieve (k=8) → prompt → generate → save to `output/` with timestamp; `generate_all()` generates both Strategy + Risk Register |
| `risk_analyzer.py` | `RiskAnalyzer` — analyzes project context, builds risk-focused RAG query, generates Risk Register with matrix + mitigations |
| `cli.py` | Terminal UI using `rich` — multi-phase flow: banner → load agent → dialogue → review → generate (Risk Register + Strategy) → feedback loop |
| `app.py` | Streamlit web UI — 4-step state machine: `intro → dialogue → review → strategy`; results shown in two tabs (Risk Register / Test Strategy); uses `@st.cache_resource` for agent |

### Key Configuration (hardcoded in source)

- `OLLAMA_MODEL = "mistral"` — change in `agent.py` to switch models
- `EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"` — must match between ingest and agent
- `TOP_K_RESULTS = 5` (agent default), `k=8` used in strategy generation
- `CHROMA_DIR` — absolute path to `chroma_db/` resolved from `agent.py` location

### Generated Output

- `output/` — gitignored; timestamped markdown files:
  - `test_strategy_ProjectName_TIMESTAMP.md` — Test Strategy
  - `risk_register_ProjectName_TIMESTAMP.md` — Risk Register (NEW v0.3)
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

> **Rule:** After every code change, run relevant tests before committing. Add new tests for every new feature.

## Roadmap

- **v0.1** ✅ Core agent + CLI + Streamlit Web UI
- **v0.2** ✅ Feedback loop — validated strategies saved to knowledge base
- **v0.3** ✅ Risk Register generation (automatic, alongside Test Strategy)
- **v0.4** Effort estimation
- **v0.5** Multi-LLM support (OpenAI, Claude API, local models)
- **v1.0** Full interactive QA Consultant + hosted version

Keep each version's scope tight — implement incrementally in this order.
