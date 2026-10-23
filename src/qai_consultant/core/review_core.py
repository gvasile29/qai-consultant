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

from qai_consultant.common.text_checks import detect_language, has_qa_signal, looks_like_qa_document

MIN_CONTENT_CHARS = 200
# A shorter text that carries an explicit QA signal (see has_qa_signal) is
# still reviewed, as long as it has at least this many words to score.
MIN_SIGNAL_WORDS = 6
MAX_INPUT_CHARS = 500_000
# Hard cap: above this, review_document() returns status "input_too_large"
# instead of silently truncating and scoring a partial document.
MAX_REVIEW_CHARS = 200_000

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
_MEASURABLE_EXIT_RE = re.compile(r"(?<!\d)\d+[ \t]{0,8}%|\ball\b[^.\n]{0,40}\bpass\b|coverage\s+(?:of\s+)?\d", re.IGNORECASE)


@dataclass
class ReviewFinding:
    dimension: str
    severity: str                  # "critical" | "major" | "minor"
    message: str                   # human-readable, factual, no LLM
    evidence: str                  # matched text or the name of the missing section
    citation_queries: list = field(default_factory=list)


# Weights for the test-case-list rubric. Plan-level criteria (objectives,
# scope, entry/exit criteria, risk coverage) do not apply to a list of test
# cases and are omitted rather than scored as false zeros.
TEST_CASE_WEIGHTS = {
    "structure_completeness": 35,
    "measurability": 30,
    "traceability": 15,
    "test_design_coverage": 20,
}

# Result statuses (ReviewResult.status). doc_type mirrors the non-"ok" ones.
STATUS_OK = "ok"
STATUS_INSUFFICIENT = "insufficient_content"
STATUS_NOT_QA = "not_a_qa_document"
STATUS_TOO_LARGE = "input_too_large"


@dataclass
class ReviewResult:
    doc_type: str                  # resolved type (after auto-detection), or a non-"ok" status string
    overall_score: int              # 0-100
    dimension_scores: dict = field(default_factory=dict)
    findings: list = field(default_factory=list)
    stats: dict = field(default_factory=dict)
    # "ok" | "insufficient_content" | "not_a_qa_document" | "input_too_large"
    status: str = STATUS_OK
    # F7: language heuristic. language_warning is non-empty (and
    # score_reliable False) when the input looks non-English.
    language: str = "unknown"
    language_warning: str = ""
    score_reliable: bool = True
    # F20: auto-detection transparency. detected_type is None when the
    # caller passed an explicit doc_type; detection_confidence is then
    # "explicit", else "high" | "medium" | "low".
    detected_type: Optional[str] = None
    detection_confidence: str = "explicit"
    detection_signals: dict = field(default_factory=dict)
    detection_note: str = ""
    # Non-empty on rejections (insufficient_content / not_a_qa_document): tells
    # the caller how to retry (explicit doc_type, or more content).
    hint: str = ""


def _retry_hint(status: str) -> str:
    types = ", ".join(DOC_TYPES)
    if status == STATUS_NOT_QA:
        return (f"If this is a genuine QA document, retry with an explicit doc_type "
                f"({types}); an explicit type only requires a core testing term. "
                "Otherwise the text is not a test plan, test strategy or test case list.")
    if status == STATUS_INSUFFICIENT:
        return (f"Add more content (at least {MIN_CONTENT_CHARS} characters), or, for a "
                f"short document that mentions testing, retry with an explicit doc_type "
                f"({types}).")
    return ""


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

_TC_ID_RE = re.compile(r"\b(?:tc|tcase|test[-_ ]?case)[-_ ]?\d+\b", re.IGNORECASE)
_EXPECTED_MENTION_RE = re.compile(r"expected[ _-]?(?:result|outcome|behaviou?r)s?", re.IGNORECASE)
_NUMBERED_STEP_RE = re.compile(r"^\s*(?:[|>*-]\s*)?\d+[.)]\s+\S", re.MULTILINE)
_STEP_WORD_RE = re.compile(r"\bsteps?\b|\bprocedure\b", re.IGNORECASE)


def _detection_signals(lower_text: str) -> dict:
    votes = {}
    for doc_type, sections in SECTION_SYNONYMS.items():
        count = 0
        for synonyms in sections.values():
            if any(syn in lower_text for syn in synonyms):
                count += 1
        votes[doc_type] = count
    # An explicit title ("# Test Plan", "Test Strategy: ...") is the strongest evidence of intent,
    # and the only evidence a very short document has.
    lines = [ln.strip() for ln in lower_text.splitlines() if ln.strip()][:5]
    title_lines = [ln for ln in lines if ln.startswith("#")] or lines[:1]
    title = " ".join(title_lines)
    if "test plan" in title:
        votes["test_plan"] += 3
    elif "test strategy" in title:
        votes["test_strategy"] += 3
    # test_cases has fewer sections total, so bias slightly toward it only
    # when it clearly dominates (its own distinguishing keywords present).
    if any(k in lower_text for k in ["test case id", "tc id", "precondition"]):
        votes["test_cases"] += 2
    tc_ids = len({re.sub(r"[-_ ]", "", m).lower() for m in _TC_ID_RE.findall(lower_text)})
    expected = len(_EXPECTED_MENTION_RE.findall(lower_text))
    if re.search(r"^\s*\|[^\n]*\bexpected\b", lower_text, re.MULTILINE):
        expected += 1
    step_markers = len(_NUMBERED_STEP_RE.findall(lower_text)) + len(_STEP_WORD_RE.findall(lower_text))
    return {"votes": votes, "tc_ids": tc_ids, "expected_result_mentions": expected,
            "step_markers": step_markers}


def _classify(signals: dict) -> tuple:
    """(doc_type, confidence). Ties/zero evidence fall back to 'test_plan'
    (the most structurally demanding checklist) with confidence 'low'."""
    votes = signals["votes"]
    tc_evidence = (signals["tc_ids"]
                   + (2 if signals["expected_result_mentions"] >= 2 else 0)
                   + (1 if signals["step_markers"] >= 1 else 0))
    other_best = max(votes["test_plan"], votes["test_strategy"])
    if tc_evidence >= 3 and tc_evidence * 2 >= other_best:
        conf = "high" if (signals["tc_ids"] >= 3 or tc_evidence >= 5) else "medium"
        return "test_cases", conf
    best = max(votes, key=lambda k: (votes[k], k == "test_plan"))
    ranked = sorted(votes.values(), reverse=True)
    margin = ranked[0] - ranked[1]
    if ranked[0] >= 4 and margin >= 3:
        conf = "high"
    elif ranked[0] >= 3 and margin >= 1:
        conf = "medium"
    else:
        conf = "low"
    return best, conf


def _detect_doc_type(lower_text: str) -> str:
    """Heading-keyword + test-case-signal vote; ties default to 'test_plan'."""
    return _classify(_detection_signals(lower_text))[0]


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

_EXPECTED_MARK_RE = re.compile(r"expected (?:result|outcome)", re.IGNORECASE)
_STATEMENT_WINDOW = 300


class _ExpectedStatements:
    """Linear-time replacement for the old `[^.\n]*expected result[^.\n]*`
    findall, which backtracked quadratically on a long delimiter-free line.
    Statement = the sentence/line around each mark, bounded to a window."""

    @staticmethod
    def findall(text: str) -> list:
        out = []
        for m in _EXPECTED_MARK_RE.finditer(text):
            lo = max(0, m.start() - _STATEMENT_WINDOW)
            hi = min(len(text), m.end() + _STATEMENT_WINDOW)
            start = max(text.rfind(".", lo, m.start()), text.rfind("\n", lo, m.start())) + 1
            if start == 0:
                start = lo
            ends = [e for e in (text.find(".", m.end(), hi), text.find("\n", m.end(), hi)) if e != -1]
            out.append(text[start:min(ends) if ends else hi])
        return out


_EXPECTED_STATEMENT_RE = _ExpectedStatements()


_NUMERIC_CRITERION_RES = (
    # Digit runs are bounded and anchored (no match may start mid-run) so a document that is one very long
    # run of digits cannot make these quadratic.
    re.compile(r"(?<![\d.])\d{1,9}(?:\.\d{1,6})?[ \t]{0,8}%"),                   # 95% pass rate
    re.compile(r"(?:<|>|<=|>=|≤|≥|under|below|within|less than|at most|at least|"
               r"more than|above)[ \t]{0,8}\d{1,9}(?:\.\d{1,6})?[ \t]{0,8}(?:ms|milliseconds?|s|sec|seconds?|"
               r"minutes?|hours?|days?|mb|gb|kb|requests?|users?|errors?|defects?|bugs?)\b",
               re.IGNORECASE),                                                   # p95 < 500 ms
    re.compile(r"\bp(?:50|90|95|99)\b|\b\d{1,9}[ \t]{0,8}(?:ms|milliseconds|seconds|tps|rps|"
               r"concurrent users|requests per second)\b", re.IGNORECASE),     # units / percentiles
    re.compile(r"\b(?:zero|no|0)\s+(?:open\s+)?(?:critical|high|blocker|sev(?:erity)?[- ]?1)\b",
               re.IGNORECASE),                                                   # zero critical defects
)


def _measurability(text: str, lower_text: str, doc_type: str = "test_plan") -> tuple:
    """Plan/strategy documents state measurable *criteria* (thresholds,
    percentages, numeric limits); 'expected result' statements are a
    test-case concept and are only scored when present."""
    statements = _EXPECTED_STATEMENT_RE.findall(text)
    total = len(statements)
    vague_count = sum(
        1 for s in statements if any(p in s.lower() for p in _VAGUE_EXPECTED_RESULT_PHRASES)
    )
    has_metric_signal = any(k in lower_text for k in _METRIC_KEYWORDS)
    numeric_kinds = sum(1 for rx in _NUMERIC_CRITERION_RES if rx.search(text))

    findings = []
    if total == 0:
        # Plan-level evidence: numeric thresholds stand in for expected results.
        base_score = 20 if numeric_kinds == 0 else (60 if numeric_kinds == 1 else 80)
        if numeric_kinds == 0:
            findings.append(ReviewFinding(
                "measurability", "major",
                "No measurable criteria found (no thresholds, percentages or numeric "
                "limits such as '95% pass rate' or 'p95 < 500 ms').",
                "measurable criteria",
                ["ISTQB measurable expected results"],
            ))
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

    if not has_metric_signal and numeric_kinds == 0:
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


# ── Test-case-list rubric (doc_type == "test_cases") ───────────────────────────

_PRECONDITION_RE = re.compile(r"precondition|prerequisite|\bgiven\b|\bsetup\b|\bset-up\b", re.IGNORECASE)
_NEGATIVE_RE = re.compile(
    r"invalid|negative|incorrect|wrong|\berror\b|lock(?:ed|out)|reject|denied|unauthori[sz]ed|\bfail(?:s|ed|ure)?\b|empty|missing|expired",
    re.IGNORECASE,
)
_BOUNDARY_RE = re.compile(
    r"boundary|\bedge[- ]cases?|equivalence|partition|off-by-one|just (?:below|above)|"
    r"upper limit|lower limit|\b(?:min(?:imum)?|max(?:imum)?)\s+(?:length|value|size|allowed|number|of|\d)|"
    r"exactly \d+|\d+ characters",
    re.IGNORECASE,
)
_TRACE_MENTION_RE = re.compile(r"requirement|traceab|user story|traces? to|covers", re.IGNORECASE)


def _test_case_expected_statements(text: str) -> list:
    """Expected-result statements in prose lines, 'Expected:' lines, and
    markdown-table 'Expected ...' column cells."""
    statements = []
    expected_col = None
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("|"):
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
                continue
            idx = next((i for i, c in enumerate(cells) if "expected" in c.lower()), None)
            if idx is not None and expected_col is None:
                expected_col = idx          # header row
                continue
            if expected_col is not None and expected_col < len(cells):
                statements.append(cells[expected_col])
            continue
        expected_col = None
        m = re.match(r"^\W*expected\W*(?:result|outcome|behaviou?r)?s?\s*[:\-]\s*(.*)$", stripped, re.IGNORECASE)
        if m:
            statements.append(m.group(1) or stripped)
        else:
            statements.extend(_EXPECTED_STATEMENT_RE.findall(line))
    return statements


def _tc_structure(text: str, lower_text: str) -> tuple:
    checks = {
        "test_case_id": bool(_TC_ID_RE.search(text)) or "test case id" in lower_text or "tc id" in lower_text,
        "steps": bool(_NUMBERED_STEP_RE.search(text)) or bool(_STEP_WORD_RE.search(text)),
        "expected_result": bool(_EXPECTED_MENTION_RE.search(text)) or "| expected" in lower_text,
        "preconditions": bool(_PRECONDITION_RE.search(text)),
    }
    severity = {"test_case_id": "major", "steps": "major", "expected_result": "major", "preconditions": "minor"}
    findings = []
    for key, present in checks.items():
        if not present:
            findings.append(ReviewFinding(
                "structure_completeness", severity[key],
                f"Missing expected test case element: {key.replace('_', ' ')}.", key,
                [f"test case {key.replace('_', ' ')}", "IEEE 829 test case specification"],
            ))
    return round(100 * sum(checks.values()) / len(checks)), findings


def _tc_measurability(text: str) -> tuple:
    statements = _test_case_expected_statements(text)
    total = len(statements)
    findings = []
    if total == 0:
        findings.append(ReviewFinding(
            "measurability", "major", "No expected results found for the test cases.",
            "expected results", ["ISTQB measurable expected results"],
        ))
        return 20, findings
    vague = sum(1 for st in statements
                if not st.strip() or any(p in st.lower() for p in _VAGUE_EXPECTED_RESULT_PHRASES))
    if vague:
        ratio = vague / total
        findings.append(ReviewFinding(
            "measurability", "major" if ratio > 0.5 else "minor",
            f"{vague}/{total} expected-result statements are vague or empty "
            f"(e.g. 'works correctly', 'as expected') rather than measurable.",
            "vague expected results",
            ["ISTQB measurable test objectives acceptance criteria"],
        ))
    return round((1 - vague / total) * 100), findings


_TC_PREFIXES = {"TC", "TCS", "TS", "TEST", "TCASE", "TCID"}


def _has_requirement_ids(text: str) -> bool:
    """Requirement-style IDs, ignoring the test cases' own IDs (TC-001 is
    not a link to a requirement)."""
    for m in _REQ_ID_RE.finditer(text):
        if m.group(0).split("-")[0].upper().rstrip("0123456789") not in _TC_PREFIXES:
            return True
    return False


def _tc_traceability(text: str, lower_text: str) -> tuple:
    if _has_requirement_ids(text):
        return 100, []
    if _TRACE_MENTION_RE.search(lower_text):
        return 50, [ReviewFinding(
            "traceability", "minor",
            "Requirements are mentioned but no requirement identifiers (REQ-, US-, ticket keys) link the test cases to them.",
            "requirement IDs", ["ISTQB traceability requirements to test cases"],
        )]
    return 0, [ReviewFinding(
        "traceability", "major",
        "No requirement/user-story identifiers found linking test cases to requirements.",
        "requirement IDs", ["ISTQB traceability requirements to test cases"],
    )]


_TECHNIQUE_RE = re.compile(
    r"state[- ]transition|decision[- ]table|pairwise|combinatorial|"
    r"error[- ]guessing|use[- ]case|concurren|race condition|permission|\brole\b|"
    r"timeout|session expir|idempoten|\bretry\b|rollback",
    re.IGNORECASE,
)
# Fewer cases than this cannot show broad design-technique coverage.
_DESIGN_COVERAGE_CASES = 8
_DESIGN_COVERAGE_SMALL_CAP = 85


def _tc_design_coverage(text: str, signals: dict) -> tuple:
    """Evidence of test-design techniques. Negative paths need >= 2 distinct
    lines (a lone 'error' word is not a negative-testing suite), boundary /
    equivalence needs an explicit technique term, a further technique (state,
    decision table, ...) is its own check, and fewer than 8 cases are capped."""
    neg_lines = {ln.strip().lower() for ln in text.split("\n") if _NEGATIVE_RE.search(ln)}
    case_count = max(signals["tc_ids"], signals["expected_result_mentions"])
    checks = {
        "multiple_cases": signals["tc_ids"] >= 3 or signals["expected_result_mentions"] >= 3,
        "negative_cases": len(neg_lines) >= 2,
        "boundary_cases": bool(_BOUNDARY_RE.search(text)),
        "other_techniques": bool(_TECHNIQUE_RE.search(text)),
    }
    findings = []
    if not checks["multiple_cases"]:
        findings.append(ReviewFinding(
            "test_design_coverage", "minor", "Fewer than 3 distinct test cases found.",
            "case count", ["ISTQB test case design coverage"]))
    if not checks["negative_cases"]:
        findings.append(ReviewFinding(
            "test_design_coverage", "major",
            "Fewer than 2 negative / error-path test cases (invalid input, lockout, rejection) found.",
            "negative cases", ["ISTQB negative testing error guessing"]))
    if not checks["boundary_cases"]:
        findings.append(ReviewFinding(
            "test_design_coverage", "minor",
            "No boundary-value or equivalence-partitioning cases found.",
            "boundary cases", ["ISTQB boundary value analysis equivalence partitioning"]))
    if not checks["other_techniques"]:
        findings.append(ReviewFinding(
            "test_design_coverage", "minor",
            "No further design technique evidenced (state transition, decision table, "
            "pairwise, error guessing, role/permission or concurrency cases).",
            "design techniques", ["ISTQB state transition decision table testing techniques"]))
    score = round(100 * sum(checks.values()) / len(checks))
    if 0 < case_count < _DESIGN_COVERAGE_CASES and score > _DESIGN_COVERAGE_SMALL_CAP:
        score = _DESIGN_COVERAGE_SMALL_CAP
        findings.append(ReviewFinding(
            "test_design_coverage", "minor",
            f"Only {case_count} test cases: design coverage is capped below 100 until "
            f"there are at least {_DESIGN_COVERAGE_CASES} cases covering the techniques above.",
            "case count", ["ISTQB test case design coverage"]))
    return score, findings


# ── Orchestrator ───────────────────────────────────────────────────────────────

def _early_result(status: str, stats: dict) -> ReviewResult:
    return ReviewResult(doc_type=status, overall_score=0, dimension_scores={},
                        findings=[], stats=stats, status=status, hint=_retry_hint(status))


def review_document(text: str, doc_type: str = "auto") -> ReviewResult:
    """Deterministically review an existing QA document. No LLM anywhere in
    this call path — see the module docstring.

    Non-"ok" `status` values (no score is produced, overall_score is 0 and
    doc_type mirrors the status): "insufficient_content", "not_a_qa_document",
    "input_too_large"."""
    raw_len = len(text or "")
    if raw_len > MAX_REVIEW_CHARS:
        return _early_result(STATUS_TOO_LARGE, {
            "char_count": raw_len, "raw_char_count": raw_len, "max_chars": MAX_REVIEW_CHARS,
            "reason": f"input is {raw_len} characters; the maximum is {MAX_REVIEW_CHARS}. "
                      "Split the document and review the parts separately."})
    cleaned = _strip_front_matter_and_footer(text or "")

    signal = has_qa_signal(cleaned)
    too_short = len(cleaned) < MIN_CONTENT_CHARS
    # A short text is only "insufficient" when it carries no QA signal or has
    # too few words to score; a 3-line "# Test Plan" still gets feedback.
    if too_short and not (signal and len(cleaned.split()) >= MIN_SIGNAL_WORDS):
        return _early_result(STATUS_INSUFFICIENT, {
            "char_count": len(cleaned), "raw_char_count": raw_len,
            "reason": f"content is under {MIN_CONTENT_CHARS} characters after cleanup"})

    lang = detect_language(cleaned)
    explicit_type = doc_type in DOC_TYPES
    if lang["reliable"]:
        # An explicit doc_type means the caller vouches for the document: only
        # require a core QA term. Auto-detect needs >= MIN_QA_TERMS distinct ones,
        # or an explicit QA signal (heading / "test plan" / "Test N:") plus a
        # core term, so weak-but-genuine documents get a low score, not a rejection.
        is_qa, hits = looks_like_qa_document(cleaned, min_terms=1 if explicit_type else 2)
        if not is_qa and not explicit_type and signal:
            is_qa, hits = looks_like_qa_document(cleaned, min_terms=1)
        if not is_qa:
            return _early_result(STATUS_NOT_QA, {
                "char_count": len(cleaned), "raw_char_count": raw_len, "qa_terms_found": hits,
                "reason": "the input does not look like a QA document (a test plan, test "
                          "strategy or test case list): too few QA-domain terms. No score "
                          "was produced."})

    lower_text = cleaned.lower()
    signals = _detection_signals(lower_text)
    auto = doc_type == "auto" or doc_type not in DOC_TYPES
    if auto:
        resolved_doc_type, confidence = _classify(signals)
        detected_type = resolved_doc_type
    else:
        resolved_doc_type, confidence, detected_type = doc_type, "explicit", None
    note = ""
    if auto and confidence == "low":
        note = ("Document type detection confidence is LOW (few or conflicting structural "
                f"signals); defaulted to '{resolved_doc_type}'. Pass doc_type explicitly "
                "(test_plan, test_strategy or test_cases) for a reliable review.")

    if resolved_doc_type == "test_cases":
        s_score, s_findings = _tc_structure(cleaned, lower_text)
        m_score, m_findings = _tc_measurability(cleaned)
        t_score, t_findings = _tc_traceability(cleaned, lower_text)
        d_score, d_findings = _tc_design_coverage(cleaned, signals)
        dimension_scores = {
            "structure_completeness": s_score,
            "measurability": m_score,
            "traceability": t_score,
            "test_design_coverage": d_score,
        }
        weights = TEST_CASE_WEIGHTS
        findings = s_findings + m_findings + t_findings + d_findings
    else:
        structure_score, structure_findings = _structure_completeness(lower_text, resolved_doc_type)
        scope_score, scope_findings = _objectives_scope_clarity(lower_text)
        entry_exit_score, entry_exit_findings = _entry_exit_criteria(cleaned, lower_text)
        traceability_score, traceability_findings = _traceability(cleaned, lower_text)
        measurability_score, measurability_findings = _measurability(cleaned, lower_text, resolved_doc_type)
        risk_score, risk_findings = _risk_coverage(lower_text)
        dimension_scores = {
            "structure_completeness": structure_score,
            "objectives_scope_clarity": scope_score,
            "entry_exit_criteria": entry_exit_score,
            "traceability": traceability_score,
            "measurability": measurability_score,
            "risk_coverage": risk_score,
        }
        weights = WEIGHTS
        findings = (
            structure_findings + scope_findings + entry_exit_findings
            + traceability_findings + measurability_findings + risk_findings
        )

    total_weight = sum(weights.values())
    overall_score = round(
        sum(dimension_scores[dim] * (weights[dim] / total_weight) for dim in dimension_scores)
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
            "auto_detected": auto,
        },
        status=STATUS_OK,
        language=lang["language"],
        language_warning=lang["warning"],
        score_reliable=lang["reliable"],
        detected_type=detected_type,
        detection_confidence=confidence,
        detection_signals=signals if auto else {},
        detection_note=note,
    )
