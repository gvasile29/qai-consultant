"""
Tests for src/ingest.py — load_documents() encoding regression guard.

Background (bug fixed alongside this test): TextLoader, when constructed
without an explicit `encoding` argument, falls back to the platform-default
encoding (cp1252 on Windows). Almost every .md file in knowledge_base/
contains non-ASCII characters (em-dashes, arrows, box-drawing characters,
etc.), so decoding as cp1252 either:
  1. Raises UnicodeDecodeError outright (4 files, previously "Skipped"), or
  2. Silently succeeds but produces mojibake — WRONG TEXT ingested into
     Pinecone with no error or warning (the more dangerous half of the bug,
     affecting ~37 files).

These tests run load_documents() against the real knowledge_base/ directory
(no mocks, no network — TextLoader/PyPDFLoader just read local files) and
assert both symptoms are gone.

Covers:
1.  load_documents() reports zero skipped files, including the 4 files that
    previously raised UnicodeDecodeError under cp1252.
2.  For every loaded .md/.txt document, page_content exactly matches the
    file's own UTF-8 text (Path.read_text(encoding="utf-8")) — this is the
    test that would have caught the silent-mojibake half of the bug, since
    a wrong-encoding load does not raise and would be missed by test 1 alone.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from ingest import load_documents, KNOWLEDGE_BASE_DIR  # noqa: E402

# The 4 files that previously raised UnicodeDecodeError under cp1252 and were
# skipped entirely (hard-crash symptom).
PREVIOUSLY_CRASHING_FILES = {
    "BDD_TDD.md",
    "Test_Pyramid.md",
    "CONTRIBUTION_GUIDE.md",
    "Scenario_TeamAlignment.md",
}

# A sample of files that previously loaded "successfully" under cp1252 but
# with silently mojibake'd content (silent-corruption symptom) — plus the
# 4 crashing files above, since their content must also now be verified
# correct once they no longer crash.
FILES_TO_VERIFY_CONTENT = [
    "methodologies/BDD_TDD.md",
    "methodologies/Test_Pyramid.md",
    "expert_knowledge/CONTRIBUTION_GUIDE.md",
    "expert_knowledge/Scenario_TeamAlignment.md",
    "methodologies/Risk_Based_Testing.md",
    "standards/owasp/OWASP_Top10_2021.md",
]


def test_load_documents_skips_nothing():
    """No .md/.txt file should be skipped — in particular none of the 4
    files that previously raised UnicodeDecodeError under the platform's
    default (cp1252) encoding."""
    documents, skipped = load_documents(KNOWLEDGE_BASE_DIR)

    assert documents, "load_documents() returned no documents at all"
    assert not (set(skipped) & PREVIOUSLY_CRASHING_FILES), (
        f"Previously-crashing files are still being skipped: "
        f"{set(skipped) & PREVIOUSLY_CRASHING_FILES}"
    )
    assert skipped == [], f"Unexpected skipped files: {skipped}"


def test_loaded_text_matches_utf8_source_exactly():
    """For a sample of files spanning both bug symptoms (hard-crash and
    silent-mojibake), the loaded page_content must be byte-for-byte
    identical to decoding the file as UTF-8 directly. A cp1252 decode would
    not raise here but WOULD produce different text, which is exactly what
    this test catches."""
    documents, skipped = load_documents(KNOWLEDGE_BASE_DIR)

    by_source = {}
    for doc in documents:
        by_source.setdefault(doc.metadata["source"], []).append(doc)

    checked = 0
    for rel_path in FILES_TO_VERIFY_CONTENT:
        normalized = rel_path.replace("/", "\\")
        docs = by_source.get(rel_path) or by_source.get(normalized)
        assert docs, f"{rel_path} was not loaded (source keys: {list(by_source)[:5]}...)"
        assert len(docs) == 1, f"{rel_path} unexpectedly produced multiple documents"

        expected_text = (KNOWLEDGE_BASE_DIR / rel_path).read_text(encoding="utf-8")
        assert docs[0].page_content == expected_text, (
            f"{rel_path}: loaded content does not match UTF-8 source "
            f"(wrong-encoding decode likely reintroduced)"
        )
        checked += 1

    assert checked == len(FILES_TO_VERIFY_CONTENT)
