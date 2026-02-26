# QAI Consultant — v0.7 HuggingFace Integration Implementation Plan

## Overview

v0.7 eliminates the biggest onboarding barrier for new users: having to manually gather
and place knowledge base files before the app works.

Two assets hosted on HuggingFace:
1. **HF Dataset** — source files (MDs + free-tier content)
2. **HF Model Repo** — ChromaDB snapshot (pre-ingested vector store)

Two download triggers:
1. `python src/download_kb.py` — explicit one-time setup script
2. Auto-detect at startup (CLI + Streamlit) — detects missing/empty KB and prompts user

---

## HuggingFace Assets Structure

### Asset 1 — HF Dataset: `qai-consultant/knowledge-base`

Two tiers hosted as a single dataset with separate configs:

```
qai-consultant/knowledge-base/
├── free/                          ← Tier 1: our own content (MDs)
│   ├── methodologies/
│   │   ├── Agile_Testing.md
│   │   ├── BDD_TDD.md
│   │   ├── Exploratory_Testing.md
│   │   ├── Risk_Based_Testing.md
│   │   ├── Test_Pyramid.md
│   │   └── Effort_Estimation_Techniques.md
│   ├── standards/
│   │   ├── ISO_26262_Automotive_Safety.md
│   │   ├── ASPICE_Process_Reference_Model.md
│   │   ├── IEEE_829_Test_Documentation.md
│   │   └── ISO_IEC_25010_Quality_Model.md
│   ├── expert_knowledge/
│   │   └── *.md (all expert knowledge files)
│   └── articles/
│       └── *.md (all article files)
│
└── README.md                      ← Dataset card with instructions

NOTE: ISTQB PDFs, OWASP PDFs — NOT included (copyright)
```

### Asset 2 — HF Model Repo: `qai-consultant/chroma-snapshot`

```
qai-consultant/chroma-snapshot/
├── chroma_db.tar.gz               ← Compressed ChromaDB (free tier only)
├── manifest.json                  ← Which files are included + chunk counts + version
└── README.md                      ← Model card with usage instructions
```

---

## Sync Architecture — Keeping Everything Up To Date

```
Developer pushes to main (GitHub)
        ↓
GitHub Action triggers (.github/workflows/sync_kb.yml)
        ↓
Action runs:
  1. pip install requirements.txt
  2. python src/ingest.py          ← full re-ingest from KB files
  3. tar.gz the chroma_db/
  4. upload chroma_db.tar.gz → HF Model Repo
  5. upload changed MD files → HF Dataset (incremental, git diff)
  6. upload updated manifest.json
        ↓
HuggingFace assets updated ✅

Existing user runs: python src/download_kb.py --update
        ↓
download_kb.py compares local manifest vs HF manifest
        ↓
Downloads only new/changed files (incremental)
        ↓
For changed MD files: calls IngestManager.ingest_file() directly
For new ChromaDB chunks: applies diff from manifest
        ↓
User KB is up to date ✅
```

### Manifest-driven incremental sync

The `manifest.json` on HF is the source of truth for sync:

```json
{
  "version": "1.0",
  "generated_at": "2026-02-26T10:00:00",
  "chromadb_version": "0.4.24",
  "files": {
    "methodologies/Agile_Testing.md": {
      "sha256": "abc123...",
      "size_bytes": 12400,
      "chunk_count": 18,
      "last_modified": "2026-02-20T10:00:00"
    }
  }
}
```

`download_kb.py --update` compares SHA256 of local files vs HF manifest.
Only files with different SHA256 are re-downloaded and re-ingested.

---

## Copyright Strategy — Two Tiers

### Tier 1 — Free (Auto-downloaded)
All markdown files we authored:
- `standards/ISO_26262_Automotive_Safety.md` ✅ ours
- `standards/ASPICE_Process_Reference_Model.md` ✅ ours
- `standards/IEEE_829_Test_Documentation.md` ✅ ours
- `standards/ISO_IEC_25010_Quality_Model.md` ✅ ours
- `methodologies/*.md` ✅ ours
- `expert_knowledge/*.md` ✅ ours
- `articles/*.md` ✅ ours

### Tier 2 — Manual (User downloads themselves with instructions)
Files with copyright restrictions:
- ISTQB PDFs (14 files) → official download from istqb.org (free but registration required)
- OWASP WSTG PDF → free download from owasp.org
- OWASP MASTG PDF → free download from owasp.org
- OWASP Top 10 HTML → scraped from owasp.org

`download_kb.py` will print clear instructions for Tier 2 files with direct URLs.

---

## GitHub Action: `.github/workflows/sync_kb.yml`

Triggers on push to `main` when files in `knowledge_base/` change:

```yaml
on:
  push:
    branches: [main]
    paths:
      - 'knowledge_base/**'
      - 'src/ingest.py'

jobs:
  sync-kb:
    runs-on: ubuntu-latest
    steps:
      - checkout
      - setup python
      - pip install requirements.txt
      - ollama serve + ollama pull mistral   ← needed for ingest
      - python src/ingest.py                 ← full re-ingest
      - python scripts/upload_to_hf.py --all ← upload to HF
    secrets:
      HF_TOKEN: ${{ secrets.HF_TOKEN }}      ← stored in GitHub Secrets
```

**Important:** GitHub Action uses HF_TOKEN stored as GitHub Secret.
Users downloading don't need a token — repos are public.

---



```
Flow:
1. Check HuggingFace connectivity
2. Download Tier 1 files (MDs) from HF Dataset → knowledge_base/
3. Download ChromaDB snapshot from HF Model Repo → chroma_db/
4. Decompress chroma_db.tar.gz
5. Print Tier 2 instructions (PDFs to download manually)
6. Verify download integrity (file count + manifest check)
7. Print summary: "Ready! X files downloaded, Y files need manual setup"
```

### CLI flags
```bash
python src/download_kb.py              # Download everything (Tier 1 + snapshot)
python src/download_kb.py --files-only # Only source files, skip ChromaDB snapshot
python src/download_kb.py --db-only    # Only ChromaDB snapshot, skip source files
python src/download_kb.py --check      # Check what's missing without downloading
```

---

## Auto-detect at Startup

### Detection Logic
```python
def check_kb_status() -> KBStatus:
    """
    Returns one of:
    - KBStatus.OK           → KB present and has content
    - KBStatus.EMPTY        → knowledge_base/ exists but has no files
    - KBStatus.NO_CHROMA    → ChromaDB missing or empty
    - KBStatus.PARTIAL      → KB present but ChromaDB missing (needs ingest)
    """
```

### CLI Startup Behavior
```
If KBStatus.EMPTY or KBStatus.NO_CHROMA:
    ┌─────────────────────────────────────────┐
    │ ⚠️  Knowledge base not found!            │
    │                                         │
    │ Run: python src/download_kb.py          │
    │ This will download ~50MB of QA          │
    │ knowledge from HuggingFace.             │
    │                                         │
    │ Download now? [yes/no]                  │
    └─────────────────────────────────────────┘
    → yes: runs download_kb.py inline
    → no: exits with instructions
```

### Streamlit Startup Behavior
```
If KBStatus.EMPTY or KBStatus.NO_CHROMA:
    → Show full-page warning with download button
    → "⚠️ Knowledge base not found"
    → "Click below to download (~50MB)"
    → [Download Knowledge Base] button
    → Progress bar during download
    → Auto-refresh when done
```

---

## New File: `src/kb_status.py`

Small utility module used by both CLI and Streamlit:

```python
class KBStatus(Enum):
    OK = "ok"
    EMPTY = "empty"
    NO_CHROMA = "no_chroma"
    PARTIAL = "partial"

def check_kb_status() -> KBStatus
def get_kb_file_count() -> int
def get_chroma_collection_size() -> int
```

---

## HuggingFace Upload Script: `scripts/upload_to_hf.py`

Used by GitHub Actions CI (not for manual use):

```bash
python scripts/upload_to_hf.py --dataset    # Upload MD files to HF Dataset
python scripts/upload_to_hf.py --snapshot   # Package + upload ChromaDB snapshot
python scripts/upload_to_hf.py --all        # Both
```

Requires: `huggingface_hub` + HF token stored as GitHub Secret `HF_TOKEN`.

---

## GitHub Actions CI: `.github/workflows/update_knowledge_base.yml`

Triggered on every push to `main` that touches `knowledge_base/`:

```yaml
on:
  push:
    branches: [main]
    paths:
      - 'knowledge_base/**'

jobs:
  update-hf:
    runs-on: ubuntu-latest
    steps:
      - Checkout repo
      - Install dependencies (pip install -r requirements.txt)
      - Run ingest.py → rebuild ChromaDB from scratch
      - Run upload_to_hf.py --all → push to HuggingFace
    env:
      HF_TOKEN: ${{ secrets.HF_TOKEN }}
```

**Why rebuild from scratch in CI (not incremental)?**
CI has no persistent ChromaDB state between runs. Full rebuild ensures
the snapshot is always clean and consistent. Local users still benefit
from incremental ingest via knowledge_watcher.py.

---

## New Dependencies

```
huggingface_hub>=0.23.0    # HF download + upload API
```

Note: `huggingface_hub` is likely already installed as a transitive dependency
of `sentence-transformers`. Add explicit pin to requirements.txt.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| HF dataset unavailable / rate limited | Low | High | Fallback message with manual download instructions |
| ChromaDB snapshot incompatible with local version | Medium | High | Pin chromadb version in requirements.txt + snapshot metadata includes version |
| Partial download (network failure mid-way) | Medium | Medium | Atomic download to temp dir → move on completion; retry logic |
| ChromaDB snapshot stale (new KB files not included) | Medium | Medium | Manifest includes hash + date; warn user if snapshot is >30 days old |
| Large snapshot size (ChromaDB can grow big) | Medium | Low | Compress with tar.gz; document expected size in README |
| User places PDFs in wrong folder | High | Low | `download_kb.py --check` shows exactly what's missing and where |
| HF token required for private repos | Low | Medium | Keep repos public; no auth required for download |

---

## README Updates

Add "Quick Start" section at the top:

```markdown
## Quick Start (2 minutes)

# 1. Install
pip install -r requirements.txt

# 2. Download knowledge base (~50MB, one-time)
python src/download_kb.py

# 3. Start Ollama
ollama serve && ollama pull mistral

# 4. Run
python src/cli.py          # Terminal
streamlit run src/app.py   # Browser
```

---

## Definition of Done for v0.7

- [ ] HF Dataset created: `qai-consultant/knowledge-base` with all Tier 1 MD files
- [ ] HF Model Repo created: `qai-consultant/chroma-snapshot` with compressed ChromaDB + manifest.json
- [ ] `src/kb_status.py` — KBStatus enum + check functions
- [ ] `src/download_kb.py` — first install + `--update` incremental sync + Tier 2 instructions
- [ ] `manifest.json` includes SHA256 per file for incremental sync
- [ ] CLI auto-detects missing KB at startup and prompts user
- [ ] Streamlit auto-detects missing KB and shows download UI
- [ ] `scripts/upload_to_hf.py` — maintainer upload script (incremental for MDs, full for snapshot)
- [ ] `.github/workflows/sync_kb.yml` — GitHub Action triggers on KB changes → re-ingest → upload to HF
- [ ] README updated with Quick Start section
- [ ] `huggingface_hub>=0.23.0` added to requirements.txt
- [ ] CLAUDE.md updated
- [ ] Tests written and passing
