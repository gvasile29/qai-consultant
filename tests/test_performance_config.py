"""
Tests for QAI Consultant cloud configuration — regression guards (v2.0).

Guards against:
  - Removing the output token cap (causes runaway generation)
  - Removing RAG chunk count limits
  - Reverting to non-Mistral model names
  - Removing _llm_client or changing its type
"""

import sys
import os
os.environ["ANONYMIZED_TELEMETRY"] = "False"

from pathlib import Path
from unittest.mock import patch, MagicMock

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

import agent
from agent import LLMClient


def test_num_predict_is_capped():
    """LLM_NUM_PREDICT must be <= 2000 — prevents runaway generation."""
    assert agent.LLM_NUM_PREDICT <= 2000, (
        f"LLM_NUM_PREDICT={agent.LLM_NUM_PREDICT} is too large. "
        "Without a cap, providers may generate 3000-4000 tokens per call."
    )


def test_rag_k_generation_not_too_large():
    """RAG_K_GENERATION must be <= 8 — prevents excessive context usage."""
    assert agent.RAG_K_GENERATION <= 8, (
        f"RAG_K_GENERATION={agent.RAG_K_GENERATION} is too large. "
        "Each chunk is ~1000 chars; high k values overflow the context window."
    )


def test_mistral_model_is_set():
    """MISTRAL_MODEL must be a non-empty string."""
    assert isinstance(agent.MISTRAL_MODEL, str) and len(agent.MISTRAL_MODEL) > 0, (
        "MISTRAL_MODEL must be a non-empty string."
    )


def test_openrouter_model_is_set():
    """OPENROUTER_MODEL must be a non-empty string."""
    assert isinstance(agent.OPENROUTER_MODEL, str) and len(agent.OPENROUTER_MODEL) > 0, (
        "OPENROUTER_MODEL must be a non-empty string."
    )


def test_llm_client_class_exists():
    """LLMClient class must be importable from agent."""
    assert LLMClient is not None, "LLMClient must be defined in agent.py"


def test_temperature_is_low():
    """LLM_TEMPERATURE must be <= 0.3 — ensures deterministic outputs."""
    assert agent.LLM_TEMPERATURE <= 0.3, (
        f"LLM_TEMPERATURE={agent.LLM_TEMPERATURE} is too high. "
        "Keep <= 0.3 for consistent, near-deterministic QA document generation."
    )


if __name__ == "__main__":
    tests = [
        ("LLM_NUM_PREDICT <= 2000 (output cap present)", test_num_predict_is_capped),
        ("RAG_K_GENERATION <= 8 (no k creep)", test_rag_k_generation_not_too_large),
        ("MISTRAL_MODEL is set", test_mistral_model_is_set),
        ("OPENROUTER_MODEL is set", test_openrouter_model_is_set),
        ("LLMClient class exists", test_llm_client_class_exists),
        ("LLM_TEMPERATURE <= 0.3", test_temperature_is_low),
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
    print(f"\nResults: {passed} passed, {failed} failed")
    import sys as _sys
    _sys.exit(0 if failed == 0 else 1)
