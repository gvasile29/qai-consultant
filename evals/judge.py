"""LLM judge/generator for the RAG-quality metrics, via the app's own ``LLMClient``
(Mistral, OpenRouter fallback). Keys resolve through ``agent._get_secret`` (.env / env
/ Streamlit secrets); without a key the judged metrics SKIP, never fail.

Trade-off: LLMClient hardcodes temperature 0.1 / max_tokens 1500 with no JSON mode, so
judge scores vary a little run-to-run.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "src"
LABEL = "mistral"

_client = None


def _secret(name: str) -> str:
    """A key via the app's own lookup (.env / env / Streamlit); '' if absent."""
    try:
        if str(_SRC) not in sys.path:
            sys.path.insert(0, str(_SRC))
        from agent import _get_secret  # noqa: PLC0415
        return _get_secret(name)
    except Exception:  # noqa: BLE001 — missing key / src not importable → unset
        return ""


def has_keys() -> bool:
    """True if a Mistral or OpenRouter key is set (free check, no network call)."""
    return bool(_secret("MISTRAL_API_KEY") or _secret("OPENROUTER_API_KEY"))


def _get_client():
    global _client
    if _client is None:
        if str(_SRC) not in sys.path:
            sys.path.insert(0, str(_SRC))
        from agent import LLMClient  # noqa: PLC0415
        _client = LLMClient(
            mistral_api_key=_secret("MISTRAL_API_KEY"),
            # openai>=2.x rejects an empty key at construction, so pass a placeholder.
            openrouter_api_key=_secret("OPENROUTER_API_KEY") or "unset",
        )
    return _client


def _chat(system: str | None, user: str) -> str:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": user})
    try:
        return _get_client().chat(messages) or ""
    except Exception as exc:  # noqa: BLE001 — one class for callers to guard → SKIP/drop
        raise RuntimeError(f"judge LLM call failed ({LABEL}): {exc}") from exc


def generate(system: str, user: str) -> str:
    """One completion (the answer under test)."""
    return _chat(system, user)


def judge_json(system: str, user: str) -> dict:
    """One completion that must contain a JSON verdict; tolerant of prose/fences."""
    return _extract_obj(_chat(system, user), prefer_key="score")


def _span_end(text: str, start: int) -> int:
    """Index just past the balanced ``{...}`` at ``start`` (string-aware), or -1."""
    depth = 0
    in_str = False
    escaped = False
    for i in range(start, len(text)):
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
                return i + 1
    return -1


def _extract_obj(text: str, prefer_key: str | None = None) -> dict:
    """First JSON object in prose/fences. Scans every ``{`` (a bad early span doesn't
    hide a later one); with ``prefer_key`` set, returns the first object holding it."""
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass
    fallback = None
    for start in (j for j, c in enumerate(text) if c == "{"):
        end = _span_end(text, start)
        if end == -1:
            continue
        try:
            obj = json.loads(text[start:end])
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            if prefer_key is None or prefer_key in obj:
                return obj
            if fallback is None:
                fallback = obj
    if fallback is not None:
        return fallback
    raise ValueError(f"judge did not return JSON: {text[:200]!r}")
