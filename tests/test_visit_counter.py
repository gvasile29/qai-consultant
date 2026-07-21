"""
Tests for get_and_increment_visit_count() in src/visit_counter.py.

All tests use unittest.mock — no real Pinecone network calls are made,
following the mocking style of test_llm_client.py (mock the client class,
not the network).

Covers:
1. First-ever visit: index.fetch() returns no match for the ID -> treated
   as count=0 -> function returns 1, upsert called with count=1.
2. Normal increment: index.fetch() returns metadata count=N -> function
   returns N+1, upsert called with count=N+1.
3. Failure path: index.fetch() raises -> function returns None, does not
   raise.
4. Failure path: the Pinecone client constructor raises -> function
   returns None, does not raise.
5. Failure path: _get_secret raises (missing credentials) -> function
   returns None, does not raise.
"""

import sys
import os
import pytest
os.environ["ANONYMIZED_TELEMETRY"] = "False"

from pathlib import Path
from unittest.mock import patch, MagicMock

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

import visit_counter
from visit_counter import get_and_increment_visit_count, NAMESPACE, VECTOR_ID, VECTOR_DIM


# ── Helpers ─────────────────────────────────────────────────────────────────────

def _make_fetch_response(count=None):
    """
    Fake Pinecone FetchResponse. When count is None, simulates "not found"
    (empty vectors mapping). Otherwise simulates a found vector whose
    metadata carries {"count": count}.
    """
    response = MagicMock()
    if count is None:
        response.vectors = {}
    else:
        vector = MagicMock()
        vector.metadata = {"count": count}
        response.vectors = {VECTOR_ID: vector}
    return response


def _patch_secrets():
    """Patch _get_secret (imported into visit_counter's namespace) with fake creds."""
    return patch.object(
        visit_counter,
        "_get_secret",
        side_effect=lambda key: {"PINECONE_API_KEY": "pk-test", "PINECONE_INDEX_NAME": "idx-test"}[key],
    )


# ── Tests ───────────────────────────────────────────────────────────────────────

def test_first_ever_visit_returns_one_and_upserts_count_one():
    """No existing vector -> current count treated as 0 -> returns 1, upserts count=1."""
    mock_index = MagicMock()
    mock_index.fetch.return_value = _make_fetch_response(count=None)
    mock_pc = MagicMock()
    mock_pc.Index.return_value = mock_index

    with _patch_secrets(), patch.object(visit_counter, "Pinecone", return_value=mock_pc) as mock_pinecone_cls:
        result = get_and_increment_visit_count()

    assert result == 1
    mock_pinecone_cls.assert_called_once_with(api_key="pk-test")
    mock_pc.Index.assert_called_once_with("idx-test")
    mock_index.fetch.assert_called_once_with(ids=[VECTOR_ID], namespace=NAMESPACE)
    mock_index.upsert.assert_called_once()
    _, upsert_kwargs = mock_index.upsert.call_args
    assert upsert_kwargs["namespace"] == NAMESPACE
    upserted_vector = upsert_kwargs["vectors"][0]
    assert upserted_vector["id"] == VECTOR_ID
    assert upserted_vector["metadata"] == {"count": 1}
    assert len(upserted_vector["values"]) == VECTOR_DIM


def test_normal_increment_returns_n_plus_one():
    """Existing vector with metadata count=N -> returns N+1, upserts count=N+1."""
    mock_index = MagicMock()
    mock_index.fetch.return_value = _make_fetch_response(count=41)
    mock_pc = MagicMock()
    mock_pc.Index.return_value = mock_index

    with _patch_secrets(), patch.object(visit_counter, "Pinecone", return_value=mock_pc):
        result = get_and_increment_visit_count()

    assert result == 42
    _, upsert_kwargs = mock_index.upsert.call_args
    assert upsert_kwargs["vectors"][0]["metadata"] == {"count": 42}


def test_fetch_failure_returns_none():
    """index.fetch() raises -> function returns None, does not raise."""
    mock_index = MagicMock()
    mock_index.fetch.side_effect = Exception("Pinecone unreachable")
    mock_pc = MagicMock()
    mock_pc.Index.return_value = mock_index

    with _patch_secrets(), patch.object(visit_counter, "Pinecone", return_value=mock_pc):
        result = get_and_increment_visit_count()

    assert result is None
    mock_index.upsert.assert_not_called()


def test_pinecone_constructor_failure_returns_none():
    """Pinecone(...) constructor raises -> function returns None, does not raise."""
    with _patch_secrets(), patch.object(visit_counter, "Pinecone", side_effect=Exception("bad api key")):
        result = get_and_increment_visit_count()

    assert result is None


def test_missing_credentials_returns_none():
    """_get_secret raises (missing credentials) -> function returns None, does not raise."""
    with patch.object(visit_counter, "_get_secret", side_effect=ValueError("Missing required secret")):
        result = get_and_increment_visit_count()

    assert result is None


# ── Manual runner ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [
        ("First-ever visit returns 1 and upserts count=1", test_first_ever_visit_returns_one_and_upserts_count_one),
        ("Normal increment returns N+1", test_normal_increment_returns_n_plus_one),
        ("fetch() failure returns None", test_fetch_failure_returns_none),
        ("Pinecone constructor failure returns None", test_pinecone_constructor_failure_returns_none),
        ("Missing credentials returns None", test_missing_credentials_returns_none),
    ]
    passed = failed = 0
    for name, fn in tests:
        print(f"\n[TEST] {name}")
        try:
            fn()
            print("  PASS")
            passed += 1
        except AssertionError as e:
            print(f"  FAIL: {e}")
            failed += 1
        except Exception as e:
            print(f"  ERROR: {type(e).__name__}: {e}")
            failed += 1
    print(f"\nResults: {passed} passed, {failed} failed")
    import sys as _sys
    _sys.exit(0 if failed == 0 else 1)
