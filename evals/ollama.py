"""Minimal local-Ollama client (stdlib only) for the judged RAG metrics.

Talks to Ollama's OpenAI-compatible endpoint at ``/v1/chat/completions``. No API
keys, nothing leaves the machine. Default ``qwen2.5:7b`` — a stable, non-reasoning
judge that grades faithfulness reliably (~0.78 on a healthy local pipeline). Lighter
option ``llama3.2:3b`` also works but under-scores (~0.67); reasoning models like
qwen3.5 are NOT viable here — their think-trace overflows the output budget on large
prompts and returns an empty body. Override with ``OLLAMA_MODEL``. The RAG-quality
metrics SKIP when this is unreachable, so a missing Ollama never fails the gate.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

BASE = os.environ.get("OLLAMA_BASE", "http://localhost:11434/v1")
MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:7b")
_TIMEOUT = float(os.environ.get("OLLAMA_TIMEOUT", "600"))


def chat(messages: list[dict], *, model: str | None = None,
         temperature: float = 0.1, max_tokens: int = 1200,
         json_mode: bool = False) -> str:
    """One chat completion → text. ``json_mode`` asks the server for a JSON body."""
    payload = {
        "model": model or MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    # Everything that can fail at the transport/parse layer is wrapped as RuntimeError
    # so callers (reachable(), judged_quality) have a single exception class to guard:
    # a bad URL (ValueError), a non-JSON 200 body (JSONDecodeError, a ValueError),
    # decode errors, and connection failures all become RuntimeError → clean SKIP.
    try:
        req = urllib.request.Request(
            f"{BASE}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": "Bearer ollama"},
        )
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError) as exc:  # down/missing/timeout/bad-url/non-JSON body
        raise RuntimeError(f"Ollama call failed ({BASE}, model {model or MODEL}): {exc}") from exc
    try:
        return body["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError) as exc:  # error body, no choices
        raise RuntimeError(f"Ollama returned no completion ({BASE}, model {model or MODEL}): {body}") from exc


def judge_json(system: str, user: str, *, model: str | None = None) -> dict:
    """Judge call that must return a JSON object. Tolerant of models that wrap the
    object in prose or fences: extracts the first ``{...}`` span.

    ``max_tokens`` is generous because reasoning models (e.g. qwen3.5) spend the
    budget on a ``<think>`` trace before the JSON — too low a cap and the answer is
    truncated to an empty body. It is a cap, not a target: non-reasoning models stop
    at the closing brace and are unaffected."""
    raw = chat(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        model=model, temperature=0.0, max_tokens=3000, json_mode=True,
    )
    return _extract_obj(raw)


def reachable() -> bool:
    """True if Ollama answers a trivial prompt — used to SKIP judged metrics."""
    try:
        chat([{"role": "user", "content": "ok"}], max_tokens=1)
        return True
    except RuntimeError:
        return False


def _extract_obj(text: str) -> dict:
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):       # a bare scalar/array is valid JSON but not a verdict
            return obj
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    depth = 0
    in_str = False
    escaped = False
    for i in range(start, len(text)) if start != -1 else []:
        ch = text[i]
        if in_str:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:i + 1])
                except json.JSONDecodeError:
                    break
    raise ValueError(f"judge did not return JSON: {text[:200]!r}")
