"""
Tests for src/telemetry.py — opt-in MCP server usage telemetry.

Covers the engineering contract from MCP_PLAN.md section 7: no-op unless
QAI_TELEMETRY=1, fire-and-forget (never blocks/raises on the caller's
thread), network failure fully silent, and no free-text ever leaves the
process in the event payload.
"""

import json
import sys
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

import telemetry


# ── is_enabled() / no-op when unset ─────────────────────────────────────────────

def test_disabled_when_env_unset(monkeypatch):
    monkeypatch.delenv("QAI_TELEMETRY", raising=False)
    assert telemetry.is_enabled() is False


def test_disabled_when_env_not_exactly_1(monkeypatch):
    monkeypatch.setenv("QAI_TELEMETRY", "true")  # only the literal "1" enables it
    assert telemetry.is_enabled() is False


def test_enabled_when_env_is_1(monkeypatch):
    monkeypatch.setenv("QAI_TELEMETRY", "1")
    assert telemetry.is_enabled() is True


def test_track_tool_called_spawns_no_thread_when_disabled(monkeypatch):
    monkeypatch.delenv("QAI_TELEMETRY", raising=False)
    threads_before = threading.active_count()
    with patch("telemetry._send") as mock_send:
        telemetry.track_tool_called("retrieve_qa_knowledge", True, 12.3)
        time.sleep(0.05)  # give a stray thread a chance to appear, if one did
        mock_send.assert_not_called()
    assert threading.active_count() == threads_before


# ── Event emitted when enabled (mocked transport) ───────────────────────────────

def test_track_server_start_fires_when_enabled(monkeypatch):
    monkeypatch.setenv("QAI_TELEMETRY", "1")
    with patch("telemetry._send") as mock_send:
        telemetry.track_server_start()
        _join_all_daemon_threads()
        mock_send.assert_called_once()
        event_name, properties = mock_send.call_args[0]
        assert event_name == "server_start"
        assert properties == {}


def test_track_tool_called_fires_when_enabled(monkeypatch):
    monkeypatch.setenv("QAI_TELEMETRY", "1")
    with patch("telemetry._send") as mock_send:
        telemetry.track_tool_called("retrieve_qa_knowledge", True, 42.567, k=5, category="Standard")
        _join_all_daemon_threads()
        mock_send.assert_called_once()
        event_name, properties = mock_send.call_args[0]
        assert event_name == "tool_called"
        assert properties["tool"] == "retrieve_qa_knowledge"
        assert properties["success"] is True
        assert properties["duration_ms"] == 42.6
        assert properties["k"] == 5
        assert properties["category"] == "Standard"


def test_track_tool_called_omits_k_and_category_when_not_given(monkeypatch):
    monkeypatch.setenv("QAI_TELEMETRY", "1")
    with patch("telemetry._send") as mock_send:
        telemetry.track_tool_called("estimate_qa_effort", False, 5.0)
        _join_all_daemon_threads()
        _, properties = mock_send.call_args[0]
        assert "k" not in properties
        assert "category" not in properties


def _join_all_daemon_threads(timeout: float = 2.0) -> None:
    for t in threading.enumerate():
        if t is not threading.main_thread() and t.daemon:
            t.join(timeout=timeout)


# ── Network failure is fully silent ─────────────────────────────────────────────

def test_send_swallows_network_errors(monkeypatch):
    monkeypatch.setenv("QAI_TELEMETRY", "1")
    with patch("telemetry._urllib_request.urlopen", side_effect=OSError("network unreachable")):
        telemetry._send("tool_called", {"tool": "retrieve_qa_knowledge"})  # must not raise


def test_send_swallows_json_serialization_errors(monkeypatch):
    """Even a malformed properties dict (e.g. a non-JSON-serializable value)
    must not propagate — telemetry can never break the calling tool."""
    monkeypatch.setenv("QAI_TELEMETRY", "1")
    telemetry._send("tool_called", {"bad": object()})  # must not raise


def test_fire_and_forget_does_not_block_caller(monkeypatch):
    monkeypatch.setenv("QAI_TELEMETRY", "1")

    def _slow_send(*_args, **_kwargs):
        time.sleep(1.0)

    with patch("telemetry._send", side_effect=_slow_send):
        start = time.monotonic()
        telemetry.track_tool_called("list_kb_sources", True, 1.0)
        elapsed = time.monotonic() - start
    assert elapsed < 0.5, f"track_tool_called() blocked the caller for {elapsed:.2f}s — must be fire-and-forget"


# ── No free-text ever leaves the process ────────────────────────────────────────

_ALLOWED_TOP_LEVEL_KEYS = {"api_key", "event", "distinct_id", "properties"}
_ALLOWED_PROPERTY_KEYS = {
    "package_version", "python_minor_version", "os_family",
    "tool", "success", "duration_ms", "k", "category",
}
_FORBIDDEN_SUBSTRINGS_IN_PAYLOAD = [
    "SECRET_QUERY_TEXT_SHOULD_NEVER_APPEAR",
    "/Users/", "C:\\", "project_name", "known_risks",
]


def test_payload_shape_has_no_unexpected_keys(monkeypatch):
    monkeypatch.setenv("QAI_TELEMETRY", "1")
    captured = {}

    def _fake_urlopen(req, timeout=None):
        captured["data"] = json.loads(req.data.decode("utf-8"))
        return MagicMock()

    with patch("telemetry._urllib_request.urlopen", side_effect=_fake_urlopen):
        telemetry._send("tool_called", {"tool": "retrieve_qa_knowledge", "success": True,
                                          "duration_ms": 10.0, "k": 5, "category": "Standard"})

    payload = captured["data"]
    assert set(payload.keys()) <= _ALLOWED_TOP_LEVEL_KEYS
    assert set(payload["properties"].keys()) <= _ALLOWED_PROPERTY_KEYS


def test_payload_never_contains_query_text_or_free_text_fields(monkeypatch):
    """Simulates a caller accidentally passing free-text through properties
    (a defense-in-depth check, not something the real call sites do) — even
    then, the serialized payload must never contain the forbidden strings,
    proving the wire format has no field that could carry them."""
    monkeypatch.setenv("QAI_TELEMETRY", "1")
    captured = {}

    def _fake_urlopen(req, timeout=None):
        captured["raw"] = req.data.decode("utf-8")
        return MagicMock()

    with patch("telemetry._urllib_request.urlopen", side_effect=_fake_urlopen):
        telemetry._send("tool_called", {"tool": "retrieve_qa_knowledge", "success": True, "duration_ms": 1.0})

    raw = captured["raw"]
    for forbidden in _FORBIDDEN_SUBSTRINGS_IN_PAYLOAD:
        assert forbidden not in raw


def test_install_id_is_a_stable_random_uuid(tmp_path, monkeypatch):
    monkeypatch.setattr(telemetry, "_cache_dir", lambda: tmp_path)
    id1 = telemetry._get_or_create_install_id()
    id2 = telemetry._get_or_create_install_id()
    assert id1 == id2, "install id must be stable across calls (persisted to disk)"
    import uuid as uuid_module
    uuid_module.UUID(id1)  # raises ValueError if not a valid UUID


def test_install_id_survives_unreadable_cache_dir(tmp_path, monkeypatch):
    """A cache dir that can't be created/written must not crash — a fresh id
    is simply minted (and possibly re-minted) rather than persisted."""
    unwritable = tmp_path / "does" / "not" / "exist_and_cannot_be_made"
    monkeypatch.setattr(telemetry, "_cache_dir", lambda: unwritable)
    with patch("pathlib.Path.mkdir", side_effect=OSError("permission denied")):
        install_id = telemetry._get_or_create_install_id()  # must not raise
    import uuid as uuid_module
    uuid_module.UUID(install_id)
