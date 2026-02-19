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

The `knowledge_base/standards/` PDFs are the authoritative source material for recommendations. The agent's outputs should be traceable to these standards. When building RAG or retrieval features, index these PDFs as the primary corpus.
