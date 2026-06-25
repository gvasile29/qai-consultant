"""
Tests for src/agent.py — QAIAgent error handling (v2.0).

All tests use unittest.mock — no real Mistral, OpenRouter, or Pinecone required.

Covers:
1.  QAIKnowledgeBaseError raised when Pinecone fails to connect
2.  QAIKnowledgeBaseError raised when Pinecone index is empty (0 vectors)
3.  QAIConnectionError raised when MISTRAL_API_KEY is missing
4.  QAIConnectionError raised when OPENROUTER_API_KEY is missing
5.  QAIKnowledgeBaseError message contains "python src/ingest.py"
6.  QAIConnectionError message contains API key setup hint
7.  ask_streaming() yields incremental text chunks via LLMClient
"""

import sys
import os

from pathlib import Path
from unittest.mock import patch, MagicMock

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from agent import QAIAgent, QAIConnectionError, QAIKnowledgeBaseError


def _mock_pinecone_client(vector_count: int = 5):
    """Return a mock Pinecone index with a given vector count."""
    mock_index = MagicMock()
    mock_stats = MagicMock()
    mock_stats.total_vector_count = vector_count
    mock_index.describe_index_stats.return_value = mock_stats
    mock_pc = MagicMock()
    mock_pc.Index.return_value = mock_index
    return mock_pc, mock_index


def test_kb_missing_raises_error():
    """QAIKnowledgeBaseError raised when Pinecone connection fails."""
    with patch("agent._get_secret", side_effect=ValueError("Missing required secret: 'PINECONE_API_KEY'")), \
         patch("agent.HuggingFaceEmbeddings"):
        try:
            QAIAgent()
            assert False, "Expected QAIKnowledgeBaseError — not raised"
        except QAIKnowledgeBaseError:
            pass


def test_kb_empty_raises_error():
    """QAIKnowledgeBaseError raised when Pinecone index has 0 vectors."""
    mock_pc, mock_index = _mock_pinecone_client(vector_count=0)

    def fake_get_secret(key):
        if key in ("PINECONE_API_KEY", "PINECONE_INDEX_NAME"):
            return "fake-value"
        raise ValueError(f"Missing required secret: '{key}'")

    with patch("agent._get_secret", side_effect=fake_get_secret), \
         patch("agent.HuggingFaceEmbeddings"), \
         patch("agent.Pinecone", return_value=mock_pc):
        try:
            QAIAgent()
            assert False, "Expected QAIKnowledgeBaseError — not raised"
        except QAIKnowledgeBaseError:
            pass


def test_missing_mistral_key_raises_connection_error():
    """QAIConnectionError raised when MISTRAL_API_KEY is missing."""
    mock_pc, mock_index = _mock_pinecone_client(vector_count=5)

    def fake_get_secret(key):
        if key in ("PINECONE_API_KEY", "PINECONE_INDEX_NAME"):
            return "fake-value"
        if key == "MISTRAL_API_KEY":
            raise ValueError(f"Missing required secret: '{key}'")
        return "fake-key"

    with patch("agent._get_secret", side_effect=fake_get_secret), \
         patch("agent.HuggingFaceEmbeddings"), \
         patch("agent.Pinecone", return_value=mock_pc):
        try:
            QAIAgent()
            assert False, "Expected QAIConnectionError — not raised"
        except QAIConnectionError:
            pass


def test_missing_openrouter_key_raises_connection_error():
    """QAIConnectionError raised when OPENROUTER_API_KEY is missing."""
    mock_pc, mock_index = _mock_pinecone_client(vector_count=5)

    def fake_get_secret(key):
        if key in ("PINECONE_API_KEY", "PINECONE_INDEX_NAME"):
            return "fake-value"
        if key == "OPENROUTER_API_KEY":
            raise ValueError(f"Missing required secret: '{key}'")
        return "fake-key"

    with patch("agent._get_secret", side_effect=fake_get_secret), \
         patch("agent.HuggingFaceEmbeddings"), \
         patch("agent.Pinecone", return_value=mock_pc):
        try:
            QAIAgent()
            assert False, "Expected QAIConnectionError — not raised"
        except QAIConnectionError:
            pass


def test_kb_error_message_mentions_ingest():
    """QAIKnowledgeBaseError message includes 'python src/ingest.py'."""
    with patch("agent._get_secret", side_effect=ValueError("Missing required secret: 'PINECONE_API_KEY'")), \
         patch("agent.HuggingFaceEmbeddings"):
        try:
            QAIAgent()
            assert False, "Expected QAIKnowledgeBaseError — not raised"
        except QAIKnowledgeBaseError as exc:
            assert "python src/ingest.py" in str(exc), \
                f"Expected 'python src/ingest.py' in message, got: {exc}"


def test_connection_error_message_mentions_api_keys():
    """QAIConnectionError message mentions API key setup."""
    mock_pc, mock_index = _mock_pinecone_client(vector_count=5)

    def fake_get_secret(key):
        if key in ("PINECONE_API_KEY", "PINECONE_INDEX_NAME"):
            return "fake-value"
        if key == "MISTRAL_API_KEY":
            raise ValueError(f"Missing required secret: 'MISTRAL_API_KEY'. Add it to .env")
        return "fake-key"

    with patch("agent._get_secret", side_effect=fake_get_secret), \
         patch("agent.HuggingFaceEmbeddings"), \
         patch("agent.Pinecone", return_value=mock_pc):
        try:
            QAIAgent()
            assert False, "Expected QAIConnectionError — not raised"
        except QAIConnectionError as exc:
            assert ".env" in str(exc) or "secret" in str(exc).lower(), \
                f"Expected API key setup hint in error message, got: {exc}"


def test_ask_streaming_yields_chunks():
    """ask_streaming() yields incremental text chunks from LLMClient."""
    mock_pc, mock_index = _mock_pinecone_client(vector_count=5)

    with patch("agent._get_secret", side_effect=lambda k: "fake-value"), \
         patch("agent.HuggingFaceEmbeddings"), \
         patch("agent.Pinecone", return_value=mock_pc), \
         patch("agent.LLMClient") as mock_llm_cls:
        mock_llm = MagicMock()
        mock_llm.chat.return_value = iter(["Hello", " world", "!"])
        mock_llm_cls.return_value = mock_llm
        agent_instance = QAIAgent()

    chunks = list(agent_instance.ask_streaming("test prompt"))
    assert chunks == ["Hello", " world", "!"], \
        f"Expected ['Hello', ' world', '!'], got: {chunks}"


if __name__ == "__main__":
    tests = [
        ("Pinecone connection fails → QAIKnowledgeBaseError", test_kb_missing_raises_error),
        ("Pinecone index empty → QAIKnowledgeBaseError", test_kb_empty_raises_error),
        ("Missing MISTRAL_API_KEY → QAIConnectionError", test_missing_mistral_key_raises_connection_error),
        ("Missing OPENROUTER_API_KEY → QAIConnectionError", test_missing_openrouter_key_raises_connection_error),
        ("QAIKnowledgeBaseError mentions 'python src/ingest.py'", test_kb_error_message_mentions_ingest),
        ("QAIConnectionError mentions .env / secrets", test_connection_error_message_mentions_api_keys),
        ("ask_streaming() yields incremental text chunks", test_ask_streaming_yields_chunks),
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
