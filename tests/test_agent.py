"""
Tests for src/agent.py — QAIAgent error handling (v1.0).

All tests use unittest.mock — no real Ollama or ChromaDB required.

Covers:
1.  QAIKnowledgeBaseError raised when chroma_db/ directory is missing
2.  QAIKnowledgeBaseError raised when collection exists but has 0 chunks
3.  QAIConnectionError raised when Ollama is not running
4.  QAIModelError raised when Ollama runs but 'mistral' is not available
5.  QAIConnectionError message contains "ollama serve"
6.  QAIModelError message contains "ollama pull mistral"
7.  QAIKnowledgeBaseError message contains "python src/ingest.py"
"""

import sys
import os
os.environ["ANONYMIZED_TELEMETRY"] = "False"
os.environ["CHROMA_TELEMETRY"] = "False"

from pathlib import Path
from unittest.mock import patch, MagicMock

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR   = REPO_ROOT / "src"
TESTS_DIR = Path(__file__).resolve().parent   # always-existing dir, stand-in for chroma_db
sys.path.insert(0, str(SRC_DIR))

from agent import QAIAgent, QAIConnectionError, QAIModelError, QAIKnowledgeBaseError


# ── Helpers ───────────────────────────────────────────────────────────────────

def _mock_empty_store() -> MagicMock:
    """Return a mock Chroma store whose collection reports 0 chunks."""
    store = MagicMock()
    store._collection.count.return_value = 0
    return store


def _mock_full_store() -> MagicMock:
    """Return a mock Chroma store whose collection reports 100 chunks (non-empty)."""
    store = MagicMock()
    store._collection.count.return_value = 100
    return store


def _ollama_models_without_mistral() -> dict:
    """Ollama response listing models that do NOT include mistral:7b-instruct-q4_0."""
    return {"models": [{"name": "llama2"}, {"name": "phi3"}]}


def _ollama_models_with_mistral() -> dict:
    """Ollama response listing models that include mistral:7b-instruct-q4_0."""
    return {"models": [{"name": "mistral:7b-instruct-q4_0"}, {"name": "llama2"}]}


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_kb_missing_raises_error():
    """QAIKnowledgeBaseError raised when chroma_db/ directory does not exist."""
    nonexistent = Path("/nonexistent/chroma_db_test_xyz_99999")
    assert not nonexistent.exists(), "Precondition: path must not exist"

    with patch("agent.CHROMA_DIR", nonexistent):
        try:
            QAIAgent()
            assert False, "Expected QAIKnowledgeBaseError — not raised"
        except QAIKnowledgeBaseError:
            pass  # expected
    print("  PASS: Missing chroma_db/ → QAIKnowledgeBaseError")


def test_kb_empty_raises_error():
    """QAIKnowledgeBaseError raised when ChromaDB collection has 0 chunks.

    CHROMA_DIR is patched to an existing path; Chroma and HuggingFaceEmbeddings
    are mocked so no real model loading occurs. The mock collection returns count=0.
    """
    with patch("agent.CHROMA_DIR", TESTS_DIR), \
         patch("agent.HuggingFaceEmbeddings"), \
         patch("agent.Chroma", return_value=_mock_empty_store()):
        try:
            QAIAgent()
            assert False, "Expected QAIKnowledgeBaseError — not raised"
        except QAIKnowledgeBaseError:
            pass  # expected
    print("  PASS: Empty ChromaDB collection (0 chunks) → QAIKnowledgeBaseError")


def test_ollama_not_running_raises_error():
    """QAIConnectionError raised when ollama.list() fails (Ollama not running).

    KB loading is mocked to succeed; ollama.list() raises a generic Exception
    simulating a connection failure.
    """
    with patch("agent.CHROMA_DIR", TESTS_DIR), \
         patch("agent.HuggingFaceEmbeddings"), \
         patch("agent.Chroma", return_value=_mock_full_store()), \
         patch("ollama.list", side_effect=Exception("Connection refused")):
        try:
            QAIAgent()
            assert False, "Expected QAIConnectionError — not raised"
        except QAIConnectionError:
            pass  # expected
    print("  PASS: ollama.list() fails → QAIConnectionError")


def test_model_not_available_raises_error():
    """QAIModelError raised when Ollama is running but 'mistral' is not in the model list.

    KB loading is mocked to succeed; ollama.list() returns a list of models
    that does NOT include 'mistral'.
    """
    with patch("agent.CHROMA_DIR", TESTS_DIR), \
         patch("agent.HuggingFaceEmbeddings"), \
         patch("agent.Chroma", return_value=_mock_full_store()), \
         patch("ollama.list", return_value=_ollama_models_without_mistral()):
        try:
            QAIAgent()
            assert False, "Expected QAIModelError — not raised"
        except QAIModelError:
            pass  # expected
    print("  PASS: 'mistral' not in available models → QAIModelError")


def test_connection_error_message_mentions_ollama_serve():
    """QAIConnectionError message includes the 'ollama serve' start command."""
    with patch("agent.CHROMA_DIR", TESTS_DIR), \
         patch("agent.HuggingFaceEmbeddings"), \
         patch("agent.Chroma", return_value=_mock_full_store()), \
         patch("ollama.list", side_effect=Exception("Connection refused")):
        try:
            QAIAgent()
            assert False, "Expected QAIConnectionError — not raised"
        except QAIConnectionError as exc:
            assert "ollama serve" in str(exc), \
                f"Expected 'ollama serve' in error message, got: {exc}"
    print("  PASS: QAIConnectionError message contains 'ollama serve'")


def test_model_error_message_mentions_pull_mistral():
    """QAIModelError message includes the 'ollama pull mistral:7b-instruct-q4_0' pull command."""
    with patch("agent.CHROMA_DIR", TESTS_DIR), \
         patch("agent.HuggingFaceEmbeddings"), \
         patch("agent.Chroma", return_value=_mock_full_store()), \
         patch("ollama.list", return_value=_ollama_models_without_mistral()):
        try:
            QAIAgent()
            assert False, "Expected QAIModelError — not raised"
        except QAIModelError as exc:
            assert "ollama pull mistral" in str(exc), \
                f"Expected 'ollama pull mistral' in error message, got: {exc}"
    print("  PASS: QAIModelError message contains 'ollama pull mistral:7b-instruct-q4_0'")


def test_kb_error_message_mentions_ingest():
    """QAIKnowledgeBaseError message includes the 'python src/ingest.py' build command."""
    nonexistent = Path("/nonexistent/chroma_db_test_xyz_99999")
    with patch("agent.CHROMA_DIR", nonexistent):
        try:
            QAIAgent()
            assert False, "Expected QAIKnowledgeBaseError — not raised"
        except QAIKnowledgeBaseError as exc:
            assert "python src/ingest.py" in str(exc), \
                f"Expected 'python src/ingest.py' in error message, got: {exc}"
    print("  PASS: QAIKnowledgeBaseError message contains 'python src/ingest.py'")


def test_ask_streaming_yields_chunks():
    """ask_streaming() yields incremental text chunks from the LLM."""
    fake_stream = [
        {"message": {"content": "Hello"}},
        {"message": {"content": " world"}},
        {"message": {"content": "!"}},
    ]

    with patch("agent.CHROMA_DIR", TESTS_DIR), \
         patch("agent.HuggingFaceEmbeddings"), \
         patch("agent.Chroma", return_value=_mock_full_store()), \
         patch("ollama.list", return_value={"models": [{"name": "mistral:7b-instruct-q4_0"}]}), \
         patch.object(__import__("agent")._ollama_client, "chat", return_value=iter(fake_stream)):
        agent_instance = QAIAgent()
        chunks = list(agent_instance.ask_streaming("test prompt"))
        assert chunks == ["Hello", " world", "!"], \
            f"Expected ['Hello', ' world', '!'], got: {chunks}"
    print("  PASS: ask_streaming() yields incremental text chunks")


# ── Runner ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [
        ("KB missing: chroma_db/ not found → QAIKnowledgeBaseError",
            test_kb_missing_raises_error),
        ("KB empty: collection has 0 chunks → QAIKnowledgeBaseError",
            test_kb_empty_raises_error),
        ("Ollama not running: ollama.list() fails → QAIConnectionError",
            test_ollama_not_running_raises_error),
        ("Model not available: 'mistral:7b-instruct-q4_0' not in Ollama → QAIModelError",
            test_model_not_available_raises_error),
        ("QAIConnectionError message contains 'ollama serve'",
            test_connection_error_message_mentions_ollama_serve),
        ("QAIModelError message contains 'ollama pull mistral'",
            test_model_error_message_mentions_pull_mistral),
        ("QAIKnowledgeBaseError message contains 'python src/ingest.py'",
            test_kb_error_message_mentions_ingest),
        ("ask_streaming() yields incremental text chunks",
            test_ask_streaming_yields_chunks),
    ]

    passed = failed = 0

    print("=" * 68)
    print("  QAI Consultant — Agent Error Handling v1.0 Tests")
    print("=" * 68)

    for name, fn in tests:
        print(f"\n[TEST] {name}")
        try:
            fn()
            passed += 1
        except AssertionError as e:
            print(f"  FAIL: {e}")
            failed += 1
        except Exception as e:
            import traceback
            print(f"  ERROR: {type(e).__name__}: {e}")
            traceback.print_exc()
            failed += 1

    print(f"\n{'=' * 68}")
    print(f"  Results: {passed} passed, {failed} failed")
    print(f"{'=' * 68}")

    import sys as _sys
    _sys.exit(0 if failed == 0 else 1)
