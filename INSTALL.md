# Installation Guide — QAI Consultant

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.10+ | Check: `python --version` |
| Git | Any | For cloning the repo |
| Mistral API key | — | Free tier at [console.mistral.ai](https://console.mistral.ai/) |
| OpenRouter API key | — | Free tier at [openrouter.ai/keys](https://openrouter.ai/keys) — automatic fallback if Mistral is unavailable |
| Pinecone API key + index | — | Free tier at [pinecone.io](https://www.pinecone.io/) |

QAI Consultant runs entirely on cloud APIs — no local GPU, no Ollama, no local vector
database. RAM/disk requirements are whatever `pip install` needs for the Python
dependencies (a few hundred MB); there is no local model to download or cache.

---

## Step 1 — Clone the Repository

```bash
git clone https://github.com/gvasile29/qai-consultant.git
cd qai-consultant
```

---

## Step 2 — Create a Virtual Environment (Recommended)

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

## Step 3 — Install Dependencies

```bash
pip install -r requirements.txt
```

This installs LangChain (embeddings only), Sentence Transformers, Streamlit, the
Mistral/OpenAI/Pinecone SDKs, and all other runtime dependencies.

For running the test suite or the `evals/` release gate, also install:
```bash
pip install -r requirements-dev.txt
```

---

## Step 4 — Set Up API Keys

Copy the example env file and fill in your four keys:

```bash
cp .env.example .env
```

```
MISTRAL_API_KEY=...
OPENROUTER_API_KEY=...
PINECONE_API_KEY=...
PINECONE_INDEX_NAME=qai-consultant
```

| Key | Where to get it |
|---|---|
| `MISTRAL_API_KEY` | [console.mistral.ai](https://console.mistral.ai/) → API Keys |
| `OPENROUTER_API_KEY` | [openrouter.ai/keys](https://openrouter.ai/keys) |
| `PINECONE_API_KEY` | [pinecone.io](https://www.pinecone.io/) → API Keys |
| `PINECONE_INDEX_NAME` | Name of a Pinecone index you create (dimensions: **384**, metric: **cosine**, to match the `all-MiniLM-L6-v2` embedding model) |

> Running on Streamlit Cloud instead? Add the same four keys to the app's
> **Secrets** panel — `agent.py`'s `_get_secret()` checks Streamlit secrets first,
> then falls back to `.env`.

---

## Step 5 — Build the Knowledge Base

```bash
python src/ingest.py
```

This chunks every file in `knowledge_base/` (1000 chars, 200 overlap), embeds each
chunk with `all-MiniLM-L6-v2`, and upserts them into your Pinecone index. Re-run this
any time you add or change knowledge base files — there is no automatic watcher.

**Expected output (truncated):**
```
Ingested N files → M chunks
Upserted to Pinecone index 'qai-consultant' (namespace: knowledge-base)
```

---

## Step 6 — Run QAI Consultant

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

- [ ] `.env` has all four keys filled in (or Streamlit secrets configured)
- [ ] `python src/ingest.py` completes without errors
- [ ] `python src/cli.py` shows the QAI Consultant banner
- [ ] First question appears: "What is the name of your project?"
- [ ] Answering all 11 questions and confirming produces a Risk Register, Effort
      Estimation Report, Test Strategy, and Test Plan

---

## Troubleshooting

### ❌ "Missing required secret: 'MISTRAL_API_KEY'" (or any other key)
Add the missing key to `.env` (local) or your Streamlit Cloud app's Secrets panel
(deployed). See Step 4.

### ❌ "Knowledge base is empty" / retrieval returns nothing
```bash
python src/ingest.py
```
Make sure you have files in `knowledge_base/` and that `PINECONE_INDEX_NAME` points
at the same index you just ingested into.

### ❌ "Both Mistral API and OpenRouter are unavailable"
Both providers failed for this request — check that both keys are valid and have
remaining credits/quota. `LLMClient` tries Mistral first and only raises this once
the OpenRouter fallback has also failed.

### ❌ pip install fails on sentence-transformers / torch
```bash
pip install --upgrade pip
pip install -r requirements.txt
```
On some platforms `sentence-transformers` needs a recent `pip` to resolve its
`torch` dependency correctly.

### ❌ Pinecone dimension/metric mismatch on ingest
Your index must be created with **dimension 384** and **metric cosine** — these
match `sentence-transformers/all-MiniLM-L6-v2`, the embedding model both `ingest.py`
and the app use. A mismatched index will reject upserts or return irrelevant matches.

---

## Windows-Specific Notes

- Use `python` instead of `python3`
- Use `venv\Scripts\activate` (backslash) to activate the virtual environment
- Long path issues: enable long paths in Windows 10/11 settings

---

## macOS-Specific Notes

- Use `python3` and `pip3`

---

## Need Help?

Open an issue on GitHub with:
1. Your OS and Python version
2. The exact error message
3. Whether the failure happens during `ingest.py`, the CLI, or the Streamlit app
