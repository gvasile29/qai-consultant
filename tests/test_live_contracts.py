"""
Live API-contract tests against real Pinecone/Mistral/OpenRouter -- see
docs/superpowers/specs/2026-07-21-ci-live-contract-tests-design.md.

These hit real external APIs and SKIP (not fail, not error) only when the
relevant API key(s) aren't configured at all. Unlike test_risk_analyzer.py's
broad agent() fixture (which SKIPs on *any* setup failure, including a bad
key or a provider outage), these fixtures only catch the missing-secret
case -- a present-but-invalid key or a genuine provider outage surfaces as a
hard FAIL/ERROR here, by design: this suite exists specifically to fail
loudly on a real contract break, not to silently skip past one. Only the
scheduled/dispatched .github/workflows/live-contract-tests.yml workflow
injects real secrets and actually executes these; a bare `pytest tests/`
run (locally or in the existing `test` CI job) continues to skip them
silently, exactly like the existing live-LLM tests already do.

The Mistral and OpenRouter tests both go through the real agent.LLMClient
code path (not raw SDK calls) so a break in message-building, response
extraction, or the Mistral-to-OpenRouter fallback logic itself is caught
here too, not just an auth/model-name/endpoint break.
"""

import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from agent import LLMClient, _get_secret
from pinecone import Pinecone

NAMESPACE = "ci-contract-tests"
VECTOR_ID = "ci-contract-test-vector"
VECTOR_DIM = 384
TEST_VECTOR = [1.0] + [0.0] * (VECTOR_DIM - 1)

# Pinecone serverless indexes are eventually consistent: an upsert is not
# guaranteed visible to an immediately-following fetch. Retry briefly rather
# than fail the whole nightly gate on a timing race that isn't a real
# contract break.
FETCH_RETRY_ATTEMPTS = 3
FETCH_RETRY_DELAY_S = 1.5


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def pinecone_index():
    try:
        api_key = _get_secret("PINECONE_API_KEY")
        index_name = _get_secret("PINECONE_INDEX_NAME")
    except Exception as exc:
        pytest.skip(f"Pinecone credentials unavailable ({type(exc).__name__}: {exc})")
    pc = Pinecone(api_key=api_key)
    return pc.Index(index_name)


@pytest.fixture
def llm_client():
    try:
        mistral_key = _get_secret("MISTRAL_API_KEY")
        openrouter_key = _get_secret("OPENROUTER_API_KEY")
    except Exception as exc:
        pytest.skip(f"LLM credentials unavailable ({type(exc).__name__}: {exc})")
    return LLMClient(mistral_api_key=mistral_key, openrouter_api_key=openrouter_key)


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_pinecone_roundtrip(pinecone_index):
    """Upsert a real, non-zero vector, fetch it back, verify metadata, then
    delete it -- the exact shape of test that would have caught the
    v3.1.1 all-zero-vector rejection before it reached production. Retries
    the fetch briefly to absorb serverless-index eventual consistency
    without masking a real contract break (a truly missing/broken index
    still fails after all retries are exhausted)."""
    try:
        pinecone_index.upsert(
            vectors=[{
                "id": VECTOR_ID,
                "values": TEST_VECTOR,
                "metadata": {"marker": "ci-contract-test"},
            }],
            namespace=NAMESPACE,
        )
        fetched = None
        for attempt in range(FETCH_RETRY_ATTEMPTS):
            fetch_result = pinecone_index.fetch(ids=[VECTOR_ID], namespace=NAMESPACE)
            vectors = getattr(fetch_result, "vectors", None) or {}
            fetched = vectors.get(VECTOR_ID)
            if fetched is not None:
                break
            if attempt < FETCH_RETRY_ATTEMPTS - 1:
                time.sleep(FETCH_RETRY_DELAY_S)
        assert fetched is not None, (
            f"Upserted vector was not found on fetch after {FETCH_RETRY_ATTEMPTS} attempts"
        )
        assert fetched.metadata.get("marker") == "ci-contract-test"
    finally:
        pinecone_index.delete(ids=[VECTOR_ID], namespace=NAMESPACE)


def test_mistral_completion(llm_client):
    """Exercise the real LLMClient.chat() Mistral path -- catches auth
    breakage, a renamed/deprecated model, a changed response shape upstream,
    or a broken message-building/extraction path in _chat_once."""
    content = llm_client.chat([{"role": "user", "content": "Reply with the single word OK."}])
    assert content and content.strip(), "LLMClient (Mistral path) returned an empty response"


def test_openrouter_fallback(llm_client):
    """Force the Mistral leg to fail and exercise LLMClient's real fallback
    path against the real OpenRouter API -- catches both a broken OpenRouter
    contract (auth/model-name/endpoint) and a broken fallback code path
    (message building, response extraction), which otherwise only surfaces
    in production during an actual Mistral outage."""
    with patch.object(
        llm_client._mistral.chat,
        "complete",
        side_effect=RuntimeError("forced failure for contract test"),
    ):
        content = llm_client.chat([{"role": "user", "content": "Reply with the single word OK."}])
    assert content and content.strip(), "LLMClient (OpenRouter fallback path) returned an empty response"
