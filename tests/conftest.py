"""Test-session defaults.

MCP telemetry is on by default (v3.7.0+), so without this every test that
calls an MCP tool or launches the stdio server would POST real events to
PostHog — from every dev machine and every CI run. tests/unit/observability/test_telemetry.py
sets QAI_TELEMETRY per test via monkeypatch, which overrides this.
"""
import os

os.environ["QAI_TELEMETRY"] = "0"


# Tests live in tests/<level>/<feature>/; the level folder is the marker, so
# `pytest -m unit` and `pytest tests/unit` select the same files.
LEVELS = ("unit", "integration", "system", "e2e")


def pytest_collection_modifyitems(items):
    import pytest

    for item in items:
        parts = item.path.parts
        if "tests" in parts:
            rest = parts[len(parts) - 1 - parts[::-1].index("tests") + 1:]
            if rest and rest[0] in LEVELS:
                item.add_marker(getattr(pytest.mark, rest[0]))
