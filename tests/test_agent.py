"""
Tests for src/agent.py — QAIAgent error handling (v2.0).

All tests use unittest.mock — no real Mistral, OpenRouter, or ChromaDB required.

Covers:
1.  QAIKnowledgeBaseError raised when ChromaDB is missing
2.  QAIKnowledgeBaseError raised when ChromaDB is empty
3.  QAIConnectionError raised when MISTRAL_API_KEY is missing
4.  QAIConnectionError raised when OPENROUTER_API_KEY is missing
5.  QAIKnowledgeBaseError message contains "python src/ingest.py"
6.  QAIConnectionError message contains API key setup hint
7.  ask_streaming() yields incremental text chunks via LLMClient
"""

import sys
import os
os.environ["ANONYMIZED_TELEMETRY"] = "False"

from pathlib import Path
from unittest.mock import patch, MagicMock

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from agent import QAIAgent, QAIConnectionError, QAIKnowledgeBaseError


def _mock_chroma(doc_count: int = 5):
    """Return a mock Chroma vectorstore with a given document count."""
    chroma = MagicMock()
    collection = MagicMock()
    collection.count.return_value = doc_count
    chroma._collection = collection
    return chroma


def test_kb_missing_raises_error():
    """QAIKnowledgeBaseError raised when chroma_db/ directory does not exist."""
    with patch("agent.CHROMA_DIR", Path("/nonexistent/chroma_db")), \
         patch("agent._get_secret", side_effect=lambda k: "fake-key"), \
         patch("agent.HuggingFaceEmbeddings"):
        try:
            QAIAgent()
            assert False, "Expected QAIKnowledgeBaseError — not raised"
        except QAIKnowledgeBaseError:
            pass


def test_kb_empty_raises_error():
    """QAIKnowledgeBaseError raised when ChromaDB collection has 0 documents."""
    with patch("agent.CHROMA_DIR") as mock_dir, \
         patch("agent._get_secret", side_effect=lambda k: "fake-key"), \
         patch("agent.HuggingFaceEmbeddings"), \
         patch("agent.Chroma") as mock_chroma_cls:
        mock_dir.exists.return_value = True
        mock_chroma_cls.return_value = _mock_chroma(doc_count=0)
        try:
            QAIAgent()
            assert False, "Expected QAIKnowledgeBaseError — not raised"
        except QAIKnowledgeBaseError:
            pass


def test_missing_mistral_key_raises_connection_error():
    """QAIConnectionError raised when MISTRAL_API_KEY is missing."""
    def fake_get_secret(key):
        if key == "MISTRAL_API_KEY":
            raise ValueError(f"Missing required secret: '{key}'")
        return "fake-key"

    with patch("agent.CHROMA_DIR") as mock_dir, \
         patch("agent._get_secret", side_effect=fake_get_secret), \
         patch("agent.HuggingFaceEmbeddings"), \
         patch("agent.Chroma") as mock_chroma_cls:
        mock_dir.exists.return_value = True
        mock_chroma_cls.return_value = _mock_chroma(doc_count=5)
        try:
            QAIAgent()
            assert False, "Expected QAIConnectionError — not raised"
        except QAIConnectionError:
            pass


def test_missing_openrouter_key_raises_connection_error():
    """QAIConnectionError raised when OPENROUTER_API_KEY is missing."""
    def fake_get_secret(key):
        if key == "OPENROUTER_API_KEY":
            raise ValueError(f"Missing required secret: '{key}'")
        return "fake-key"

    with patch("agent.CHROMA_DIR") as mock_dir, \
         patch("agent._get_secret", side_effect=fake_get_secret), \
         patch("agent.HuggingFaceEmbeddings"), \
         patch("agent.Chroma") as mock_chroma_cls:
        mock_dir.exists.return_value = True
        mock_chroma_cls.return_value = _mock_chroma(doc_count=5)
        try:
            QAIAgent()
            assert False, "Expected QAIConnectionError — not raised"
        except QAIConnectionError:
            pass


def test_kb_error_message_mentions_ingest():
    """QAIKnowledgeBaseError message includes 'python src/ingest.py'."""
    with patch("agent.CHROMA_DIR", Path("/nonexistent/chroma_db")), \
         patch("agent._get_secret", side_effect=lambda k: "fake-key"), \
         patch("agent.HuggingFaceEmbeddings"):
        try:
            QAIAgent()
            assert False, "Expected QAIKnowledgeBaseError — not raised"
        except QAIKnowledgeBaseError as exc:
            assert "python src/ingest.py" in str(exc), \
                f"Expected 'python src/ingest.py' in message, got: {exc}"


def test_connection_error_message_mentions_api_keys():
    """QAIConnectionError message mentions API key setup."""
    def fake_get_secret(key):
        if key == "MISTRAL_API_KEY":
            raise ValueError(f"Missing required secret: 'MISTRAL_API_KEY'. Add it to .env")
        return "fake-key"

    with patch("agent.CHROMA_DIR") as mock_dir, \
         patch("agent._get_secret", side_effect=fake_get_secret), \
         patch("agent.HuggingFaceEmbeddings"), \
         patch("agent.Chroma") as mock_chroma_cls:
        mock_dir.exists.return_value = True
        mock_chroma_cls.return_value = _mock_chroma(doc_count=5)
        try:
            QAIAgent()
            assert False, "Expected QAIConnectionError — not raised"
        except QAIConnectionError as exc:
            assert ".env" in str(exc) or "secret" in str(exc).lower(), \
                f"Expected API key setup hint in error message, got: {exc}"


def test_ask_streaming_yields_chunks():
    """ask_streaming() yields incremental text chunks from LLMClient."""
    with patch("agent.CHROMA_DIR") as mock_dir, \
         patch("agent._get_secret", side_effect=lambda k: "fake-key"), \
         patch("agent.HuggingFaceEmbeddings"), \
         patch("agent.Chroma") as mock_chroma_cls, \
         patch("agent.LLMClient") as mock_llm_cls:
        mock_dir.exists.return_value = True
        mock_chroma_cls.return_value = _mock_chroma(doc_count=5)
        mock_llm = MagicMock()
        mock_llm.chat.return_value = iter(["Hello", " world", "!"])
        mock_llm_cls.return_value = mock_llm
        agent_instance = QAIAgent()

    chunks = list(agent_instance.ask_streaming("test prompt"))
    assert chunks == ["Hello", " world", "!"], \
        f"Expected ['Hello', ' world', '!'], got: {chunks}"


if __name__ == "__main__":
    tests = [
        ("chroma_db/ missing → QAIKnowledgeBaseError", test_kb_missing_raises_error),
        ("ChromaDB empty → QAIKnowledgeBaseError", test_kb_empty_raises_error),
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
