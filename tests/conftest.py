"""Test-session defaults.

MCP telemetry is on by default (v3.7.0+), so without this every test that
calls an MCP tool or launches the stdio server would POST real events to
PostHog — from every dev machine and every CI run. tests/test_telemetry.py
sets QAI_TELEMETRY per test via monkeypatch, which overrides this.
"""
import os

os.environ["QAI_TELEMETRY"] = "0"
