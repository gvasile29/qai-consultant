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
import threading
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from fastembed import TextEmbedding

from qai_consultant.common.kb_config import CHUNK_OVERLAP, CHUNK_SIZE, EMBEDDING_MODEL, get_source_category

_REPO_ROOT = Path(__file__).resolve().parents[3]
_CACHE_FORMAT_VERSION = 4  # 4: chunks capped at chunk_size incl. overlap, header-only judged pre-overlap (3: single-pass overlap, 2: fastembed backend)
_MAX_QCACHE_ENTRIES = 256  # LRU cap on _query_vector()'s per-instance cache


def _resolve_default_kb_dir() -> Path:
    """knowledge_base/ lives two different places depending on how this module
    got here: a sibling of src/ in the git repo (dev), or a sibling of the
    qai_consultant package once installed (site-packages/knowledge_base/, a
    top-level package next to site-packages/qai_consultant/). Repo layout is checked
    first since it's the more common case during development/testing."""
    repo_layout = _REPO_ROOT / "knowledge_base"
    if repo_layout.is_dir():
        return repo_layout
    return Path(__file__).resolve().parents[2] / "knowledge_base"


_DEFAULT_KB_DIR = _resolve_default_kb_dir()


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

STRONG_MATCH = 0.55
MODERATE_MATCH = 0.40
WEAK_MATCH_NOTE = (
    "No strong match: the best chunk is only a moderate or weak semantic match, and chunks "
    "tagged \"weak\" are often a different topic that merely shares vocabulary. Use only "
    "chunks whose text actually answers the question; otherwise answer from your own "
    "knowledge and say the knowledge base had no direct match."
)


STRONG_MIN_TERM_COVERAGE = 0.6  # share of the query's content terms a "strong" chunk must contain

_STOPWORDS = frozenset(
    "a an the of for to in on and or is are was were what how why when which who with by from as at "
    "be it its this that do does can i me my we our you your about use using vs".split()
)


def _stem(word: str) -> str:
    for suffix in ("ing", "es", "ed", "s"):
        if len(word) > len(suffix) + 3 and word.endswith(suffix):
            return word[: -len(suffix)]
    return word


def _query_terms(query: str) -> list[str]:
    return [_stem(w) for w in re.findall(r"[a-z0-9]+", query.lower()) if w not in _STOPWORDS]


def term_coverage(query_terms: list[str], text: str, source: str = "") -> float:
    """Share of the query's content terms (stopwords removed, crude stemming) that
    appear in the chunk text or its source path. 1.0 when the query has no terms."""
    if not query_terms:
        return 1.0
    present = {_stem(w) for w in re.findall(r"[a-z0-9]+", f"{text} {source}".lower())}
    return sum(t in present for t in query_terms) / len(query_terms)


def match_strength(score: float, coverage: Optional[float] = None) -> str:
    """Label a cosine score so callers need not guess what 0.456 means.

    Cosine similarity from a small embedding model compresses into 0.4-0.6 for
    anything that shares vocabulary, so the score alone over-states relevance
    (an automation-statistics article scored 0.55+ for "AI/ML system testing").
    When ``coverage`` (see ``term_coverage``) is given, "strong" additionally
    requires the chunk to contain at least STRONG_MIN_TERM_COVERAGE of the
    query's content terms; otherwise it is capped at "moderate"."""
    if score >= STRONG_MATCH:
        if coverage is None or coverage >= STRONG_MIN_TERM_COVERAGE:
            return "strong"
        return "moderate"
    return "moderate" if score >= MODERATE_MATCH else "weak"


LOW_RELEVANCE_NOTE = (
    "No sufficiently relevant match in the local knowledge base. The local index covers "
    "Markdown guides only (methodologies, selected standards, audit frameworks, case studies); "
    "the ISTQB and OWASP PDF syllabi are not included for licensing reasons, so fundamentals "
    "(e.g. test design techniques, test levels) are often absent. Answer from your own "
    "knowledge and say the knowledge base had no match."
)

# Sources people ask for by name that this KB deliberately does NOT ship (their
# PDFs are excluded by the wheel's licensing gate, see tests/system/release/
# test_packaging.py). name -> lowercase query aliases. A note is added when a
# query names one of them and no indexed document's path or title does.
EXCLUDED_SOURCES = {
    "ISTQB syllabi (CTFL/CTAL)": ("istqb", "ctfl", "ctal"),
    "OWASP Web Security Testing Guide (WSTG)": ("wstg",),
    "OWASP Mobile Application Security Testing Guide (MASTG)": ("mastg",),
}

CLAMP_WARNING = "k={given} is outside [1, 20]; it was clamped to {used}."

_DEDUPE_OVERLAP = 0.5  # overlap coefficient above which two same-source chunks are near-duplicates


def _shingles(text: str, n: int = 5) -> frozenset:
    words = text.lower().split()
    if len(words) < n:
        return frozenset([" ".join(words)]) if words else frozenset()
    return frozenset(" ".join(words[i:i + n]) for i in range(len(words) - n + 1))


def _overlap_ratio(a: frozenset, b: frozenset) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


@dataclass(frozen=True)
class Chunk:
    text: str
    source: str      # KB-relative path, e.g. "methodologies/Risk_Based_Testing.md"
    category: str
    title: str        # first "# " heading in the source file, or its filename


class _FastEmbedEmbeddings:
    """Adapter matching HuggingFaceEmbeddings' two methods LocalIndex calls,
    backed by fastembed's ONNX Runtime instead of sentence-transformers/torch —
    see docs/superpowers/specs/2026-09-17-mcp-embedding-backend-simplification-design.md.
    Cuts cold-start import time roughly 3x (no torch), which is what actually
    matters for the MCP server's uvx-launched cold start."""

    def __init__(self, model_name: str):
        self._model = TextEmbedding(model_name=model_name)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [v.tolist() for v in self._model.embed(texts)]

    def embed_query(self, text: str) -> list[float]:
        return next(iter(self._model.embed([text]))).tolist()


def _atoms(piece: str, chunk_size: int, seps: list[str]) -> list[str]:
    """Break ``piece`` into contiguous atoms of at most ``chunk_size`` characters
    along the highest-priority separator that applies. Atoms concatenate back to
    ``piece`` exactly (separators stay as a prefix of the following part), and no
    overlap is added here - overlap is applied exactly once, in the caller."""
    if len(piece) <= chunk_size:
        return [piece] if piece.strip() else []
    if not seps:
        return [c for c in (piece[i:i + chunk_size] for i in range(0, len(piece), chunk_size))
                if c.strip()]
    sep, rest = seps[0], seps[1:]
    parts = piece.split(sep)
    if len(parts) == 1:
        return _atoms(piece, chunk_size, rest)
    out: list[str] = []
    for part in [parts[0]] + [sep + p for p in parts[1:]]:
        out.extend(_atoms(part, chunk_size, rest))
    return out


def _overlap_tail(text: str, size: int) -> str:
    """Last ~``size`` characters of ``text``, trimmed forward to a word boundary
    so an overlap never starts mid-word."""
    if size <= 0:
        return ""
    tail = text[-size:]
    if len(text) > size and not text[-size - 1].isspace():
        cut = re.search(r"\s", tail)
        tail = tail[cut.end():] if cut else ""
    return tail


def _simple_chunk_splits(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    """Chunk on the same separator priority the production ingest splitter
    (RecursiveCharacterTextSplitter) uses (## headings first, then paragraph/line/word
    boundaries), without requiring langchain at import time - keeps this module's
    dependency surface minimal for the MCP server path. Not byte-identical to
    langchain's splitter, but the same size/overlap/separator *policy*, which is what
    determines retrieval granularity.

    Pipeline: split into atoms (<= chunk_size) -> greedily merge atoms into chunks
    (<= chunk_size) -> prepend each chunk with the tail of the PREVIOUS RAW chunk,
    once. (An earlier version applied overlap at every recursion level and so
    stacked the same heading/paragraph two or three times inside one chunk.)"""
    if len(text) <= chunk_size:
        return [text] if text.strip() else []

    # A finished chunk is its raw text plus the overlap tail, so raw text is capped at chunk_size -
    # chunk_overlap to keep every returned chunk within chunk_size, like the production splitter.
    limit = chunk_size - chunk_overlap if 0 < chunk_overlap < chunk_size else chunk_size
    separators = ["\n## ", "\n### ", "\n---", "\n\n", "\n", " "]
    merged: list[str] = []
    current = ""
    for atom in _atoms(text, limit, separators):
        if len(current) + len(atom) <= limit:
            current += atom
        else:
            if current.strip():
                merged.append(current)
            current = atom
    if current.strip():
        merged.append(current)
    # A tiny trailing chunk would be mostly its own overlap prefix (a near-duplicate
    # of its neighbour); fold it into the previous chunk instead.
    if len(merged) > 1 and len(merged[-1]) < chunk_overlap and len(merged[-2]) + len(merged[-1]) <= limit:
        tail_chunk = merged.pop()
        merged[-1] += tail_chunk

    out: list[str] = []
    for i, raw in enumerate(merged):
        # Header-only / near-empty RAW chunks are not indexed (judged before the overlap prefix is added,
        # which would otherwise count as body). Their tail still prefixes the next chunk, so the heading
        # stays attached to the content it introduces.
        if len(merged) > 1 and _body_chars(raw) < MIN_BODY_CHARS:
            continue
        prefix = _overlap_tail(merged[i - 1], chunk_overlap) if (i > 0 and chunk_overlap > 0) else ""
        out.append(prefix + raw)
    return out


_HEADING_RE = re.compile(r"#{1,6}\s")
_SEPARATOR_CHARS = frozenset("|:- \t")


def _is_non_body_line(line: str) -> bool:
    """Blank lines, headings, horizontal rules and table-separator rows. Plain string checks (no
    backtracking regex) so a pathological line cannot stall index construction."""
    s = line.strip()
    if not s or _HEADING_RE.match(s):
        return True
    if set(s) <= _SEPARATOR_CHARS:
        return True
    return len(s) >= 3 and len(set(s)) == 1 and s[0] in "*_"


def _body_chars(text: str) -> int:
    """Characters of real content in a chunk: everything except headings,
    horizontal rules, table-separator rows and blank lines."""
    return sum(len(line.strip()) for line in text.splitlines() if not _is_non_body_line(line))


MIN_BODY_CHARS = 80  # chunks with less real content than this are never indexed


def _first_heading_or_filename(text: str, path: Path) -> str:
    match = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return path.name


NON_INDEXED_DIRS = ("generated_strategies",)  # app feedback samples, not reference material; the wheel excludes them too


def _indexed_md_files(kb_dir: Path) -> list[Path]:
    """The .md files the local index serves: everything under the KB except sample documents the app saved
    from earlier runs (they are not standards, and a repo checkout must behave like the published wheel)."""
    return [
        p for p in sorted(kb_dir.rglob("*.md"))
        if p.relative_to(kb_dir).parts[0] not in NON_INDEXED_DIRS
    ]


def _kb_content_hash(kb_dir: Path) -> str:
    """Hash of every indexed .md file's relative path + content, sorted for determinism.
    Used both as kb_version (so MCP callers can detect drift) and the cache key
    (so an edited/added/removed KB file self-invalidates the disk cache)."""
    h = hashlib.sha256()
    for path in _indexed_md_files(kb_dir):
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
        # Cheap (file hashing only, no embedding) — safe to compute eagerly.
        self.kb_version: str = _kb_content_hash(self.kb_dir)
        self._qcache: "OrderedDict[str, list[float]]" = OrderedDict()
        self._embedder = None
        self._built = False
        self._build_lock = threading.Lock()

    # ── Construction ─────────────────────────────────────────────────────────

    def _embedding_model(self):
        if self._embedder is None:
            self._embedder = _FastEmbedEmbeddings(EMBEDDING_MODEL)
        return self._embedder

    def warmup_embedder(self) -> None:
        """Force the embedding model's one-time native init (model download
        if needed, native runtime thread + DLL init) via a single cheap
        embed_query() call — deliberately WITHOUT embedding the full KB
        corpus. Call this on the main thread before mcp.run() starts
        stdio_server()'s concurrent stdin-reader task: the Windows loader-
        lock deadlock documented in CLAUDE.md is specifically about that
        first native init racing the reader thread, not about subsequent
        calls into an already-initialized native runtime — so the (much
        slower) full corpus build in _ensure_built() can safely stay lazy
        and run later, off the main thread, once a real tool call needs it."""
        self._embedding_model().embed_query("warmup")

    def _cache_path(self, kb_version: str) -> Path:
        return self.cache_dir / f"index_v{_CACHE_FORMAT_VERSION}_{kb_version}.json"

    def _ensure_built(self) -> None:
        """Lazily build or load the full corpus index on first real use
        (search()/list_sources()) — deliberately not done in __init__ or
        warmup_embedder(); see warmup_embedder()'s docstring for why."""
        if self._built:
            return
        with self._build_lock:
            self._ensure_built_locked()

    def _ensure_built_locked(self) -> None:
        if self._built:
            return

        cache_path = self._cache_path(self.kb_version)
        if cache_path.exists():
            try:
                self._load_cache(cache_path)
                self._built = True
                return
            except Exception:
                pass  # corrupted/unreadable cache — fall through to a rebuild

        self._build_fresh()
        self._built = True
        try:
            self._save_cache(cache_path)
            self._evict_stale_cache_files(cache_path)
        except Exception:
            pass  # a cache write/eviction failure must never break index construction

    def _build_fresh(self) -> None:
        chunks: list[Chunk] = []
        for path in _indexed_md_files(self.kb_dir):
            text = path.read_text(encoding="utf-8")
            rel_source = str(path.relative_to(self.kb_dir)).replace("\\", "/")
            category = get_source_category(path)
            title = _first_heading_or_filename(text, path)
            pieces = _simple_chunk_splits(text, CHUNK_SIZE, CHUNK_OVERLAP)
            for piece in pieces:
                chunks.append(Chunk(text=piece, source=rel_source, category=category, title=title))

        self._chunks = chunks
        if chunks:
            vecs = self._embedding_model().embed_documents([c.text for c in chunks])
        else:
            vecs = []
        self._vectors = vecs
        self._norms = [math.sqrt(sum(x * x for x in v)) or 1.0 for v in vecs]
        self._qcache = OrderedDict()

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

    def _evict_stale_cache_files(self, current_path: Path) -> None:
        """Delete sibling index_v*_*.json cache files left behind by a prior
        KB content edit (old kb_version) or a _CACHE_FORMAT_VERSION bump (old
        format) — without this, the cache dir grows without bound across the
        life of an MCP install as the KB is edited over time."""
        for stale in self.cache_dir.glob("index_v*_*.json"):
            if stale != current_path:
                stale.unlink(missing_ok=True)

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
        self._qcache = OrderedDict()

    # ── Query ────────────────────────────────────────────────────────────────

    def _query_vector(self, query: str) -> list[float]:
        if query in self._qcache:
            self._qcache.move_to_end(query)
            return self._qcache[query]
        vec = self._embedding_model().embed_query(query)
        self._qcache[query] = vec
        if len(self._qcache) > _MAX_QCACHE_ENTRIES:
            self._qcache.popitem(last=False)
        return vec

    def search(
        self, query: str, category: Optional[str] = None, k: int = 5, min_score: float = 0.0,
    ) -> dict:
        """Returns {"chunks": [...], "kb_version": ..., "best_score": float|None,
        "low_relevance": bool[, "note": str]} on success, or
        {"error": "invalid_argument", "message": ..., ...} for an empty query,
        a non-numeric/out-of-range min_score, or an unrecognized category —
        never raises for those.

        Near-duplicate chunks (adjacent/overlapping chunks of one source whose
        text overlaps heavily) are collapsed, keeping the higher score, and
        the result is backfilled up to k.

        min_score (default 0.0 = off): chunks scoring below it are dropped.
        When nothing reaches it, `chunks` is empty and `low_relevance` is True
        with an explanatory `note`; `best_score` is the best cosine similarity
        found (before filtering), so the caller can see how close the miss was."""
        if not isinstance(query, str) or not query.strip():
            return {
                "error": "invalid_argument",
                "message": "query must be a non-empty string.",
            }
        if isinstance(min_score, bool) or not isinstance(min_score, (int, float)) \
                or not 0.0 <= float(min_score) <= 1.0:
            return {
                "error": "invalid_argument",
                "message": "min_score must be a number between 0 and 1.",
            }
        if category is not None and category not in VALID_CATEGORIES:
            return {
                "error": "invalid_argument",
                "message": f"Unknown category {category!r}.",
                "valid_categories": list(VALID_CATEGORIES),
            }

        if isinstance(k, bool) or not isinstance(k, int):
            return {
                "error": "invalid_argument",
                "message": "k must be an integer between 1 and 20.",
            }

        self._ensure_built()
        warnings: list[str] = []
        used_k = max(1, min(k, 20))
        if used_k != k:
            warnings.append(CLAMP_WARNING.format(given=k, used=used_k))
        k = used_k

        if not self._chunks:
            empty: dict = {"chunks": [], "kb_version": self.kb_version, "best_score": None,
                           "low_relevance": False}
            if warnings:
                empty["warnings"] = warnings
            return empty

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

        best_score = round(scored[0][0], 4) if scored else None
        top: list = []
        top_shingles: list = []
        for score, chunk in scored:
            if len(top) >= k or score < min_score:
                break
            shingles = _shingles(chunk.text)
            if any(
                prev.source == chunk.source and _overlap_ratio(shingles, prev_sh) > _DEDUPE_OVERLAP
                for (_, prev), prev_sh in zip(top, top_shingles)
            ):
                continue  # near-duplicate of a higher-scoring chunk already kept
            top.append((score, chunk))
            top_shingles.append(shingles)

        terms = _query_terms(query)
        labelled = [
            (score, c, match_strength(score, term_coverage(terms, c.text, c.source) if len(terms) >= 2 else None))
            for score, c in top
        ]
        result: dict = {
            "chunks": [
                {"source": c.source, "category": c.category, "text": c.text, "score": round(score, 4),
                 "match": label}
                for score, c, label in labelled
            ],
            "kb_version": self.kb_version,
            "best_score": best_score,
            "low_relevance": False,
        }
        if not top and min_score > 0.0:
            result["low_relevance"] = True
            result["note"] = LOW_RELEVANCE_NOTE
        elif top and not any(label == "strong" for _, _, label in labelled):
            result["note"] = WEAK_MATCH_NOTE
        excluded_note = self._excluded_source_note(query)
        if excluded_note:
            result["note"] = f"{result['note']} {excluded_note}" if "note" in result else excluded_note
        if warnings:
            result["warnings"] = warnings
        return result

    def _excluded_source_note(self, query: str) -> str:
        """Honest note when the query names a known source this KB does not ship."""
        words = set(re.findall(r"[a-z0-9]+", query.lower()))
        names = []
        for name, aliases in EXCLUDED_SOURCES.items():
            if not words.intersection(aliases):
                continue
            indexed = any(
                a in f"{c.source} {c.title}".lower() for c in self._chunks for a in aliases
            )
            if not indexed:
                names.append(name)
        if not names:
            return ""
        return (
            f"Not in the knowledge base: {', '.join(names)} (not bundled for licensing reasons). "
            "The chunks returned are from other documents and must not be cited as that source."
        )

    # ── Background build ─────────────────────────────────────────────────────

    def start_background_build(self) -> None:
        """Kick off _ensure_built() on a daemon thread so the first real
        search() doesn't pay the full-corpus embed. MUST only be called after
        warmup_embedder() has completed on the main thread (the native
        runtime's first init is what races stdio's reader on Windows; later
        calls from another thread are the same situation as a FastMCP worker
        thread). Never raises; a failed build is retried lazily by the first
        real call."""
        def _run() -> None:
            try:
                self._ensure_built()
            except Exception:
                pass

        threading.Thread(target=_run, name="qai-index-build", daemon=True).start()

    def list_sources(self) -> dict:
        """Returns {"categories": {category: [{"source", "title"}]}, "kb_version", "doc_count"}."""
        self._ensure_built()
        seen: dict[str, dict[str, str]] = {}
        for chunk in self._chunks:
            seen.setdefault(chunk.category, {})[chunk.source] = chunk.title

        categories = {
            category: [{"source": src, "title": title} for src, title in sorted(sources.items())]
            for category, sources in sorted(seen.items())
        }
        doc_count = sum(len(v) for v in categories.values())

        return {"categories": categories, "kb_version": self.kb_version, "doc_count": doc_count}
