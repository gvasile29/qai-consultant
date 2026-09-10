"""
QAI Consultant — Deterministic QA Maturity Assessment Core (v3.5).

Dependency-free (stdlib only: re, dataclasses, typing) so this module is
importable from the MCP server path (no agent.py/Pinecone/Streamlit in its
import graph) and trivially unit-testable. Same input always yields the
same output — no LLM anywhere in this file.

Two independent rubrics:
  1. TMMi (always scored) — 10 process areas across Level 2 (Managed) and
     Level 3 (Defined), evidence-keyword checks per area. The indicative
     level (1-3) NEVER claims Level 4/5 — those require quantitative
     evidence (metrics programs, statistical process control) that a text
     description cannot substantiate. See
     knowledge_base/evaluation_audit/TMMi_Test_Maturity_Model.md's own
     "QAI Consultant Application" section, which forbids claiming or
     implying a certified TMMi level.
  2. EU AI Act readiness (conditional) — 7 checks mapped 1:1 to Articles
     9-15 (knowledge_base/standards/eu_ai_act/EU_AI_Act_Overview.md), only
     scored when the input signals an AI/ML system; otherwise omitted
     entirely rather than scored as a false 0.

Findings carry `citation_queries` (plain strings) rather than resolved
citations — the MCP layer resolves them via LocalIndex.search(), the
Streamlit/CLI layer via agent.retrieve_knowledge(); this module never
touches either.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

MIN_CONTENT_CHARS = 200
MAX_INPUT_CHARS = 500_000
TMMI_LEVEL_THRESHOLD = 60

_DISCLAIMER = (
    "This is an informal indicative signal derived from a text description, "
    "not a certified TMMi appraisal — a real appraisal requires evidence "
    "and interviews reviewed by an accredited assessor, and levels cannot "
    "be skipped."
)

_AI_ACT_NOTE = (
    "Risk-tier classification (whether this system is legally 'high-risk' "
    "under the EU AI Act) is a determination this tool does not make — "
    "these checks apply if the project is high-risk, which the user/team "
    "must confirm independently."
)


@dataclass
class MaturityFinding:
    framework: str                 # "tmmi" | "eu_ai_act"
    dimension: str                 # process area / article key
    level: Optional[int]           # 2 or 3 for TMMi findings; None for AI Act
    severity: str                  # "critical" | "major" | "minor"
    message: str
    evidence: str
    citation_queries: list = field(default_factory=list)


@dataclass
class MaturityResult:
    status: str                        # "ok" | "insufficient_content"
    indicative_tmmi_level: int         # 1-3, 0 if insufficient_content
    tmmi_dimension_scores: dict = field(default_factory=dict)
    ai_act_relevant: bool = False
    ai_act_dimension_scores: dict = field(default_factory=dict)
    ai_act_note: str = ""
    findings: list = field(default_factory=list)
    disclaimer: str = ""
    stats: dict = field(default_factory=dict)


# ── Input hygiene (same convention as review_core.py, redefined locally —
# core modules stay independently dependency-free, no cross-import). ──────

_FRONT_MATTER_RE = re.compile(r"\A---\n.*?\n---\n?", re.DOTALL)
_AI_FOOTER_RE = re.compile(r"\n\n---\n\n\*.*AI-generated content.*\Z", re.DOTALL)


def _strip_front_matter_and_footer(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _FRONT_MATTER_RE.sub("", text, count=1)
    text = _AI_FOOTER_RE.sub("", text)
    return text.strip()


# ── TMMi Process Area Checks ──────────────────────────────────────────────

_REQ_ID_RE = re.compile(r"\b(?:REQ|US|STORY|JIRA)-?\d+\b|\b[A-Z]{2,10}-\d+\b")

# level -> {area_key: [(check_name, keywords), ...]}
_TMMI_CHECKS = {
    2: {
        "test_policy_and_strategy": [
            ("policy_or_strategy_named", ["test policy", "test strategy", "testing strategy"]),
            ("objectives_stated", ["test objective", "testing objective", "quality objective"]),
            ("generic_approach", ["risk class", "risk-based", "generic test approach", "test approach"]),
        ],
        "test_planning": [
            ("test_plan_named", ["test plan"]),
            ("estimates_or_schedule", ["estimate", "schedule", "timeline", "effort"]),
            ("risk_based_prioritization", ["risk-based prioritization", "prioritized by risk", "risk-based testing"]),
        ],
        "test_monitoring_and_control": [
            ("progress_tracking", ["defect log", "defect tracking", "status report", "progress report"]),
            ("corrective_action", ["corrective action", "tracked against plan", "monitored against the plan", "report status"]),
        ],
        "test_design_and_execution": [
            ("test_design_technique", ["test design technique", "test case design", "structured test design"]),
            ("entry_exit_criteria", ["entry criteria", "exit criteria", "entry/exit criteria"]),
        ],
        "test_environment": [
            ("environment_named", ["test environment", "staging environment"]),
            ("representative_of_production", ["representative of production", "production-like", "mirrors production"]),
        ],
    },
    3: {
        "test_organization": [
            ("independent_test_team", ["test team", "qa team", "independent test", "test organization", "test department"]),
            ("defined_roles", ["test manager", "test lead", "qa lead", "roles and responsibilities"]),
        ],
        "test_training_program": [
            ("training_program", ["training program", "training curriculum", "certification program"]),
            ("onboarding", ["onboarding", "skills development"]),
        ],
        "test_lifecycle_and_integration": [
            ("master_test_plan", ["master test plan", "test lifecycle"]),
            ("integrated_from_requirements", ["from the requirements phase", "integrated into the software lifecycle", "shift-left", "early test involvement"]),
        ],
        "non_functional_testing": [
            ("performance", ["performance test", "load test", "stress test"]),
            ("security", ["security test", "penetration test"]),
            ("usability_or_reliability", ["usability test", "reliability test", "accessibility test"]),
        ],
        "peer_reviews": [
            ("review_type", ["code review", "peer review", "inspection", "walkthrough", "technical review"]),
            ("applied_to_requirements_or_design", ["requirements review", "design review"]),
        ],
    },
}

_TMMI_SEVERITY = {
    2: "major",   # Level 2 areas are foundational — a gap here is a major finding
    3: "minor",   # Level 3 gaps are expected until Level 2 is solid; upgraded below when relevant
}


_NEGATION_WINDOW_CHARS = 40  # generous enough to catch e.g. "nobody has ever written a test plan"
_NEGATORS = ("no ", "not ", "never", "without", "lack of", "n't ", "nobody", "none of")


def _keyword_present_without_negation(text: str, keyword: str) -> bool:
    """True if `keyword` occurs in `text` at least once without a negator
    (e.g. "no ", "not ", "never", "without", "lack of", "n't ", "nobody",
    "none of") immediately before it. A description that explicitly denies
    having something (e.g. "we have no test plan") must not score that
    keyword as evidence just because it appears as a substring."""
    for match in re.finditer(re.escape(keyword), text):
        window_start = max(0, match.start() - _NEGATION_WINDOW_CHARS)
        window = text[window_start:match.start()]
        if not any(neg in window for neg in _NEGATORS):
            return True
    return False


def _score_area(lower_text: str, checks: list, req_id_present: Optional[bool]) -> tuple:
    """One process area's score + findings. `req_id_present` folds in the
    requirement-traceability signal for test_design_and_execution only —
    callers pass None for areas where it doesn't apply."""
    results = {}
    for name, keywords in checks:
        results[name] = any(_keyword_present_without_negation(lower_text, k) for k in keywords)
    if req_id_present is not None:
        results["requirement_traceability"] = req_id_present
    score = round(100 * sum(results.values()) / len(results)) if results else 0
    return score, results


def _score_tmmi(text: str, lower_text: str) -> tuple:
    """Returns (dimension_scores: dict, findings: list[MaturityFinding])."""
    scores = {}
    findings = []
    req_id_present = bool(_REQ_ID_RE.search(text))

    for level, areas in _TMMI_CHECKS.items():
        for area_key, checks in areas.items():
            is_design_area = area_key == "test_design_and_execution"
            score, results = _score_area(
                lower_text, checks, req_id_present if is_design_area else None,
            )
            scores[area_key] = score
            for check_name, passed in results.items():
                if not passed:
                    label = area_key.replace("_", " ").title()
                    findings.append(MaturityFinding(
                        framework="tmmi",
                        dimension=area_key,
                        level=level,
                        severity=_TMMI_SEVERITY[level],
                        message=f"No evidence found for '{check_name.replace('_', ' ')}' "
                                f"in the {label} process area.",
                        evidence=check_name,
                        citation_queries=[f"TMMi {label} process area"],
                    ))
    return scores, findings


def _indicative_level(tmmi_scores: dict) -> int:
    """Cumulative, no-skip logic — see the TMMi KB doc's own no-skip rule.
    Never returns 4 or 5 (out of this rubric's evidentiary reach)."""
    level2_areas = [
        "test_policy_and_strategy", "test_planning", "test_monitoring_and_control",
        "test_design_and_execution", "test_environment",
    ]
    level3_areas = [
        "test_organization", "test_training_program", "test_lifecycle_and_integration",
        "non_functional_testing", "peer_reviews",
    ]
    level2_avg = sum(tmmi_scores[a] for a in level2_areas) / len(level2_areas)
    level3_avg = sum(tmmi_scores[a] for a in level3_areas) / len(level3_areas)

    if level2_avg < TMMI_LEVEL_THRESHOLD:
        return 1
    if level3_avg < TMMI_LEVEL_THRESHOLD:
        return 2
    return 3


# ── EU AI Act Articles 9-15 Readiness Checks ──────────────────────────────

_AI_RELEVANCE_RE = re.compile(
    r"\b(ai|artificial intelligence|machine learning|neural network|"
    r"llm|large language model|deep learning|generative ai|ml model)\b",
    re.IGNORECASE,
)

# article -> (dimension_key, severity, keywords, citation_query)
_AI_ACT_CHECKS = [
    ("risk_management", "critical",
     ["risk management system", "risk management process", "continuous risk", "iterative risk"],
     "EU AI Act Article 9 risk management system"),
    ("data_governance", "major",
     ["training data", "data governance", "dataset bias", "data quality", "representative dataset"],
     "EU AI Act Article 10 data and data governance"),
    ("technical_documentation", "major",
     ["technical documentation", "annex iv", "validation report", "design specification"],
     "EU AI Act Article 11 technical documentation"),
    ("record_keeping", "major",
     ["logging", "audit log", "automatic logging", "record-keeping", "traceability of the system's operation"],
     "EU AI Act Article 12 record-keeping logging"),
    ("transparency_instructions", "major",
     ["instructions for use", "known limitations", "declared accuracy", "foreseeable misuse"],
     "EU AI Act Article 13 transparency instructions for deployers"),
    ("human_oversight", "critical",
     ["human oversight", "human-in-the-loop", "human in the loop", "override", "human intervention"],
     "EU AI Act Article 14 human oversight"),
    ("accuracy_robustness_security", "major",
     ["accuracy metric", "robustness", "adversarial", "data poisoning", "model drift"],
     "EU AI Act Article 15 accuracy robustness cybersecurity"),
]


def _is_ai_act_relevant(lower_text: str) -> bool:
    return bool(_AI_RELEVANCE_RE.search(lower_text))


def _score_ai_act(lower_text: str) -> tuple:
    """Returns (dimension_scores: dict, findings: list[MaturityFinding]).
    Only called when _is_ai_act_relevant() is True."""
    scores = {}
    findings = []
    for dimension_key, severity, keywords, citation_query in _AI_ACT_CHECKS:
        present = any(k in lower_text for k in keywords)
        scores[dimension_key] = 100 if present else 0
        if not present:
            article_ref = citation_query.split("EU AI Act ")[1]  # e.g. "Article 9 risk management system"
            findings.append(MaturityFinding(
                framework="eu_ai_act",
                dimension=dimension_key,
                level=None,
                severity=severity,
                message=f"No evidence found for {dimension_key.replace('_', ' ')} ({article_ref}).",
                evidence=dimension_key,
                citation_queries=[citation_query],
            ))
    return scores, findings


def assess_maturity(text: str) -> MaturityResult:
    """Deterministically assess QA process maturity from a free-text
    description or pasted document. No LLM anywhere in this call path."""
    raw_len = len(text or "")
    cleaned = _strip_front_matter_and_footer(text or "")
    if len(cleaned) > MAX_INPUT_CHARS:
        cleaned = cleaned[:MAX_INPUT_CHARS]

    if len(cleaned) < MIN_CONTENT_CHARS:
        return MaturityResult(
            status="insufficient_content",
            indicative_tmmi_level=0,
            tmmi_dimension_scores={},
            ai_act_relevant=False,
            ai_act_dimension_scores={},
            ai_act_note="",
            findings=[],
            disclaimer=_DISCLAIMER,
            stats={"char_count": len(cleaned), "raw_char_count": raw_len,
                   "reason": f"content is under {MIN_CONTENT_CHARS} characters after cleanup"},
        )

    lower_text = cleaned.lower()

    tmmi_scores, tmmi_findings = _score_tmmi(cleaned, lower_text)
    indicative_level = _indicative_level(tmmi_scores)

    ai_act_relevant = _is_ai_act_relevant(lower_text)
    ai_act_scores, ai_act_findings = ({}, [])
    ai_act_note = ""
    if ai_act_relevant:
        ai_act_scores, ai_act_findings = _score_ai_act(lower_text)
        ai_act_note = _AI_ACT_NOTE

    word_count = len(cleaned.split())
    return MaturityResult(
        status="ok",
        indicative_tmmi_level=indicative_level,
        tmmi_dimension_scores=tmmi_scores,
        ai_act_relevant=ai_act_relevant,
        ai_act_dimension_scores=ai_act_scores,
        ai_act_note=ai_act_note,
        findings=tmmi_findings + ai_act_findings,
        disclaimer=_DISCLAIMER,
        stats={"char_count": len(cleaned), "word_count": word_count, "ai_act_relevant": ai_act_relevant},
    )
