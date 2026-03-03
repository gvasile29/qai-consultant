# Installation Guide — QAI Consultant

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.10+ | Check: `python --version` |
| Git | Any | For cloning the repo |
| Ollama | Latest | LLM runtime — see below |
| RAM | 8GB+ | Mistral 7B requires ~4GB |
| Disk | 5GB+ | ChromaDB + model weights |

---

## Step 1 — Install Ollama

Ollama runs the Mistral LLM locally on your machine.

### Windows
Download and run the installer from: https://ollama.ai/download/windows

### macOS
```bash
brew install ollama
```
Or download from: https://ollama.ai/download/mac

### Linux
```bash
curl -fsSL https://ollama.ai/install.sh | sh
```

**Verify installation:**
```bash
ollama --version
```

---

## Step 2 — Pull the Quantized Mistral Model

```bash
ollama pull mistral:7b-instruct-q4_0
```

This downloads ~4GB (4-bit quantized — ~3x faster on CPU than the default float16 `mistral` tag).
Run it once — the model is cached locally.

**Verify:**
```bash
ollama list
# Should show: mistral:7b-instruct-q4_0   ...   4.1 GB
```

---

## Step 3 — Clone the Repository

```bash
git clone https://github.com/gvasile29/qai-consultant.git
cd qai-consultant
```

---

## Step 4 — Create a Virtual Environment (Recommended)

### Windows
```bash
python -m venv venv
venv\Scripts\activate
```

### macOS / Linux
```bash
python3 -m venv venv
source venv/bin/activate
```

---

## Step 5 — Install Dependencies

```bash
pip install -r requirements.txt
```

This installs LangChain, ChromaDB, Sentence Transformers, Streamlit, and all other dependencies.
First install may take 2-5 minutes as it downloads the embedding model (~90MB).

---

## Step 6 — Add Knowledge Base Files

QAI Consultant needs QA knowledge documents to generate strategies.

### Required folder structure
```
knowledge_base/
├── standards/          ← QA standards (ISTQB, OWASP, ISO, etc.)
├── methodologies/      ← Testing methodologies (Agile, Risk-Based, etc.)
├── articles/           ← QA articles and guides
└── expert_knowledge/   ← Domain-specific expert knowledge
```

### What to add
- **ISTQB syllabus PDFs** — download free from https://www.istqb.org
- **OWASP guides** — download free from https://owasp.org
- **Your own MD files** — see [CONTRIBUTING.md](CONTRIBUTING.md)

> The `methodologies/` and `expert_knowledge/` folders already contain
> markdown files included in the repository.

---

## Step 7 — Build the Knowledge Base

```bash
python src/ingest.py
```

This processes all files in `knowledge_base/` and builds the ChromaDB vector store.

- First run: **5-10 minutes** (downloads embedding model + processes all documents)
- Subsequent runs: faster (only new/changed files are re-processed)
- Output: `chroma_db/` folder (gitignored)

**Expected output:**
```
✅ Ingested 42 files → 6,486 chunks
ChromaDB ready at: chroma_db/
```

---

## Step 8 — Run QAI Consultant

### Option A — Terminal UI (CLI)
```bash
python src/cli.py
```

### Option B — Web UI (Streamlit)
```bash
streamlit run src/app.py
```
Then open: http://localhost:8501

---

## Verification Checklist

- [ ] `ollama list` shows `mistral:7b-instruct-q4_0`
- [ ] `python src/ingest.py` completes without errors
- [ ] `chroma_db/` folder exists and is non-empty
- [ ] `python src/cli.py` shows the QAI Consultant banner
- [ ] First question appears: "What is the name of your project?"

---

## Troubleshooting

### ❌ "Ollama is not running"
```bash
# Start Ollama in a separate terminal
ollama serve
```
Keep this terminal open while using QAI Consultant.

### ❌ "Model 'mistral:7b-instruct-q4_0' not found"
```bash
ollama pull mistral:7b-instruct-q4_0
```

### ❌ "Knowledge base not found"
```bash
python src/ingest.py
```
Make sure you have files in `knowledge_base/` first.

### ❌ "Knowledge base is empty"
Add documents to `knowledge_base/` subfolders, then re-run `python src/ingest.py`.

### ❌ Slow generation (>1 minute per section)
Normal on first call — model loading into memory.
After the first generation, subsequent calls in the same session are faster (~30–60s each).
Expected total time for all three documents: **2–3 minutes** on CPU with the quantized model.

### ❌ Windows: encoding errors during ingest
```bash
# Set UTF-8 encoding
set PYTHONIOENCODING=utf-8
python src/ingest.py
```

### ❌ pip install fails on sentence-transformers
```bash
pip install --upgrade pip
pip install sentence-transformers
```

---

## Windows-Specific Notes

- Use `python` instead of `python3`
- Use `venv\Scripts\activate` (backslash) to activate virtual environment
- If Ollama doesn't start: run as Administrator or check Windows Defender firewall
- Long path issues: enable long paths in Windows 10/11 settings

---

## macOS-Specific Notes

- Use `python3` and `pip3`
- On Apple Silicon (M1/M2/M3): Ollama runs natively — no GPU config needed
- If `brew install ollama` fails: use the direct download from ollama.ai

---

## Need Help?

Open an issue on GitHub with:
1. Your OS and Python version
2. The exact error message
3. Output of `ollama list`
