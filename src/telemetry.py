"""
QAI Consultant — MCP server opt-in usage telemetry (v3.0).

Disabled by default; enabled only when QAI_TELEMETRY=1. Answers "what do the
people who opted in actually use?" — passive PyPI/GitHub stats (reviewed
manually, no code involved) already answer "is anyone installing this?".

Backend: PostHog free tier, a single plain HTTPS POST per event (no SDK
dependency, no extra install weight). The project API key below is a PUBLIC
write-only key — embedding it is PostHog's designed use for client-side
event capture, not a secret; it can be overridden via
QAI_TELEMETRY_POSTHOG_KEY for local testing or a future key rotation.

Engineering contract (telemetry must never touch the actual tool call):
  - fire-and-forget from a daemon thread
  - 2-second network timeout
  - every exception swallowed — a telemetry failure must never break or
    slow down a tool call, and never raises/logs/retries
  - no retries, no disk buffering — a dropped event just never arrives

Never sent: query text, project fields, KB content, file paths, hostnames,
or any other free-text. Only: event name, tool name, success flag, duration
ms, k/category (retrieval calls only — both fixed small enums, not
free-text), package version, Python minor version, OS family, and a random
anonymous install id.
"""

from __future__ import annotations

import json
import os
import platform
import sys
import threading
import uuid
from pathlib import Path
from typing import Optional
from urllib import request as _urllib_request

_POSTHOG_HOST = "https://eu.i.posthog.com"  # this project's PostHog org is on EU Cloud
# Public write-only PostHog Project API Key (not a secret — see module
# docstring). If this ever needs rotating, generate a new one from PostHog's
# Project Settings (NOT "Personal API Keys", which is a different, sensitive
# credential type — phx_... prefix, must never end up here).
_POSTHOG_PROJECT_API_KEY_DEFAULT = "phc_pgVvXQx4idPNe7JNcX6uQHhTUryPfVEYKDxRVWcYNWVP"
_TIMEOUT_SECONDS = 2.0
_INSTALL_ID_FILENAME = "install_id.txt"


def _posthog_api_key() -> str:
    return os.environ.get("QAI_TELEMETRY_POSTHOG_KEY", _POSTHOG_PROJECT_API_KEY_DEFAULT)


def is_enabled() -> bool:
    return os.environ.get("QAI_TELEMETRY") == "1"


def _cache_dir() -> Path:
    """Same cache root as local_index.py's LocalIndex (platformdirs; a
    same-shape fallback if platformdirs is unavailable), so the anonymous
    install id lives alongside the embeddings cache. Duplicated rather than
    imported from local_index.py to keep the two modules independently
    importable/testable."""
    try:
        from platformdirs import user_cache_dir
        return Path(user_cache_dir("qai-consultant-mcp", "qai-consultant"))
    except Exception:
        return Path(__file__).resolve().parent.parent / ".qai_mcp_cache"


def _get_or_create_install_id() -> str:
    """Random anonymous UUID, persisted so it's stable across server
    restarts. Carries no identifying information — it's a fresh random
    value, not derived from hostname/MAC/etc."""
    path = _cache_dir() / _INSTALL_ID_FILENAME
    try:
        if path.exists():
            existing = path.read_text(encoding="utf-8").strip()
            if existing:
                return existing
    except Exception:
        pass
    new_id = str(uuid.uuid4())
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(new_id, encoding="utf-8")
    except Exception:
        pass  # a failed write just means a fresh id may be re-minted next call
    return new_id


def _package_version() -> str:
    try:
        from version import __version__
        return __version__
    except Exception:
        return "unknown"


def _base_properties() -> dict:
    return {
        "package_version": _package_version(),
        "python_minor_version": f"{sys.version_info.major}.{sys.version_info.minor}",
        "os_family": platform.system(),
    }


def _send(event_name: str, properties: dict) -> None:
    """The actual network call — always executed inside the fire-and-forget
    thread from _fire(), never on the caller's thread."""
    try:
        payload = {
            "api_key": _posthog_api_key(),
            "event": event_name,
            "distinct_id": _get_or_create_install_id(),
            "properties": {**_base_properties(), **properties},
        }
        data = json.dumps(payload).encode("utf-8")
        req = _urllib_request.Request(
            f"{_POSTHOG_HOST}/capture/",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        _urllib_request.urlopen(req, timeout=_TIMEOUT_SECONDS)
    except Exception:
        pass  # telemetry must never raise, log, or retry — a dropped event is fine


def _fire(event_name: str, properties: dict) -> None:
    if not is_enabled():
        return
    thread = threading.Thread(target=_send, args=(event_name, properties), daemon=True)
    thread.start()


def track_server_start() -> None:
    _fire("server_start", {})


def track_tool_called(
    tool_name: str,
    success: bool,
    duration_ms: float,
    k: Optional[int] = None,
    category: Optional[str] = None,
    extra: Optional[dict] = None,
) -> None:
    """tool_name is one of the 5 fixed MCP tool names; category (retrieval
    calls only) is one of kb_config.SOURCE_CATEGORIES' values or None; extra
    (review_qa_document/analyze_test_results only) carries a few fixed
    small-enum/numeric fields (e.g. doc_type, score bucket, finding/run
    counts) — never free-text, per the module-level telemetry contract."""
    properties = {"tool": tool_name, "success": success, "duration_ms": round(duration_ms, 1)}
    if k is not None:
        properties["k"] = k
    if category is not None:
        properties["category"] = category
    if extra:
        properties.update(extra)
    _fire("tool_called", properties)
