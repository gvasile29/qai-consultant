"""
QAI Consultant — Knowledge Base Watcher & Auto Re-ingest
Monitors knowledge_base/ for new/modified files and incrementally ingests them.
"""

import os
import sys
import json
import time
import threading
import logging
from pathlib import Path
from datetime import datetime

os.environ["ANONYMIZED_TELEMETRY"] = "False"
os.environ["CHROMA_TELEMETRY"] = "False"

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileModifiedEvent, FileMovedEvent

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
KB_DIR = BASE_DIR / "knowledge_base"
CHROMA_DIR = BASE_DIR / "chroma_db"
MANIFEST_PATH = CHROMA_DIR / "ingest_manifest.json"

# ── Config ─────────────────────────────────────────────────────────────────────
SUPPORTED_EXTENSIONS = {".pdf", ".md", ".txt"}
IGNORED_PATTERNS = {"~$", ".tmp", ".gitkeep", ".DS_Store", "Thumbs.db"}
DEBOUNCE_SECONDS = 3
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
COLLECTION_NAME = "qai_knowledge_base"
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200

logger = logging.getLogger(__name__)


# ── Ingest Manifest ────────────────────────────────────────────────────────────

class IngestManifest:
    """Tracks which files have been ingested and their last modified timestamps."""

    def __init__(self):
        self._data = {"version": "1.0", "last_updated": "", "files": {}}
        self._lock = threading.Lock()

    def load(self) -> dict:
        """Load manifest from disk."""
        with self._lock:
            if MANIFEST_PATH.exists():
                try:
                    self._data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
                except Exception:
                    self._data = {"version": "1.0", "last_updated": "", "files": {}}
            return self._data

    def save(self):
        """Persist manifest to disk."""
        with self._lock:
            self._data["last_updated"] = datetime.now().isoformat()
            MANIFEST_PATH.write_text(
                json.dumps(self._data, indent=2), encoding="utf-8"
            )

    def is_new_or_changed(self, filepath: Path) -> bool:
        """Return True if file is not in manifest or has been modified since last ingest."""
        key = str(filepath.relative_to(KB_DIR))
        try:
            current_mtime = filepath.stat().st_mtime
        except FileNotFoundError:
            return False
        if key not in self._data["files"]:
            return True
        return current_mtime > self._data["files"][key]["last_modified"]

    def get_new_or_changed_files(self) -> list:
        """Scan knowledge_base/ and return list of new or changed files."""
        self.load()
        changed = []
        for ext in SUPPORTED_EXTENSIONS:
            for filepath in KB_DIR.rglob(f"*{ext}"):
                if self._should_ignore(filepath):
                    continue
                if self.is_new_or_changed(filepath):
                    changed.append(filepath)
        return changed

    def update(self, filepath: Path, chunk_count: int):
        """Update manifest entry for a file."""
        key = str(filepath.relative_to(KB_DIR))
        with self._lock:
            self._data["files"][key] = {
                "last_modified": filepath.stat().st_mtime,
                "chunk_count": chunk_count,
                "ingested_at": datetime.now().isoformat(),
            }

    def build_from_existing(self):
        """
        First-run migration: build manifest from all existing KB files
        without re-ingesting them. Marks all current files as already ingested.
        """
        self.load()
        if self._data["files"]:
            return  # manifest already exists, skip

        logger.info("Building initial manifest from existing knowledge base...")
        for ext in SUPPORTED_EXTENSIONS:
            for filepath in KB_DIR.rglob(f"*{ext}"):
                if self._should_ignore(filepath):
                    continue
                key = str(filepath.relative_to(KB_DIR))
                self._data["files"][key] = {
                    "last_modified": filepath.stat().st_mtime,
                    "chunk_count": 0,  # unknown, already in ChromaDB
                    "ingested_at": datetime.now().isoformat(),
                }
        self.save()
        logger.info(f"Manifest built: {len(self._data['files'])} files tracked")

    def _should_ignore(self, filepath: Path) -> bool:
        name = filepath.name
        return any(pattern in name for pattern in IGNORED_PATTERNS)


# ── Ingest Manager ─────────────────────────────────────────────────────────────

class IngestManager:
    """Handles incremental ingestion of new/changed files into ChromaDB."""

    def __init__(self):
        self._lock = threading.Lock()
        self._manifest = IngestManifest()
        self._embeddings = None
        self._vector_store = None

    def _ensure_loaded(self):
        """Lazy-load embeddings and vector store."""
        if self._embeddings is None:
            from langchain_community.embeddings import HuggingFaceEmbeddings
            from langchain_community.vectorstores import Chroma
            self._embeddings = HuggingFaceEmbeddings(
                model_name=EMBEDDING_MODEL,
                model_kwargs={"device": "cpu"},
            )
            self._vector_store = Chroma(
                persist_directory=str(CHROMA_DIR),
                embedding_function=self._embeddings,
                collection_name=COLLECTION_NAME,
            )

    def ingest_file(self, filepath: Path) -> int:
        """
        Incrementally ingest a single file.
        Deletes existing chunks for the file before re-ingesting.
        Returns number of chunks added.
        """
        if not filepath.exists():
            return 0
        if filepath.suffix not in SUPPORTED_EXTENSIONS:
            return 0

        with self._lock:
            self._ensure_loaded()
            self._delete_existing_chunks(filepath)
            docs = self._load_file(filepath)
            if not docs:
                return 0

            chunks = self._split_documents(docs)
            self._add_chunks(chunks)
            self._manifest.update(filepath, len(chunks))
            self._manifest.save()
            logger.info(f"Ingested {len(chunks)} chunks from {filepath.name}")
            return len(chunks)

    def ingest_new_files(self, files: list = None) -> int:
        """
        Ingest all new/changed files. If files is None, auto-detect from manifest.
        Returns total chunks added.
        """
        if files is None:
            files = self._manifest.get_new_or_changed_files()

        if not files:
            return 0

        total = 0
        for filepath in files:
            total += self.ingest_file(filepath)
        return total

    def initialize(self):
        """Initialize manifest on first run without re-ingesting existing files."""
        self._manifest.build_from_existing()

    def _delete_existing_chunks(self, filepath: Path):
        """Remove all existing chunks for a file from ChromaDB."""
        try:
            source_key = str(filepath.relative_to(KB_DIR))
            collection = self._vector_store._collection
            results = collection.get(where={"source": source_key})
            if results and results.get("ids"):
                collection.delete(ids=results["ids"])
                logger.debug(f"Deleted {len(results['ids'])} existing chunks for {filepath.name}")
        except Exception as e:
            logger.warning(f"Could not delete existing chunks for {filepath.name}: {e}")

    def _load_file(self, filepath: Path) -> list:
        """Load a file using the appropriate LangChain loader."""
        try:
            suffix = filepath.suffix.lower()
            rel_path = str(filepath.relative_to(KB_DIR))
            category = self._detect_category(filepath)

            if suffix == ".pdf":
                from langchain_community.document_loaders import PyPDFLoader
                loader = PyPDFLoader(str(filepath))
                docs = loader.load()
            elif suffix in (".md", ".txt"):
                # Use TextLoader for .md and .txt — UnstructuredMarkdownLoader
                # requires NLTK downloads not guaranteed in watcher context.
                from langchain_community.document_loaders import TextLoader
                loader = TextLoader(str(filepath), encoding="utf-8")
                docs = loader.load()
            else:
                return []

            # Enrich metadata
            for doc in docs:
                doc.metadata["source"] = rel_path
                doc.metadata["filename"] = filepath.name
                doc.metadata["category"] = category

            return docs
        except Exception as e:
            logger.error(f"Failed to load {filepath.name}: {e}")
            return []

    def _split_documents(self, docs: list) -> list:
        """Split documents into chunks."""
        from langchain.text_splitter import RecursiveCharacterTextSplitter
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
            separators=["\n\n", "\n", ".", " ", ""],
        )
        return splitter.split_documents(docs)

    def _add_chunks(self, chunks: list):
        """Add chunks to ChromaDB in batches."""
        batch_size = 100
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            self._vector_store.add_documents(batch)

    def _detect_category(self, filepath: Path) -> str:
        """Detect category from file path."""
        rel = str(filepath.relative_to(KB_DIR)).lower()
        if "standards" in rel:
            return "Standard"
        elif "methodologies" in rel:
            return "Methodology"
        elif "articles" in rel:
            return "Article"
        elif "expert_knowledge" in rel or "generated_strategies" in rel:
            return "Expert Knowledge"
        return "General"


# ── Knowledge Base Watcher ─────────────────────────────────────────────────────

class _FileEventHandler(FileSystemEventHandler):
    """Handles file system events with debouncing."""

    def __init__(self, ingest_manager: IngestManager, callback):
        super().__init__()
        self._manager = ingest_manager
        self._callback = callback
        self._pending = {}  # filepath → timer
        self._lock = threading.Lock()

    def on_created(self, event):
        if not event.is_directory:
            self._schedule(Path(event.src_path))

    def on_modified(self, event):
        if not event.is_directory:
            self._schedule(Path(event.src_path))

    def on_moved(self, event):
        if not event.is_directory:
            self._schedule(Path(event.dest_path))

    def _schedule(self, filepath: Path):
        """Debounce: cancel pending timer and reschedule."""
        if filepath.suffix not in SUPPORTED_EXTENSIONS:
            return
        if any(p in filepath.name for p in IGNORED_PATTERNS):
            return

        with self._lock:
            if filepath in self._pending:
                self._pending[filepath].cancel()
            timer = threading.Timer(
                DEBOUNCE_SECONDS,
                self._trigger_ingest,
                args=[filepath],
            )
            self._pending[filepath] = timer
            timer.start()

    def _trigger_ingest(self, filepath: Path):
        """Called after debounce period — run ingest."""
        with self._lock:
            self._pending.pop(filepath, None)

        try:
            chunks = self._manager.ingest_file(filepath)
            if chunks > 0 and self._callback:
                self._callback(f"✅ Knowledge base updated! +{chunks} new chunks from '{filepath.name}'")
        except Exception as e:
            logger.error(f"Auto-ingest failed for {filepath.name}: {e}")
            if self._callback:
                self._callback(f"⚠️ Auto-ingest failed for '{filepath.name}': {e}")


class KnowledgeBaseWatcher:
    """
    Watches knowledge_base/ for new/modified files and triggers incremental ingest.
    Runs in a background thread — never blocks the UI.
    """

    def __init__(self, ingest_manager: IngestManager = None):
        self._manager = ingest_manager or IngestManager()
        self._observer = None
        self._callback = None
        self._running = False

    def start(self, callback=None):
        """
        Start watching knowledge_base/ in a background thread.
        callback(message: str) is called after each successful ingest.
        """
        if self._running:
            return

        self._callback = callback
        self._manager.initialize()

        handler = _FileEventHandler(self._manager, callback)
        self._observer = Observer()
        self._observer.schedule(handler, str(KB_DIR), recursive=True)
        self._observer.start()
        self._running = True
        logger.info("Knowledge base watcher started")

    def stop(self):
        """Stop the file watcher."""
        if self._observer and self._running:
            self._observer.stop()
            self._observer.join()
            self._running = False
            logger.info("Knowledge base watcher stopped")

    @property
    def ingest_manager(self) -> IngestManager:
        return self._manager

    def is_running(self) -> bool:
        return self._running


# ── Module-level singleton ─────────────────────────────────────────────────────

_watcher: KnowledgeBaseWatcher = None


def get_watcher() -> KnowledgeBaseWatcher:
    """Get or create the global watcher singleton."""
    global _watcher
    if _watcher is None:
        _watcher = KnowledgeBaseWatcher()
    return _watcher


# ── Quick test ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    manager = IngestManager()
    manager.initialize()

    print("🔍 Checking for new or changed files...")
    new_files = IngestManifest().get_new_or_changed_files()

    if new_files:
        print(f"Found {len(new_files)} new/changed files:")
        for f in new_files:
            print(f"  - {f.name}")
        print("\n⚙️ Ingesting...")
        total = manager.ingest_new_files(new_files)
        print(f"✅ Done! Ingested {total} chunks")
    else:
        print("✅ Knowledge base is up to date — nothing to ingest")

    print("\n👁️ Starting file watcher (Ctrl+C to stop)...")

    def on_update(msg):
        print(f"\n{msg}")

    watcher = KnowledgeBaseWatcher(manager)
    watcher.start(callback=on_update)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        watcher.stop()
        print("\nWatcher stopped.")
