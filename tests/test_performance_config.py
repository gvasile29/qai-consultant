"""
Tests for QAI Consultant performance configuration — regression guards (v1.0).

These tests ensure that performance-critical constants in agent.py are never
accidentally reverted to slow defaults. They act as a safety net against:
  - Restoring the default 32K Mistral context window (causes CPU hangs)
  - Removing the output token cap (causes runaway generation)
  - Reverting to the slow float16 "mistral" model
  - Breaking the real HTTP timeout (infinite hang protection)
  - Silently increasing RAG chunk count beyond safe limits

Covers:
1.  LLM_NUM_CTX <= 8192 (guards against 32K context regression)
2.  LLM_NUM_PREDICT <= 2000 (guards against unlimited output regression)
3.  GENERATION_TIMEOUT > 0 (guards against zero/infinite timeout)
4.  RAG_K_GENERATION <= 8 (guards against k creep)
5.  _ollama_client is a real OllamaClient instance (guards against revert to module-level chat)
6.  OLLAMA_MODEL is not the slow float16 "mistral" tag
"""

import sys
import os
os.environ["ANONYMIZED_TELEMETRY"] = "False"
os.environ["CHROMA_TELEMETRY"] = "False"

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR   = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

import agent
from ollama import Client as OllamaClient


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_num_ctx_not_too_large():
    """LLM_NUM_CTX must be ≤ 8192 — prevents Mistral 32K default causing CPU hangs."""
    assert agent.LLM_NUM_CTX <= 8192, (
        f"LLM_NUM_CTX={agent.LLM_NUM_CTX} is too large. "
        "Mistral's 32K default causes massive memory overhead on CPU. "
        "Keep ≤ 8192 for acceptable performance."
    )


def test_num_predict_is_capped():
    """LLM_NUM_PREDICT must be ≤ 2000 — prevents runaway generation (15+ min per call)."""
    assert agent.LLM_NUM_PREDICT <= 2000, (
        f"LLM_NUM_PREDICT={agent.LLM_NUM_PREDICT} is too large. "
        "Without a cap, Mistral generates 3000-4000 tokens per call at 3-5 tok/s on CPU."
    )


def test_timeout_is_finite():
    """GENERATION_TIMEOUT must be > 0 — prevents infinite hang on stuck Ollama process."""
    assert agent.GENERATION_TIMEOUT > 0, (
        f"GENERATION_TIMEOUT={agent.GENERATION_TIMEOUT} must be positive. "
        "A zero or negative value disables the HTTP timeout and allows infinite hangs."
    )


def test_rag_k_generation_not_too_large():
    """RAG_K_GENERATION must be ≤ 8 — prevents excessive context window usage."""
    assert agent.RAG_K_GENERATION <= 8, (
        f"RAG_K_GENERATION={agent.RAG_K_GENERATION} is too large. "
        "Each chunk is ~1000 chars. At k=8, context is ~8000 chars = ~2000 tokens, "
        "leaving little room for output within a 4096-token window."
    )


def test_ollama_client_is_real_instance():
    """_ollama_client must be an OllamaClient — ensures real HTTP timeout is set via httpx."""
    assert isinstance(agent._ollama_client, OllamaClient), (
        f"agent._ollama_client is {type(agent._ollama_client).__name__}, not OllamaClient. "
        "The timeout must be set via OllamaClient(timeout=N), not via options dict "
        "(which is silently ignored for timeout)."
    )


def test_model_is_not_slow_float16():
    """OLLAMA_MODEL must not be the bare 'mistral' tag (float16, ~3x slower than quantized)."""
    assert agent.OLLAMA_MODEL != "mistral", (
        "OLLAMA_MODEL='mistral' is the slow float16 variant (requires 8+ GB RAM). "
        "Use 'mistral:7b-instruct-q4_0' (4-bit quantized, ~4 GB RAM, ~3x faster on CPU)."
    )


# ── Runner ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [
        ("LLM_NUM_CTX <= 8192 (no 32K default)", test_num_ctx_not_too_large),
        ("LLM_NUM_PREDICT <= 2000 (output cap present)", test_num_predict_is_capped),
        ("GENERATION_TIMEOUT > 0 (finite timeout)", test_timeout_is_finite),
        ("RAG_K_GENERATION <= 8 (no k creep)", test_rag_k_generation_not_too_large),
        ("_ollama_client is OllamaClient (real HTTP timeout)", test_ollama_client_is_real_instance),
        ("OLLAMA_MODEL != 'mistral' (no slow float16 model)", test_model_is_not_slow_float16),
    ]

    passed = failed = 0

    print("=" * 68)
    print("  QAI Consultant — Performance Config Regression Guards")
    print("=" * 68)

    for name, fn in tests:
        print(f"\n[TEST] {name}")
        try:
            fn()
            print(f"  PASS")
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
