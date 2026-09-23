"""
QAI Consultant — Usage Guard (server-side daily run limits)

The per-session cap in app.py (MAX_RUNS_PER_SESSION) lives in
st.session_state, so opening a new tab resets it. This module adds two
limits that survive new sessions, persisted in Pinecone's "app-metrics"
namespace next to the visit counter (see visit_counter.py):

  - a global daily cap across all users (the real cost backstop), and
  - a best-effort per-client daily cap, keyed on a salted hash of the
    client IP — the raw IP is never stored. The salt is the date, so
    hashes can't be linked across days.

Design choices (from the 2026-09-23 external audit, docs/audits/):
  - Fail-open: if Pinecone is unreachable the run is allowed. A metrics
    outage must not take the app down; the provider-side spend limit in
    the Mistral/OpenRouter consoles is the hard backstop.
  - Not atomic: fetch → check → upsert can race under concurrent clicks,
    overshooting a cap by a handful of runs. Acceptable for cost control.
  - Per-client is skipped when no trustworthy public IP is available
    (localhost, or a private/proxy address) — otherwise every user behind
    the same proxy would share one quota and lock each other out.
    X-Forwarded-For is client-spoofable, which only defeats the
    per-client cap; the global cap still holds.

Used only from app.py — never imported by the MCP server path.
"""

import hashlib
import ipaddress
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Mapping, Optional, Protocol

from logger import get_logger

logger = get_logger(__name__)

NAMESPACE = "app-metrics"
VECTOR_DIM = 384  # matches the index dimension; values carry no meaning
DUMMY_VECTOR = [1.0] + [0.0] * (VECTOR_DIM - 1)  # must not be all-zero (Pinecone rejects it)

DEFAULT_GLOBAL_DAILY_LIMIT = 100
DEFAULT_CLIENT_DAILY_LIMIT = 10


@dataclass
class GuardDecision:
    allowed: bool
    reason: str = "ok"  # "ok" | "global_limit" | "client_limit"


class CounterStore(Protocol):
    def fetch(self, ids: list) -> dict: ...
    def set(self, counter_id: str, count: int) -> None: ...


def client_key(headers: Optional[Mapping], ip_address: Optional[str]) -> Optional[str]:
    """Pick the client's public IP: leftmost X-Forwarded-For entry, else
    st.context.ip_address. Returns None for missing, malformed, private,
    or loopback addresses."""
    candidate = None
    forwarded = (headers or {}).get("X-Forwarded-For") or (headers or {}).get("x-forwarded-for")
    if forwarded:
        candidate = forwarded.split(",")[0].strip()
    elif ip_address:
        candidate = ip_address.strip()
    if not candidate:
        return None
    try:
        ip = ipaddress.ip_address(candidate)
    except ValueError:
        return None
    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_unspecified:
        return None
    return str(ip)


def _day(now: datetime) -> str:
    return now.astimezone(timezone.utc).strftime("%Y-%m-%d")


def _client_counter_id(day: str, ip: str) -> str:
    digest = hashlib.sha256(f"{day}:{ip}".encode()).hexdigest()[:16]
    return f"usage_client_{day}_{digest}"


def check_and_record(
    store: CounterStore,
    client_ip: Optional[str],
    global_limit: int = DEFAULT_GLOBAL_DAILY_LIMIT,
    client_limit: int = DEFAULT_CLIENT_DAILY_LIMIT,
    now: Optional[datetime] = None,
) -> GuardDecision:
    """Check both daily caps and, if allowed, record one run against them.
    Never raises — any store failure fails open."""
    day = _day(now or datetime.now(timezone.utc))
    global_id = f"usage_global_{day}"
    client_id = _client_counter_id(day, client_ip) if client_ip else None

    try:
        counts = store.fetch([global_id] + ([client_id] if client_id else []))
        global_count = int(counts.get(global_id, 0))
        client_count = int(counts.get(client_id, 0)) if client_id else 0

        if global_count >= global_limit:
            return GuardDecision(False, "global_limit")
        if client_id and client_count >= client_limit:
            return GuardDecision(False, "client_limit")

        store.set(global_id, global_count + 1)
        if client_id:
            store.set(client_id, client_count + 1)
        return GuardDecision(True)
    except Exception as exc:
        logger.warning("Usage guard failed open: %s", exc)
        return GuardDecision(True)


class PineconeCounterStore:
    """CounterStore backed by one metadata-only vector per counter."""

    def __init__(self, index):
        self._index = index

    def fetch(self, ids: list) -> dict:
        result = self._index.fetch(ids=ids, namespace=NAMESPACE)
        vectors = getattr(result, "vectors", None) or {}
        counts = {}
        for vid, vec in vectors.items():
            metadata = getattr(vec, "metadata", None) or {}
            counts[vid] = int(metadata.get("count", 0))
        return counts

    def set(self, counter_id: str, count: int) -> None:
        self._index.upsert(
            vectors=[{"id": counter_id, "values": DUMMY_VECTOR, "metadata": {"count": count}}],
            namespace=NAMESPACE,
        )


def _int_secret(name: str, default: int) -> int:
    from agent import _get_secret
    try:
        value = _get_secret(name)
        return int(value) if value else default
    except Exception:
        return default


def consume_run(headers: Optional[Mapping], ip_address: Optional[str]) -> GuardDecision:
    """app.py entry point: resolve the client, open the Pinecone store,
    and check/record one run. Limits are overridable via the
    QAI_GLOBAL_DAILY_RUN_LIMIT / QAI_CLIENT_DAILY_RUN_LIMIT secrets."""
    try:
        from pinecone import Pinecone
        from agent import _get_secret

        index = Pinecone(api_key=_get_secret("PINECONE_API_KEY")).Index(_get_secret("PINECONE_INDEX_NAME"))
        store = PineconeCounterStore(index)
    except Exception as exc:
        logger.warning("Usage guard store unavailable, failing open: %s", exc)
        return GuardDecision(True)

    return check_and_record(
        store,
        client_key(headers, ip_address),
        global_limit=_int_secret("QAI_GLOBAL_DAILY_RUN_LIMIT", DEFAULT_GLOBAL_DAILY_LIMIT),
        client_limit=_int_secret("QAI_CLIENT_DAILY_RUN_LIMIT", DEFAULT_CLIENT_DAILY_LIMIT),
    )
