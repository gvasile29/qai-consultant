"""
QAI Consultant — Local Knowledge Base Index (v3.0, MCP server).

A fully local, keyless, in-memory cosine-similarity index over
``knowledge_base/**/*.md`` — the retrieval backend behind the MCP server's
``retrieve_qa_knowledge`` and ``list_kb_sources`` tools. No Pinecone, no API
keys: the same embedding model and chunking parameters as the production
Pinecone index (via ``kb_config``), computed locally and cached to disk.

Deliberately different from ``evals/rag.py``'s index: that one embeds
whole-document 4000-char excerpts, which is adequate for eval labelling but
too coarse for real retrieval. This module chunks at 1000/200 like
``ingest.py`` so served results match what the production RAG pipeline
actually retrieves.

Only ``.md`` files are indexed (PDFs excluded — see MCP_PLAN.md section 5's
licensing gate: the distributed MCP package ships no third-party PDFs).
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from langchain_community.embeddings import HuggingFaceEmbeddings

from kb_config import CHUNK_OVERLAP, CHUNK_SIZE, EMBEDDING_MODEL, get_source_category

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_KB_DIR = _REPO_ROOT / "knowledge_base"
_CACHE_FORMAT_VERSION = 1  # bump if the cache file's schema changes


def _default_cache_dir() -> Path:
    """platformdirs cache dir (Windows %LOCALAPPDATA%, Linux ~/.cache, etc.);
    a plain fallback under the repo if platformdirs is unavailable for some
    reason — never crash just because the cache location can't be resolved."""
    try:
        from platformdirs import user_cache_dir
        return Path(user_cache_dir("qai-consultant-mcp", "qai-consultant"))
    except Exception:
        return _REPO_ROOT / ".qai_mcp_cache"


VALID_CATEGORIES = ("Standard", "Methodology", "Article", "Expert Knowledge", "Audit/Evaluation")


@dataclass(frozen=True)
class Chunk:
    text: str
    source: str      # KB-relative path, e.g. "methodologies/Risk_Based_Testing.md"
    category: str
    title: str        # first "# " heading in the source file, or its filename


def _simple_chunk_splits(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    """Chunk on the same separator priority ingest.py's RecursiveCharacterTextSplitter
    uses (## headings first, then paragraph/line/word boundaries), without requiring
    langchain at import time — keeps this module's dependency surface minimal for the
    MCP server path. Not byte-identical to langchain's splitter, but the same
    size/overlap/separator *policy*, which is what determines retrieval granularity."""
    if len(text) <= chunk_size:
        return [text] if text.strip() else []

    separators = ["\n## ", "\n### ", "\n---", "\n\n", "\n", " "]

    def split(piece: str, seps: list[str]) -> list[str]:
        if len(piece) <= chunk_size:
            return [piece] if piece.strip() else []
        if not seps:
            # No more separators — hard-cut at chunk_size with overlap.
            out = []
            start = 0
            while start < len(piece):
                out.append(piece[start:start + chunk_size])
                start += max(chunk_size - chunk_overlap, 1)
            return [c for c in out if c.strip()]

        sep, rest_seps = seps[0], seps[1:]
        parts = piece.split(sep)
        if len(parts) == 1:
            return split(piece, rest_seps)

        # Reassemble parts into chunks close to chunk_size, preserving the
        # separator between parts (except the very first part).
        rejoined = [parts[0]] + [sep + p for p in parts[1:]]
        chunks: list[str] = []
        current = ""
        for part in rejoined:
            if len(part) > chunk_size:
                if current.strip():
                    chunks.append(current)
                chunks.extend(split(part, rest_seps))
                current = ""
                continue
            if len(current) + len(part) <= chunk_size:
                current += part
            else:
                if current.strip():
                    chunks.append(current)
                current = part
        if current.strip():
            chunks.append(current)

        # Apply overlap between consecutive chunks.
        if chunk_overlap > 0 and len(chunks) > 1:
            overlapped = [chunks[0]]
            for c in chunks[1:]:
                prev_tail = overlapped[-1][-chunk_overlap:]
                overlapped.append(prev_tail + c)
            return overlapped
        return chunks

    return [c for c in split(text, separators) if c.strip()]


def _first_heading_or_filename(text: str, path: Path) -> str:
    match = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return path.name


def _kb_content_hash(kb_dir: Path) -> str:
    """Hash of every .md file's relative path + content, sorted for determinism.
    Used both as kb_version (so MCP callers can detect drift) and the cache key
    (so an edited/added/removed KB file self-invalidates the disk cache)."""
    h = hashlib.sha256()
    for path in sorted(kb_dir.rglob("*.md")):
        rel = str(path.relative_to(kb_dir)).replace("\\", "/")
        h.update(rel.encode("utf-8"))
        h.update(path.read_bytes())
    return h.hexdigest()[:16]


class LocalIndex:
    """In-memory cosine index over knowledge_base/*.md, with a disk-backed
    embeddings cache. Safe to construct repeatedly (e.g. per MCP server
    start) — a matching cache makes construction fast; anything else
    (missing, corrupted, stale) triggers a full local rebuild."""

    def __init__(self, kb_dir: Optional[Path] = None, cache_dir: Optional[Path] = None):
        self.kb_dir = Path(kb_dir) if kb_dir else _DEFAULT_KB_DIR
        self.cache_dir = Path(cache_dir) if cache_dir else _default_cache_dir()
        self._chunks: list[Chunk] = []
        self._vectors: list[list[float]] = []
        self._norms: list[float] = []
        self.kb_version: str = ""
        self._qcache: dict[str, list[float]] = {}
        self._embedder = None
        self._build_or_load()

    # ── Construction ─────────────────────────────────────────────────────────

    def _embedding_model(self):
        if self._embedder is None:
            self._embedder = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
        return self._embedder

    def _cache_path(self, kb_version: str) -> Path:
        return self.cache_dir / f"index_v{_CACHE_FORMAT_VERSION}_{kb_version}.json"

    def _build_or_load(self) -> None:
        kb_version = _kb_content_hash(self.kb_dir)
        self.kb_version = kb_version
        cache_path = self._cache_path(kb_version)

        if cache_path.exists():
            try:
                self._load_cache(cache_path)
                return
            except Exception:
                pass  # corrupted/unreadable cache — fall through to a rebuild

        self._build_fresh(kb_version)
        try:
            self._save_cache(cache_path)
        except Exception:
            pass  # a cache write failure must never break index construction

    def _build_fresh(self, kb_version: str) -> None:
        chunks: list[Chunk] = []
        for path in sorted(self.kb_dir.rglob("*.md")):
            text = path.read_text(encoding="utf-8")
            rel_source = str(path.relative_to(self.kb_dir)).replace("\\", "/")
            category = get_source_category(path)
            title = _first_heading_or_filename(text, path)
            for piece in _simple_chunk_splits(text, CHUNK_SIZE, CHUNK_OVERLAP):
                chunks.append(Chunk(text=piece, source=rel_source, category=category, title=title))

        self._chunks = chunks
        if chunks:
            vecs = self._embedding_model().embed_documents([c.text for c in chunks])
        else:
            vecs = []
        self._vectors = vecs
        self._norms = [math.sqrt(sum(x * x for x in v)) or 1.0 for v in vecs]
        self._qcache = {}

    # ── Disk cache ───────────────────────────────────────────────────────────

    def _save_cache(self, cache_path: Path) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "format_version": _CACHE_FORMAT_VERSION,
            "kb_version": self.kb_version,
            "embedding_model": EMBEDDING_MODEL,
            "chunks": [
                {"text": c.text, "source": c.source, "category": c.category, "title": c.title}
                for c in self._chunks
            ],
            "vectors": self._vectors,
        }
        tmp_path = cache_path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(payload), encoding="utf-8")
        tmp_path.replace(cache_path)  # atomic on both Windows and POSIX

    def _load_cache(self, cache_path: Path) -> None:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
        if payload.get("format_version") != _CACHE_FORMAT_VERSION:
            raise ValueError("cache format version mismatch")
        if payload.get("embedding_model") != EMBEDDING_MODEL:
            raise ValueError("cache embedding model mismatch")
        chunks = [
            Chunk(text=c["text"], source=c["source"], category=c["category"], title=c["title"])
            for c in payload["chunks"]
        ]
        vectors = payload["vectors"]
        if len(chunks) != len(vectors):
            raise ValueError("cache chunk/vector count mismatch")
        self._chunks = chunks
        self._vectors = vectors
        self._norms = [math.sqrt(sum(x * x for x in v)) or 1.0 for v in vectors]
        self._qcache = {}

    # ── Query ────────────────────────────────────────────────────────────────

    def _query_vector(self, query: str) -> list[float]:
        if query not in self._qcache:
            self._qcache[query] = self._embedding_model().embed_query(query)
        return self._qcache[query]

    def search(self, query: str, category: Optional[str] = None, k: int = 5) -> dict:
        """Returns {"chunks": [...], "kb_version": ...} on success, or
        {"error": "invalid_argument", "message": ..., "valid_categories": [...]}
        for an unrecognized category — never raises for a bad category."""
        if category is not None and category not in VALID_CATEGORIES:
            return {
                "error": "invalid_argument",
                "message": f"Unknown category {category!r}.",
                "valid_categories": list(VALID_CATEGORIES),
            }

        k = max(1, min(k, 20))

        if not self._chunks:
            return {"chunks": [], "kb_version": self.kb_version}

        qvec = self._query_vector(query)
        qnorm = math.sqrt(sum(x * x for x in qvec)) or 1.0

        scored = []
        for i, chunk in enumerate(self._chunks):
            if category is not None and chunk.category != category:
                continue
            dot = sum(a * b for a, b in zip(qvec, self._vectors[i]))
            score = dot / (qnorm * self._norms[i])
            scored.append((score, chunk))

        scored.sort(key=lambda pair: pair[0], reverse=True)
        top = scored[:k]

        return {
            "chunks": [
                {"source": c.source, "category": c.category, "text": c.text, "score": round(score, 4)}
                for score, c in top
            ],
            "kb_version": self.kb_version,
        }

    def list_sources(self) -> dict:
        """Returns {"categories": {category: [{"source", "title"}]}, "kb_version", "doc_count"}."""
        seen: dict[str, dict[str, str]] = {}
        for chunk in self._chunks:
            seen.setdefault(chunk.category, {})[chunk.source] = chunk.title

        categories = {
            category: [{"source": src, "title": title} for src, title in sorted(sources.items())]
            for category, sources in sorted(seen.items())
        }
        doc_count = sum(len(v) for v in categories.values())

        return {"categories": categories, "kb_version": self.kb_version, "doc_count": doc_count}
