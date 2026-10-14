"""
QAI Consultant — MCP server usage telemetry (v3.0; on by default since v3.7.0).

Enabled by default; disabled by QAI_TELEMETRY=0 (also "false"/"no"/"off")
or the cross-tool DO_NOT_TRACK=1 convention. main() prints a one-line
notice to stderr at server start saying so (stderr is safe for a stdio MCP
server — only stdout carries the protocol). Answers "how many servers are
actually running, and which tools get called?", which PyPI download counts
(they include CI, mirrors and bots, and miss cached re-launches) can't.

Backend: PostHog free tier (EU Cloud), a single plain HTTPS POST per event
(no SDK dependency, no extra install weight). The project API key below is a
PUBLIC write-only key — embedding it is PostHog's designed use for
client-side event capture, not a secret; it can be overridden via
QAI_TELEMETRY_POSTHOG_KEY for local testing or a future key rotation.

Engineering contract (telemetry must never touch the actual tool call):
  - fire-and-forget from a daemon thread
  - 2-second network timeout
  - every exception swallowed — a telemetry failure must never break or
    slow down a tool call, and never raises/logs/retries
  - no retries, no disk buffering — a dropped event just never arrives

Privacy contract: nothing is stored on the user's machine. The distinct id
is a random UUID minted per server process (_SESSION_ID), never persisted,
so events can't be linked across restarts (the pre-v3.7.0 persisted
install id was removed with the switch to default-on — storing an
identifier on the user's device would need prior consent under EU ePrivacy
Art. 5(3)). Events are sent with $process_person_profile=false and
$geoip_disable=true, and the PostHog project discards client IPs.
Never sent: query text, project fields, KB content, file paths, hostnames,
or any other free-text. Only: event name, tool name, success flag, duration
ms, k/category (retrieval calls only — both fixed small enums, not
free-text), package version, Python minor version, OS family.
"""

from __future__ import annotations

import json
import os
import platform
import sys
import threading
import uuid
from typing import Optional
from urllib import request as _urllib_request

from kb_config import SOURCE_CATEGORIES

_ALLOWED_CATEGORIES = frozenset(SOURCE_CATEGORIES.values())

_POSTHOG_HOST = "https://eu.i.posthog.com"  # this project's PostHog org is on EU Cloud
# Public write-only PostHog Project API Key (not a secret — see module
# docstring). If this ever needs rotating, generate a new one from PostHog's
# Project Settings (NOT "Personal API Keys", which is a different, sensitive
# credential type — phx_... prefix, must never end up here).
_POSTHOG_PROJECT_API_KEY_DEFAULT = "phc_pgVvXQx4idPNe7JNcX6uQHhTUryPfVEYKDxRVWcYNWVP"
_TIMEOUT_SECONDS = 2.0
_OPT_OUT_VALUES = {"0", "false", "no", "off"}
_SESSION_ID = str(uuid.uuid4())  # per process, never persisted — see the privacy contract above


def _posthog_api_key() -> str:
    return os.environ.get("QAI_TELEMETRY_POSTHOG_KEY", _POSTHOG_PROJECT_API_KEY_DEFAULT)


def is_enabled() -> bool:
    if os.environ.get("QAI_TELEMETRY", "").strip().lower() in _OPT_OUT_VALUES:
        return False
    do_not_track = os.environ.get("DO_NOT_TRACK", "").strip().lower()
    if do_not_track and do_not_track not in _OPT_OUT_VALUES:
        return False
    return True


STARTUP_NOTICE = (
    "qai-consultant-mcp: anonymous usage telemetry is on (tool name, success, duration, "
    "version, OS family; never your queries or documents). Opt out with QAI_TELEMETRY=0 "
    "or DO_NOT_TRACK=1."
)


def print_startup_notice() -> None:
    """One line on stderr when telemetry is enabled — stdout is the MCP
    protocol channel and must never be written to."""
    if is_enabled():
        try:
            print(STARTUP_NOTICE, file=sys.stderr, flush=True)
        except Exception:
            pass


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
        "$process_person_profile": False,
        "$geoip_disable": True,
    }


def _send(event_name: str, properties: dict) -> None:
    """The actual network call — always executed inside the fire-and-forget
    thread from _fire(), never on the caller's thread."""
    try:
        payload = {
            "api_key": _posthog_api_key(),
            "event": event_name,
            "distinct_id": _SESSION_ID,
            "properties": {**_base_properties(), **properties},
        }
        data = json.dumps(payload).encode("utf-8")
        req = _urllib_request.Request(
            f"{_POSTHOG_HOST}/capture/",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        _urllib_request.urlopen(req, timeout=_TIMEOUT_SECONDS)  # nosec B310 -- URL is built from a hardcoded https:// constant (_POSTHOG_HOST), never user-influenced
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
    """tool_name is one of the 6 fixed MCP tool names; category (retrieval
    calls only) is one of kb_config.SOURCE_CATEGORIES' values or None; extra
    (review_qa_document/analyze_test_results only) carries a few fixed
    small-enum/numeric fields (e.g. doc_type, score bucket, finding/run
    counts) — never free-text, per the module-level telemetry contract."""
    properties = {"tool": tool_name, "success": success, "duration_ms": round(duration_ms, 1)}
    if k is not None:
        properties["k"] = k
    # The raw argument arrives before LocalIndex.search() validates it, so an
    # MCP client could put free text here; only a known category is sent.
    if isinstance(category, str) and category in _ALLOWED_CATEGORIES:
        properties["category"] = category
    if extra:
        properties.update(extra)
    _fire("tool_called", properties)
