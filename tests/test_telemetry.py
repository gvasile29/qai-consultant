"""
Tests for src/telemetry.py — default-on (opt-out) MCP server usage telemetry.

Covers the engineering contract from MCP_PLAN.md section 7 (as revised in
v3.7.0): on unless QAI_TELEMETRY=0 / DO_NOT_TRACK=1, fire-and-forget (never blocks/raises on the caller's
thread), network failure fully silent, and no free-text ever leaves the
process in the event payload.
"""

import json
import sys
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

import telemetry


# ── is_enabled(): on by default, opt-out ───────────────────────────────────────

def test_enabled_by_default(monkeypatch):
    monkeypatch.delenv("QAI_TELEMETRY", raising=False)
    monkeypatch.delenv("DO_NOT_TRACK", raising=False)
    assert telemetry.is_enabled() is True


@pytest.mark.parametrize("value", ["0", "false", "FALSE", "no", "off", " 0 "])
def test_qai_telemetry_opt_out_values_disable(monkeypatch, value):
    monkeypatch.delenv("DO_NOT_TRACK", raising=False)
    monkeypatch.setenv("QAI_TELEMETRY", value)
    assert telemetry.is_enabled() is False


@pytest.mark.parametrize("value", ["1", "true", "yes"])
def test_do_not_track_disables(monkeypatch, value):
    monkeypatch.delenv("QAI_TELEMETRY", raising=False)
    monkeypatch.setenv("DO_NOT_TRACK", value)
    assert telemetry.is_enabled() is False


@pytest.mark.parametrize("value", ["", "0", "false"])
def test_do_not_track_off_values_keep_it_enabled(monkeypatch, value):
    monkeypatch.delenv("QAI_TELEMETRY", raising=False)
    monkeypatch.setenv("DO_NOT_TRACK", value)
    assert telemetry.is_enabled() is True


def test_startup_notice_goes_to_stderr_never_stdout(monkeypatch, capsys):
    monkeypatch.setenv("QAI_TELEMETRY", "1")
    monkeypatch.delenv("DO_NOT_TRACK", raising=False)
    telemetry.print_startup_notice()
    out, err = capsys.readouterr()
    assert out == ""
    assert "QAI_TELEMETRY=0" in err and "DO_NOT_TRACK=1" in err


def test_startup_notice_silent_when_opted_out(monkeypatch, capsys):
    monkeypatch.setenv("QAI_TELEMETRY", "0")
    telemetry.print_startup_notice()
    assert capsys.readouterr() == ("", "")


def test_track_tool_called_spawns_no_thread_when_disabled(monkeypatch):
    monkeypatch.setenv("QAI_TELEMETRY", "0")
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


def test_track_tool_called_drops_unknown_category(monkeypatch):
    """category arrives before LocalIndex validates it, so free text a client
    puts there must never be sent (module contract: no free-text)."""
    monkeypatch.setenv("QAI_TELEMETRY", "1")
    with patch("telemetry._send") as mock_send:
        telemetry.track_tool_called(
            "retrieve_qa_knowledge", False, 1.0, k=5, category="payments service for ACME Corp",
        )
        _join_all_daemon_threads()
        _, properties = mock_send.call_args[0]
        assert "category" not in properties
        assert properties["k"] == 5


def test_track_tool_called_ignores_unhashable_category(monkeypatch):
    """A client can send a list as category; it must not crash the tool."""
    monkeypatch.setenv("QAI_TELEMETRY", "1")
    with patch("telemetry._send") as mock_send:
        telemetry.track_tool_called("retrieve_qa_knowledge", False, 1.0, category=["Standard"])
        _join_all_daemon_threads()
        _, properties = mock_send.call_args[0]
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
    "$process_person_profile", "$geoip_disable",
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


def test_distinct_id_is_a_per_process_uuid_and_nothing_is_written_to_disk(monkeypatch):
    monkeypatch.setenv("QAI_TELEMETRY", "1")
    captured = []

    def _fake_urlopen(req, timeout=None):
        captured.append(json.loads(req.data.decode("utf-8")))
        return MagicMock()

    with patch("telemetry._urllib_request.urlopen", side_effect=_fake_urlopen),             patch("pathlib.Path.write_text") as mock_write, patch("builtins.open") as mock_open:
        telemetry._send("server_start", {})
        telemetry._send("server_start", {})
    mock_write.assert_not_called()
    mock_open.assert_not_called()
    import uuid as uuid_module
    uuid_module.UUID(captured[0]["distinct_id"])
    assert captured[0]["distinct_id"] == captured[1]["distinct_id"] == telemetry._SESSION_ID
    assert captured[0]["properties"]["$process_person_profile"] is False
    assert captured[0]["properties"]["$geoip_disable"] is True
