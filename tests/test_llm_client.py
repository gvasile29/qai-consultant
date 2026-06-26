"""
Tests for LLMClient in src/agent.py.

All tests use unittest.mock — no real Mistral or OpenRouter API calls are made.

Covers:
1.  _chat_once returns Mistral response when Mistral succeeds
2.  _chat_once falls back to OpenRouter when Mistral raises an exception
3.  _chat_once raises QAIConnectionError when both providers fail
4.  _chat_stream yields chunks from Mistral when Mistral succeeds
5.  _chat_stream falls back to OpenRouter when Mistral streaming fails
6.  _chat_stream raises QAIConnectionError when both providers fail
7.  chat(stream=False) calls _chat_once and not _chat_stream
8.  chat(stream=True) returns a generator via _chat_stream
"""

import sys
import os
import pytest
os.environ["ANONYMIZED_TELEMETRY"] = "False"

from pathlib import Path
from unittest.mock import patch, MagicMock

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from agent import LLMClient, QAIConnectionError


# ── Helpers ─────────────────────────────────────────────────────────────────────

def _make_client() -> LLMClient:
    """Instantiate LLMClient with fake keys (constructors are key-only, no network)."""
    return LLMClient(mistral_api_key="mk-test", openrouter_api_key="or-test")


def _make_mistral_response(text: str) -> MagicMock:
    """Fake Mistral SDK non-streaming response (choices[0].message.content)."""
    choice = MagicMock()
    choice.message.content = text
    response = MagicMock()
    response.choices = [choice]
    return response


def _make_openrouter_response(text: str) -> MagicMock:
    """Fake OpenAI-compatible (OpenRouter) non-streaming response (choices[0].message.content)."""
    choice = MagicMock()
    choice.message.content = text
    response = MagicMock()
    response.choices = [choice]
    return response


def _make_mistral_stream_events(chunks: list):
    """
    Fake Mistral SDK streaming events.
    Each event exposes event.data.choices[0].delta.content.
    """
    events = []
    for text in chunks:
        delta = MagicMock()
        delta.content = text
        choice = MagicMock()
        choice.delta = delta
        event = MagicMock()
        event.data.choices = [choice]
        events.append(event)
    return iter(events)


def _make_openrouter_stream_chunks(chunks: list):
    """
    Fake OpenAI-compatible (OpenRouter) streaming chunks.
    Each chunk exposes chunk.choices[0].delta.content.
    """
    items = []
    for text in chunks:
        delta = MagicMock()
        delta.content = text
        choice = MagicMock()
        choice.delta = delta
        chunk_mock = MagicMock()
        chunk_mock.choices = [choice]
        items.append(chunk_mock)
    return iter(items)


# ── Tests ───────────────────────────────────────────────────────────────────────

def test_mistral_primary_returns_response():
    """_chat_once returns Mistral response when Mistral succeeds."""
    client = _make_client()
    messages = [{"role": "user", "content": "generate a strategy"}]

    with patch.object(client._mistral, "chat") as mock_mistral_chat, \
         patch.object(client._openrouter.chat.completions, "create") as mock_or_create:
        mock_mistral_chat.complete.return_value = _make_mistral_response("Mistral generated this.")
        result = client._chat_once(messages)

    assert result == "Mistral generated this."
    mock_mistral_chat.complete.assert_called_once()
    mock_or_create.assert_not_called()


def test_openrouter_fallback_on_mistral_failure():
    """_chat_once falls back to OpenRouter when Mistral raises an exception."""
    client = _make_client()
    messages = [{"role": "user", "content": "generate a strategy"}]

    with patch.object(client._mistral, "chat") as mock_mistral_chat, \
         patch.object(client._openrouter.chat.completions, "create") as mock_or_create:
        mock_mistral_chat.complete.side_effect = Exception("Mistral API unavailable")
        mock_or_create.return_value = _make_openrouter_response("OpenRouter fallback response.")
        result = client._chat_once(messages)

    assert result == "OpenRouter fallback response."
    mock_mistral_chat.complete.assert_called_once()
    mock_or_create.assert_called_once()


def test_both_fail_raises_connection_error():
    """_chat_once raises QAIConnectionError when both Mistral and OpenRouter fail."""
    client = _make_client()
    messages = [{"role": "user", "content": "generate a strategy"}]

    with patch.object(client._mistral, "chat") as mock_mistral_chat, \
         patch.object(client._openrouter.chat.completions, "create") as mock_or_create:
        mock_mistral_chat.complete.side_effect = Exception("Mistral down")
        mock_or_create.side_effect = Exception("OpenRouter down")

        with pytest.raises(QAIConnectionError) as exc_info:
            client._chat_once(messages)

    error_msg = str(exc_info.value)
    assert "LLM generation failed" in error_msg or "OpenRouter" in error_msg


def test_streaming_mistral_primary():
    """_chat_stream yields chunks from Mistral when Mistral streaming succeeds."""
    client = _make_client()
    messages = [{"role": "user", "content": "stream test"}]

    with patch.object(client._mistral, "chat") as mock_mistral_chat, \
         patch.object(client._openrouter.chat.completions, "create") as mock_or_create:
        mock_mistral_chat.stream.return_value = _make_mistral_stream_events(
            ["Risk ", "Register ", "generated."]
        )
        result = list(client._chat_stream(messages))

    assert result == ["Risk ", "Register ", "generated."]
    mock_mistral_chat.stream.assert_called_once()
    mock_or_create.assert_not_called()


def test_streaming_openrouter_fallback():
    """_chat_stream falls back to OpenRouter when Mistral streaming raises an exception."""
    client = _make_client()
    messages = [{"role": "user", "content": "stream test"}]

    with patch.object(client._mistral, "chat") as mock_mistral_chat, \
         patch.object(client._openrouter.chat.completions, "create") as mock_or_create:
        mock_mistral_chat.stream.side_effect = Exception("Mistral streaming unavailable")
        mock_or_create.return_value = _make_openrouter_stream_chunks(["Fallback ", "chunks."])
        result = list(client._chat_stream(messages))

    assert result == ["Fallback ", "chunks."]
    mock_mistral_chat.stream.assert_called_once()
    mock_or_create.assert_called_once()


def test_streaming_both_fail_raises_connection_error():
    """_chat_stream raises QAIConnectionError when both providers fail during streaming."""
    client = _make_client()
    messages = [{"role": "user", "content": "stream test"}]

    with patch.object(client._mistral, "chat") as mock_mistral_chat, \
         patch.object(client._openrouter.chat.completions, "create") as mock_or_create:
        mock_mistral_chat.stream.side_effect = Exception("Mistral streaming down")
        mock_or_create.side_effect = Exception("OpenRouter streaming down")

        with pytest.raises(QAIConnectionError) as exc_info:
            list(client._chat_stream(messages))

    error_msg = str(exc_info.value)
    assert "LLM streaming failed" in error_msg or "OpenRouter" in error_msg


def test_chat_non_streaming_calls_chat_once():
    """chat(stream=False) delegates to _chat_once and does not call _chat_stream."""
    client = _make_client()
    messages = [{"role": "user", "content": "test"}]

    with patch.object(client, "_chat_once", return_value="once response") as mock_once, \
         patch.object(client, "_chat_stream") as mock_stream:
        result = client.chat(messages, stream=False)

    mock_once.assert_called_once_with(messages)
    mock_stream.assert_not_called()
    assert result == "once response"


def test_chat_streaming_calls_chat_stream():
    """chat(stream=True) delegates to _chat_stream and does not call _chat_once."""
    client = _make_client()
    messages = [{"role": "user", "content": "test"}]
    expected_chunks = ["chunk1", "chunk2", "chunk3"]

    with patch.object(client, "_chat_stream", return_value=iter(expected_chunks)) as mock_stream, \
         patch.object(client, "_chat_once") as mock_once:
        result = client.chat(messages, stream=True)

    mock_stream.assert_called_once_with(messages)
    mock_once.assert_not_called()
    assert list(result) == expected_chunks


# ── Manual runner ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [
        ("_chat_once returns Mistral response when Mistral succeeds", test_mistral_primary_returns_response),
        ("_chat_once falls back to OpenRouter on Mistral failure", test_openrouter_fallback_on_mistral_failure),
        ("_chat_once raises QAIConnectionError when both fail", test_both_fail_raises_connection_error),
        ("_chat_stream yields chunks from Mistral when Mistral succeeds", test_streaming_mistral_primary),
        ("_chat_stream falls back to OpenRouter when Mistral streaming fails", test_streaming_openrouter_fallback),
        ("_chat_stream raises QAIConnectionError when both streaming fail", test_streaming_both_fail_raises_connection_error),
        ("chat(stream=False) calls _chat_once", test_chat_non_streaming_calls_chat_once),
        ("chat(stream=True) returns generator via _chat_stream", test_chat_streaming_calls_chat_stream),
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
