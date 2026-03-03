"""
Tests for src/agent.py — Ollama availability checks (v1.0).

All tests mock both Ollama and ChromaDB — no real services required.
Test #1 can also be skipped if Ollama is not available.

Covers:
1.  When Ollama is running and mistral:7b-instruct-q4_0 available → QAIAgent loads without error
    (mock both ollama.list() and ChromaDB)
2.  When ollama.list() raises ConnectionRefusedError → QAIConnectionError raised
3.  When ollama.list() returns models without OLLAMA_MODEL → QAIModelError raised
4.  QAIConnectionError message mentions "ollama serve"
5.  QAIModelError message mentions the available models list
"""

import sys
import os
os.environ["ANONYMIZED_TELEMETRY"] = "False"
os.environ["CHROMA_TELEMETRY"] = "False"

from pathlib import Path
from unittest.mock import patch, MagicMock

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR   = REPO_ROOT / "src"
TESTS_DIR = Path(__file__).resolve().parent   # always-existing dir
sys.path.insert(0, str(SRC_DIR))

from agent import QAIAgent, QAIConnectionError, QAIModelError, QAIKnowledgeBaseError, OLLAMA_MODEL


# ── Helpers ───────────────────────────────────────────────────────────────────

def _mock_full_store() -> MagicMock:
    """Chroma mock with 100 chunks — simulates a healthy knowledge base."""
    store = MagicMock()
    store._collection.count.return_value = 100
    return store


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_agent_loads_without_error_when_ollama_ready():
    """QAIAgent initialises cleanly when both ChromaDB and Ollama/mistral are mocked.

    This is the 'happy path' — all checks pass:
      - ChromaDB directory exists (patched to tests/ dir)
      - HuggingFaceEmbeddings mocked (no model download)
      - Chroma mocked with 100 chunks (non-empty)
      - ollama.list() returns a model list that includes 'mistral'
    """
    with patch("agent.CHROMA_DIR", TESTS_DIR), \
         patch("agent.HuggingFaceEmbeddings"), \
         patch("agent.Chroma", return_value=_mock_full_store()), \
         patch("ollama.list", return_value={"models": [{"name": OLLAMA_MODEL}, {"name": "llama2"}]}):
        try:
            agent = QAIAgent()
            # If we reach here, no exception was raised
            assert agent is not None
        except (QAIConnectionError, QAIModelError, QAIKnowledgeBaseError) as exc:
            assert False, f"Unexpected error in happy-path test: {exc}"
    print("  PASS: Ollama ready + mistral available → QAIAgent loads without error")


def test_connection_refused_raises_connection_error():
    """When ollama.list() raises ConnectionRefusedError → QAIConnectionError is raised.

    Simulates Ollama process not running on the machine.
    """
    with patch("agent.CHROMA_DIR", TESTS_DIR), \
         patch("agent.HuggingFaceEmbeddings"), \
         patch("agent.Chroma", return_value=_mock_full_store()), \
         patch("ollama.list", side_effect=ConnectionRefusedError("Connection refused")):
        try:
            QAIAgent()
            assert False, "Expected QAIConnectionError — not raised"
        except QAIConnectionError:
            pass  # expected
        except QAIModelError as exc:
            assert False, f"Got QAIModelError instead of QAIConnectionError: {exc}"
    print("  PASS: ConnectionRefusedError from ollama.list() → QAIConnectionError")


def test_model_not_in_list_raises_model_error():
    """When ollama.list() returns models without 'mistral' → QAIModelError is raised.

    Simulates user having Ollama installed but 'mistral' not pulled.
    """
    other_models = {"models": [{"name": "llama2"}, {"name": "phi3"}, {"name": "gemma"}]}
    with patch("agent.CHROMA_DIR", TESTS_DIR), \
         patch("agent.HuggingFaceEmbeddings"), \
         patch("agent.Chroma", return_value=_mock_full_store()), \
         patch("ollama.list", return_value=other_models):
        try:
            QAIAgent()
            assert False, "Expected QAIModelError — not raised"
        except QAIModelError:
            pass  # expected
        except QAIConnectionError as exc:
            assert False, f"Got QAIConnectionError instead of QAIModelError: {exc}"
    print("  PASS: 'mistral' missing from ollama list → QAIModelError")


def test_connection_error_message_mentions_ollama_serve():
    """QAIConnectionError message must tell the user how to start Ollama ('ollama serve')."""
    with patch("agent.CHROMA_DIR", TESTS_DIR), \
         patch("agent.HuggingFaceEmbeddings"), \
         patch("agent.Chroma", return_value=_mock_full_store()), \
         patch("ollama.list", side_effect=Exception("host not found")):
        try:
            QAIAgent()
            assert False, "Expected QAIConnectionError — not raised"
        except QAIConnectionError as exc:
            msg = str(exc)
            assert "ollama serve" in msg, \
                f"Expected 'ollama serve' in QAIConnectionError message.\nGot: {msg}"
    print("  PASS: QAIConnectionError message contains 'ollama serve'")


def test_model_error_message_mentions_available_models():
    """QAIModelError message lists the models actually available on the system.

    When 'mistral' is not found, the error message should list what IS available
    so the user knows what models they have.
    """
    available = ["llama2", "phi3"]
    mock_response = {"models": [{"name": m} for m in available]}
    with patch("agent.CHROMA_DIR", TESTS_DIR), \
         patch("agent.HuggingFaceEmbeddings"), \
         patch("agent.Chroma", return_value=_mock_full_store()), \
         patch("ollama.list", return_value=mock_response):
        try:
            QAIAgent()
            assert False, "Expected QAIModelError — not raised"
        except QAIModelError as exc:
            msg = str(exc)
            # The error should mention at least one of the available models
            assert any(m in msg for m in available), \
                f"Expected available models ({available}) to appear in error message.\nGot: {msg}"
    print(f"  PASS: QAIModelError message mentions available models: {available}")


# ── Runner ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [
        ("Ollama + mistral ready → QAIAgent loads without error (mocked)",
            test_agent_loads_without_error_when_ollama_ready),
        ("ollama.list() raises ConnectionRefusedError → QAIConnectionError",
            test_connection_refused_raises_connection_error),
        ("ollama.list() returns models without 'mistral' → QAIModelError",
            test_model_not_in_list_raises_model_error),
        ("QAIConnectionError message contains 'ollama serve'",
            test_connection_error_message_mentions_ollama_serve),
        ("QAIModelError message lists available models",
            test_model_error_message_mentions_available_models),
    ]

    passed = failed = 0

    print("=" * 68)
    print("  QAI Consultant — Ollama Availability Checks v1.0 Tests")
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
