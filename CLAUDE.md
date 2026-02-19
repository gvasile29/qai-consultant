# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

QAI Consultant is a Python-based AI agent that acts as a senior QA Architect. It generates Test Strategies, Test Plans, and effort estimations from product descriptions, grounded in ISTQB, OWASP, and IEEE standards.

## Development Commands

The project is in early development. Once `requirements.txt` exists:

```bash
pip install -r requirements.txt          # Install dependencies
python download_knowledge_base.py        # Download/update knowledge base
python qai.py                            # Run the main agent
```

## Architecture

The agent follows a "Sky View to Ground View" approach — taking a high-level product description as input and progressively generating structured QA artifacts (strategy → plan → effort estimates → risk-based recommendations).

### Key directories

- `src/` — Application source code (to be built)
- `knowledge_base/standards/istqb/` — 14 ISTQB syllabus PDFs used as RAG source material
- `knowledge_base/standards/owasp/` — OWASP WSTG (web) and MASTG (mobile) PDFs
- `knowledge_base/methodologies/` — Future home for QA methodology content
- `knowledge_base/expert_knowledge/` — Future home for curated expert QA guidance
- `docs/` — Documentation (to be built)

### Planned entry points (from README)

- `qai.py` — Main agent entry point
- `download_knowledge_base.py` — Script to fetch/update knowledge base resources

## Roadmap Context

The roadmap progresses from basic strategy generation (v0.1) through multi-LLM support (v0.5) to a full interactive consultant (v1.0). When implementing features, follow this incremental order and keep each version's scope tight.

## Knowledge Base

The knowledge base is the core data layer for the agent. All agent outputs should be traceable to it.

### Standards (`knowledge_base/standards/`)
- **ISTQB** — 14 certification syllabi PDFs (CTFL, CTAL-TA, CTAL-TM, CTAL-TAE, CT-AI, CT-GenAI, CT-MBT, CT-ATLaS, CT-MAT, CTel-ITP, and more)
- **OWASP** — WSTG v4.2 PDF, MASTG PDF, OWASP Top 10 2021 in both HTML and Markdown
- **IEEE 829** — Test documentation standard overview (`IEEE_829_Test_Documentation.md`)
- **ISO/IEC 25010** — Software quality model with all 8 product quality characteristics (`ISO_IEC_25010_Quality_Model.md`)

### Methodologies (`knowledge_base/methodologies/`)
Five fully written guides: `Agile_Testing.md`, `BDD_TDD.md`, `Exploratory_Testing.md`, `Risk_Based_Testing.md`, `Test_Pyramid.md`. Each file ends with a "QAI Consultant application" section that maps the methodology to agent behavior.

### Expert Knowledge (`knowledge_base/expert_knowledge/`)
Community contribution framework. Three PROMPT files drive AI-assisted knowledge extraction interviews:
- `PROMPT_Lessons_Learned.md` — 7-question interview → structured lesson file
- `PROMPT_Real_Scenarios.md` — 7-question interview → scenario file capturing decision-making
- `PROMPT_Effort_Estimation.md` — 8-question interview → estimation heuristics file

`CONTRIBUTION_GUIDE.md` defines the 5 contribution categories and file naming conventions.

### Articles (`knowledge_base/articles/`)
- `AI-DrivenQA_case_studies.md` — 10 real-world AI QA transformation case studies with quantified outcomes (used to ground agent claims with evidence)

### RAG Indexing Priority
When building retrieval, index in this order: OWASP Top 10 MD + methodology MDs first (structured, directly queryable), then ISTQB/OWASP PDFs (bulk reference), then expert knowledge and articles as supplementary context.
