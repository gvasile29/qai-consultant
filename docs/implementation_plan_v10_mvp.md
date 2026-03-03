# QAI Consultant — v1.0 MVP Implementation Plan

## Overview

v1.0 is the first public-ready release. No new features — focus is entirely on
stability, error handling, input validation, logging, testing, and documentation.

Goal: a new user can clone the repo, follow the README, and have a working
QAI Consultant in under 10 minutes.

---

## 1. Error Handling

### 1.1 Ollama not running
Current behavior: cryptic connection error deep in stack trace.
Target: clear message at startup.

```
❌ Ollama is not running!

Please start Ollama before running QAI Consultant:
  ollama serve

Then pull the recommended model:
  ollama pull mistral

For installation instructions: https://ollama.ai
```

**Where:** `agent.py` → `QAIAgent.__init__()` catches `ConnectionRefusedError` / `httpx.ConnectError`

### 1.2 Ollama model not pulled
Current behavior: timeout or model error.
Target:

```
❌ Model 'mistral' not found in Ollama!

Pull it with:
  ollama pull mistral

Available models on your system: [llama3, phi3]
```

### 1.3 ChromaDB missing or corrupt
Current behavior: FileNotFoundError or ChromaDB internal error.
Target:

```
❌ Knowledge base not found! (chroma_db/ is missing or empty)

Build it with:
  python src/ingest.py

This will take 5-10 minutes on first run.
```

### 1.4 knowledge_base/ empty
Current behavior: ingest runs but produces 0 chunks silently.
Target: warning during ingest + warning at agent startup.

### 1.5 Generation timeout
Current behavior: hangs indefinitely if Mistral is slow.
Target: 120 second timeout with clear message.

---

## 2. Input Validation — Dialogue

### 2.1 Empty answers
- Block empty or whitespace-only answers
- Message: "Please provide an answer to continue."

### 2.2 Too short answers
- Minimum 3 characters for most fields
- Exception: numeric fields (team size, timeline)
- Message: "Answer seems too short — please be more specific."

### 2.3 Invalid characters
- Strip dangerous characters: `<>{}|\\`
- Log stripped characters for debugging

### 2.4 Project name validation
- Used in filenames — strip characters invalid for filenames: `/ \ : * ? " < > |`
- Replace spaces with underscores for file saving
- Max 50 characters

### 2.5 Numeric field hints
- Team size: if user types "five" → hint "Please use a number (e.g., 5)"
- Timeline: accept "6 months", "2 years", "Q3 2026" — all valid

---

## 3. Logging

### 3.1 Log file location
```
logs/qai_consultant.log   ← gitignored
```

### 3.2 Log levels
- `INFO` — normal operations (agent loaded, strategy generated, file saved)
- `WARNING` — non-fatal issues (file watcher missed event, manifest mismatch)
- `ERROR` — failures (Ollama down, ChromaDB corrupt, ingest failed)
- `DEBUG` — verbose details (chunk counts, RAG scores, PERT calculations)

### 3.3 Log format
```
2026-02-26 10:00:00 [INFO] agent.py:42 - QAIAgent loaded: 6486 chunks in ChromaDB
2026-02-26 10:01:23 [INFO] strategy_generator.py:88 - Strategy generated for 'BMW ECU' in 34.2s
2026-02-26 10:01:24 [INFO] effort_estimator.py:201 - Effort estimated: 1704-4913 days, confidence=Medium
2026-02-26 10:01:25 [WARNING] knowledge_watcher.py:112 - Ingest failed for 'test.pdf': unsupported encoding
2026-02-26 10:01:30 [ERROR] agent.py:28 - Ollama connection failed: ConnectionRefusedError
```

### 3.4 New file: `src/logger.py`
```python
def get_logger(name: str) -> logging.Logger
def setup_logging(level: str = "INFO")
```

All modules import from `src/logger.py` instead of using `print()` or raw `logging`.

---

## 4. README Updates

### 4.1 Quick Start (top of README)
```markdown
## Quick Start

# Prerequisites: Ollama installed (https://ollama.ai)
ollama pull mistral

# 1. Clone
git clone https://github.com/yourusername/qai-consultant
cd qai-consultant

# 2. Install
pip install -r requirements.txt

# 3. Build knowledge base (~5-10 min, one-time)
python src/ingest.py

# 4. Run
python src/cli.py            # Terminal UI
streamlit run src/app.py     # Web UI → http://localhost:8501
```

### 4.2 Screenshots section
- Screenshot of CLI dialogue flow
- Screenshot of Streamlit results with 3 tabs
- Screenshot of generated Risk Register
- Screenshot of generated Effort Estimation Report

### 4.3 Troubleshooting section
- Ollama not running
- ChromaDB missing
- Slow generation
- Windows-specific issues (path separators)

---

## 5. New Documentation Files

### 5.1 INSTALL.md
Detailed installation guide:
- Prerequisites (Python 3.10+, Ollama, Git)
- Step-by-step for Windows, Mac, Linux
- Virtual environment setup
- Troubleshooting common issues
- Verification checklist

### 5.2 CONTRIBUTING.md
How to contribute knowledge to the KB:
- Adding new MD files to `knowledge_base/`
- Following the KB structure conventions
- Running `ingest.py` after adding files
- Using expert knowledge prompts
- Submitting pull requests

### 5.3 Version file: `src/version.py`
```python
__version__ = "1.0.0"
__release_date__ = "2026-02-26"
```

Displayed in CLI banner and Streamlit sidebar.

---

## 6. Docstrings

All modules need complete docstrings:
- Module-level docstring explaining purpose
- Class-level docstring
- Method docstrings with Args/Returns where non-obvious

Priority order (most used → least used):
1. `agent.py`
2. `dialogue.py`
3. `strategy_generator.py`
4. `risk_analyzer.py`
5. `effort_estimator.py`
6. `knowledge_watcher.py`
7. `ingest.py`

---

## 7. Tests

### 7.1 `tests/test_agent.py`
- `QAIAgent` loads successfully when Ollama is running
- `QAIAgent.__init__` raises `QAIConnectionError` when Ollama is down
- `retrieve_knowledge()` returns list of Documents
- `format_knowledge_context()` returns non-empty string

### 7.2 `tests/test_dialogue.py`
- All 11 questions are defined
- `submit_answer()` stores answer correctly
- `get_context()` returns `ProjectContext` with all fields
- `to_rag_query()` returns non-empty string
- Input validation: empty answer rejected
- Input validation: too-short answer rejected
- Input validation: invalid chars stripped from project name

### 7.3 `tests/test_integration.py`
- End-to-end: full dialogue → Risk Register + Effort Report + Test Strategy generated
- All 3 output files saved to `output/`
- Manifest updated after generation
- Generated content has minimum expected sections

### 7.4 `tests/test_ollama_check.py`
- Ollama running → no error
- Ollama not running → clear `QAIConnectionError` with helpful message
- Wrong model → clear error with available models listed

---

## 8. Polish Items

### 8.1 `.gitignore` review
Ensure these are gitignored:
- `logs/`
- `output/`
- `chroma_db/`
- `__pycache__/`
- `.env`
- `*.pyc`

### 8.2 `requirements.txt` — pin all versions
Currently some deps have loose versions. Pin everything for reproducibility.

### 8.3 Python version
Add `.python-version` file (3.10+) and note in README.

---

## Definition of Done for v1.0

### Error Handling
- [ ] Clear error when Ollama not running (CLI + Streamlit)
- [ ] Clear error when model not pulled
- [ ] Clear error when ChromaDB missing
- [ ] Clear error when knowledge_base/ empty
- [ ] 120s generation timeout with message

### Input Validation
- [ ] Empty answers blocked in CLI and Streamlit
- [ ] Too-short answers flagged
- [ ] Invalid filename chars stripped from project name
- [ ] Numeric hints for team size / timeline fields

### Logging
- [ ] `src/logger.py` created
- [ ] All modules use logger (not print for operational messages)
- [ ] `logs/qai_consultant.log` created on first run
- [ ] `logs/` gitignored

### Documentation
- [ ] README Quick Start section added
- [ ] README Screenshots section added
- [ ] README Troubleshooting section added
- [ ] `INSTALL.md` created
- [ ] `CONTRIBUTING.md` created
- [ ] `src/version.py` created (v1.0.0)
- [ ] Version shown in CLI banner and Streamlit sidebar
- [ ] Docstrings complete in all 7 modules

### Tests
- [ ] `tests/test_agent.py` — 4+ tests
- [ ] `tests/test_dialogue.py` — 7+ tests
- [ ] `tests/test_integration.py` — 4+ tests
- [ ] `tests/test_ollama_check.py` — 3+ tests
- [ ] All existing tests still passing (regression)

### Polish
- [ ] `.gitignore` reviewed and complete
- [ ] `requirements.txt` all versions pinned
- [ ] `.python-version` file added
- [ ] CLAUDE.md updated
