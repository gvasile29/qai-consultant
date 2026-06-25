"""
Tests for LLMClient in src/agent.py — Mistral primary + OpenRouter fallback.

Covers:
1.  chat() returns text from Mistral on success
2.  chat() falls back to OpenRouter when Mistral raises an API error
3.  chat() raises QAIConnectionError when both Mistral and OpenRouter fail
4.  chat(stream=True) yields text chunks from Mistral
5.  chat(stream=True) falls back to OpenRouter streaming when Mistral fails
"""

import sys
import os
os.environ["ANONYMIZED_TELEMETRY"] = "False"

from pathlib import Path
from unittest.mock import patch, MagicMock

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from agent import LLMClient, QAIConnectionError


def _make_mistral_response(text: str) -> MagicMock:
    """Fake Mistral SDK non-streaming response."""
    choice = MagicMock()
    choice.message.content = text
    response = MagicMock()
    response.choices = [choice]
    return response


def _make_openai_response(text: str) -> MagicMock:
    """Fake OpenAI-compatible (OpenRouter) non-streaming response."""
    choice = MagicMock()
    choice.message.content = text
    response = MagicMock()
    response.choices = [choice]
    return response


def _make_mistral_stream(chunks: list) -> list:
    """Fake Mistral SDK streaming events."""
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


def _make_openai_stream(chunks: list) -> list:
    """Fake OpenAI-compatible (OpenRouter) streaming chunks."""
    items = []
    for text in chunks:
        delta = MagicMock()
        delta.content = text
        choice = MagicMock()
        choice.delta = delta
        chunk = MagicMock()
        chunk.choices = [choice]
        items.append(chunk)
    return iter(items)


def test_chat_returns_mistral_response():
    """chat() returns text from Mistral when it succeeds."""
    client = LLMClient(mistral_api_key="mk-test", openrouter_api_key="or-test")
    messages = [{"role": "user", "content": "hello"}]

    with patch.object(client._mistral, "chat") as mock_chat:
        mock_chat.complete.return_value = _make_mistral_response("Hello from Mistral")
        result = client.chat(messages)

    assert result == "Hello from Mistral", f"Expected 'Hello from Mistral', got: {result}"


def test_chat_falls_back_to_openrouter_on_mistral_error():
    """chat() uses OpenRouter when Mistral raises an exception."""
    client = LLMClient(mistral_api_key="mk-test", openrouter_api_key="or-test")
    messages = [{"role": "user", "content": "hello"}]

    with patch.object(client._mistral, "chat") as mock_mistral_chat, \
         patch.object(client._openrouter.chat.completions, "create") as mock_or:
        mock_mistral_chat.complete.side_effect = Exception("Rate limit exceeded")
        mock_or.return_value = _make_openai_response("Hello from OpenRouter")
        result = client.chat(messages)

    assert result == "Hello from OpenRouter", f"Expected 'Hello from OpenRouter', got: {result}"


def test_chat_raises_connection_error_when_both_fail():
    """chat() raises QAIConnectionError when both Mistral and OpenRouter fail."""
    client = LLMClient(mistral_api_key="mk-test", openrouter_api_key="or-test")
    messages = [{"role": "user", "content": "hello"}]

    with patch.object(client._mistral, "chat") as mock_mistral_chat, \
         patch.object(client._openrouter.chat.completions, "create") as mock_or:
        mock_mistral_chat.complete.side_effect = Exception("Mistral down")
        mock_or.side_effect = Exception("OpenRouter down")
        try:
            client.chat(messages)
            assert False, "Expected QAIConnectionError — not raised"
        except QAIConnectionError:
            pass


def test_chat_stream_yields_chunks_from_mistral():
    """chat(stream=True) yields text chunks from Mistral streaming."""
    client = LLMClient(mistral_api_key="mk-test", openrouter_api_key="or-test")
    messages = [{"role": "user", "content": "hello"}]

    with patch.object(client._mistral, "chat") as mock_chat:
        mock_chat.stream.return_value = _make_mistral_stream(["Hello", " world", "!"])
        chunks = list(client.chat(messages, stream=True))

    assert chunks == ["Hello", " world", "!"], f"Expected ['Hello', ' world', '!'], got: {chunks}"


def test_chat_stream_falls_back_to_openrouter():
    """chat(stream=True) falls back to OpenRouter streaming when Mistral fails."""
    client = LLMClient(mistral_api_key="mk-test", openrouter_api_key="or-test")
    messages = [{"role": "user", "content": "hello"}]

    with patch.object(client._mistral, "chat") as mock_mistral_chat, \
         patch.object(client._openrouter.chat.completions, "create") as mock_or:
        mock_mistral_chat.stream.side_effect = Exception("Mistral streaming down")
        mock_or.return_value = _make_openai_stream(["Hi", " there"])
        chunks = list(client.chat(messages, stream=True))

    assert chunks == ["Hi", " there"], f"Expected ['Hi', ' there'], got: {chunks}"


if __name__ == "__main__":
    tests = [
        ("chat() returns Mistral response on success", test_chat_returns_mistral_response),
        ("chat() falls back to OpenRouter on Mistral error", test_chat_falls_back_to_openrouter_on_mistral_error),
        ("chat() raises QAIConnectionError when both fail", test_chat_raises_connection_error_when_both_fail),
        ("chat(stream=True) yields chunks from Mistral", test_chat_stream_yields_chunks_from_mistral),
        ("chat(stream=True) falls back to OpenRouter streaming", test_chat_stream_falls_back_to_openrouter),
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
