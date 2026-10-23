"""
QAI Consultant — MCP server (v3.0 MVP).

Local stdio transport, fully keyless: no Pinecone, no Mistral/OpenRouter,
no Streamlit. See MCP_PLAN.md section 1 ("the MCP lens") for why: the
client LLM (Claude Code, Claude Desktop, claude.ai) is stronger than this
project's internal mistral-small, so this server never generates text —
it exposes what the client cannot do alone: standards-grounded knowledge
retrieval (retrieve_qa_knowledge, list_kb_sources), deterministic QA
effort estimation (estimate_qa_effort), deterministic QA document review
(review_qa_document), deterministic test-results health analysis
(analyze_test_results), and deterministic QA process maturity assessment
(assess_qa_maturity), plus MCP prompts (the 11-question interview +
document structures, src/qai_consultant/mcp/prompts.py) that instruct the client to ground
its own generation in those tools rather than call a second LLM.

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
import re
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Optional, Union


from mcp.server.fastmcp import FastMCP

from qai_consultant.core import maturity_core
from qai_consultant.core import results_core
from qai_consultant.core import review_core
from qai_consultant.common import telemetry
from qai_consultant.core.dialogue import InputValidator, ProjectContext
from qai_consultant.core import effort_core
from qai_consultant.core.effort_core import compute_estimation
from qai_consultant.mcp.local_index import LocalIndex
from qai_consultant.mcp.prompts import (
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
    "analyze_test_results for flaky/ever-failing/slowest/failure-cluster "
    "metrics from JUnit XML or CSV, and assess_qa_maturity for a TMMi/EU AI "
    "Act indicative maturity assessment from a free-text project/process "
    "description — in every case, write your own narrative around the "
    "deterministic numbers/findings returned."
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

# Calibrated against the real index (all-MiniLM-L6-v2, 2026-10): off-topic or
# gibberish queries score 0.11-0.34 ("how to cook pasta carbonara" 0.17,
# "asdfgh qwerty zxcv" 0.34, "python list comprehension" 0.30, "what is boundary
# value analysis" 0.34 - a topic the Markdown-only index genuinely lacks), while
# on-topic queries land at 0.45-0.75 ("risk-based testing" 0.75, "exploratory
# testing charter" 0.68, "OWASP top 10 injection" 0.61).
DEFAULT_MIN_SCORE = 0.40

# Tool-boundary input cap for free-text/document arguments (characters).
MAX_INPUT_CHARS = 200_000

# review_qa_document / assess_qa_maturity citation policy (F11).
_CITATION_MIN_SCORE = 0.45
_AI_REGULATION_RE = re.compile(
    r"\b(?:AI|A\.I\.|artificial intelligence|machine[- ]learning|LLMs?|GPT|generative|"
    r"EU AI Act|AI Act|regulat\w*|GDPR|high-risk)\b",
    re.IGNORECASE,
)


def _too_long(name: str, value: Optional[str]) -> Optional[dict]:
    """Structured invalid_argument error for an over-long text argument, else None."""
    if isinstance(value, str) and len(value) > MAX_INPUT_CHARS:
        return {
            "error": "invalid_argument",
            "message": f"{name} is {len(value)} characters; the limit is {MAX_INPUT_CHARS}.",
            "max_chars": MAX_INPUT_CHARS,
        }
    return None


def _resolve_citations(index, queries, *, allow_regulation: bool) -> list[dict]:
    """KB citations for a finding's citation_queries: only chunks scoring at
    least _CITATION_MIN_SCORE, regulation (EU AI Act) sources only when
    allow_regulation is True, one entry per source (best score)."""
    best: dict[str, dict] = {}
    for query in queries:
        search_result = index.search(query, k=3, min_score=_CITATION_MIN_SCORE)
        if "error" in search_result:
            continue
        for c in search_result["chunks"]:
            if not allow_regulation and "eu_ai_act" in c["source"].lower():
                continue
            entry = {"source": c["source"], "category": c["category"], "score": c["score"]}
            if c["source"] not in best or entry["score"] > best[c["source"]]["score"]:
                best[c["source"]] = entry
    return sorted(best.values(), key=lambda e: e["score"], reverse=True)


@mcp.tool()
def retrieve_qa_knowledge(
    query: str,
    category: Optional[str] = None,
    k: int = 5,
    min_score: float = 0.40,  # literal (keep == DEFAULT_MIN_SCORE; tests/system/release/test_skill_doc.py parses it)
) -> dict:
    """Retrieve grounding chunks from the local QA knowledge base (Markdown
    guides: testing methodologies, IEEE/ISO/OWASP Markdown standards,
    audit/evaluation frameworks, AI-SDLC case studies, the EU AI Act). NOT
    included: the ISTQB and OWASP PDF syllabi (licensing) - so fundamentals
    such as test design techniques (boundary value analysis), smoke vs sanity
    or test levels are often absent; the first call after server start may take
    ~30s while the index builds (usually done in the background by then).
    Returns {"chunks": [{"source", "category", "text", "score", "match"}],
    "kb_version", "best_score", "low_relevance"[, "note"][, "warnings"]}; "match" is
    strong (score >=0.55 AND the chunk contains most of the query's content terms),
    moderate (>=0.40) or weak, and when even the best chunk is
    not strong a note says to use only chunks that really answer the question
    (a 0.45 hit on an unrelated case study is vocabulary overlap). A query that
    names a source the KB does not ship (e.g. ISTQB) gets a note saying so;
    an out-of-range k is clamped and reported in "warnings". Chunks scoring below min_score
    (cosine similarity, default 0.40, 0 disables) are dropped; if nothing
    reaches it, chunks is empty, low_relevance is true and note says so - then
    answer from your own knowledge and tell the user the KB had no match
    (best_score shows how close the best miss was). Near-duplicate overlapping
    chunks of one document are collapsed. category, if given, must be one of:
    Standard, Methodology, Article, Expert Knowledge, Audit/Evaluation; an
    empty query, an unrecognized category or an out-of-range min_score returns
    a structured {"error": "invalid_argument", ...} rather than raising. k is
    clamped to [1, 20]."""
    start = time.monotonic()
    too_long = _too_long("query", query)
    if too_long is not None:
        telemetry.track_tool_called("retrieve_qa_knowledge", success=False, duration_ms=0.0)
        return too_long
    result = _get_index().search(query, category=category, k=k, min_score=min_score)
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
    project_name: str = "",
    project_description: str = "",
    project_type: str = "",
    tech_stack: str = "",
    team_qa_size: str = "",
    team_dev_size: str = "",
    timeline: str = "",
    methodology: str = "",
    known_risks: str = "",
    existing_automation: str = "",
    compliance_requirements: str = "",
    additional_context: str = "",
) -> dict:
    """Deterministic QA effort estimate (PERT + complexity multipliers + team
    capacity + confidence score) — no LLM narrative; write your own from these
    numbers. Fields mirror the app's project-intake dialogue and are validated
    with the same rules; a validation failure returns
    {"error": "validation", "fields": {field: message}}, never a crash; all eleven
    fields are needed, and a missing or empty one is reported by name in that same shape
    Success returns the full EstimationData as JSON (baseline, multipliers,
    pert_activities, capacity, risk_buffer_days, final_effort_min/max,
    confidence_level/confidence_score, confidence_note, data_quality_score out
    of data_quality_max=20). Negative team sizes and negative or zero timelines
    are rejected with a validation error; decimal team sizes ("2.5") are
    rounded half up to a whole headcount with a warning. capacity_gap =
    available_person_days - pert_total_expected, so POSITIVE is a surplus and
    NEGATIVE a deficit; capacity_status ("surplus"/"deficit"/"balanced") and
    capacity_note state this unambiguously. methodology_note is set only when
    the methodology does not change the numbers (it is then a label only)."""
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
        if not (raw[field] or "").strip():
            field_errors[field] = f"{field} is required (missing or empty)."
            continue
        result = validator.validate(field, raw[field])
        if not result.valid:
            field_errors[field] = result.error
        else:
            cleaned[field] = result.cleaned

    additional_result = validator.validate_additional_context(additional_context)
    if not additional_result.valid:
        field_errors["additional_context"] = additional_result.error

    # Negative team sizes / negative or zero durations are rejected, not guessed.
    for numeric_field, message in effort_core.validate_numeric_inputs(
        raw["team_qa_size"], raw["team_dev_size"], raw["timeline"],
    ).items():
        field_errors.setdefault(numeric_field, message)

    if field_errors:
        duration_ms = (time.monotonic() - start) * 1000
        telemetry.track_tool_called("estimate_qa_effort", success=False, duration_ms=duration_ms)
        return {"error": "validation", "fields": field_errors}

    context = ProjectContext(
        additional_context=additional_result.cleaned,
        **cleaned,
    )
    data = compute_estimation(context)
    estimation_result = asdict(data)
    # multipliers is a list of (reason, pct) tuples — dataclasses.asdict() leaves
    # tuples as tuples, which json.dumps renders as arrays anyway, but the MCP
    # SDK's schema validation expects genuine JSON-safe types; normalize explicitly.
    estimation_result["multipliers"] = [list(m) for m in estimation_result["multipliers"]]

    duration_ms = (time.monotonic() - start) * 1000
    telemetry.track_tool_called("estimate_qa_effort", success=True, duration_ms=duration_ms)
    return estimation_result


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
    with overall_score=0 rather than an error, unless they carry an explicit QA
    signal (test plan/strategy/case wording, "Test N:" lines) and enough words
    to score — those get a (low) score with findings. In "auto" mode a weak
    but genuine QA document (a QA signal plus a core testing term) is scored as
    its most likely type instead of being rejected. Rejections carry a `hint`
    telling you to retry with an explicit doc_type. Each finding carries
    kb_citations resolved from the knowledge base for its citation queries —
    a finding with no resolvable source is returned with an empty
    kb_citations list rather than a fabricated one. Non-QA input returns status="not_a_qa_document" (doc_type equals the
    status, no score); oversize input returns status="input_too_large". Non-
    English input is still scored but score_reliable=false and language_warning
    explains the rubric is English-keyword based. detection_confidence says how
    sure the "auto" type guess was. Returns {doc_type, overall_score,
    dimension_scores, findings, stats, status, language, language_warning,
    score_reliable, detection_confidence, detection_note, hint, kb_version}."""
    start = time.monotonic()

    if doc_type not in _REVIEW_DOC_TYPES:
        duration_ms = (time.monotonic() - start) * 1000
        telemetry.track_tool_called("review_qa_document", success=False, duration_ms=duration_ms)
        return {
            "error": "invalid_argument",
            "message": f"Unknown doc_type {doc_type!r}.",
            "valid_doc_types": list(_REVIEW_DOC_TYPES),
        }

    too_long = _too_long("document_text", document_text)
    if too_long is not None:
        telemetry.track_tool_called("review_qa_document", success=False, duration_ms=0.0)
        return too_long

    result = review_core.review_document(document_text, doc_type=doc_type)
    index = _get_index()

    # EU AI Act chunks are only cited for documents that are themselves about
    # AI/regulation - generic findings ("no stated objectives") must not cite them.
    allow_regulation = bool(_AI_REGULATION_RE.search(document_text or ""))
    findings = []
    for finding in result.findings:
        kb_citations = _resolve_citations(
            index, finding.citation_queries, allow_regulation=allow_regulation,
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
        "status": result.status,
        "language": result.language,
        "language_warning": result.language_warning,
        "score_reliable": result.score_reliable,
        "detection_confidence": result.detection_confidence,
        "detection_note": result.detection_note,
        "hint": result.hint,
        "kb_version": index.kb_version,
    }


# ── Tool: assess_qa_maturity ──────────────────────────────────────────────────

@mcp.tool()
def assess_qa_maturity(project_description: str) -> dict:
    """Deterministically assess QA process maturity from a free-text project/
    process description (or a pasted existing Test Strategy/Risk Register) —
    no LLM anywhere in this call path; write your own narrative from the
    returned findings. Scores 10 TMMi process areas (Level 2 Managed + Level 3
    Defined) and returns an indicative_tmmi_level (1-3 — NEVER higher; Levels
    4-5 require quantitative evidence a text description cannot substantiate,
    per TMMi's own no-skip rule — always read the returned `disclaimer` and
    never claim a certified TMMi level yourself). When the description signals
    an AI/ML system, also scores 7 EU AI Act Articles 9-15 readiness checks
    (ai_act_relevant=true, ai_act_dimension_scores populated); otherwise that
    dimension is omitted entirely (ai_act_relevant=false, empty dict) rather
    than scored as a false gap. Descriptions under ~200 characters (after
    stripping this app's own AI-disclosure front matter/footer) return
    indicative_tmmi_level=0 with empty findings rather than an error
    (status="insufficient_content"). Input with essentially no software-
    testing/QA vocabulary (a recipe, meeting notes) returns
    status="not_a_qa_description" with indicative_tmmi_level=null, a message
    and no findings; a successful assessment has status="ok". Mentions of AI
    that are negated ("no machine learning is used", "AI-free") do not switch
    the EU AI Act dimension on. Each
    finding carries kb_citations resolved from the knowledge base for its
    citation queries — a finding with no resolvable source is returned with
    an empty kb_citations list rather than a fabricated one. When
    ai_act_relevant=true, ai_act_note carries a fixed caveat that risk-tier
    classification (whether the system is legally "high-risk") is a
    determination this tool does not make — the user/team must confirm
    that independently; ai_act_note is empty when ai_act_relevant=false.
    Returns {status, indicative_tmmi_level, tmmi_dimension_scores, ai_act_relevant,
    ai_act_dimension_scores, ai_act_note, findings, disclaimer,
    detection_caveat, language, language_warning, score_reliable,
    keyword_list_warning, stats, kb_version}. Detection is keyword-based and
    can under-score paraphrased practices (see detection_caveat); non-English
    input sets score_reliable=false."""
    start = time.monotonic()

    too_long = _too_long("project_description", project_description)
    if too_long is not None:
        telemetry.track_tool_called("assess_qa_maturity", success=False, duration_ms=0.0)
        return too_long

    result = maturity_core.assess_maturity(project_description)
    index = _get_index()

    if result.status == maturity_core.STATUS_NOT_QA:
        telemetry.track_tool_called(
            "assess_qa_maturity", success=True,
            duration_ms=(time.monotonic() - start) * 1000,
            extra={"status": result.status},
        )
        return {
            "status": result.status,
            "indicative_tmmi_level": None,
            "message": (
                "The input does not look like a description of software testing or "
                "QA practice (too few testing/QA/process terms), so no TMMi level "
                "or findings were produced. Describe how the team plans, designs, "
                "executes and tracks tests, then call this tool again."
            ),
            "findings": [],
            "tmmi_dimension_scores": {},
            "ai_act_relevant": False,
            "ai_act_dimension_scores": {},
            "ai_act_note": "",
            "disclaimer": result.disclaimer,
            "detection_caveat": result.detection_caveat,
            "language": result.language,
            "language_warning": result.language_warning,
            # Same key set as a scored result so clients indexing these keys never fail; nothing was scored.
            "score_reliable": False,
            "keyword_list_warning": result.keyword_list_warning,
            "stats": result.stats,
            "kb_version": index.kb_version,
        }

    findings = []
    for finding in result.findings:
        kb_citations = _resolve_citations(
            index, finding.citation_queries,
            allow_regulation=bool(result.ai_act_relevant) or finding.framework == "eu_ai_act",
        )
        findings.append({
            "framework": finding.framework,
            "dimension": finding.dimension,
            "level": finding.level,
            "severity": finding.severity,
            "message": finding.message,
            "evidence": finding.evidence,
            "kb_citations": kb_citations,
        })

    duration_ms = (time.monotonic() - start) * 1000
    telemetry.track_tool_called(
        "assess_qa_maturity", success=True, duration_ms=duration_ms,
        extra={
            "indicative_tmmi_level": result.indicative_tmmi_level,
            "ai_act_relevant": result.ai_act_relevant,
            "finding_count": len(findings),
        },
    )

    return {
        "status": result.status,
        "indicative_tmmi_level": result.indicative_tmmi_level,
        "tmmi_dimension_scores": result.tmmi_dimension_scores,
        "ai_act_relevant": result.ai_act_relevant,
        "ai_act_dimension_scores": result.ai_act_dimension_scores,
        "ai_act_note": result.ai_act_note,
        "findings": findings,
        "disclaimer": result.disclaimer,
        "detection_caveat": result.detection_caveat,
        "language": result.language,
        "language_warning": result.language_warning,
        "score_reliable": result.score_reliable,
        "keyword_list_warning": result.keyword_list_warning,
        "stats": result.stats,
        "kb_version": index.kb_version,
    }


# ── Tool: analyze_test_results ───────────────────────────────────────────────────

_MAX_RESULTS_INPUT_BYTES = 10 * 1024 * 1024  # 10 MB — plan section 3.3 clamp (real JUnit reports are far larger than prose documents, so this tool is not held to MAX_INPUT_CHARS)
_MAX_RESULTS_EXECUTIONS = 500_000            # plan section 3.3 clamp
_MAX_RUN_ENTRIES = 1_000
_MAX_REFERENCE_TESTS = 50_000


def _entry_xml_bytes(entry) -> int:
    raw = entry if isinstance(entry, str) else (entry.get("xml", "") if isinstance(entry, dict) else "")
    return len(str(raw).encode("utf-8", errors="ignore"))


def _records_from_run_entries(entries) -> tuple:
    """Parse a list of {"run_id", "xml"} dicts (or plain XML strings, which get
    run ids run-1, run-2, ... by position) into (TestRecords, warnings),
    skipping (with a warning, never raising) any malformed entry. A repeated
    run_id is made unique with a "#2", "#3" suffix (never silently merged into
    one run) and reported in a warning."""
    records = []
    warnings = []
    seen: dict = {}
    duplicated: list = []
    for index, entry in enumerate(entries, start=1):
        if isinstance(entry, str):
            run_id, xml = f"run-{index}", entry
        elif isinstance(entry, dict) and "run_id" in entry and "xml" in entry:
            run_id, xml = str(entry["run_id"]), str(entry["xml"])
        else:
            warnings.append(
                "Skipped a malformed run entry (expected an XML string or an object with run_id and xml)."
            )
            continue
        if run_id in seen:
            original = run_id
            if original not in duplicated:
                duplicated.append(original)
            while run_id in seen:  # never reuse an id the caller supplied (e.g. their own "a#2")
                seen[original] += 1
                run_id = f"{original}#{seen[original]}"
        seen.setdefault(run_id, 1)
        run_records, run_warnings = results_core.parse_junit_xml_detailed(xml, run_id)
        records.extend(run_records)
        warnings.extend(run_warnings)
    if duplicated:
        warnings.append(
            "Duplicate run_id(s) " + ", ".join(repr(d) for d in duplicated[:10])
            + ": each repeat was kept as a separate run with a '#2', '#3' ... suffix instead of being "
            "merged into one run. Use distinct run_ids if these are different executions."
        )
    return records, warnings


def _valid_fraction(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and 0.0 <= value <= 1.0


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
    (or simply a JSON array of XML strings, auto-named run-1, run-2, ...;
    repeated run_ids are kept as separate runs with a #2/#3 suffix and a
    warning) instead — either as a genuine JSON array/list argument, or as a string
    starting with "[" (some MCP clients stringify array arguments; both
    forms are accepted). csv_text needs a test-name column (name | test_name
    | test | testcase | title) and a status column (status | result |
    outcome); headers are matched case-insensitively. Status synonyms are
    accepted (pass/ok/success, fail/failure/ko, error/err,
    skip/ignored/pending). Optional columns: classname (or suite), run_id
    (or run/build; default "csv"), duration_s (or duration/time/elapsed, in
    seconds; a *_ms header or "350ms" values mean milliseconds), message
    (or error/details). Dropped rows and unrecognised columns are listed in
    `warnings`. If NO test could be parsed (wrong columns, empty or
    header-only CSV, HTML or non-JUnit XML, malformed XML) the call returns
    {"error": "no_tests_found", "message", "warnings"} instead of an empty
    0% result. reference_tests, if given, is a list of test identities
    ("classname::name", or just "name" when there is no classname) expected
    to have run — any absent from the results are reported under never_run. A
    bare "name" also matches when exactly one executed test has that name
    (ambiguous bare names are not guessed; a warning explains).
    Skipped tests are NOT failures: they are excluded from pass rates and from
    the flaky/ever-failing verdicts and are reported separately (skipped,
    skipped_executions). Flaky = pass_rate (over non-skipped executions)
    strictly between flaky_min and flaky_max with at least 3 such executions;
    ever-failing = zero passes across at least 3 non-skipped executions.
    flaky_min/flaky_max must satisfy 0 <= flaky_min < flaky_max <= 1. Tests
    with fewer executions are left out of both lists; with fewer than 3 runs a
    warning says so, and tests that both passed and failed are listed under
    mixed_outcome (needs more runs). An empty flaky list on 1-2 runs means not
    enough data, not a stable suite. Malformed/oversized input never raises — it returns
    a structured {"error": "invalid_argument" | "no_tests_found", ...}.
    Returns the full ResultsAnalysis as JSON (runs, total_tests, executions,
    overall_pass_rate, flaky, ever_failing, never_run, slowest,
    failure_clusters, per_run, warnings, skipped_executions, skipped,
    mixed_outcome)."""
    start = time.monotonic()

    def _fail(message: str, error: str = "invalid_argument", **extra) -> dict:
        duration_ms = (time.monotonic() - start) * 1000
        telemetry.track_tool_called("analyze_test_results", success=False, duration_ms=duration_ms)
        return {"error": error, "message": message, **extra}

    provided = [v for v in (junit_xml, csv_text) if v is not None]
    if len(provided) != 1:
        return _fail("Provide exactly one of junit_xml or csv_text.")

    if not _valid_fraction(flaky_min) or not _valid_fraction(flaky_max):
        return _fail("flaky_min and flaky_max must be numbers between 0 and 1.")
    if flaky_min >= flaky_max:
        return _fail(
            f"flaky_min ({flaky_min}) must be smaller than flaky_max ({flaky_max}); "
            "the flaky band is the open interval between them.",
        )
    if reference_tests is not None and len(reference_tests) > _MAX_REFERENCE_TESTS:
        return _fail(f"reference_tests exceeds the {_MAX_REFERENCE_TESTS}-entry limit.")

    parse_warnings: list = []

    if isinstance(junit_xml, list):
        if len(junit_xml) > _MAX_RUN_ENTRIES:
            return _fail(f"junit_xml has more than {_MAX_RUN_ENTRIES} run entries.")
        total_bytes = sum(_entry_xml_bytes(e) for e in junit_xml)
        if total_bytes > _MAX_RESULTS_INPUT_BYTES:
            return _fail(f"Input exceeds the {_MAX_RESULTS_INPUT_BYTES}-byte limit.")
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
                    '{"run_id", "xml"} objects or of XML strings.'
                )
            if len(parsed) > _MAX_RUN_ENTRIES:
                return _fail(f"junit_xml has more than {_MAX_RUN_ENTRIES} run entries.")
            records, parse_warnings = _records_from_run_entries(parsed)
        else:
            records, parse_warnings = results_core.parse_junit_xml_detailed(junit_xml, "run1")
    else:
        # Reached only when junit_xml is None; the `len(provided) != 1` guard
        # above already ensured exactly one of junit_xml/csv_text is non-None.
        assert csv_text is not None
        if len(csv_text.encode("utf-8", errors="ignore")) > _MAX_RESULTS_INPUT_BYTES:
            return _fail(f"Input exceeds the {_MAX_RESULTS_INPUT_BYTES}-byte limit.")
        records, parse_warnings = results_core.parse_results_csv_detailed(csv_text)

    if not records:
        reason = parse_warnings[0] if parse_warnings else "No test results could be parsed from the input."
        return _fail(
            "No test results could be parsed from the input. " + reason,
            error="no_tests_found", warnings=parse_warnings,
        )

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
# Structural templates extracted from the app's own document generators (src/qai_consultant/mcp/prompts.py)
# — see MCP_PLAN.md section 1: this server never generates documents itself, so these
# are guidance for the CLIENT to follow, grounded via retrieve_qa_knowledge/
# estimate_qa_effort rather than a second internal LLM call.

@mcp.prompt()
def qa_project_interview() -> str:
    """The 11-question project-intake interview to run before any QA deliverable."""
    return _qa_project_interview()


@mcp.prompt()
def risk_register_structure(project_name: str = "") -> str:
    """The Risk Register document structure and grounding instructions (optional project_name fills the title)."""
    return _risk_register_structure(project_name)


@mcp.prompt()
def test_strategy_structure(project_name: str = "") -> str:
    """The Test Strategy document structure and grounding instructions (optional project_name fills the title)."""
    return _test_strategy_structure(project_name)


@mcp.prompt()
def test_plan_structure(project_name: str = "") -> str:
    """The IEEE-829-aligned Test Plan document structure and grounding instructions (optional project_name fills the title)."""
    return _test_plan_structure(project_name)


def main() -> None:
    telemetry.print_startup_notice()
    telemetry.track_server_start()
    try:
        index = _get_index()
        # Force the FIRST real embedding-model inference (constructing the
        # embedding backend + one embed_query() call — native runtime thread
        # and DLL init) to happen here, on the main thread, before mcp.run()
        # starts stdio_server()'s concurrent stdin-reader task. Deferring this
        # to the first retrieve_qa_knowledge call (which FastMCP dispatches to
        # an anyio worker thread) deadlocks on Windows: that worker thread's
        # native thread creation races the stdin-reader thread's blocking
        # ReadFile() on the piped stdin for the process loader lock, and
        # neither ever proceeds. Originally found with torch/MKL (v3.0/v3.0.1
        # E2E test, hanging indefinitely on the second tool call); the hazard
        # is about ANY native runtime's first init, not torch specifically —
        # re-verified against fastembed's onnxruntime backend via
        # scripts/verify_mcp_stdio_no_deadlock.py (Task 4 of the 2026-09-17
        # embedding-backend-simplification plan) before this backend switch shipped.
        #
        # Deliberately NOT a full index build (that used to be bundled into
        # this same call via search("warmup", k=1), which forced embedding
        # the entire KB corpus here too — v3.1.6 found this made cold-start
        # exceed real clients' initialize handshake timeout, e.g. Claude
        # Desktop's ~60s, since the server can't respond to `initialize`
        # until mcp.run() starts). warmup_embedder() only forces the
        # one-time native init; LocalIndex._ensure_built() defers the slow
        # full-corpus embed_documents() call to the first real search()/
        # list_sources() call. That's safe from the same deadlock because
        # the loader-lock race is specifically about the native runtime's
        # *first* initialization, not about ordinary calls into an
        # already-initialized one from a different thread afterward.
        #
        # Trade-off: this no longer fails fast on a corrupted/unreadable KB
        # file (only caught lazily on the first real tool call) — accepted,
        # since the shipped KB is package content, not user-editable, and
        # the far more common startup failure (no network / HF Hub down /
        # disk full for the model cache) still fails fast here.
        index.warmup_embedder()
    except Exception as exc:
        print(f"FATAL: could not initialize the embedding model: {exc}", file=sys.stderr)
        raise SystemExit(1)
    # Pre-build the corpus index on a daemon thread so the first real tool call
    # doesn't pay ~30s. Safe w.r.t. the deadlock above: the native runtime's
    # first init already happened on this thread (warmup_embedder), and a
    # later call from another thread is exactly what FastMCP's worker threads
    # do anyway. Non-blocking: mcp.run() starts immediately; a tool call that
    # arrives mid-build waits on LocalIndex's build lock instead of rebuilding.
    # Best-effort: a failure here is retried lazily by the first real call.
    try:
        index.start_background_build()
    except Exception:
        pass
    mcp.run()


if __name__ == "__main__":
    main()
