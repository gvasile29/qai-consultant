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

def test_all_five_tools_registered():
    tools = _run(_list_tools())
    names = {t.name for t in tools}
    assert names == {
        "retrieve_qa_knowledge", "list_kb_sources", "estimate_qa_effort",
        "review_qa_document", "analyze_test_results",
    }


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


def test_review_qa_document_schema_has_expected_params():
    tools = _run(_list_tools())
    tool = next(t for t in tools if t.name == "review_qa_document")
    props = tool.inputSchema["properties"]
    assert set(props.keys()) == {"document_text", "doc_type"}


def test_analyze_test_results_schema_has_expected_params():
    tools = _run(_list_tools())
    tool = next(t for t in tools if t.name == "analyze_test_results")
    props = tool.inputSchema["properties"]
    assert set(props.keys()) == {
        "junit_xml", "csv_text", "reference_tests", "flaky_min", "flaky_max",
    }


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


# ── review_qa_document ───────────────────────────────────────────────────────────

_STRONG_TEST_PLAN_TEXT = """
# Test Plan — Acme Checkout

## Scope
This document defines the scope of testing for the checkout service.

## Test Items
The checkout API and payment gateway integration are the items to be tested.

## Features to be Tested
The following will be tested: cart totals, tax calculation, discount codes.

## Features Not to be Tested
Out of scope: third-party fraud detection internals are excluded from this plan.

## Objectives
The objective of this test plan is to validate checkout correctness end-to-end.

## Test Levels
Testing includes unit test, integration test, system test, and regression test levels.

## Approach
A risk-based testing approach is used, with risk-based prioritization of test cases.

## Pass/Fail Criteria
A test case passes when the expected result matches the observed output exactly.

## Entry Criteria
Entry criteria: all REQ-101 and REQ-102 requirements are code-complete and deployed to QA.

## Exit Criteria
Exit criteria: 95% of test cases pass and code coverage of 80% is achieved.

## Suspension Criteria
Testing will be suspended if the build fails smoke tests; resumption criteria apply after a fix.

## Deliverables
Test deliverables include the traceability matrix and the final test summary report.

## Schedule
The testing schedule spans two weeks per the project milestones.

## Risks
### R01 — Payment gateway instability
- **Severity:** Critical
- **Likelihood:** High priority risk requiring mitigation.
- **Mitigation:** A contingency plan and mitigation strategy are documented for R01.

Quality metrics tracked include defect density, coverage %, and pass rate (KPI).

Expected result: the total is calculated to the exact cent per REQ-101.
Expected result: the discount code REQ-102 reduces the total by exactly 10%.

## Approvals
Sign-off is required from the QA Lead and Project Manager before release.
"""


def test_review_qa_document_happy_path_shape():
    result = _run(_call_tool("review_qa_document", {
        "document_text": _STRONG_TEST_PLAN_TEXT, "doc_type": "test_plan",
    }))
    assert "error" not in result
    assert result["doc_type"] == "test_plan"
    assert 0 <= result["overall_score"] <= 100
    assert set(result["dimension_scores"].keys()) == {
        "structure_completeness", "objectives_scope_clarity", "entry_exit_criteria",
        "traceability", "measurability", "risk_coverage",
    }
    assert isinstance(result["findings"], list)
    assert "kb_version" in result
    assert "stats" in result


def test_review_qa_document_findings_carry_kb_citations_list():
    weak_doc = "Just a short note. " * 20  # long enough, no structure/keywords
    result = _run(_call_tool("review_qa_document", {
        "document_text": weak_doc, "doc_type": "test_plan",
    }))
    assert result["findings"], "expected findings on a weak document"
    for finding in result["findings"]:
        assert set(finding.keys()) == {"dimension", "severity", "message", "evidence", "kb_citations"}
        assert isinstance(finding["kb_citations"], list)
        for citation in finding["kb_citations"]:
            assert set(citation.keys()) == {"source", "category", "score"}


def test_review_qa_document_invalid_doc_type_returns_structured_error():
    result = _run(_call_tool("review_qa_document", {
        "document_text": _STRONG_TEST_PLAN_TEXT, "doc_type": "not_a_real_type",
    }))
    assert result["error"] == "invalid_argument"
    assert "valid_doc_types" in result


def test_review_qa_document_insufficient_content_is_not_an_error():
    result = _run(_call_tool("review_qa_document", {
        "document_text": "Too short.", "doc_type": "auto",
    }))
    assert "error" not in result
    assert result["doc_type"] == "insufficient_content"
    assert result["overall_score"] == 0
    assert result["findings"] == []


def test_review_qa_document_auto_detects_doc_type():
    result = _run(_call_tool("review_qa_document", {
        "document_text": _STRONG_TEST_PLAN_TEXT, "doc_type": "auto",
    }))
    assert result["doc_type"] == "test_plan"


# ── analyze_test_results ─────────────────────────────────────────────────────────

_SINGLE_RUN_XML = """<testsuites>
    <testsuite name="suite">
        <testcase classname="pkg.A" name="test_pass" time="0.5"/>
        <testcase classname="pkg.A" name="test_fail" time="0.1">
            <failure message="boom">Traceback...</failure>
        </testcase>
    </testsuite>
</testsuites>"""

_MULTI_RUN_XML_ARRAY = json.dumps([
    {"run_id": "run1", "xml": '<testsuite><testcase classname="pkg.B" name="test_flaky" time="0.1"/></testsuite>'},
    {"run_id": "run2", "xml": '<testsuite><testcase classname="pkg.B" name="test_flaky" time="0.1"><failure message="x">x</failure></testcase></testsuite>'},
    {"run_id": "run3", "xml": '<testsuite><testcase classname="pkg.B" name="test_flaky" time="0.1"/></testsuite>'},
])

_SIMPLE_CSV = "name,classname,status,duration_s\ntest_one,pkg.C,passed,1.0\ntest_two,pkg.C,failed,2.0\n"


def test_analyze_test_results_junit_xml_happy_path():
    result = _run(_call_tool("analyze_test_results", {"junit_xml": _SINGLE_RUN_XML}))
    assert "error" not in result
    assert result["runs"] == 1
    assert result["total_tests"] == 2
    assert result["executions"] == 2
    assert result["overall_pass_rate"] == 0.5


def test_analyze_test_results_csv_happy_path():
    result = _run(_call_tool("analyze_test_results", {"csv_text": _SIMPLE_CSV}))
    assert "error" not in result
    assert result["total_tests"] == 2
    assert result["executions"] == 2


def test_analyze_test_results_multi_run_json_array():
    result = _run(_call_tool("analyze_test_results", {
        "junit_xml": _MULTI_RUN_XML_ARRAY, "flaky_min": 0.2, "flaky_max": 0.8,
    }))
    assert "error" not in result
    assert result["runs"] == 3
    assert result["executions"] == 3
    assert len(result["flaky"]) == 1
    assert result["flaky"][0]["test"] == "pkg.B::test_flaky"


def test_analyze_test_results_requires_exactly_one_input():
    both = _run(_call_tool("analyze_test_results", {"junit_xml": _SINGLE_RUN_XML, "csv_text": _SIMPLE_CSV}))
    assert both["error"] == "invalid_argument"

    neither = _run(_call_tool("analyze_test_results", {}))
    assert neither["error"] == "invalid_argument"


def test_analyze_test_results_malformed_xml_never_crashes():
    result = _run(_call_tool("analyze_test_results", {"junit_xml": "<not valid xml"}))
    assert "error" not in result
    assert result["runs"] == 0
    assert result["executions"] == 0


def test_analyze_test_results_reference_tests_reports_never_run():
    result = _run(_call_tool("analyze_test_results", {
        "junit_xml": _SINGLE_RUN_XML,
        "reference_tests": ["pkg.A::test_pass", "pkg.A::test_never_ran"],
    }))
    assert "error" not in result
    assert result["never_run"] == [{"test": "pkg.A::test_never_ran"}]


# ── Telemetry silence when disabled ─────────────────────────────────────────────

def test_telemetry_disabled_by_default_does_not_raise_on_new_tools(monkeypatch):
    monkeypatch.delenv("QAI_TELEMETRY", raising=False)
    assert mcp_server.telemetry.is_enabled() is False
    result = _run(_call_tool("review_qa_document", {
        "document_text": _STRONG_TEST_PLAN_TEXT, "doc_type": "test_plan",
    }))
    assert "error" not in result


def test_track_tool_called_merges_extra_properties(monkeypatch):
    captured = {}
    monkeypatch.setattr(mcp_server.telemetry, "is_enabled", lambda: True)
    monkeypatch.setattr(mcp_server.telemetry, "_send", lambda name, props: captured.update(props))
    mcp_server.telemetry.track_tool_called(
        "review_qa_document", success=True, duration_ms=1.0,
        extra={"doc_type": "test_plan", "score_bucket": "80-100", "finding_count": 0},
    )
    import time as _time
    _time.sleep(0.2)  # fire-and-forget thread — give it a moment to run
    assert captured.get("doc_type") == "test_plan"
    assert captured.get("score_bucket") == "80-100"
    assert captured.get("finding_count") == 0


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


class _FakeIndex:
    """Records search() calls — `main()` must warm up the embedding model
    with one real search() call, on the main thread, before mcp.run()."""

    def __init__(self):
        self.search_calls = []

    def search(self, query, k=1):
        self.search_calls.append((query, k))
        return {"chunks": [], "kb_version": "fake"}


def test_main_starts_server_and_fires_telemetry_when_index_builds(monkeypatch):
    calls = []
    fake_index = _FakeIndex()
    monkeypatch.setattr(mcp_server, "_get_index", lambda: fake_index)
    monkeypatch.setattr(mcp_server.telemetry, "track_server_start", lambda: calls.append("server_start"))
    monkeypatch.setattr(mcp_server.mcp, "run", lambda: calls.append("run"))

    mcp_server.main()

    assert calls == ["server_start", "run"]


def test_main_warms_up_embedding_model_before_run(monkeypatch):
    """Regression test: main() must call index.search() (forcing the real
    embedding model to initialize on the main thread) BEFORE mcp.run()
    starts stdio_server()'s concurrent stdin-reader task — deferring this to
    the first client-triggered retrieve_qa_knowledge call deadlocks on
    Windows (confirmed via a real `uvx qai-consultant-mcp` stdio subprocess
    hanging indefinitely on the second tool call)."""
    order = []
    fake_index = _FakeIndex()
    monkeypatch.setattr(mcp_server, "_get_index", lambda: fake_index)
    monkeypatch.setattr(mcp_server.telemetry, "track_server_start", lambda: None)
    monkeypatch.setattr(mcp_server.mcp, "run", lambda: order.append("run"))

    mcp_server.main()

    assert fake_index.search_calls == [("warmup", 1)]


def test_main_exits_nonzero_if_warmup_search_fails(monkeypatch):
    class _BrokenIndex:
        def search(self, query, k=1):
            raise RuntimeError("simulated embedding model init failure")

    monkeypatch.setattr(mcp_server, "_get_index", lambda: _BrokenIndex())
    monkeypatch.setattr(mcp_server.telemetry, "track_server_start", lambda: None)
    with pytest.raises(SystemExit) as exc_info:
        mcp_server.main()
    assert exc_info.value.code == 1
