"""
Tests for src/mcp_server.py — the MCP server's tool surface (v3.0 step 6).

Uses the MCP SDK's in-memory client/server session (mcp.shared.memory) —
no subprocess, no real stdio transport — to exercise the server exactly as
a real MCP client would: list_tools(), call_tool(). Covers the pinned
contracts from MCP_PLAN.md section 3: schemas, the happy path for each of
the 3 tools, the invalid-category and validation-error contracts (both
return a structured error, neither raises), and that estimate_qa_effort's
output is bit-for-bit identical to calling compute_estimation() directly.
"""

import asyncio
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from mcp.shared.memory import create_connected_server_and_client_session

import mcp_server
from effort_core import compute_estimation
from dialogue import ProjectContext


def _run(coro):
    return asyncio.run(coro)


async def _call_tool(name: str, arguments: dict) -> dict:
    async with create_connected_server_and_client_session(mcp_server.mcp._mcp_server) as client:
        await client.initialize()
        result = await client.call_tool(name, arguments)
        assert not result.isError, f"{name} call errored at the protocol level: {result.content}"
        assert len(result.content) == 1
        return json.loads(result.content[0].text)


async def _list_tools() -> list:
    async with create_connected_server_and_client_session(mcp_server.mcp._mcp_server) as client:
        await client.initialize()
        result = await client.list_tools()
        return result.tools


async def _list_prompts() -> list:
    async with create_connected_server_and_client_session(mcp_server.mcp._mcp_server) as client:
        await client.initialize()
        result = await client.list_prompts()
        return result.prompts


async def _get_prompt(name: str) -> str:
    async with create_connected_server_and_client_session(mcp_server.mcp._mcp_server) as client:
        await client.initialize()
        result = await client.get_prompt(name)
        return result.messages[0].content.text


# ── Tool registration ────────────────────────────────────────────────────────────

def test_all_three_tools_registered():
    tools = _run(_list_tools())
    names = {t.name for t in tools}
    assert names == {"retrieve_qa_knowledge", "list_kb_sources", "estimate_qa_effort"}


def test_retrieve_qa_knowledge_schema_has_expected_params():
    tools = _run(_list_tools())
    tool = next(t for t in tools if t.name == "retrieve_qa_knowledge")
    props = tool.inputSchema["properties"]
    assert set(props.keys()) >= {"query", "category", "k"}


def test_estimate_qa_effort_schema_has_expected_params():
    tools = _run(_list_tools())
    tool = next(t for t in tools if t.name == "estimate_qa_effort")
    props = tool.inputSchema["properties"]
    expected = set(mcp_server._REQUIRED_FIELDS) | {"additional_context"}
    assert set(props.keys()) == expected


# ── retrieve_qa_knowledge ────────────────────────────────────────────────────────

def test_retrieve_qa_knowledge_happy_path():
    result = _run(_call_tool("retrieve_qa_knowledge", {
        "query": "How should I prioritize tests by failure likelihood and business impact?",
        "k": 3,
    }))
    assert "error" not in result
    assert "chunks" in result and "kb_version" in result
    assert len(result["chunks"]) <= 3
    for chunk in result["chunks"]:
        assert set(chunk.keys()) == {"source", "category", "text", "score"}


def test_retrieve_qa_knowledge_invalid_category_returns_structured_error():
    result = _run(_call_tool("retrieve_qa_knowledge", {
        "query": "anything",
        "category": "NotARealCategory",
    }))
    assert result["error"] == "invalid_argument"
    assert "valid_categories" in result


def test_retrieve_qa_knowledge_category_filter():
    result = _run(_call_tool("retrieve_qa_knowledge", {
        "query": "risk based testing prioritization",
        "category": "Methodology",
        "k": 5,
    }))
    assert "error" not in result
    assert all(c["category"] == "Methodology" for c in result["chunks"])


# ── list_kb_sources ──────────────────────────────────────────────────────────────

def test_list_kb_sources_happy_path():
    result = _run(_call_tool("list_kb_sources", {}))
    assert "categories" in result
    assert "kb_version" in result
    assert "doc_count" in result
    assert result["doc_count"] > 0
    assert "Standard" in result["categories"]


# ── estimate_qa_effort ───────────────────────────────────────────────────────────

_VALID_ESTIMATE_ARGS = {
    "project_name": "Sample Fintech API",
    "project_description": "Payment processing API for a fintech startup",
    "project_type": "api",
    "tech_stack": "Python, FastAPI, PostgreSQL",
    "team_qa_size": "3",
    "team_dev_size": "8",
    "timeline": "6 months",
    "methodology": "agile",
    "known_risks": "third-party payment gateway integration",
    "existing_automation": "some unit tests",
    "compliance_requirements": "PCI-DSS",
}


def test_estimate_qa_effort_happy_path_returns_estimation_data_shape():
    result = _run(_call_tool("estimate_qa_effort", _VALID_ESTIMATE_ARGS))
    assert "error" not in result
    for key in ("project_type_detected", "baseline_effort_min", "baseline_effort_max",
                "multipliers", "pert_activities", "final_effort_min", "final_effort_max",
                "confidence_level", "confidence_score"):
        assert key in result
    assert result["confidence_level"] in ("Low", "Medium", "High")
    assert isinstance(result["multipliers"], list)
    for m in result["multipliers"]:
        assert isinstance(m, list) and len(m) == 2  # (reason, pct) tuples -> JSON-safe lists


def test_estimate_qa_effort_matches_compute_estimation_directly():
    """The tool's output must be identical to calling compute_estimation()
    directly with an equivalent ProjectContext — no drift between the MCP
    surface and the underlying deterministic core."""
    from dataclasses import asdict
    context = ProjectContext(**_VALID_ESTIMATE_ARGS, additional_context="")
    direct = asdict(compute_estimation(context))
    direct["multipliers"] = [list(m) for m in direct["multipliers"]]

    via_tool = _run(_call_tool("estimate_qa_effort", _VALID_ESTIMATE_ARGS))
    assert via_tool == direct


def test_estimate_qa_effort_validation_error_shape_never_crashes():
    bad_args = dict(_VALID_ESTIMATE_ARGS)
    bad_args["project_name"] = ""  # empty -> InputValidator rejects it
    bad_args["project_description"] = "short"  # under MIN_DESCRIPTION_LENGTH

    result = _run(_call_tool("estimate_qa_effort", bad_args))
    assert result["error"] == "validation"
    assert "project_name" in result["fields"]
    assert "project_description" in result["fields"]


def test_estimate_qa_effort_validation_error_does_not_flag_valid_fields():
    bad_args = dict(_VALID_ESTIMATE_ARGS)
    bad_args["team_qa_size"] = ""

    result = _run(_call_tool("estimate_qa_effort", bad_args))
    assert result["error"] == "validation"
    assert "team_qa_size" in result["fields"]
    assert "project_name" not in result["fields"]


def test_estimate_qa_effort_invalid_additional_context_reported():
    bad_args = dict(_VALID_ESTIMATE_ARGS)
    bad_args["additional_context"] = "x" * 3000  # over MAX_ADDITIONAL_CONTEXT_LENGTH

    result = _run(_call_tool("estimate_qa_effort", bad_args))
    assert result["error"] == "validation"
    assert "additional_context" in result["fields"]


# ── Prompts ───────────────────────────────────────────────────────────────────────

def test_all_four_prompts_registered():
    prompts = _run(_list_prompts())
    names = {p.name for p in prompts}
    assert names == {
        "qa_project_interview", "risk_register_structure",
        "test_strategy_structure", "test_plan_structure",
    }


def test_qa_project_interview_lists_all_eleven_questions():
    from dialogue import QUESTIONS
    text = _run(_get_prompt("qa_project_interview"))
    for q in QUESTIONS:
        assert q["key"] in text
        assert q["question"] in text


def test_risk_register_structure_content_matches_app_convention():
    text = _run(_get_prompt("risk_register_structure"))
    for heading in ("Executive Summary", "Risk Matrix Overview", "Detailed Risk Analysis",
                    "Risk-Based Testing Priorities", "Recommendations for QA Strategy"):
        assert heading in text
    assert "retrieve_qa_knowledge" in text
    assert "[Source N]" in text
    assert "AI-generated" in text


def test_test_strategy_structure_content_matches_app_convention():
    text = _run(_get_prompt("test_strategy_structure"))
    for heading in ("Project Overview", "Risk Assessment", "Test Types Recommended",
                    "Entry & Exit Criteria", "Resources & Man Power Estimation", "References"):
        assert heading in text
    assert "estimate_qa_effort" in text
    assert "retrieve_qa_knowledge" in text
    assert "AI-generated" in text


def test_test_plan_structure_content_matches_app_convention():
    text = _run(_get_prompt("test_plan_structure"))
    for heading in ("Introduction", "Test Items", "Features to be Tested",
                    "Entry and Exit Criteria", "Testing Schedule", "Environmental Needs"):
        assert heading in text
    assert "IEEE 829" in text
    assert "version not specified" in text
    assert "retrieve_qa_knowledge" in text
    assert "AI-generated" in text


# ── Fail-fast startup ─────────────────────────────────────────────────────────────

def test_main_exits_nonzero_if_index_build_fails(monkeypatch):
    def _raise(*_args, **_kwargs):
        raise RuntimeError("simulated index build failure")

    monkeypatch.setattr(mcp_server, "_get_index", _raise)
    monkeypatch.setattr(mcp_server, "_index", None)
    with pytest.raises(SystemExit) as exc_info:
        mcp_server.main()
    assert exc_info.value.code == 1


def test_main_starts_server_and_fires_telemetry_when_index_builds(monkeypatch):
    calls = []
    monkeypatch.setattr(mcp_server, "_get_index", lambda: object())
    monkeypatch.setattr(mcp_server.telemetry, "track_server_start", lambda: calls.append("server_start"))
    monkeypatch.setattr(mcp_server.mcp, "run", lambda: calls.append("run"))

    mcp_server.main()

    assert calls == ["server_start", "run"]
