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
  → StrategyGenerator.generate(context)
      → context.to_rag_query() → agent.retrieve_knowledge() → ChromaDB similarity search
      → build_strategy_prompt(context, knowledge_context)
      → agent.ask(prompt) → Ollama Mistral
  → Markdown output saved to output/
```

### Source Files (`src/`)

| File | Role |
|------|------|
| `agent.py` | `QAIAgent` — loads ChromaDB + HuggingFace embeddings, exposes `retrieve_knowledge()`, `ask()`, `ask_with_rag()` |
| `ingest.py` | One-time pipeline: load PDFs/Markdowns → chunk (1000 chars, 200 overlap) → embed (all-MiniLM-L6-v2) → persist to `chroma_db/` |
| `dialogue.py` | `DialogueManager` + `ProjectContext` dataclass — collects 11 project fields; `to_rag_query()` builds the retrieval query |
| `strategy_generator.py` | `StrategyGenerator` — orchestrates retrieve (k=8) → prompt → generate → save to `output/` with timestamp |
| `cli.py` | Terminal UI using `rich` — multi-phase flow: banner → load agent → dialogue → review → generate → display |
| `app.py` | Streamlit web UI — 4-step state machine: `intro → dialogue → review → strategy`; uses `@st.cache_resource` for agent |

### Key Configuration (hardcoded in source)

- `OLLAMA_MODEL = "mistral"` — change in `agent.py` to switch models
- `EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"` — must match between ingest and agent
- `TOP_K_RESULTS = 5` (agent default), `k=8` used in strategy generation
- `CHROMA_DIR` — absolute path to `chroma_db/` resolved from `agent.py` location

### Generated Output

- `output/` — gitignored; timestamped markdown files (e.g., `test_strategy_ProjectName_20260220_115311.md`)
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

## Roadmap

- **v0.1** ✅ Test Strategy generation (current)
- **v0.2** Test Plan with phases
- **v0.3** Effort estimation
- **v0.4** Risk-based testing recommendations
- **v0.5** Multi-LLM support
- **v1.0** Full interactive QA Consultant

Keep each version's scope tight — implement incrementally in this order.
