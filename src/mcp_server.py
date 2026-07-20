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

import json
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Optional, Union

sys.path.insert(0, str(Path(__file__).resolve().parent))  # `python src/mcp_server.py` direct-run support

from mcp.server.fastmcp import FastMCP

import results_core
import review_core
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
    "IEEE, ISO, EU AI Act), deterministic QA effort estimation, deterministic QA "
    "document quality review, and deterministic test-results health analysis. "
    "This server never generates documents — call retrieve_qa_knowledge to "
    "ground your own analysis in the knowledge base, estimate_qa_effort for a "
    "deterministic PERT-based effort calculation, review_qa_document for a "
    "rubric-scored review of an existing Test Plan/Strategy/test case list, "
    "and analyze_test_results for flaky/ever-failing/slowest/failure-cluster "
    "metrics from JUnit XML or CSV — in every case, write your own narrative "
    "around the deterministic numbers/findings returned."
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


# ── Tool: review_qa_document ─────────────────────────────────────────────────────

_REVIEW_DOC_TYPES = ("auto",) + review_core.DOC_TYPES


def _score_bucket(score: int) -> str:
    """Fixed small enum for telemetry — never the raw score."""
    if score >= 80:
        return "80-100"
    if score >= 60:
        return "60-79"
    if score >= 40:
        return "40-59"
    if score >= 20:
        return "20-39"
    return "0-19"


@mcp.tool()
def review_qa_document(document_text: str, doc_type: str = "auto") -> dict:
    """Deterministically review an existing QA document (Test Plan, Test
    Strategy, or a test case list) against a six-dimension ISTQB/IEEE-829-
    grounded rubric (structure completeness, objectives & scope clarity,
    entry/exit criteria, traceability, measurability, risk coverage) — no
    LLM anywhere in this call path; write your own narrative from the
    returned findings. doc_type must be one of "auto", "test_plan",
    "test_strategy", "test_cases" — "auto" runs a cheap heading-keyword
    classifier and reports which type it assumed; an unrecognized value
    returns a structured {"error": "invalid_argument", ...} rather than
    raising. Documents under ~200 characters (after stripping this app's own
    AI-disclosure front matter/footer) return doc_type="insufficient_content"
    with overall_score=0 rather than an error. Each finding carries
    kb_citations resolved from the knowledge base for its citation queries —
    a finding with no resolvable source is returned with an empty
    kb_citations list rather than a fabricated one. Returns {doc_type,
    overall_score, dimension_scores, findings, stats, kb_version}."""
    start = time.monotonic()

    if doc_type not in _REVIEW_DOC_TYPES:
        duration_ms = (time.monotonic() - start) * 1000
        telemetry.track_tool_called("review_qa_document", success=False, duration_ms=duration_ms)
        return {
            "error": "invalid_argument",
            "message": f"Unknown doc_type {doc_type!r}.",
            "valid_doc_types": list(_REVIEW_DOC_TYPES),
        }

    result = review_core.review_document(document_text, doc_type=doc_type)
    index = _get_index()

    findings = []
    for finding in result.findings:
        kb_citations = []
        for query in finding.citation_queries:
            search_result = index.search(query, k=2)
            if "error" not in search_result:
                kb_citations.extend(
                    {"source": c["source"], "category": c["category"], "score": c["score"]}
                    for c in search_result["chunks"]
                )
        findings.append({
            "dimension": finding.dimension,
            "severity": finding.severity,
            "message": finding.message,
            "evidence": finding.evidence,
            "kb_citations": kb_citations,
        })

    duration_ms = (time.monotonic() - start) * 1000
    telemetry.track_tool_called(
        "review_qa_document", success=True, duration_ms=duration_ms,
        extra={
            "doc_type": result.doc_type,
            "score_bucket": _score_bucket(result.overall_score),
            "finding_count": len(findings),
        },
    )

    return {
        "doc_type": result.doc_type,
        "overall_score": result.overall_score,
        "dimension_scores": result.dimension_scores,
        "findings": findings,
        "stats": result.stats,
        "kb_version": index.kb_version,
    }


# ── Tool: analyze_test_results ───────────────────────────────────────────────────

_MAX_RESULTS_INPUT_BYTES = 10 * 1024 * 1024  # 10 MB — plan section 3.3 clamp
_MAX_RESULTS_EXECUTIONS = 500_000            # plan section 3.3 clamp


def _records_from_run_entries(entries) -> tuple:
    """Parse a list of {"run_id", "xml"} dicts into TestRecords, skipping
    (with a warning, never raising) any malformed entry."""
    records = []
    warnings = []
    for entry in entries:
        if not isinstance(entry, dict) or "run_id" not in entry or "xml" not in entry:
            warnings.append("Skipped a malformed run entry (missing run_id/xml).")
            continue
        records.extend(results_core.parse_junit_xml(str(entry["xml"]), str(entry["run_id"])))
    return records, warnings


@mcp.tool()
def analyze_test_results(
    junit_xml: Optional[Union[str, list]] = None,
    csv_text: Optional[str] = None,
    reference_tests: Optional[list[str]] = None,
    flaky_min: float = 0.2,
    flaky_max: float = 0.8,
) -> dict:
    """Deterministic test-results health metrics (flaky / ever-failing /
    never-run / slowest / failure clustering) from real test execution
    data — no LLM anywhere in this call path; write your own narrative
    from the returned numbers. Provide exactly one of junit_xml or
    csv_text. junit_xml is normally one JUnit XML report string for one
    run (accepts both a <testsuites> and a bare <testsuite> root); to
    analyze flakiness across MULTIPLE runs in one call, pass a JSON array
    of {"run_id": "...", "xml": "<testsuites>...</testsuites>"} objects
    instead — either as a genuine JSON array/list argument, or as a string
    starting with "[" (some MCP clients stringify array arguments; both
    forms are accepted). csv_text columns: required
    name/classname/status (passed|failed|error|skipped), optional
    run_id/duration_s/message. reference_tests, if given, is a list of
    test identities ("classname::name") expected to have run — any absent
    from the results are reported under never_run. Flaky = pass_rate
    strictly between flaky_min and flaky_max with at least 3 executions;
    fewer executions is reported as insufficient data, not flaky.
    Malformed/oversized input never raises — it returns a structured
    {"error": "invalid_argument", ...}. Returns the full ResultsAnalysis
    as JSON (runs, total_tests, executions, overall_pass_rate, flaky,
    ever_failing, never_run, slowest, failure_clusters, per_run,
    warnings)."""
    start = time.monotonic()

    def _fail(message: str) -> dict:
        duration_ms = (time.monotonic() - start) * 1000
        telemetry.track_tool_called("analyze_test_results", success=False, duration_ms=duration_ms)
        return {"error": "invalid_argument", "message": message}

    provided = [v for v in (junit_xml, csv_text) if v is not None]
    if len(provided) != 1:
        return _fail("Provide exactly one of junit_xml or csv_text.")

    parse_warnings: list = []

    if isinstance(junit_xml, list):
        records, parse_warnings = _records_from_run_entries(junit_xml)
    elif junit_xml is not None:
        if len(junit_xml.encode("utf-8", errors="ignore")) > _MAX_RESULTS_INPUT_BYTES:
            return _fail(f"Input exceeds the {_MAX_RESULTS_INPUT_BYTES}-byte limit.")
        stripped = junit_xml.strip()
        if stripped.startswith("["):
            try:
                parsed = json.loads(stripped)
            except (ValueError, TypeError):
                parsed = None
            if not isinstance(parsed, list):
                return _fail(
                    'junit_xml starting with "[" must be a JSON array of '
                    '{"run_id", "xml"} objects.'
                )
            records, parse_warnings = _records_from_run_entries(parsed)
        else:
            records = results_core.parse_junit_xml(junit_xml, "run1")
    else:
        if len(csv_text.encode("utf-8", errors="ignore")) > _MAX_RESULTS_INPUT_BYTES:
            return _fail(f"Input exceeds the {_MAX_RESULTS_INPUT_BYTES}-byte limit.")
        records = results_core.parse_results_csv(csv_text)

    if len(records) > _MAX_RESULTS_EXECUTIONS:
        return _fail(f"Input exceeds the {_MAX_RESULTS_EXECUTIONS}-execution cap.")

    analysis = results_core.analyze(
        records, reference_tests=reference_tests, flaky_min=flaky_min, flaky_max=flaky_max,
    )
    analysis.warnings.extend(parse_warnings)

    duration_ms = (time.monotonic() - start) * 1000
    telemetry.track_tool_called(
        "analyze_test_results", success=True, duration_ms=duration_ms,
        extra={
            "runs": analysis.runs,
            "executions": analysis.executions,
            "flaky_count": len(analysis.flaky),
        },
    )
    return asdict(analysis)


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
        index = _get_index()  # fail-fast: a server with no usable KB index is useless
        # Force the FIRST real embedding-model inference (constructing
        # HuggingFaceEmbeddings + one encode() call — native torch/MKL thread
        # and DLL init) to happen here, on the main thread, before mcp.run()
        # starts stdio_server()'s concurrent stdin-reader task. Deferring this
        # to the first retrieve_qa_knowledge call (which FastMCP dispatches to
        # an anyio worker thread) deadlocks on Windows: that worker thread's
        # torch/MKL native thread creation races the stdin-reader thread's
        # blocking ReadFile() on the piped stdin for the process loader lock,
        # and neither ever proceeds. Confirmed via a real `uvx qai-consultant-
        # mcp` stdio subprocess (v3.0/v3.0.1 E2E test) hanging indefinitely on
        # the second tool call; a warmup call here — even with a warm on-disk
        # index cache, where list_kb_sources alone never touches the model —
        # eliminates it because the model init lands before stdin_reader()
        # exists as a concurrent task. list_kb_sources() doesn't trigger this
        # (it never calls the embedding model), so this warmup is the only
        # thing standing between a cold-cache-index-but-first-query session
        # and a silent, unrecoverable hang.
        index.search("warmup", k=1)
    except Exception as exc:
        print(f"FATAL: could not build the knowledge base index: {exc}", file=sys.stderr)
        raise SystemExit(1)
    mcp.run()


if __name__ == "__main__":
    main()
