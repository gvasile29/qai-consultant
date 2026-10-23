"""v3.9.2 regression tests for the MCP prompts (end-user finding F5): no
unresolved template placeholder, no repo-internal references, citation
convention matching retrieve_qa_knowledge's actual output."""

import pytest

from qai_consultant.mcp import prompts
from qai_consultant.mcp import server as mcp_server

STRUCTURE_PROMPTS = [
    prompts.risk_register_structure,
    prompts.test_strategy_structure,
    prompts.test_plan_structure,
]
ALL_PROMPTS = [prompts.qa_project_interview, *STRUCTURE_PROMPTS]


@pytest.mark.parametrize("fn", ALL_PROMPTS)
def test_no_repo_internal_references(fn):
    text = fn()
    for forbidden in ("evals/", "MCP_PLAN", "[Source N]", "source_attribution", ".md section"):
        assert forbidden not in text, f"{fn.__name__} leaks repo-internal reference {forbidden!r}"


@pytest.mark.parametrize("fn", STRUCTURE_PROMPTS)
def test_no_literal_brace_placeholder(fn):
    assert "{project_name}" not in fn()
    assert "{{" not in fn()


@pytest.mark.parametrize("fn", STRUCTURE_PROMPTS)
def test_default_uses_explicit_marker_with_fill_in_instruction(fn):
    text = fn()
    assert "<Project Name>" in text
    assert "Replace <Project Name>" in text


@pytest.mark.parametrize("fn", STRUCTURE_PROMPTS)
def test_project_name_argument_fills_title(fn):
    text = fn("Acme Portal")
    assert "Acme Portal" in text
    assert "<Project Name>" not in text


@pytest.mark.parametrize("fn", STRUCTURE_PROMPTS)
def test_citation_instruction_matches_tool_output(fn):
    text = fn()
    assert "retrieve_qa_knowledge" in text
    assert "`source`" in text


def test_interview_prompt_still_works():
    assert "project_name" in prompts.qa_project_interview()


def test_server_prompts_expose_optional_project_name():
    import asyncio

    prompts_list = asyncio.run(mcp_server.mcp.list_prompts())
    by_name = {p.name: p for p in prompts_list}
    for name in ("risk_register_structure", "test_strategy_structure", "test_plan_structure"):
        args = by_name[name].arguments or []
        assert [(a.name, a.required) for a in args] == [("project_name", False)]
    assert not (by_name["qa_project_interview"].arguments or [])
    text = asyncio.run(mcp_server.mcp.get_prompt("risk_register_structure", {"project_name": "Zed"}))
    assert "Risk Register: Zed" in text.messages[0].content.text
