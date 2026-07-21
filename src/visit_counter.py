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
are a dummy zero-vector — Pinecone requires one structurally, but it
carries no semantic meaning here.

Used only from app.py — never imported by the MCP server path, so unlike
kb_config.py it doesn't need to stay keyless/Pinecone-free.
"""

from typing import Optional

from pinecone import Pinecone

from agent import _get_secret

NAMESPACE = "app-metrics"
VECTOR_ID = "visit_counter"
VECTOR_DIM = 384  # matches kb_config.EMBEDDING_MODEL (all-MiniLM-L6-v2); values carry no semantic meaning


def get_and_increment_visit_count() -> Optional[int]:
    """
    Fetch the current visit_counter vector from the app-metrics namespace,
    increment its count metadata by 1, upsert it back, and return the new
    total.

    Returns:
        The new total visit count, or None on any failure (missing
        credentials, network error, index unreachable) — never raises.
        If the counter vector doesn't exist yet (first-ever visit), the
        current count is treated as 0.
    """
    try:
        api_key = _get_secret("PINECONE_API_KEY")
        index_name = _get_secret("PINECONE_INDEX_NAME")
        pc = Pinecone(api_key=api_key)
        index = pc.Index(index_name)

        fetch_result = index.fetch(ids=[VECTOR_ID], namespace=NAMESPACE)
        vectors = getattr(fetch_result, "vectors", None) or {}
        existing = vectors.get(VECTOR_ID)

        current_count = 0
        if existing is not None:
            metadata = getattr(existing, "metadata", None) or {}
            current_count = int(metadata.get("count", 0))

        new_count = current_count + 1
        index.upsert(
            vectors=[
                {
                    "id": VECTOR_ID,
                    "values": [0.0] * VECTOR_DIM,
                    "metadata": {"count": new_count},
                }
            ],
            namespace=NAMESPACE,
        )
        return new_count
    except Exception:
        return None
