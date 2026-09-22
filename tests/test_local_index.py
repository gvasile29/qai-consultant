"""
Tests for src/local_index.py — the MCP server's local, keyless KB index.

Uses a small synthetic knowledge_base/ (tmp_path) and a deterministic fake
embedder (bag-of-words over a fixed vocabulary) instead of the real fastembed
model, so these tests are fast and don't depend on model-download
availability. The real model is exercised by evals/local_index_parity.py
against the actual knowledge_base/.

Covers: chunk counts/boundaries, category filtering, disk-cache round-trip,
cache invalidation on KB edits, corrupted-cache recovery, and k clamping.
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from local_index import LocalIndex, VALID_CATEGORIES, _kb_content_hash


_VOCAB = ["apple", "banana", "cherry", "risk", "testing", "priority", "gdpr", "security"]


class _FakeEmbeddings:
    """Deterministic bag-of-word-count vectors over a small fixed vocabulary —
    good enough to make cosine ranking predictable in tests without loading
    the real sentence-transformers model."""

    def embed_documents(self, texts):
        return [self._vec(t) for t in texts]

    def embed_query(self, text):
        return self._vec(text)

    def _vec(self, text):
        t = text.lower()
        vec = [float(t.count(w)) for w in _VOCAB]
        return vec if any(vec) else [0.01] * len(_VOCAB)  # avoid an all-zero vector


def _write_kb(kb_dir: Path, files: dict) -> None:
    for rel_path, content in files.items():
        p = kb_dir / rel_path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")


def _build_index(kb_dir: Path, cache_dir: Path) -> LocalIndex:
    """Construct AND eagerly build the corpus index — LocalIndex itself is
    lazy now (see local_index.py's _ensure_built() docstring), but these
    tests are about corpus/cache mechanics, not the lazy-build timing
    itself, so force it here to keep their original intent."""
    with patch("local_index._FastEmbedEmbeddings", return_value=_FakeEmbeddings()):
        index = LocalIndex(kb_dir=kb_dir, cache_dir=cache_dir)
        index._ensure_built()
        return index


# ── Chunk counts and boundaries ─────────────────────────────────────────────────

def test_short_document_becomes_one_chunk(tmp_path):
    kb = tmp_path / "kb"
    _write_kb(kb, {"standards/short.md": "# Short Doc\n\nJust a few words."})
    idx = _build_index(kb, tmp_path / "cache")
    sources = {c.source for c in idx._chunks}
    assert sources == {"standards/short.md"}
    assert len(idx._chunks) == 1


def test_long_document_splits_into_multiple_chunks(tmp_path):
    from local_index import CHUNK_SIZE, CHUNK_OVERLAP
    kb = tmp_path / "kb"
    paragraph = "This paragraph discusses testing priority and risk. " * 20  # ~1100 chars
    long_text = "# Long Doc\n\n" + "\n\n".join([paragraph] * 5)  # well over CHUNK_SIZE
    _write_kb(kb, {"standards/long.md": long_text})
    idx = _build_index(kb, tmp_path / "cache")

    chunks = [c for c in idx._chunks if c.source == "standards/long.md"]
    assert len(chunks) > 1, "A document well over CHUNK_SIZE must split into multiple chunks"
    for c in chunks:
        assert len(c.text) <= CHUNK_SIZE + CHUNK_OVERLAP, (
            f"Chunk length {len(c.text)} exceeds CHUNK_SIZE+CHUNK_OVERLAP "
            f"({CHUNK_SIZE + CHUNK_OVERLAP})"
        )
        assert c.text.strip(), "No empty/whitespace-only chunks"


def test_chunk_title_extraction(tmp_path):
    kb = tmp_path / "kb"
    _write_kb(kb, {
        "standards/with_heading.md": "# My Standard Title\n\nSome content here about risk.",
        "standards/no_heading.md": "Some content with no top-level heading at all, about testing.",
    })
    idx = _build_index(kb, tmp_path / "cache")
    titles = {c.source: c.title for c in idx._chunks}
    assert titles["standards/with_heading.md"] == "My Standard Title"
    assert titles["standards/no_heading.md"] == "no_heading.md"


# ── Category filter ──────────────────────────────────────────────────────────────

def test_category_filter_only_returns_matching_category(tmp_path):
    kb = tmp_path / "kb"
    _write_kb(kb, {
        "standards/std.md": "# Std Doc\n\nrisk risk risk testing priority",
        "methodologies/meth.md": "# Meth Doc\n\nrisk risk risk testing priority",
    })
    idx = _build_index(kb, tmp_path / "cache")

    result = idx.search("risk testing priority", category="Standard", k=10)
    assert "error" not in result
    assert all(c["category"] == "Standard" for c in result["chunks"])
    assert any(c["source"] == "standards/std.md" for c in result["chunks"])
    assert not any(c["source"] == "methodologies/meth.md" for c in result["chunks"])


def test_invalid_category_returns_structured_error_not_raise(tmp_path):
    kb = tmp_path / "kb"
    _write_kb(kb, {"standards/std.md": "# Std\n\ncontent"})
    idx = _build_index(kb, tmp_path / "cache")

    result = idx.search("anything", category="NotACategory")
    assert result["error"] == "invalid_argument"
    assert set(result["valid_categories"]) == set(VALID_CATEGORIES)


# ── k clamping ───────────────────────────────────────────────────────────────────

def test_k_clamped_to_minimum_1(tmp_path):
    kb = tmp_path / "kb"
    _write_kb(kb, {f"standards/doc{i}.md": f"# Doc {i}\n\nrisk testing content {i}" for i in range(5)})
    idx = _build_index(kb, tmp_path / "cache")

    result = idx.search("risk testing", k=0)
    assert len(result["chunks"]) == 1

    result_negative = idx.search("risk testing", k=-5)
    assert len(result_negative["chunks"]) == 1


def test_k_clamped_to_maximum_20(tmp_path):
    kb = tmp_path / "kb"
    _write_kb(kb, {f"standards/doc{i}.md": f"# Doc {i}\n\nrisk testing content number {i}" for i in range(30)})
    idx = _build_index(kb, tmp_path / "cache")

    result = idx.search("risk testing", k=100)
    assert len(result["chunks"]) == 20


# ── Disk cache round-trip ────────────────────────────────────────────────────────

def test_cache_round_trip_avoids_recomputing_embeddings(tmp_path):
    kb = tmp_path / "kb"
    cache_dir = tmp_path / "cache"
    _write_kb(kb, {"standards/std.md": "# Std\n\nrisk testing content"})

    fake1 = _FakeEmbeddings()
    with patch("local_index._FastEmbedEmbeddings", return_value=fake1):
        idx1 = LocalIndex(kb_dir=kb, cache_dir=cache_dir)
        idx1._ensure_built()
    assert len(list(cache_dir.glob("*.json"))) == 1, "First construction must write a cache file"

    with patch("local_index._FastEmbedEmbeddings") as mock_cls:
        idx2 = LocalIndex(kb_dir=kb, cache_dir=cache_dir)
        idx2._ensure_built()
        mock_cls.assert_not_called()  # unchanged KB must load from cache, not re-embed

    assert idx2.kb_version == idx1.kb_version
    assert len(idx2._chunks) == len(idx1._chunks)
    assert idx2._vectors == idx1._vectors


def test_cache_invalidates_when_kb_file_changes(tmp_path):
    kb = tmp_path / "kb"
    cache_dir = tmp_path / "cache"
    _write_kb(kb, {"standards/std.md": "# Std\n\noriginal content about risk"})

    idx1 = _build_index(kb, cache_dir)
    version1 = idx1.kb_version

    _write_kb(kb, {"standards/std.md": "# Std\n\nCHANGED content about testing priority"})

    with patch("local_index._FastEmbedEmbeddings", return_value=_FakeEmbeddings()) as mock_cls:
        idx2 = LocalIndex(kb_dir=kb, cache_dir=cache_dir)
        idx2._ensure_built()
        assert mock_cls.called, "An edited KB file must invalidate the cache and trigger a rebuild"

    assert idx2.kb_version != version1
    remaining = list(cache_dir.glob("*.json"))
    assert len(remaining) == 1, (
        "The stale (old kb_version) cache file must be evicted once the new "
        "one is successfully written, not left to accumulate forever"
    )
    assert idx2.kb_version in remaining[0].name


def test_kb_content_hash_changes_on_new_file(tmp_path):
    kb = tmp_path / "kb"
    _write_kb(kb, {"standards/a.md": "content a"})
    h1 = _kb_content_hash(kb)
    _write_kb(kb, {"standards/b.md": "content b"})
    h2 = _kb_content_hash(kb)
    assert h1 != h2


# ── Corrupted cache recovery ──────────────────────────────────────────────────────

def test_corrupted_cache_falls_back_to_rebuild(tmp_path):
    kb = tmp_path / "kb"
    cache_dir = tmp_path / "cache"
    _write_kb(kb, {"standards/std.md": "# Std\n\nrisk testing content"})

    idx1 = _build_index(kb, cache_dir)
    cache_files = list(cache_dir.glob("*.json"))
    assert len(cache_files) == 1
    cache_files[0].write_text("{ this is not valid json !!!", encoding="utf-8")

    with patch("local_index._FastEmbedEmbeddings", return_value=_FakeEmbeddings()):
        idx2 = LocalIndex(kb_dir=kb, cache_dir=cache_dir)
        idx2._ensure_built()  # must not raise

    assert idx2.kb_version == idx1.kb_version
    assert len(idx2._chunks) == len(idx1._chunks)
    result = idx2.search("risk testing")
    assert "error" not in result
    assert result["chunks"]


def test_cache_with_wrong_embedding_model_falls_back_to_rebuild(tmp_path):
    kb = tmp_path / "kb"
    cache_dir = tmp_path / "cache"
    _write_kb(kb, {"standards/std.md": "# Std\n\nrisk testing content"})

    idx1 = _build_index(kb, cache_dir)
    cache_files = list(cache_dir.glob("*.json"))
    payload = json.loads(cache_files[0].read_text(encoding="utf-8"))
    payload["embedding_model"] = "some/other-model"
    cache_files[0].write_text(json.dumps(payload), encoding="utf-8")

    with patch("local_index._FastEmbedEmbeddings", return_value=_FakeEmbeddings()) as mock_cls:
        idx2 = LocalIndex(kb_dir=kb, cache_dir=cache_dir)
        idx2._ensure_built()
        assert mock_cls.called, "A cache built with a different embedding model must not be trusted"

    assert idx2.kb_version == idx1.kb_version


def test_cache_format_version_is_2():
    from local_index import _CACHE_FORMAT_VERSION
    assert _CACHE_FORMAT_VERSION == 2, (
        "Bumped for the fastembed backend switch — an old format-1 cache (built "
        "with sentence-transformers vectors) must never be read as if it were "
        "fastembed output; see docs/superpowers/specs/"
        "2026-09-17-mcp-embedding-backend-simplification-design.md"
    )


def test_cache_written_under_old_format_version_is_treated_as_miss(tmp_path):
    kb = tmp_path / "kb"
    cache_dir = tmp_path / "cache"
    _write_kb(kb, {"standards/std.md": "# Std\n\nrisk testing content"})

    idx1 = _build_index(kb, cache_dir)
    cache_files = list(cache_dir.glob("*.json"))
    assert len(cache_files) == 1
    payload = json.loads(cache_files[0].read_text(encoding="utf-8"))
    payload["format_version"] = 1  # simulate a pre-upgrade, sentence-transformers-era cache
    cache_files[0].write_text(json.dumps(payload), encoding="utf-8")

    with patch("local_index._FastEmbedEmbeddings", return_value=_FakeEmbeddings()) as mock_cls:
        idx2 = LocalIndex(kb_dir=kb, cache_dir=cache_dir)
        idx2._ensure_built()
        assert mock_cls.called, "A format-1 cache must not be trusted after the format-2 bump"

    assert idx2.kb_version == idx1.kb_version


# ── Stale cache eviction (architecture-review Minor finding #5) ────────────────────

def test_stale_format_version_cache_file_is_evicted_on_rebuild(tmp_path):
    """A leftover index_v1_*.json (pre-fastembed-switch cache) must be
    cleaned up once a fresh format-2 cache is successfully built, not left
    to accumulate forever across format-version bumps."""
    kb = tmp_path / "kb"
    cache_dir = tmp_path / "cache"
    _write_kb(kb, {"standards/std.md": "# Std\n\nrisk testing content"})

    stale_v1 = cache_dir / "index_v1_deadbeefdeadbeef.json"
    cache_dir.mkdir(parents=True)
    stale_v1.write_text("{}", encoding="utf-8")

    idx = _build_index(kb, cache_dir)

    remaining = list(cache_dir.glob("*.json"))
    assert not stale_v1.exists(), "Stale format-1 cache file must be evicted"
    assert len(remaining) == 1
    assert idx.kb_version in remaining[0].name


def test_eviction_never_deletes_the_just_written_cache_file(tmp_path):
    kb = tmp_path / "kb"
    cache_dir = tmp_path / "cache"
    _write_kb(kb, {"standards/std.md": "# Std\n\nrisk testing content"})

    idx = _build_index(kb, cache_dir)

    cache_files = list(cache_dir.glob("*.json"))
    assert len(cache_files) == 1
    assert idx.kb_version in cache_files[0].name


def test_eviction_failure_does_not_break_index_construction(tmp_path, monkeypatch):
    """A best-effort cleanup: if deleting a stale cache file raises for any
    reason, _ensure_built() must still succeed rather than propagate."""
    kb = tmp_path / "kb"
    cache_dir = tmp_path / "cache"
    _write_kb(kb, {"standards/std.md": "# Std\n\nrisk testing content"})

    with patch("local_index._FastEmbedEmbeddings", return_value=_FakeEmbeddings()):
        idx = LocalIndex(kb_dir=kb, cache_dir=cache_dir)
        with patch.object(LocalIndex, "_evict_stale_cache_files", side_effect=OSError("boom")):
            idx._ensure_built()  # must not raise

    assert idx._built
    result = idx.search("risk testing")
    assert "error" not in result


# ── Query-vector LRU cache bound (architecture-review Minor finding #6) ────────────

def test_qcache_evicts_least_recently_used_entry_past_the_cap(tmp_path):
    from local_index import _MAX_QCACHE_ENTRIES

    kb = tmp_path / "kb"
    _write_kb(kb, {"standards/std.md": "# Std\n\nrisk testing content"})
    idx = _build_index(kb, tmp_path / "cache")

    for i in range(_MAX_QCACHE_ENTRIES):
        idx._query_vector(f"query {i}")
    assert len(idx._qcache) == _MAX_QCACHE_ENTRIES
    assert "query 0" in idx._qcache

    idx._query_vector("query overflow")

    assert len(idx._qcache) == _MAX_QCACHE_ENTRIES, "Cache must stay capped at _MAX_QCACHE_ENTRIES"
    assert "query 0" not in idx._qcache, "The least-recently-used entry must be evicted"
    assert "query overflow" in idx._qcache


def test_qcache_hit_refreshes_recency_and_protects_from_eviction(tmp_path):
    from local_index import _MAX_QCACHE_ENTRIES

    kb = tmp_path / "kb"
    _write_kb(kb, {"standards/std.md": "# Std\n\nrisk testing content"})
    idx = _build_index(kb, tmp_path / "cache")

    for i in range(_MAX_QCACHE_ENTRIES):
        idx._query_vector(f"query {i}")

    idx._query_vector("query 0")  # re-access — should move to most-recently-used
    idx._query_vector("query overflow")  # should now evict "query 1", not "query 0"

    assert "query 0" in idx._qcache
    assert "query 1" not in idx._qcache


# ── list_sources() ────────────────────────────────────────────────────────────────

def test_list_sources_groups_by_category(tmp_path):
    kb = tmp_path / "kb"
    _write_kb(kb, {
        "standards/std.md": "# Standard Doc\n\ncontent",
        "methodologies/meth.md": "# Method Doc\n\ncontent",
    })
    idx = _build_index(kb, tmp_path / "cache")
    result = idx.list_sources()

    assert result["doc_count"] == 2
    assert result["kb_version"] == idx.kb_version
    assert "Standard" in result["categories"]
    assert "Methodology" in result["categories"]
    assert result["categories"]["Standard"] == [{"source": "standards/std.md", "title": "Standard Doc"}]


def test_empty_kb_does_not_crash(tmp_path):
    kb = tmp_path / "kb"
    kb.mkdir()
    idx = _build_index(kb, tmp_path / "cache")
    assert idx._chunks == []
    result = idx.search("anything")
    assert result["chunks"] == []
    sources = idx.list_sources()
    assert sources["doc_count"] == 0
