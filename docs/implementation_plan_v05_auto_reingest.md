# QAI Consultant — v0.5 Auto Re-ingest Implementation Plan

## Overview

Auto re-ingest monitors `knowledge_base/` for new or modified files and automatically
re-ingests them into ChromaDB without requiring the user to manually run `python src/ingest.py`.

Two triggers:
1. **File watcher** — detects new/modified files in `knowledge_base/`
2. **Post-feedback** — triggered automatically after a strategy is saved to `generated_strategies/`

User experience: silent background processing + visual notification when done.

---

## How It Works

```
Trigger A: New file in knowledge_base/
        ↓
KnowledgeBaseWatcher detects change (watchdog)
        ↓
Debounce 3 seconds (wait for file to finish writing)
        ↓
IngestManager.ingest_new_files(changed_files)
        ↓
Only new/changed files are ingested (not full re-ingest)
        ↓
Notification: "Knowledge base updated! +3 new chunks"

Trigger B: Feedback yes/partially → strategy saved to generated_strategies/
        ↓
cli.py / app.py calls IngestManager.ingest_file(path) directly
        ↓
File ingested immediately
        ↓
Notification: "Strategy added to knowledge base!"
```

---

## Key Design Decisions

### 1. Incremental Ingest — NOT Full Re-ingest
Full re-ingest (delete ChromaDB + re-ingest everything) takes 5-10 minutes.
Instead, we ingest ONLY new or changed files.

**How to detect new/changed files:**
- Maintain a manifest file: `chroma_db/ingest_manifest.json`
- Stores: `{filepath: last_modified_timestamp}` for every ingested file
- On trigger: compare current files vs manifest → only ingest diff

### 2. Watchdog Library for File Watching
Use `watchdog` Python library — cross-platform file system events (Windows, Mac, Linux).
Watch `knowledge_base/` recursively for:
- `FileCreatedEvent`
- `FileModifiedEvent`
- `FileMovedEvent` (rename)

### 3. Debouncing
File watchers can fire multiple events for a single save operation.
Apply 3-second debounce — wait for events to settle before triggering ingest.

### 4. Thread Safety
File watcher runs in a background thread.
ChromaDB writes must be thread-safe — use a lock to prevent concurrent writes.

### 5. Supported File Types
Same as ingest.py: `.pdf`, `.md`, `.txt`
Ignore: `.json`, `.gitkeep`, system files, temp files (`~$*`, `*.tmp`)

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Partial file write detected as new file | High | Medium | Debounce 3 sec + check file size stability |
| Concurrent ingest corrupts ChromaDB | Medium | High | Thread lock — only one ingest at a time |
| Large PDF triggers slow ingest, blocks UI | Medium | Medium | Run ingest in background thread, never block UI |
| Duplicate chunks if file modified multiple times | Medium | Medium | Delete existing chunks for file before re-ingesting |
| Watcher misses events on network drives | Low | Low | Document limitation, suggest local KB only |
| Watcher consumes high CPU on large KB | Low | Low | Watchdog is event-based, not polling — low overhead |
| App starts before watcher is ready | Low | Low | Watcher starts async, no blocking |

---

## New File: `src/knowledge_watcher.py`

```python
class IngestManifest:
    """Tracks which files have been ingested and their last modified time."""
    def load() -> dict
    def save(manifest: dict)
    def get_new_or_changed_files(kb_dir: Path) -> list[Path]
    def update(filepath: Path)

class IngestManager:
    """Handles incremental ingestion of new/changed files."""
    def ingest_file(filepath: Path) -> int          # returns chunk count
    def ingest_new_files(files: list[Path]) -> int  # returns total chunk count
    def _delete_existing_chunks(filepath: Path)     # removes old chunks before re-ingest

class KnowledgeBaseWatcher:
    """Watches knowledge_base/ for changes and triggers incremental ingest."""
    def start(callback: callable)   # callback(message: str) called after ingest
    def stop()
    def _on_file_event(event)
    def _debounced_ingest(filepath: Path)
```

---

## Manifest File Format

```json
{
  "version": "1.0",
  "last_updated": "2026-02-24T10:00:00",
  "files": {
    "standards/istqb/ISTQB_CTFL_Syllabus_v4.0.1.pdf": {
      "last_modified": 1708765200.0,
      "chunk_count": 142,
      "ingested_at": "2026-02-24T10:00:00"
    },
    "methodologies/Agile_Testing.md": {
      "last_modified": 1708765200.0,
      "chunk_count": 18,
      "ingested_at": "2026-02-24T10:00:00"
    }
  }
}
```

---

## Integration Points

### cli.py
- Start watcher at startup (background thread)
- Pass notification callback → prints `[bold green]✅ Knowledge base updated! +N chunks[/bold green]`
- After feedback save → call `IngestManager.ingest_file()` directly

### app.py
- Start watcher via `@st.cache_resource` (runs once per session)
- Store notification in `st.session_state.kb_notification`
- Display as `st.success("✅ Knowledge base updated! +N new chunks")` — auto-dismisses after 5 sec
- After feedback save → call `IngestManager.ingest_file()` directly + show notification

---

## New Dependency

```
watchdog==4.0.0
```

Add to `requirements.txt`.

---

## Migration — First Run

On first run after v0.5 upgrade, manifest doesn't exist yet.
`IngestManager` detects missing manifest → treats all existing files as "already ingested"
→ builds manifest from current ChromaDB state → no re-ingest triggered.

---

## Definition of Done for v0.5

- [ ] `IngestManifest` tracks ingested files with timestamps
- [ ] `IngestManager.ingest_file()` ingests a single file incrementally
- [ ] `IngestManager` deletes old chunks before re-ingesting modified files
- [ ] `KnowledgeBaseWatcher` detects new/modified files in `knowledge_base/`
- [ ] 3-second debounce prevents duplicate triggers
- [ ] Thread lock prevents concurrent ChromaDB writes
- [ ] CLI shows notification after auto-ingest
- [ ] Streamlit shows notification after auto-ingest
- [ ] Post-feedback ingest works in both CLI and Streamlit
- [ ] Manifest built correctly on first run (no re-ingest of existing files)
- [ ] `watchdog==4.0.0` added to `requirements.txt`
- [ ] CLAUDE.md updated
- [ ] Tests written and passing
