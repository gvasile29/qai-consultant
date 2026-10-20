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
6. Regression guard: the vector passed to upsert() must not be all-zero.
   The original implementation used an all-zero dummy vector, which the
   mocks above don't catch since they don't replicate Pinecone's real API
   validation -- Pinecone's real API rejects that with "Dense vectors must
   contain at least one non-zero value", which silently made every real
   upsert() fail (caught by the bare except, so it never surfaced until a
   live reproduction against the real Pinecone API was run).
"""

import sys
import os
import pytest
os.environ["ANONYMIZED_TELEMETRY"] = "False"

from pathlib import Path
from unittest.mock import patch, MagicMock

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
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
    assert any(v != 0 for v in upserted_vector["values"]), (
        "upserted vector must not be all-zero -- Pinecone's real API rejects "
        "all-zero dense vectors, see module docstring"
    )


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


# ── Usage event counters (downloads + feedback) ─────────────────────────────────

import ast  # noqa: E402

APP_PY = SRC_DIR / "app.py"


def test_increment_counter_uses_given_id_and_non_zero_vector():
    mock_index = MagicMock()
    mock_index.fetch.return_value = MagicMock(vectors={})
    mock_pc = MagicMock()
    mock_pc.Index.return_value = mock_index
    with _patch_secrets(), patch.object(visit_counter, "Pinecone", return_value=mock_pc):
        result = visit_counter.increment_counter("download_test_plan_pdf")
    assert result == 1
    mock_index.fetch.assert_called_once_with(ids=["download_test_plan_pdf"], namespace=NAMESPACE)
    upserted = mock_index.upsert.call_args.kwargs["vectors"][0]
    assert upserted["id"] == "download_test_plan_pdf"
    assert upserted["metadata"] == {"count": 1}
    assert any(v != 0 for v in upserted["values"])


def test_record_event_runs_increment_in_background_thread():
    with patch.object(visit_counter, "increment_counter") as mock_inc:
        thread = visit_counter.record_event("feedback_yes")
        thread.join(timeout=5)
    assert thread.daemon
    mock_inc.assert_called_once_with("feedback_yes")


def test_record_event_never_raises_when_pinecone_is_down():
    with patch.object(visit_counter, "_get_secret", side_effect=ValueError("no creds")):
        thread = visit_counter.record_event("feedback_no")
        thread.join(timeout=5)
    assert not thread.is_alive()


def test_read_counters_defaults_missing_ids_to_zero():
    found = MagicMock()
    found.metadata = {"count": 7}
    mock_index = MagicMock()
    mock_index.fetch.return_value = MagicMock(vectors={"feedback_yes": found})
    counts = visit_counter.read_counters(["feedback_yes", "feedback_no"], index=mock_index)
    assert counts == {"feedback_yes": 7, "feedback_no": 0}


def test_event_counter_ids_are_unique_and_cover_every_doc_and_value():
    ids = visit_counter.all_event_counter_ids()
    assert len(ids) == len(set(ids))
    assert len(ids) == (
        len(visit_counter.DOWNLOAD_DOCS) * len(visit_counter.DOWNLOAD_FORMATS)
        + 1  # the Download-all bundle
        + len(visit_counter.FEEDBACK_VALUES)
    )
    assert VECTOR_ID not in ids


def _download_button_calls():
    tree = ast.parse(APP_PY.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "attr", None) == "download_button":
            yield node


def test_every_app_download_button_is_tracked_with_a_known_counter():
    """A new download button without on_click=_track_download would silently go uncounted."""
    calls = list(_download_button_calls())
    assert calls, "no st.download_button calls found in app.py"
    seen = set()
    for call in calls:
        kwargs = {kw.arg: kw.value for kw in call.keywords}
        assert isinstance(kwargs.get("on_click"), ast.Name) and kwargs["on_click"].id == "_track_download", (
            f"download_button at app.py:{call.lineno} has no on_click=_track_download"
        )
        doc, fmt = ast.literal_eval(kwargs["args"])
        if (doc, fmt) != visit_counter.DOWNLOAD_BUNDLE:
            assert doc in visit_counter.DOWNLOAD_DOCS, f"app.py:{call.lineno} unknown doc {doc!r}"
            assert fmt in visit_counter.DOWNLOAD_FORMATS, f"app.py:{call.lineno} unknown fmt {fmt!r}"
        file_name = ast.unparse(kwargs["file_name"])
        assert doc in file_name and file_name.rstrip("'\"").endswith("." + fmt), (
            f"app.py:{call.lineno} counter ({doc}, {fmt}) doesn't match file_name {file_name}"
        )
        seen.add((doc, fmt))
    expected = {(d, f) for d in visit_counter.DOWNLOAD_DOCS for f in visit_counter.DOWNLOAD_FORMATS}
    expected.add(visit_counter.DOWNLOAD_BUNDLE)
    assert seen == expected


def test_every_feedback_value_is_recorded_in_app():
    source = APP_PY.read_text(encoding="utf-8")
    for value in visit_counter.FEEDBACK_VALUES:
        assert f'record_event(feedback_counter_id("{value}"))' in source, value
