"""v3.9.2 regression tests for retrieve_qa_knowledge quality (end-user findings
F8 duplicated text, F7 misleading relevance, N8 silent k clamping). Keyless: a
deterministic fake embedder stands in for fastembed."""

import re
from pathlib import Path
from unittest.mock import patch

from qai_consultant.common.kb_config import CHUNK_OVERLAP, CHUNK_SIZE
from qai_consultant.mcp import local_index as li
from qai_consultant.mcp.local_index import LocalIndex, match_strength

_REPO_KB = li._DEFAULT_KB_DIR
_VOCAB = ["risk", "testing", "owasp", "api", "security", "istqb", "level", "gdpr", "tier", "ai"]


class _Fake:
    def embed_documents(self, texts):
        return [self._vec(t) for t in texts]

    def embed_query(self, text):
        return self._vec(text)

    @staticmethod
    def _vec(text):
        t = text.lower()
        v = [float(t.count(w)) for w in _VOCAB]
        return v if any(v) else [0.01] * len(_VOCAB)


def _index(kb: Path, tmp_path: Path) -> LocalIndex:
    with patch("qai_consultant.mcp.local_index._FastEmbedEmbeddings", return_value=_Fake()):
        idx = LocalIndex(kb_dir=kb, cache_dir=tmp_path / "cache")
        idx._ensure_built()
        return idx


def _write(kb: Path, files: dict) -> None:
    for rel, content in files.items():
        p = kb / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")


def _repeated_segments(text: str, min_len: int = 60) -> list:
    segs = [s.strip() for s in text.split("\n") if len(s.strip()) >= min_len]
    return sorted({s for s in segs if segs.count(s) > 1})


# ── F8: no chunk repeats itself ────────────────────────────────────────────────

def test_no_real_kb_chunk_repeats_a_paragraph_or_row():
    bad = []
    for path in sorted(_REPO_KB.rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        assert not _repeated_segments(text), f"{path} itself repeats a line; fix the source"
        for chunk in li._simple_chunk_splits(text, CHUNK_SIZE, CHUNK_OVERLAP):
            if _repeated_segments(chunk):
                bad.append(str(path.relative_to(_REPO_KB)))
    assert not bad, f"chunks with repeated >=60-char lines: {sorted(set(bad))}"


def test_returned_chunks_never_repeat_for_representative_queries(tmp_path):
    idx = _index(_REPO_KB, tmp_path)
    for q in ("EU AI Act risk tiers", "GDPR personal data", "OWASP security testing",
              "risk testing", "ai testing level", "api security"):
        for c in idx.search(q, k=20, min_score=0.0)["chunks"]:
            assert not _repeated_segments(c["text"]), (q, c["source"])


def test_overlap_is_applied_once_for_nested_oversize_sections():
    heading = "## Risk Tiers & Classification\n\n"
    para = "The Act regulates systems through tiers. Tier placement drives obligations. " * 3
    big = "- " + "word " * 400  # forces the recursive split path
    doc = "# T\n\nintro text here\n\n---\n\n" + heading + para + "\n" + big + "\n\n## Next\n\n" + para
    for chunk in li._simple_chunk_splits(doc, 1000, 200):
        assert chunk.count("## Risk Tiers & Classification") <= 1


# ── F7: header-only chunks, labels, excluded sources ───────────────────────────

def test_header_only_chunks_are_not_indexed(tmp_path):
    kb = tmp_path / "kb"
    body = "OWASP API security testing covers authorization checks and rate limiting. " * 20
    _write(kb, {"standards/asvs.md": "# OWASP ASVS\n\n## Overview\n\n---\n\n" + "\n\n".join(
        [""] * 1) + "\n## Details\n\n" + body})
    idx = _index(kb, tmp_path)
    assert idx._chunks
    for c in idx._chunks:
        assert li._body_chars(c.text) >= li.MIN_BODY_CHARS


def test_body_chars_ignores_headings_rules_and_table_separators():
    assert li._body_chars("# Title\n\n## Sub\n---\n|---|---|\n") == 0
    assert li._body_chars("# Title\n\nReal content line.") == len("Real content line.")


def test_strong_requires_term_coverage():
    terms = li._query_terms("AI/ML system testing")
    low = li.term_coverage(terms, "test automation adoption API testing ai", "a.md")
    high = li.term_coverage(terms, "ai ml system testing guide", "a.md")
    assert match_strength(0.59, low) == "moderate"
    assert match_strength(0.59, high) == "strong"
    assert match_strength(0.59) == "strong"  # no coverage info: score only (back-compat)
    assert match_strength(0.45, 0.0) == "moderate" and match_strength(0.2, 1.0) == "weak"


def test_unrelated_high_score_chunk_not_labelled_strong(tmp_path):
    kb = tmp_path / "kb"
    _write(kb, {"articles/stats.md": "# Stats\n\n" + "testing testing ai statistics adoption. " * 20})
    idx = _index(kb, tmp_path)
    r = idx.search("ai ml system testing", k=3, min_score=0.0)
    assert r["chunks"] and all(c["match"] != "strong" for c in r["chunks"])
    assert "note" in r


def test_excluded_source_gets_honest_note(tmp_path):
    kb = tmp_path / "kb"
    _write(kb, {"standards/IEEE.md": "# IEEE 829\n\n" + "test level documentation plan. " * 20})
    r = _index(kb, tmp_path).search("ISTQB test levels", min_score=0.0)
    assert "ISTQB" in r["note"] and "not bundled" in r["note"]


def test_excluded_source_note_absent_when_source_is_indexed(tmp_path):
    kb = tmp_path / "kb"
    _write(kb, {"standards/istqb/Syllabus.md": "# ISTQB Syllabus\n\n" + "test level istqb content. " * 20})
    r = _index(kb, tmp_path).search("ISTQB test levels", min_score=0.0)
    assert "Not in the knowledge base" not in r.get("note", "")


def test_no_note_for_ordinary_query(tmp_path):
    kb = tmp_path / "kb"
    _write(kb, {"methodologies/rbt.md": "# RBT\n\n" + "risk testing prioritisation. " * 20})
    r = _index(kb, tmp_path).search("risk testing", min_score=0.0)
    assert "Not in the knowledge base" not in r.get("note", "")


# ── N8: k clamping is reported ─────────────────────────────────────────────────

def test_k_out_of_range_is_clamped_with_warning(tmp_path):
    kb = tmp_path / "kb"
    _write(kb, {"methodologies/rbt.md": "# RBT\n\n" + "risk testing prioritisation. " * 20})
    idx = _index(kb, tmp_path)
    for given, used in ((0, 1), (-1, 1), (100, 20)):
        r = idx.search("risk testing", k=given, min_score=0.0)
        assert r["warnings"] == [f"k={given} is outside [1, 20]; it was clamped to {used}."]
    assert "warnings" not in idx.search("risk testing", k=5, min_score=0.0)


def test_non_integer_k_is_a_structured_error(tmp_path):
    kb = tmp_path / "kb"
    _write(kb, {"methodologies/rbt.md": "# RBT\n\n" + "risk testing. " * 20})
    r = _index(kb, tmp_path).search("risk", k="five")
    assert r["error"] == "invalid_argument"


def test_cache_invalidated_by_format_bump(tmp_path):
    # Old (format 2) caches hold duplicated/header-only chunks and must never be read.
    assert li._CACHE_FORMAT_VERSION >= 3
