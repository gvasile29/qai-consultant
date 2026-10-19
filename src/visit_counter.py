"""
QAI Consultant — Visit Counter

Tracks a single running total of app visits (one increment per new
Streamlit browser session), persisted in Pinecone so the count survives
Streamlit Community Cloud process restarts on every redeploy/reboot (see
the "Streamlit deploy lag" gotcha in CLAUDE.md). Full design rationale:
docs/superpowers/specs/2026-07-21-visit-counter-design.md

Storage: the existing Pinecone index, but a new dedicated namespace,
"app-metrics" — fully isolated from the RAG namespace ("knowledge-base",
see agent.PINECONE_NAMESPACE) so the counter vector can never surface in
agent.retrieve_knowledge() search results. A single vector at a fixed ID
("visit_counter") holds the count in its metadata; the vector's own values
are a dummy placeholder — Pinecone requires one structurally, but it
carries no semantic meaning here. It must NOT be all-zero: Pinecone's API
rejects dense vectors with "Dense vectors must contain at least one
non-zero value" (found the hard way — the original all-zero dummy made
every upsert() fail, silently swallowed by the except below, so the
counter never worked from its first deploy). DUMMY_VECTOR sets just the
first component to a non-zero value to satisfy that constraint.

The same fetch→increment→upsert mechanism also backs the other usage
counters (one vector per counter, same namespace): file downloads
("download_<doc>_<md|pdf>") and strategy feedback ("feedback_<yes|
partially|no>"). record_event() fires those from a daemon thread so a
download click or feedback button never waits on Pinecone.
scripts/usage_report.py reads them all back. Like the visit counter they
are not atomic — concurrent clicks can drop an increment, acceptable for
usage metrics.

Used only from app.py — never imported by the MCP server path, so unlike
kb_config.py it doesn't need to stay keyless/Pinecone-free.
"""

import threading
from typing import Iterable, Optional

from pinecone import Pinecone

from agent import _get_secret
from logger import get_logger

logger = get_logger(__name__)

NAMESPACE = "app-metrics"
VECTOR_ID = "visit_counter"
VECTOR_DIM = 384  # matches kb_config.EMBEDDING_MODEL (all-MiniLM-L6-v2); values carry no semantic meaning
DUMMY_VECTOR = [1.0] + [0.0] * (VECTOR_DIM - 1)  # must not be all-zero — see module docstring


DOWNLOAD_DOCS = (
    "risk_register", "effort_estimation", "test_strategy", "test_plan",
    "quality_review", "maturity_assessment",
)
DOWNLOAD_FORMATS = ("md", "pdf")
DOWNLOAD_BUNDLE = ("all_documents", "zip")  # the "Download all" button (not a doc x format pair)
FEEDBACK_VALUES = ("yes", "partially", "no")


def download_counter_id(doc: str, fmt: str) -> str:
    return f"download_{doc}_{fmt}"


def feedback_counter_id(value: str) -> str:
    return f"feedback_{value}"


def all_event_counter_ids() -> list:
    """Every download/feedback counter ID app.py can record, in report order."""
    ids = [download_counter_id(d, f) for d in DOWNLOAD_DOCS for f in DOWNLOAD_FORMATS]
    ids.append(download_counter_id(*DOWNLOAD_BUNDLE))
    return ids + [feedback_counter_id(v) for v in FEEDBACK_VALUES]


def _open_index():
    pc = Pinecone(api_key=_get_secret("PINECONE_API_KEY"))
    return pc.Index(_get_secret("PINECONE_INDEX_NAME"))


def increment_counter(counter_id: str) -> Optional[int]:
    """
    Fetch the counter vector from the app-metrics namespace, increment its
    count metadata by 1, upsert it back, and return the new total.

    Returns:
        The new total, or None on any failure (missing credentials,
        network error, index unreachable) — never raises. A counter that
        doesn't exist yet starts from 0.
    """
    try:
        index = _open_index()

        fetch_result = index.fetch(ids=[counter_id], namespace=NAMESPACE)
        vectors = getattr(fetch_result, "vectors", None) or {}
        existing = vectors.get(counter_id)

        current_count = 0
        if existing is not None:
            metadata = getattr(existing, "metadata", None) or {}
            current_count = int(metadata.get("count", 0))

        new_count = current_count + 1
        index.upsert(
            vectors=[
                {
                    "id": counter_id,
                    "values": DUMMY_VECTOR,
                    "metadata": {"count": new_count},
                }
            ],
            namespace=NAMESPACE,
        )
        return new_count
    except Exception as exc:
        logger.warning("Counter %s increment failed: %s", counter_id, exc)
        return None


def get_and_increment_visit_count() -> Optional[int]:
    """Increment the visit counter (once per browser session, see app.py)."""
    return increment_counter(VECTOR_ID)


def record_event(counter_id: str) -> threading.Thread:
    """Fire-and-forget increment_counter() on a daemon thread."""
    thread = threading.Thread(target=increment_counter, args=(counter_id,), daemon=True)
    thread.start()
    return thread


def read_counters(counter_ids: Iterable[str], index=None) -> dict:
    """Return {counter_id: count} for the given IDs; missing counters read as 0.
    Raises on Pinecone errors — this is for the report script, not the app."""
    ids = list(counter_ids)
    index = index or _open_index()
    counts = {cid: 0 for cid in ids}
    for i in range(0, len(ids), 100):  # Pinecone fetch accepts at most 1000 ids; stay well under
        result = index.fetch(ids=ids[i:i + 100], namespace=NAMESPACE)
        for vid, vec in (getattr(result, "vectors", None) or {}).items():
            metadata = getattr(vec, "metadata", None) or {}
            counts[vid] = int(metadata.get("count", 0))
    return counts
