"""
QAI Consultant — MCP server (v3.0 MVP).

Local stdio transport, fully keyless: no Pinecone, no Mistral/OpenRouter,
no Streamlit. See MCP_PLAN.md section 1 ("the MCP lens") for why: the
client LLM (Claude Code, Claude Desktop, claude.ai) is stronger than this
project's internal mistral-small, so this server never generates text —
it exposes what the client cannot do alone: standards-grounded knowledge
retrieval (retrieve_qa_knowledge, list_kb_sources) and deterministic QA
effort estimation (estimate_qa_effort), plus MCP prompts (the 11-question
interview + document structures, src/prompts.py) that instruct the client
to ground its own generation in those tools rather than call a second LLM.

Run directly: `python src/mcp_server.py`
Packaged entry point (step 8): `qai-consultant-mcp`

NOTE: deliberately no `from __future__ import annotations` here. The
installed mcp SDK's Tool.from_function() (mcp/server/fastmcp/tools/base.py)
inspects each parameter's live annotation object and does
`issubclass(param.annotation, Context)` once `typing.get_origin()` returns
None for it. With postponed evaluation, every annotation becomes a plain
string instead (e.g. "Optional[str]"), get_origin() then also returns None
for it, and issubclass() on a string raises TypeError — breaking @mcp.tool()
registration for any tool with a non-trivial type hint (Optional[str], etc.).
"""

import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))  # `python src/mcp_server.py` direct-run support

from mcp.server.fastmcp import FastMCP

import telemetry
from dialogue import InputValidator, ProjectContext
from effort_core import compute_estimation
from local_index import LocalIndex
from prompts import (
    qa_project_interview as _qa_project_interview,
    risk_register_structure as _risk_register_structure,
    test_plan_structure as _test_plan_structure,
    test_strategy_structure as _test_strategy_structure,
)

INSTRUCTIONS = (
    "QAI Consultant — standards-grounded QA knowledge retrieval (ISTQB, OWASP, "
    "IEEE, ISO, EU AI Act) and deterministic QA effort estimation. This server "
    "never generates documents — call retrieve_qa_knowledge to ground your own "
    "analysis in the knowledge base, and estimate_qa_effort for a deterministic "
    "PERT-based effort calculation you can write a narrative around."
)

mcp = FastMCP("qai-consultant-mcp", instructions=INSTRUCTIONS)

# Built lazily (and once) on first tool call, not at import time — importing this
# module (e.g. for tests) must not eagerly load the embedding model.
_index: Optional[LocalIndex] = None


def _get_index() -> LocalIndex:
    global _index
    if _index is None:
        _index = LocalIndex()
    return _index


# ── Tool: retrieve_qa_knowledge ─────────────────────────────────────────────────

@mcp.tool()
def retrieve_qa_knowledge(query: str, category: Optional[str] = None, k: int = 5) -> dict:
    """Retrieve grounding chunks from the QA knowledge base (ISTQB, OWASP, IEEE,
    ISO standards; testing methodologies; audit/evaluation frameworks; the EU AI
    Act). Returns {"chunks": [{"source", "category", "text", "score"}], "kb_version"}.
    category, if given, must be one of: Standard, Methodology, Article,
    Expert Knowledge, Audit/Evaluation — an unrecognized value returns a
    structured {"error": "invalid_argument", ...} rather than raising. k is
    clamped to [1, 20]."""
    start = time.monotonic()
    result = _get_index().search(query, category=category, k=k)
    duration_ms = (time.monotonic() - start) * 1000
    telemetry.track_tool_called(
        "retrieve_qa_knowledge", success="error" not in result,
        duration_ms=duration_ms, k=k, category=category,
    )
    return result


# ── Tool: list_kb_sources ────────────────────────────────────────────────────────

@mcp.tool()
def list_kb_sources() -> dict:
    """List every document in the knowledge base, grouped by category. Returns
    {"categories": {category: [{"source", "title"}]}, "kb_version", "doc_count"}."""
    start = time.monotonic()
    result = _get_index().list_sources()
    duration_ms = (time.monotonic() - start) * 1000
    telemetry.track_tool_called("list_kb_sources", success=True, duration_ms=duration_ms)
    return result


# ── Tool: estimate_qa_effort ─────────────────────────────────────────────────────

# Order matches dialogue.QUESTIONS (minus additional_context, appended last as
# it's optional there too) — kept as an explicit list here rather than importing
# QUESTIONS, since the tool's parameter list is part of the pinned MCP contract
# (MCP_PLAN.md section 3) and must not silently reshape if the dialogue's
# question set changes.
_REQUIRED_FIELDS = [
    "project_name", "project_description", "project_type", "tech_stack",
    "team_qa_size", "team_dev_size", "timeline", "methodology",
    "known_risks", "existing_automation", "compliance_requirements",
]


@mcp.tool()
def estimate_qa_effort(
    project_name: str,
    project_description: str,
    project_type: str,
    tech_stack: str,
    team_qa_size: str,
    team_dev_size: str,
    timeline: str,
    methodology: str,
    known_risks: str,
    existing_automation: str,
    compliance_requirements: str,
    additional_context: str = "",
) -> dict:
    """Deterministic QA effort estimate (PERT + complexity multipliers + team
    capacity + confidence score) — no LLM narrative; write your own from these
    numbers. Fields mirror the app's project-intake dialogue and are validated
    with the same rules; a validation failure returns
    {"error": "validation", "fields": {field: message}}, never a crash.
    Success returns the full EstimationData as JSON (baseline, multipliers,
    pert_activities, capacity, risk_buffer_days, final_effort_min/max,
    confidence_level/confidence_score)."""
    start = time.monotonic()
    raw = {
        "project_name": project_name,
        "project_description": project_description,
        "project_type": project_type,
        "tech_stack": tech_stack,
        "team_qa_size": team_qa_size,
        "team_dev_size": team_dev_size,
        "timeline": timeline,
        "methodology": methodology,
        "known_risks": known_risks,
        "existing_automation": existing_automation,
        "compliance_requirements": compliance_requirements,
    }

    validator = InputValidator()
    field_errors: dict[str, str] = {}
    cleaned: dict[str, str] = {}
    for field in _REQUIRED_FIELDS:
        result = validator.validate(field, raw[field])
        if not result.valid:
            field_errors[field] = result.error
        else:
            cleaned[field] = result.cleaned

    additional_result = validator.validate_additional_context(additional_context)
    if not additional_result.valid:
        field_errors["additional_context"] = additional_result.error

    if field_errors:
        duration_ms = (time.monotonic() - start) * 1000
        telemetry.track_tool_called("estimate_qa_effort", success=False, duration_ms=duration_ms)
        return {"error": "validation", "fields": field_errors}

    context = ProjectContext(
        additional_context=additional_result.cleaned,
        **cleaned,
    )
    data = compute_estimation(context)
    result = asdict(data)
    # multipliers is a list of (reason, pct) tuples — dataclasses.asdict() leaves
    # tuples as tuples, which json.dumps renders as arrays anyway, but the MCP
    # SDK's schema validation expects genuine JSON-safe types; normalize explicitly.
    result["multipliers"] = [list(m) for m in result["multipliers"]]

    duration_ms = (time.monotonic() - start) * 1000
    telemetry.track_tool_called("estimate_qa_effort", success=True, duration_ms=duration_ms)
    return result


# ── Prompts ───────────────────────────────────────────────────────────────────────
# Structural templates extracted from the app's own document generators (src/prompts.py)
# — see MCP_PLAN.md section 1: this server never generates documents itself, so these
# are guidance for the CLIENT to follow, grounded via retrieve_qa_knowledge/
# estimate_qa_effort rather than a second internal LLM call.

@mcp.prompt()
def qa_project_interview() -> str:
    """The 11-question project-intake interview to run before any QA deliverable."""
    return _qa_project_interview()


@mcp.prompt()
def risk_register_structure() -> str:
    """The Risk Register document structure and grounding instructions."""
    return _risk_register_structure()


@mcp.prompt()
def test_strategy_structure() -> str:
    """The Test Strategy document structure and grounding instructions."""
    return _test_strategy_structure()


@mcp.prompt()
def test_plan_structure() -> str:
    """The IEEE-829-aligned Test Plan document structure and grounding instructions."""
    return _test_plan_structure()


def main() -> None:
    telemetry.track_server_start()
    try:
        _get_index()  # fail-fast: a server with no usable KB index is useless
    except Exception as exc:
        print(f"FATAL: could not build the knowledge base index: {exc}", file=sys.stderr)
        raise SystemExit(1)
    mcp.run()


if __name__ == "__main__":
    main()
