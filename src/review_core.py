"""
QAI Consultant — Deterministic QA Document Quality Review Core (v3.1).

Dependency-free (stdlib only: re, dataclasses) so this module is importable
from the MCP server path (no agent.py/Pinecone/Streamlit in its import
graph) and trivially unit-testable. Same input always yields the same
output — no LLM anywhere in this file.

Rubric: six dimensions, each scored 0-100 from mechanical checks
(regex/keyword matching), overall = weighted mean (weights normalized at
runtime, same defensive pattern as effort_core.pert_breakdown()'s
ACTIVITY_BREAKDOWN normalization). Findings carry `citation_queries`
(plain strings) rather than resolved citations — the MCP layer resolves
them via LocalIndex.search(), the Streamlit layer via Pinecone
retrieve_knowledge(); this module never touches either.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

MIN_CONTENT_CHARS = 200
MAX_INPUT_CHARS = 500_000

DOC_TYPES = ("test_plan", "test_strategy", "test_cases")

# Dimension weight is out of 100 (see WEIGHTS normalization in overall_score()).
WEIGHTS = {
    "structure_completeness": 25,
    "objectives_scope_clarity": 15,
    "entry_exit_criteria": 15,
    "traceability": 15,
    "measurability": 15,
    "risk_coverage": 15,
}

# ── Section checklists per doc_type (used by structure_completeness + the
# cheap doc_type="auto" classifier) — synonym lists, matched as case-
# insensitive substrings anywhere in the document. ──────────────────────────

SECTION_SYNONYMS = {
    "test_plan": {
        "scope": ["scope"],
        "test_items": ["test items", "items to be tested", "items under test"],
        "features_to_be_tested": ["features to be tested", "in scope", "what will be tested"],
        "features_not_to_be_tested": ["features not to be tested", "out of scope", "not to be tested", "will not be tested"],
        "approach": ["approach", "test approach", "testing approach"],
        "pass_fail_criteria": ["pass/fail criteria", "pass / fail criteria", "acceptance criteria"],
        "entry_exit_criteria": ["entry criteria", "exit criteria", "entry/exit criteria"],
        "suspension_resumption": ["suspension criteria", "resumption criteria", "suspension/resumption"],
        "deliverables": ["deliverables", "test deliverables"],
        "schedule": ["schedule", "timeline", "milestones"],
        "risks": ["risk", "risks"],
        "approvals": ["approvals", "sign-off", "sign off", "approval"],
    },
    "test_strategy": {
        "scope": ["scope"],
        "objectives": ["objective", "goals"],
        "test_levels": ["test levels", "test types", "types of testing"],
        "approach": ["approach", "methodology", "test approach"],
        "entry_exit_criteria": ["entry criteria", "exit criteria", "entry/exit criteria"],
        "risks": ["risk", "risks", "risk assessment"],
        "resources": ["resources", "roles and responsibilities", "team"],
        "tools_environment": ["tools", "environment", "test environment"],
        "references": ["references", "standards"],
    },
    "test_cases": {
        "test_case_id": ["test case id", "tc id", "test case"],
        "preconditions": ["precondition", "prerequisite"],
        "steps": ["steps", "test steps", "procedure"],
        "expected_result": ["expected result", "expected outcome"],
        "traceability": ["requirement", "req id", "user story"],
    },
}

_TEST_LEVEL_KEYWORDS = [
    "unit test", "integration test", "system test", "functional test",
    "performance test", "security test", "regression test", "acceptance test",
    "test level", "test type",
]
_VAGUE_EXPECTED_RESULT_PHRASES = [
    "works correctly", "as expected", "should work", "works as intended",
    "functions properly", "works fine", "should function",
]
_METRIC_KEYWORDS = ["defect density", "coverage %", "% coverage", "pass rate", "kpi"]
_REQ_ID_RE = re.compile(r"\b(?:REQ|US|STORY|JIRA)-?\d+\b|\b[A-Z]{2,10}-\d+\b")
_RISK_ID_RE = re.compile(r"\bR\d{1,3}\b")
_MEASURABLE_EXIT_RE = re.compile(r"\d+\s*%|\ball\b[^.\n]{0,40}\bpass\b|coverage\s+(?:of\s+)?\d", re.IGNORECASE)


@dataclass
class ReviewFinding:
    dimension: str
    severity: str                  # "critical" | "major" | "minor"
    message: str                   # human-readable, factual, no LLM
    evidence: str                  # matched text or the name of the missing section
    citation_queries: list = field(default_factory=list)


@dataclass
class ReviewResult:
    doc_type: str                  # resolved type (after auto-detection), or "insufficient_content"
    overall_score: int              # 0-100
    dimension_scores: dict = field(default_factory=dict)
    findings: list = field(default_factory=list)
    stats: dict = field(default_factory=dict)


# ── Input hygiene ──────────────────────────────────────────────────────────────

_FRONT_MATTER_RE = re.compile(r"\A---\n.*?\n---\n?", re.DOTALL)
_AI_FOOTER_RE = re.compile(r"\n\n---\n\n\*.*AI-generated content.*\Z", re.DOTALL)


def _strip_front_matter_and_footer(text: str) -> str:
    """Strip the app's own build_front_matter() YAML block and
    with_ai_footer() disclosure footer, so re-reviewing QAI Consultant's
    own output scores the actual content, not its own AI-disclosure marks."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _FRONT_MATTER_RE.sub("", text, count=1)
    text = _AI_FOOTER_RE.sub("", text)
    return text.strip()


# ── Cheap doc_type classifier ──────────────────────────────────────────────────

def _detect_doc_type(lower_text: str) -> str:
    """Heading-keyword vote across the three checklists; ties default to
    'test_plan' (the most structurally demanding checklist)."""
    votes = {}
    for doc_type, sections in SECTION_SYNONYMS.items():
        count = 0
        for synonyms in sections.values():
            if any(syn in lower_text for syn in synonyms):
                count += 1
        votes[doc_type] = count
    # test_cases has fewer sections total, so bias slightly toward it only
    # when it clearly dominates (its own distinguishing keywords present).
    if any(k in lower_text for k in ["test case id", "tc id", "precondition"]):
        votes["test_cases"] += 2
    best = max(votes, key=lambda k: (votes[k], k == "test_plan"))
    return best


# ── Dimension: structure_completeness ──────────────────────────────────────────

def _structure_completeness(lower_text: str, doc_type: str) -> tuple:
    sections = SECTION_SYNONYMS[doc_type]
    findings = []
    found_count = 0
    for section_key, synonyms in sections.items():
        found = any(syn in lower_text for syn in synonyms)
        if found:
            found_count += 1
        else:
            severity = "critical" if section_key in ("scope", "risks") else "major"
            findings.append(ReviewFinding(
                dimension="structure_completeness",
                severity=severity,
                message=f"Missing expected section: {section_key.replace('_', ' ')}.",
                evidence=section_key,
                citation_queries=[f"IEEE 829 {section_key.replace('_', ' ')}",
                                   f"{doc_type.replace('_', ' ')} {section_key.replace('_', ' ')}"],
            ))
    score = round(100 * found_count / len(sections)) if sections else 0
    return score, findings


# ── Dimension: objectives_scope_clarity ────────────────────────────────────────

def _objectives_scope_clarity(lower_text: str) -> tuple:
    checks = {
        "objectives_stated": any(k in lower_text for k in ["objective", "goal"]),
        "in_scope_signal": any(k in lower_text for k in ["in scope", "will be tested", "included"]),
        "out_of_scope_signal": any(k in lower_text for k in ["out of scope", "will not be tested", "excluded", "not to be tested"]),
        "test_levels_stated": any(k in lower_text for k in _TEST_LEVEL_KEYWORDS),
    }
    findings = []
    if not checks["objectives_stated"]:
        findings.append(ReviewFinding(
            "objectives_scope_clarity", "major",
            "No stated objectives or goals found.", "objectives",
            ["ISTQB test objectives definition"],
        ))
    if not checks["in_scope_signal"]:
        findings.append(ReviewFinding(
            "objectives_scope_clarity", "major",
            "No explicit in-scope statement found.", "in-scope",
            ["IEEE 829 features to be tested"],
        ))
    if not checks["out_of_scope_signal"]:
        findings.append(ReviewFinding(
            "objectives_scope_clarity", "major",
            "No explicit out-of-scope statement found.", "out-of-scope",
            ["IEEE 829 features not to be tested"],
        ))
    if not checks["test_levels_stated"]:
        findings.append(ReviewFinding(
            "objectives_scope_clarity", "minor",
            "No test levels/types (unit, integration, system, ...) mentioned.", "test levels",
            ["ISTQB test levels and types"],
        ))
    score = round(100 * sum(checks.values()) / len(checks))
    return score, findings


# ── Dimension: entry_exit_criteria ─────────────────────────────────────────────

def _entry_exit_criteria(text: str, lower_text: str) -> tuple:
    has_entry = any(k in lower_text for k in ["entry criteria", "entry/exit criteria"])
    has_exit = any(k in lower_text for k in ["exit criteria", "entry/exit criteria", "pass/fail criteria"])
    measurable = bool(_MEASURABLE_EXIT_RE.search(text))

    findings = []
    if not has_entry:
        findings.append(ReviewFinding(
            "entry_exit_criteria", "major",
            "No explicit entry criteria found.", "entry criteria",
            ["IEEE 829 entry criteria"],
        ))
    if not has_exit:
        findings.append(ReviewFinding(
            "entry_exit_criteria", "major",
            "No explicit exit criteria found.", "exit criteria",
            ["IEEE 829 exit criteria"],
        ))
    if not measurable:
        findings.append(ReviewFinding(
            "entry_exit_criteria", "minor",
            "Exit criteria are not measurable (no % / coverage / pass-rate expression found).",
            "measurable exit criteria",
            ["ISTQB measurable exit criteria coverage"],
        ))
    checks = [has_entry, has_exit, measurable]
    score = round(100 * sum(checks) / len(checks))
    return score, findings


# ── Dimension: traceability ─────────────────────────────────────────────────────

def _traceability(text: str, lower_text: str) -> tuple:
    has_req_ids = bool(_REQ_ID_RE.search(text))
    has_risk_refs = bool(_RISK_ID_RE.search(text))
    has_matrix_mention = "traceability" in lower_text

    findings = []
    if not has_req_ids:
        findings.append(ReviewFinding(
            "traceability", "major",
            "No requirement/user-story identifiers (REQ-, US-, ticket-style keys) found.",
            "requirement IDs",
            ["ISTQB traceability requirements to test cases"],
        ))
    if not has_risk_refs:
        findings.append(ReviewFinding(
            "traceability", "minor",
            "No risk-ID references (e.g. R01) found.", "risk references",
            ["risk-based testing traceability"],
        ))
    if not has_matrix_mention:
        findings.append(ReviewFinding(
            "traceability", "minor",
            "No traceability matrix mentioned.", "traceability matrix",
            ["ISTQB traceability matrix"],
        ))
    checks = [has_req_ids, has_risk_refs, has_matrix_mention]
    score = round(100 * sum(checks) / len(checks))
    return score, findings


# ── Dimension: measurability ────────────────────────────────────────────────────

_EXPECTED_STATEMENT_RE = re.compile(r"[^.\n]*expected (?:result|outcome)[^.\n]*", re.IGNORECASE)


def _measurability(text: str, lower_text: str) -> tuple:
    statements = _EXPECTED_STATEMENT_RE.findall(text)
    total = len(statements)
    vague_count = sum(
        1 for s in statements if any(p in s.lower() for p in _VAGUE_EXPECTED_RESULT_PHRASES)
    )
    has_metric_signal = any(k in lower_text for k in _METRIC_KEYWORDS)

    findings = []
    if total == 0:
        findings.append(ReviewFinding(
            "measurability", "major",
            "No 'expected result' statements found at all.", "expected results",
            ["ISTQB measurable expected results"],
        ))
        base_score = 20
    else:
        vague_ratio = vague_count / total
        base_score = round((1 - vague_ratio) * 80)
        if vague_count > 0:
            findings.append(ReviewFinding(
                "measurability", "major" if vague_ratio > 0.5 else "minor",
                f"{vague_count}/{total} expected-result statements are vague "
                f"(e.g. 'works correctly', 'as expected') rather than measurable.",
                "vague expected results",
                ["ISTQB measurable test objectives acceptance criteria"],
            ))

    if not has_metric_signal:
        findings.append(ReviewFinding(
            "measurability", "minor",
            "No concrete quality metrics (defect density, coverage %, pass rate) found.",
            "quality metrics",
            ["ISO/IEC 25010 quality metrics"],
        ))
    score = min(100, base_score + (20 if has_metric_signal else 0))
    return score, findings


# ── Dimension: risk_coverage ────────────────────────────────────────────────────

def _risk_coverage(lower_text: str) -> tuple:
    checks = {
        "risk_section": "risk" in lower_text,
        "severity_markers": any(k in lower_text for k in ["critical", "high", "medium", "low", "priority", "severity", "likelihood"]),
        "mitigation": any(k in lower_text for k in ["mitigation", "mitigate", "contingency"]),
        "risk_based_prioritization": any(k in lower_text for k in ["risk-based", "risk based", "prioritiz"]),
    }
    findings = []
    if not checks["risk_section"]:
        findings.append(ReviewFinding(
            "risk_coverage", "critical",
            "No risk section found at all.", "risk section",
            ["risk-based testing risk register"],
        ))
    if not checks["severity_markers"]:
        findings.append(ReviewFinding(
            "risk_coverage", "major",
            "Risks are not rated by severity/likelihood/priority.", "severity markers",
            ["risk likelihood impact matrix"],
        ))
    if not checks["mitigation"]:
        findings.append(ReviewFinding(
            "risk_coverage", "major",
            "No mitigation/contingency strategy mentioned for risks.", "mitigation",
            ["risk mitigation strategy testing"],
        ))
    if not checks["risk_based_prioritization"]:
        findings.append(ReviewFinding(
            "risk_coverage", "minor",
            "No risk-based prioritization signal found in the approach.", "risk-based prioritization",
            ["risk-based testing prioritization approach"],
        ))
    score = round(100 * sum(checks.values()) / len(checks))
    return score, findings


# ── Orchestrator ───────────────────────────────────────────────────────────────

def review_document(text: str, doc_type: str = "auto") -> ReviewResult:
    """Deterministically review an existing QA document. No LLM anywhere in
    this call path — see the module docstring."""
    raw_len = len(text or "")
    cleaned = _strip_front_matter_and_footer(text or "")
    if len(cleaned) > MAX_INPUT_CHARS:
        cleaned = cleaned[:MAX_INPUT_CHARS]

    if len(cleaned) < MIN_CONTENT_CHARS:
        return ReviewResult(
            doc_type="insufficient_content",
            overall_score=0,
            dimension_scores={},
            findings=[],
            stats={"char_count": len(cleaned), "raw_char_count": raw_len,
                   "reason": f"content is under {MIN_CONTENT_CHARS} characters after cleanup"},
        )

    lower_text = cleaned.lower()

    resolved_doc_type = doc_type
    if doc_type == "auto" or doc_type not in DOC_TYPES:
        resolved_doc_type = _detect_doc_type(lower_text)

    structure_score, structure_findings = _structure_completeness(lower_text, resolved_doc_type)
    scope_score, scope_findings = _objectives_scope_clarity(lower_text)
    entry_exit_score, entry_exit_findings = _entry_exit_criteria(cleaned, lower_text)
    traceability_score, traceability_findings = _traceability(cleaned, lower_text)
    measurability_score, measurability_findings = _measurability(cleaned, lower_text)
    risk_score, risk_findings = _risk_coverage(lower_text)

    dimension_scores = {
        "structure_completeness": structure_score,
        "objectives_scope_clarity": scope_score,
        "entry_exit_criteria": entry_exit_score,
        "traceability": traceability_score,
        "measurability": measurability_score,
        "risk_coverage": risk_score,
    }

    total_weight = sum(WEIGHTS.values())
    overall_score = round(
        sum(dimension_scores[dim] * (WEIGHTS[dim] / total_weight) for dim in dimension_scores)
    )

    findings = (
        structure_findings + scope_findings + entry_exit_findings
        + traceability_findings + measurability_findings + risk_findings
    )

    word_count = len(cleaned.split())
    heading_count = len(re.findall(r"^#{1,6}\s+\S", cleaned, re.MULTILINE))

    return ReviewResult(
        doc_type=resolved_doc_type,
        overall_score=overall_score,
        dimension_scores=dimension_scores,
        findings=findings,
        stats={
            "char_count": len(cleaned),
            "word_count": word_count,
            "heading_count": heading_count,
            "auto_detected": doc_type == "auto" or doc_type not in DOC_TYPES,
        },
    )
