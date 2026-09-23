"""Tests for src/usage_guard.py — server-side daily run limits (no Pinecone calls)."""

import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

import usage_guard
from usage_guard import PineconeCounterStore, check_and_record, client_key

NOW = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
TOMORROW = datetime(2026, 9, 24, 0, 5, tzinfo=timezone.utc)


class FakeStore:
    def __init__(self):
        self.counts = {}

    def fetch(self, ids):
        return {i: self.counts[i] for i in ids if i in self.counts}

    def set(self, counter_id, count):
        self.counts[counter_id] = count


class BrokenStore:
    def fetch(self, ids):
        raise ConnectionError("pinecone down")

    def set(self, counter_id, count):
        raise AssertionError("must not write after a failed fetch")


# ── client_key ────────────────────────────────────────────────────────────────

def test_client_key_prefers_leftmost_forwarded_for():
    headers = {"X-Forwarded-For": "8.8.8.8, 10.0.0.1"}
    assert client_key(headers, "10.0.0.1") == "8.8.8.8"


def test_client_key_falls_back_to_ip_address():
    assert client_key({}, "1.1.1.1") == "1.1.1.1"


def test_client_key_rejects_private_loopback_and_garbage():
    """A proxy/private address would make every user share one quota."""
    assert client_key({}, "127.0.0.1") is None
    assert client_key({}, "10.1.2.3") is None
    assert client_key({"X-Forwarded-For": "192.168.0.5"}, None) is None
    assert client_key({"X-Forwarded-For": "not-an-ip"}, None) is None
    assert client_key(None, None) is None


# ── check_and_record ──────────────────────────────────────────────────────────

def test_allows_and_records_until_client_limit():
    store = FakeStore()
    for _ in range(3):
        assert check_and_record(store, "8.8.8.8", global_limit=100, client_limit=3, now=NOW).allowed
    decision = check_and_record(store, "8.8.8.8", global_limit=100, client_limit=3, now=NOW)
    assert not decision.allowed and decision.reason == "client_limit"
    # A different client is unaffected.
    assert check_and_record(store, "1.1.1.1", global_limit=100, client_limit=3, now=NOW).allowed


def test_global_limit_applies_to_everyone_including_unknown_clients():
    store = FakeStore()
    assert check_and_record(store, "8.8.8.8", global_limit=2, client_limit=10, now=NOW).allowed
    assert check_and_record(store, None, global_limit=2, client_limit=10, now=NOW).allowed
    decision = check_and_record(store, "1.1.1.1", global_limit=2, client_limit=10, now=NOW)
    assert not decision.allowed and decision.reason == "global_limit"


def test_blocked_attempt_is_not_recorded():
    store = FakeStore()
    check_and_record(store, None, global_limit=1, client_limit=10, now=NOW)
    before = dict(store.counts)
    check_and_record(store, None, global_limit=1, client_limit=10, now=NOW)
    assert store.counts == before


def test_counters_reset_next_utc_day():
    store = FakeStore()
    check_and_record(store, "8.8.8.8", global_limit=1, client_limit=1, now=NOW)
    assert not check_and_record(store, "8.8.8.8", global_limit=1, client_limit=1, now=NOW).allowed
    assert check_and_record(store, "8.8.8.8", global_limit=1, client_limit=1, now=TOMORROW).allowed


def test_raw_ip_is_never_stored():
    store = FakeStore()
    check_and_record(store, "8.8.8.8", now=NOW)
    assert all("8.8.8.8" not in counter_id for counter_id in store.counts)


def test_store_failure_fails_open():
    assert check_and_record(BrokenStore(), "8.8.8.8", now=NOW).allowed


def test_consume_run_fails_open_without_pinecone_credentials(monkeypatch):
    import agent
    monkeypatch.setattr(agent, "_get_secret", MagicMock(side_effect=ValueError("missing")))
    assert usage_guard.consume_run({}, "8.8.8.8").allowed


# ── PineconeCounterStore ──────────────────────────────────────────────────────

def test_pinecone_store_round_trip_uses_nonzero_vector_in_metrics_namespace():
    index = MagicMock()
    vec = MagicMock()
    vec.metadata = {"count": 4}
    index.fetch.return_value = MagicMock(vectors={"usage_global_2026-09-23": vec})
    store = PineconeCounterStore(index)

    assert store.fetch(["usage_global_2026-09-23"]) == {"usage_global_2026-09-23": 4}
    store.set("usage_global_2026-09-23", 5)

    upserted = index.upsert.call_args.kwargs
    assert upserted["namespace"] == "app-metrics"
    record = upserted["vectors"][0]
    assert record["metadata"] == {"count": 5}
    assert any(v != 0.0 for v in record["values"])
