# assess_qa_maturity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship `assess_qa_maturity` — a deterministic TMMi process-maturity + conditional EU AI Act Articles 9-15 readiness assessment — as MCP tool, Streamlit mode, and CLI flag, closing the gap `MCP_PLAN.md` §2 left open in v3.1.

**Architecture:** A new dependency-free `src/maturity_core.py` (same import-graph tier as `effort_core.py`/`review_core.py`) scores free text against two independent rubrics and returns a `MaturityResult`. A new `src/maturity_generator.py` (Streamlit/CLI only) wraps it with an LLM narrative, mirroring `review_generator.py` exactly. Three thin call surfaces (MCP tool, Streamlit mode, CLI flag) each call `maturity_core` directly and resolve `citation_queries` via their own existing mechanism (`LocalIndex` / `agent.retrieve_knowledge()`), the same split F1 (`review_qa_document`) already established.

**Tech Stack:** Python stdlib (`re`, `dataclasses`, `typing`) for the core; existing `agent.LLMClient`/`ask()` for the narrative; existing `mcp.server.fastmcp`, `streamlit`, `argparse` surfaces — no new third-party dependencies.

**Spec:** `docs/superpowers/specs/2026-09-09-assess-qa-maturity-design.md`

## Global Constraints

- `maturity_core.py` must be dependency-free (stdlib only: `re`, `dataclasses`, `typing`) — no `agent.py`, no Pinecone, no Streamlit, no LLM import, so it stays importable from the MCP server's keyless path.
- `maturity_generator.py` is Streamlit/CLI-only — never imported by `mcp_server.py`, same as `review_generator.py`.
- Indicative TMMi level is capped at **1, 2, or 3** — never 4 or 5 (per `TMMi_Test_Maturity_Model.md`'s explicit rule that a level requiring quantitative evidence cannot be claimed from a text description). `MaturityResult.disclaimer` must always be non-empty.
- The EU AI Act dimension is *conditional*: when the input has no AI/ML relevance signal, `ai_act_relevant=False` and `ai_act_dimension_scores={}` — never scored as 0 for an irrelevant project.
- Level-2 average threshold and Level-3 average threshold are both **60** (`>= 60` counts as "met").
- `MIN_CONTENT_CHARS = 200`, `MAX_INPUT_CHARS = 500_000` — same values as `review_core.py`, redefined locally (no cross-import between core modules).
- Every finding carries `citation_queries: list[str]` (plain strings), resolved to real citations only by the caller (MCP via `LocalIndex`, Streamlit/CLI via `agent.retrieve_knowledge()`) — `maturity_core.py` never resolves them itself.
- No tool/mode/flag may raise on malformed or short input — always return a structured result (`status="insufficient_content"` at the core level; `{"error": ...}` only for genuinely invalid arguments at the MCP layer, matching `review_qa_document`'s contract).
- Version for this feature: **v3.5.0**. Release Checklist (CLAUDE.md) applies in full: `version.py`, `pyproject.toml`, `CHANGELOG.md`, `README.md`, `README_MCP.md`, `CLAUDE.md` all updated in the same PR.

---

## Task 1: `src/maturity_core.py` — TMMi rubric (data shapes, 10 process areas, indicative level)

**Files:**
- Create: `src/maturity_core.py`
- Test: `tests/test_maturity_core.py`

**Interfaces:**
- Consumes: nothing (new module).
- Produces: `MaturityFinding` (dataclass: `framework: str`, `dimension: str`, `level: Optional[int]`, `severity: str`, `message: str`, `evidence: str`, `citation_queries: list`), `MaturityResult` (dataclass: `status: str`, `indicative_tmmi_level: int`, `tmmi_dimension_scores: dict`, `ai_act_relevant: bool`, `ai_act_dimension_scores: dict`, `findings: list`, `disclaimer: str`, `stats: dict`), `MIN_CONTENT_CHARS: int`, `MAX_INPUT_CHARS: int`, `TMMI_LEVEL_THRESHOLD: int`, `assess_maturity(text: str) -> MaturityResult` (AI Act dimension wired in Task 2 — this task's `assess_maturity` always returns `ai_act_relevant=False`).

- [ ] **Step 1: Write the failing test for input hygiene + insufficient content**

```python
# tests/test_maturity_core.py
"""
Tests for src/maturity_core.py — deterministic TMMi process-maturity rubric
+ conditional EU AI Act Articles 9-15 readiness dimension (v3.5).

Pure stdlib module: mechanical regex/keyword checks. No LLM anywhere in
this file's call path. Mirrors tests/test_review_core.py's structure.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from maturity_core import (  # noqa: E402
    MAX_INPUT_CHARS,
    MIN_CONTENT_CHARS,
    MaturityFinding,
    MaturityResult,
    assess_maturity,
)


def test_insufficient_content_returns_structured_status():
    result = assess_maturity("Too short.")
    assert result.status == "insufficient_content"
    assert result.indicative_tmmi_level == 0
    assert result.findings == []
    assert result.tmmi_dimension_scores == {}
    assert "reason" in result.stats


def test_disclaimer_always_present():
    result = assess_maturity("word " * 100)
    assert result.disclaimer
    assert "not a certified" in result.disclaimer.lower() or "informal" in result.disclaimer.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_maturity_core.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'maturity_core'`

- [ ] **Step 3: Implement input hygiene, data shapes, and the insufficient-content path**

```python
# src/maturity_core.py
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
            findings=[],
            disclaimer=_DISCLAIMER,
            stats={"char_count": len(cleaned), "raw_char_count": raw_len,
                   "reason": f"content is under {MIN_CONTENT_CHARS} characters after cleanup"},
        )

    lower_text = cleaned.lower()

    tmmi_scores, tmmi_findings = _score_tmmi(cleaned, lower_text)
    indicative_level = _indicative_level(tmmi_scores)

    word_count = len(cleaned.split())
    return MaturityResult(
        status="ok",
        indicative_tmmi_level=indicative_level,
        tmmi_dimension_scores=tmmi_scores,
        ai_act_relevant=False,
        ai_act_dimension_scores={},
        findings=tmmi_findings,
        disclaimer=_DISCLAIMER,
        stats={"char_count": len(cleaned), "word_count": word_count, "ai_act_relevant": False},
    )
```

Note: `_score_tmmi` and `_indicative_level` are implemented in Step 5 below — this step alone leaves them undefined, which is expected and fixed within the same task before moving on.

- [ ] **Step 4: Run test to verify the insufficient-content path passes (dimension tests will still fail — expected)**

Run: `python -m pytest tests/test_maturity_core.py -v`
Expected: `test_insufficient_content_returns_structured_status` and `test_disclaimer_always_present` FAIL with `NameError: name '_score_tmmi' is not defined` (not yet implemented) — this confirms the harness/import wiring is correct before adding rubric logic.

- [ ] **Step 5: Write the failing tests for all 10 TMMi process-area checks**

```python
# append to tests/test_maturity_core.py

_LEVEL2_STRONG = """
Our team maintains a documented test policy and test strategy defining our
test objectives. Every release has a test plan with estimates, a schedule,
and risk-based prioritization. We track defects in a defect log and report
status against the plan, taking corrective action when we fall behind. Test
design follows structured test design techniques with clear entry criteria
and exit criteria; requirements are tracked as REQ-101, REQ-102. We run
everything in a dedicated test environment that is representative of
production.
"""

_LEVEL3_STRONG = _LEVEL2_STRONG + """
We have an independent test team led by a test manager, with defined roles
and responsibilities. New testers go through a formal training program and
onboarding. A master test plan integrates test activities from the
requirements phase onward. Beyond functional checks we run performance
test, security test, and usability test cycles. Every change goes through
a peer review, including requirements review and design review.
"""

_NO_PROCESS_SIGNAL = "We write some code and then people click around the app to see if it works. " * 5


def test_tmmi_scores_all_ten_process_areas():
    result = assess_maturity(_LEVEL3_STRONG)
    assert set(result.tmmi_dimension_scores.keys()) == {
        "test_policy_and_strategy", "test_planning", "test_monitoring_and_control",
        "test_design_and_execution", "test_environment",
        "test_organization", "test_training_program", "test_lifecycle_and_integration",
        "non_functional_testing", "peer_reviews",
    }


def test_tmmi_strong_level3_text_scores_higher_than_no_signal_text():
    strong = assess_maturity(_LEVEL3_STRONG)
    weak = assess_maturity(_NO_PROCESS_SIGNAL)
    for area in strong.tmmi_dimension_scores:
        assert strong.tmmi_dimension_scores[area] >= weak.tmmi_dimension_scores[area]
    assert sum(strong.tmmi_dimension_scores.values()) > sum(weak.tmmi_dimension_scores.values())


def test_tmmi_findings_carry_citation_queries():
    result = assess_maturity(_NO_PROCESS_SIGNAL)
    assert result.findings
    for finding in result.findings:
        assert finding.framework == "tmmi"
        assert finding.citation_queries
        assert finding.level in (2, 3)
```

- [ ] **Step 6: Run tests to verify they fail**

Run: `python -m pytest tests/test_maturity_core.py -v`
Expected: FAIL with `NameError: name '_score_tmmi' is not defined`

- [ ] **Step 7: Implement the 10 TMMi process-area check functions + `_score_tmmi`/`_indicative_level`**

```python
# add to src/maturity_core.py, after the input-hygiene section

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


def _score_area(lower_text: str, checks: list, req_id_present: bool) -> tuple:
    """One process area's score + findings. `req_id_present` folds in the
    requirement-traceability signal for test_design_and_execution only —
    callers pass False for areas where it doesn't apply."""
    results = {}
    for name, keywords in checks:
        results[name] = any(k in lower_text for k in keywords)
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
```

Also update `assess_maturity()`'s `"ok"` branch (already calling `_score_tmmi`/`_indicative_level` from Step 3) — no change needed there since it already calls them by name.

- [ ] **Step 8: Run tests to verify they pass**

Run: `python -m pytest tests/test_maturity_core.py -v`
Expected: PASS (all 5 tests so far)

- [ ] **Step 9: Write the failing tests for the no-skip level logic and determinism**

```python
# append to tests/test_maturity_core.py

_LEVEL3_KEYWORDS_ONLY_NO_LEVEL2 = (
    "We have an independent test team, a test manager, a training program, "
    "a master test plan, performance test and security test cycles, and "
    "every change goes through a peer review and design review. " * 3
)


def test_level3_keywords_without_level2_evidence_never_skips_to_level3():
    result = assess_maturity(_LEVEL3_KEYWORDS_ONLY_NO_LEVEL2)
    assert result.indicative_tmmi_level == 1


def test_strong_level2_and_level3_text_reaches_level3():
    result = assess_maturity(_LEVEL3_STRONG)
    assert result.indicative_tmmi_level == 3


def test_level2_only_text_reaches_level2_not_level3():
    result = assess_maturity(_LEVEL2_STRONG)
    assert result.indicative_tmmi_level == 2


def test_assess_maturity_is_deterministic():
    first = assess_maturity(_LEVEL3_STRONG)
    second = assess_maturity(_LEVEL3_STRONG)
    assert first == second
```

- [ ] **Step 10: Run tests to verify they fail, then confirm they pass with no further code changes**

Run: `python -m pytest tests/test_maturity_core.py -v`
Expected: these 4 new tests should already PASS given Step 7's implementation (the no-skip logic and determinism fall out of `_indicative_level`'s design and `assess_maturity`'s pure-function structure) — if `test_level3_keywords_without_level2_evidence_never_skips_to_level3` fails, the `_LEVEL3_KEYWORDS_ONLY_NO_LEVEL2` fixture's Level-2 area scores are accidentally high; adjust the fixture to remove any accidental Level-2 keyword overlap (e.g. it must not contain "test plan", "test environment", etc.) rather than changing the threshold logic.

- [ ] **Step 11: Commit**

```bash
git add src/maturity_core.py tests/test_maturity_core.py
git commit -m "$(cat <<'EOF'
feat: add TMMi process-maturity rubric (maturity_core.py)

Deterministic, dependency-free scoring across 10 TMMi Level 2/3 process
areas with a no-skip indicative level (capped at 3 per TMMi's own rule
against claiming levels requiring quantitative evidence). EU AI Act
dimension lands in the next commit.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_0144znX3oCn8cGtUrB88a1ZM
EOF
)"
```

---

## Task 2: `src/maturity_core.py` — EU AI Act readiness dimension

**Files:**
- Modify: `src/maturity_core.py`
- Test: `tests/test_maturity_core.py`

**Interfaces:**
- Consumes: `MaturityFinding`, `MaturityResult` from Task 1.
- Produces: `assess_maturity()` now populates `ai_act_relevant`/`ai_act_dimension_scores` when the input is AI-relevant; adds `_is_ai_act_relevant(lower_text) -> bool` and `_score_ai_act(lower_text) -> tuple` (dimension_scores dict, findings list) as new internal functions.

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_maturity_core.py

_AI_RELEVANT_TEXT = """
We are building a machine learning model that screens loan applications.
The model is trained on historical applicant data. We have a documented
risk management process covering the model's full lifecycle, and our
training data governance process checks for dataset bias. Technical
documentation captures design specifications and validation reports. The
system has automatic logging for traceability. Instructions for use state
known limitations and declared accuracy. A human reviewer can override
any decision (human oversight). We test robustness against adversarial
inputs and monitor for model drift.
"""

_NON_AI_TEXT = "We test a standard e-commerce checkout flow with unit and integration tests. " * 5


def test_ai_act_dimension_absent_for_non_ai_project():
    result = assess_maturity(_NON_AI_TEXT)
    assert result.ai_act_relevant is False
    assert result.ai_act_dimension_scores == {}
    assert not any(f.framework == "eu_ai_act" for f in result.findings)


def test_ai_act_dimension_scored_for_ai_project():
    result = assess_maturity(_AI_RELEVANT_TEXT)
    assert result.ai_act_relevant is True
    assert set(result.ai_act_dimension_scores.keys()) == {
        "risk_management", "data_governance", "technical_documentation",
        "record_keeping", "transparency_instructions", "human_oversight",
        "accuracy_robustness_security",
    }


def test_ai_act_findings_carry_citation_queries_and_severity():
    sparse_ai_text = "We are building an AI system using a neural network model. " * 5
    result = assess_maturity(sparse_ai_text)
    assert result.ai_act_relevant is True
    ai_findings = [f for f in result.findings if f.framework == "eu_ai_act"]
    assert ai_findings
    for finding in ai_findings:
        assert finding.citation_queries
        assert finding.severity in ("critical", "major")
        assert finding.level is None


def test_ai_act_risk_management_and_human_oversight_are_critical():
    sparse_ai_text = "We are building an AI system using a neural network model. " * 5
    result = assess_maturity(sparse_ai_text)
    by_dim = {f.dimension: f.severity for f in result.findings if f.framework == "eu_ai_act"}
    assert by_dim.get("risk_management") == "critical"
    assert by_dim.get("human_oversight") == "critical"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_maturity_core.py -v`
Expected: FAIL — `ai_act_relevant` stays `False` for all inputs (Task 1's stub).

- [ ] **Step 3: Implement the relevance gate and 7 Article checks**

```python
# add to src/maturity_core.py

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
```

Then update `assess_maturity()`'s `"ok"` branch from Task 1's Step 3:

```python
    lower_text = cleaned.lower()

    tmmi_scores, tmmi_findings = _score_tmmi(cleaned, lower_text)
    indicative_level = _indicative_level(tmmi_scores)

    ai_act_relevant = _is_ai_act_relevant(lower_text)
    ai_act_scores, ai_act_findings = ({}, [])
    if ai_act_relevant:
        ai_act_scores, ai_act_findings = _score_ai_act(lower_text)

    word_count = len(cleaned.split())
    return MaturityResult(
        status="ok",
        indicative_tmmi_level=indicative_level,
        tmmi_dimension_scores=tmmi_scores,
        ai_act_relevant=ai_act_relevant,
        ai_act_dimension_scores=ai_act_scores,
        findings=tmmi_findings + ai_act_findings,
        disclaimer=_DISCLAIMER,
        stats={"char_count": len(cleaned), "word_count": word_count, "ai_act_relevant": ai_act_relevant},
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_maturity_core.py -v`
Expected: PASS (all tests in the file)

- [ ] **Step 5: Commit**

```bash
git add src/maturity_core.py tests/test_maturity_core.py
git commit -m "$(cat <<'EOF'
feat: add conditional EU AI Act readiness dimension to maturity_core

Gated on AI/ML relevance detection so non-AI projects never see a false
compliance-gap score. 7 checks map 1:1 to Articles 9-15, risk_management
and human_oversight flagged critical per EU_AI_Act_Overview.md.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_0144znX3oCn8cGtUrB88a1ZM
EOF
)"
```

---

## Task 3: `src/maturity_generator.py` — LLM narrative + save()

**Files:**
- Create: `src/maturity_generator.py`
- Test: `tests/test_maturity_generator.py`

**Interfaces:**
- Consumes: `MaturityResult`, `MaturityFinding` from `maturity_core.py` (Tasks 1-2); `agent.MISTRAL_MODEL`; `ai_disclosure.build_front_matter`, `ai_disclosure.with_ai_footer`.
- Produces: `MATURITY_SYSTEM_PROMPT: str`, `build_maturity_prompt(result: MaturityResult, knowledge_context: str) -> str`, `build_maturity_report_markdown(result: MaturityResult, narrative: str = "") -> str`, `save_maturity_report(markdown_text: str, source_label: str, output_dir: Optional[Path] = None) -> Path`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_maturity_generator.py
"""
Tests for src/maturity_generator.py — narrative prompt building, report
markdown assembly, and save() conventions for the QA Maturity Assessment
(v3.5). No LLM call is made here — only the pure prompt/markdown builders
and the file-save path. Mirrors tests/test_review_generator.py's structure.
"""

import shutil
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from maturity_core import MaturityFinding, MaturityResult  # noqa: E402
from maturity_generator import (  # noqa: E402
    MATURITY_SYSTEM_PROMPT,
    build_maturity_prompt,
    build_maturity_report_markdown,
    save_maturity_report,
)

_SAMPLE_RESULT = MaturityResult(
    status="ok",
    indicative_tmmi_level=2,
    tmmi_dimension_scores={"test_policy_and_strategy": 100, "peer_reviews": 0},
    ai_act_relevant=True,
    ai_act_dimension_scores={"risk_management": 0, "human_oversight": 100},
    findings=[
        MaturityFinding(
            framework="tmmi", dimension="peer_reviews", level=3, severity="minor",
            message="No evidence found for 'review_type'.", evidence="review_type",
            citation_queries=["TMMi Peer Reviews process area"],
        ),
        MaturityFinding(
            framework="eu_ai_act", dimension="risk_management", level=None, severity="critical",
            message="No evidence found for risk management (Article 9 risk management system).",
            evidence="risk_management",
            citation_queries=["EU AI Act Article 9 risk management system"],
        ),
    ],
    disclaimer="This is an informal indicative signal, not a certified TMMi appraisal.",
    stats={"char_count": 1000, "word_count": 150, "ai_act_relevant": True},
)

_NO_FINDINGS_RESULT = MaturityResult(
    status="ok",
    indicative_tmmi_level=3,
    tmmi_dimension_scores={"test_policy_and_strategy": 100},
    ai_act_relevant=False,
    ai_act_dimension_scores={},
    findings=[],
    disclaimer="This is an informal indicative signal, not a certified TMMi appraisal.",
    stats={"char_count": 2000, "word_count": 300, "ai_act_relevant": False},
)


# ── build_maturity_prompt ────────────────────────────────────────────────────

def test_build_maturity_prompt_includes_indicative_level():
    prompt = build_maturity_prompt(_SAMPLE_RESULT, "some knowledge context")
    assert "2" in prompt


def test_build_maturity_prompt_includes_findings():
    prompt = build_maturity_prompt(_SAMPLE_RESULT, "")
    assert "[CRITICAL]" in prompt
    assert "risk management" in prompt.lower()


def test_build_maturity_prompt_no_findings_says_so():
    prompt = build_maturity_prompt(_NO_FINDINGS_RESULT, "")
    assert "no findings" in prompt.lower()


def test_build_maturity_prompt_includes_knowledge_context():
    prompt = build_maturity_prompt(_SAMPLE_RESULT, "UNIQUE_KB_MARKER_XYZ")
    assert "UNIQUE_KB_MARKER_XYZ" in prompt


def test_build_maturity_prompt_instructs_not_to_rescore():
    prompt = build_maturity_prompt(_SAMPLE_RESULT, "")
    assert "do not invent" in prompt.lower() or "do not re-score" in prompt.lower()


def test_maturity_system_prompt_forbids_rescoring():
    assert "never invent" in MATURITY_SYSTEM_PROMPT.lower() or "never change" in MATURITY_SYSTEM_PROMPT.lower()


# ── build_maturity_report_markdown ───────────────────────────────────────────

def test_build_maturity_report_markdown_includes_level_and_disclaimer():
    md = build_maturity_report_markdown(_SAMPLE_RESULT, "")
    assert "Indicative TMMi Level" in md
    assert _SAMPLE_RESULT.disclaimer in md


def test_build_maturity_report_markdown_includes_ai_act_section_when_relevant():
    md = build_maturity_report_markdown(_SAMPLE_RESULT, "")
    assert "EU AI Act" in md
    assert "risk_management".replace("_", " ") in md.lower()


def test_build_maturity_report_markdown_omits_ai_act_section_when_not_relevant():
    md = build_maturity_report_markdown(_NO_FINDINGS_RESULT, "")
    assert "EU AI Act Readiness" not in md


def test_build_maturity_report_markdown_appends_narrative_when_given():
    md = build_maturity_report_markdown(_SAMPLE_RESULT, "# QA Maturity Assessment\n\nNarrative body text.")
    assert "Narrative body text." in md
    assert md.rstrip().endswith("Narrative body text.")


def test_build_maturity_report_markdown_is_deterministic():
    md1 = build_maturity_report_markdown(_SAMPLE_RESULT, "narrative")
    md2 = build_maturity_report_markdown(_SAMPLE_RESULT, "narrative")
    assert md1 == md2


# ── save_maturity_report ──────────────────────────────────────────────────────

def test_save_maturity_report_writes_file_with_front_matter_and_footer():
    tmp_dir = Path(tempfile.mkdtemp())
    try:
        path = save_maturity_report("# QA Maturity Assessment\n\nBody.", "My Project", output_dir=tmp_dir)
        assert path.exists()
        content = path.read_text(encoding="utf-8")
        assert content.startswith("---\n")
        assert "ai_generated: true" in content
        assert "AI-generated content" in content
        assert "Body." in content
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_save_maturity_report_sanitizes_filename():
    tmp_dir = Path(tempfile.mkdtemp())
    try:
        path = save_maturity_report("body", "My:Weird/Project*Name?", output_dir=tmp_dir)
        assert path.exists()
        for bad_char in [':', '/', '*', '?']:
            assert bad_char not in path.name
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_save_maturity_report_filename_starts_with_maturity_assessment_prefix():
    tmp_dir = Path(tempfile.mkdtemp())
    try:
        path = save_maturity_report("body", "Acme", output_dir=tmp_dir)
        assert path.name.startswith("maturity_assessment_Acme_")
        assert path.name.endswith(".md")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_save_maturity_report_handles_empty_label():
    tmp_dir = Path(tempfile.mkdtemp())
    try:
        path = save_maturity_report("body", "", output_dir=tmp_dir)
        assert path.exists()
        assert "Assessment" in path.name
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_maturity_generator.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'maturity_generator'`

- [ ] **Step 3: Implement `maturity_generator.py`**

```python
# src/maturity_generator.py
"""
QAI Consultant — QA Maturity Assessment: narrative + save.

Wraps the deterministic src/maturity_core.py rubric with an LLM-written
narrative and the same save()/Article 50(2) marking conventions as the
other generator modules (review_generator.py, risk_analyzer.py). Streamlit/
CLI only — the MCP server never generates text (see mcp_server.py's
docstring and MCP_PLAN.md section 1); this module is not in the MCP
server's import graph.
"""

import re
from pathlib import Path
from datetime import datetime
from typing import Optional

from agent import MISTRAL_MODEL
from ai_disclosure import build_front_matter, with_ai_footer
from maturity_core import MaturityResult
from logger import get_logger

logger = get_logger(__name__)

MATURITY_SYSTEM_PROMPT = """You are QAI Consultant, a senior QA Architect performing a QA process
maturity assessment. A deterministic rubric has already scored the process — you never invent,
change, or contradict the given indicative TMMi level, dimension scores, or findings. Your job is
to explain why they matter (grounded in the TMMi/CMMI/EU AI Act knowledge base provided) and give
the team concrete, prioritized next steps toward the next maturity level.
"""


def build_maturity_prompt(result: MaturityResult, knowledge_context: str) -> str:
    """Build the narrative-generation prompt from an already-computed
    MaturityResult — the LLM explains and prioritizes, it does not re-score."""
    tmmi_text = "\n".join(
        f"- {dim.replace('_', ' ').title()}: {score}/100"
        for dim, score in result.tmmi_dimension_scores.items()
    )
    ai_act_text = "\n".join(
        f"- {dim.replace('_', ' ').title()}: {score}/100"
        for dim, score in result.ai_act_dimension_scores.items()
    ) if result.ai_act_relevant else "Not applicable — no AI/ML system signal detected in the input."

    findings_text = "\n".join(
        f"- [{f.severity.upper()}] ({f.framework}/{f.dimension}) {f.message} (evidence: {f.evidence})"
        for f in result.findings
    ) or "- No findings — every mechanical check passed."

    return f"""
A deterministic rubric has already assessed a QA process description against a TMMi-based process
maturity model{"and EU AI Act Articles 9-15 readiness" if result.ai_act_relevant else ""}. Write a
narrative QA Maturity Assessment report explaining these already-computed results to the team and
prioritizing what to address first toward the next maturity level. Do not invent a different level,
score, or additional findings — use exactly what is given below.

INDICATIVE TMMI LEVEL: {result.indicative_tmmi_level}
DISCLAIMER (include this verbatim in your Summary): {result.disclaimer}

TMMI PROCESS AREA SCORES:
{tmmi_text}

EU AI ACT ARTICLE 9-15 READINESS SCORES:
{ai_act_text}

FINDINGS (deterministic, already computed):
{findings_text}

RELEVANT QA KNOWLEDGE BASE:
{knowledge_context}

Generate the narrative using EXACTLY this structure:

# QA Maturity Assessment

## Summary
2-3 sentences on the indicative maturity level and the single most important next step. Include the
disclaimer above verbatim.

## What's Working Well
Bullet points on the process areas that scored well.

## Priority Gaps
For each Critical and Major finding: explain why it matters (reference the standards in the
knowledge base where relevant) and give a concrete, actionable next step.

## Minor Improvements
Briefly list the Minor findings with suggested next steps.

## References
List the standards/methodologies referenced above.

Be specific — reference the actual dimension/article names and evidence given above rather than
generic advice.
"""


def build_maturity_report_markdown(result: MaturityResult, narrative: str = "") -> str:
    """Deterministic score/findings section + the optional LLM narrative —
    used for both the in-app display and the saved file."""
    lines = [
        "# QA Maturity Assessment",
        "",
        f"**Indicative TMMi Level:** {result.indicative_tmmi_level}",
        "",
        f"> {result.disclaimer}",
        "",
        "## TMMi Process Area Scores",
        "",
        "| Process Area | Score |",
        "|---|---|",
    ]
    for dim, score in result.tmmi_dimension_scores.items():
        lines.append(f"| {dim.replace('_', ' ').title()} | {score}/100 |")

    if result.ai_act_relevant:
        lines.append("")
        lines.append("## EU AI Act Readiness (Articles 9-15)")
        lines.append("")
        lines.append("| Article Area | Score |")
        lines.append("|---|---|")
        for dim, score in result.ai_act_dimension_scores.items():
            lines.append(f"| {dim.replace('_', ' ').title()} | {score}/100 |")

    lines.append("")
    lines.append("## Findings")
    lines.append("")
    if not result.findings:
        lines.append("No findings — every mechanical check in the rubric passed.")
    else:
        for finding in result.findings:
            lines.append(
                f"- **[{finding.severity.upper()}]** ({finding.framework}/{finding.dimension}) "
                f"{finding.message} — _evidence: {finding.evidence}_"
            )
    if narrative:
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append(narrative)
    return "\n".join(lines)


def save_maturity_report(markdown_text: str, source_label: str, output_dir: Optional[Path] = None) -> Path:
    """Save a QA maturity assessment report with the same filename-
    sanitization and Article 50(2) front-matter/footer convention as the
    other generators."""
    if output_dir is None:
        output_dir = Path(__file__).resolve().parent.parent / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = re.sub(r'[^\w\-.]', '_', (source_label or "Assessment").replace(' ', '_')) or "Assessment"
    filename = f"maturity_assessment_{safe_name}_{timestamp}.md"
    output_path = output_dir / filename

    front_matter = build_front_matter("QA Maturity Assessment", source_label or "Assessment", MISTRAL_MODEL)
    full_content = f"""{front_matter}

{with_ai_footer(markdown_text)}
"""
    output_path.write_text(full_content, encoding="utf-8")
    return output_path
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_maturity_generator.py -v`
Expected: PASS (all tests)

- [ ] **Step 5: Commit**

```bash
git add src/maturity_generator.py tests/test_maturity_generator.py
git commit -m "$(cat <<'EOF'
feat: add maturity_generator.py (LLM narrative + save for QA Maturity Assessment)

Mirrors review_generator.py's shape exactly: prompt building, markdown
report assembly, and the same filename-sanitization/AI-footer save()
convention. Streamlit/CLI only, not in the MCP server's import graph.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_0144znX3oCn8cGtUrB88a1ZM
EOF
)"
```

---

## Task 4: MCP tool `assess_qa_maturity` in `src/mcp_server.py`

**Files:**
- Modify: `src/mcp_server.py`
- Test: `tests/test_mcp_server.py`

**Interfaces:**
- Consumes: `maturity_core.assess_maturity()`, `maturity_core.MaturityResult`/`MaturityFinding` (Tasks 1-2); `_get_index()` (existing, `src/mcp_server.py`); `telemetry.track_tool_called()` (existing).
- Produces: `@mcp.tool() assess_qa_maturity(project_description: str) -> dict`.

- [ ] **Step 1: Write the failing tests**

First check how `tests/test_mcp_server.py` invokes tools (`_run`, `_call_tool`, `_list_tools` helpers already exist — reuse them, don't redefine). Add:

```python
# append to tests/test_mcp_server.py

_LEVEL2_PROCESS_TEXT = """
Our team maintains a documented test policy and test strategy defining our
test objectives. Every release has a test plan with estimates, a schedule,
and risk-based prioritization. We track defects in a defect log and report
status against the plan, taking corrective action when we fall behind. Test
design follows structured test design techniques with clear entry criteria
and exit criteria; requirements are tracked as REQ-101, REQ-102. We run
everything in a dedicated test environment that is representative of
production.
"""


def test_assess_qa_maturity_schema_has_expected_params():
    tools = _run(_list_tools())
    tool = next(t for t in tools if t.name == "assess_qa_maturity")
    props = tool.inputSchema["properties"]
    assert set(props.keys()) == {"project_description"}


def test_assess_qa_maturity_happy_path_shape():
    result = _run(_call_tool("assess_qa_maturity", {
        "project_description": _LEVEL2_PROCESS_TEXT,
    }))
    assert "error" not in result
    assert result["indicative_tmmi_level"] in (1, 2, 3)
    assert set(result["tmmi_dimension_scores"].keys()) == {
        "test_policy_and_strategy", "test_planning", "test_monitoring_and_control",
        "test_design_and_execution", "test_environment",
        "test_organization", "test_training_program", "test_lifecycle_and_integration",
        "non_functional_testing", "peer_reviews",
    }
    assert isinstance(result["findings"], list)
    assert "disclaimer" in result and result["disclaimer"]
    assert "kb_version" in result


def test_assess_qa_maturity_findings_carry_kb_citations_list():
    result = _run(_call_tool("assess_qa_maturity", {
        "project_description": "We write some code and click around to test it. " * 20,
    }))
    assert result["findings"], "expected findings on a weak process description"
    for finding in result["findings"]:
        assert set(finding.keys()) == {
            "framework", "dimension", "level", "severity", "message", "evidence", "kb_citations",
        }
        assert isinstance(finding["kb_citations"], list)
        for citation in finding["kb_citations"]:
            assert set(citation.keys()) == {"source", "category", "score"}


def test_assess_qa_maturity_insufficient_content_is_not_an_error():
    result = _run(_call_tool("assess_qa_maturity", {"project_description": "Too short."}))
    assert "error" not in result
    assert result["indicative_tmmi_level"] == 0
    assert result["findings"] == []


def test_assess_qa_maturity_ai_act_omitted_for_non_ai_project():
    result = _run(_call_tool("assess_qa_maturity", {
        "project_description": "We test a standard e-commerce checkout flow. " * 20,
    }))
    assert result["ai_act_relevant"] is False
    assert result["ai_act_dimension_scores"] == {}


def test_assess_qa_maturity_ai_act_scored_for_ai_project():
    ai_text = (
        "We are building a machine learning model for loan screening, trained on "
        "historical applicant data, with a documented risk management process. " * 3
    )
    result = _run(_call_tool("assess_qa_maturity", {"project_description": ai_text}))
    assert result["ai_act_relevant"] is True
    assert set(result["ai_act_dimension_scores"].keys()) == {
        "risk_management", "data_governance", "technical_documentation",
        "record_keeping", "transparency_instructions", "human_oversight",
        "accuracy_robustness_security",
    }
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_mcp_server.py -k assess_qa_maturity -v`
Expected: FAIL — tool not found / `next()` raises `StopIteration`.

- [ ] **Step 3: Implement the tool**

```python
# add to src/mcp_server.py, near the top imports
import maturity_core

# add after the review_qa_document tool section (after line ~284)

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
    indicative_tmmi_level=0 with empty findings rather than an error. Each
    finding carries kb_citations resolved from the knowledge base for its
    citation queries — a finding with no resolvable source is returned with
    an empty kb_citations list rather than a fabricated one. Returns
    {indicative_tmmi_level, tmmi_dimension_scores, ai_act_relevant,
    ai_act_dimension_scores, findings, disclaimer, stats, kb_version}."""
    start = time.monotonic()

    result = maturity_core.assess_maturity(project_description)
    index = _get_index()

    findings = []
    for finding in result.findings:
        kb_citations: list[dict] = []
        for query in finding.citation_queries:
            search_result = index.search(query, k=2)
            if "error" not in search_result:
                kb_citations.extend(
                    {"source": c["source"], "category": c["category"], "score": c["score"]}
                    for c in search_result["chunks"]
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
        "indicative_tmmi_level": result.indicative_tmmi_level,
        "tmmi_dimension_scores": result.tmmi_dimension_scores,
        "ai_act_relevant": result.ai_act_relevant,
        "ai_act_dimension_scores": result.ai_act_dimension_scores,
        "findings": findings,
        "disclaimer": result.disclaimer,
        "stats": result.stats,
        "kb_version": index.kb_version,
    }
```

Also update the module docstring's tool list (line ~9) and the `INSTRUCTIONS` string (line ~51-62) to mention `assess_qa_maturity`, following the same one-clause-per-tool pattern already used for `review_qa_document`/`analyze_test_results`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_mcp_server.py -k assess_qa_maturity -v`
Expected: PASS (all tests)

- [ ] **Step 5: Run the full MCP test file to check for regressions**

Run: `python -m pytest tests/test_mcp_server.py -v`
Expected: PASS (no regressions in `review_qa_document`/`analyze_test_results`/other tools)

- [ ] **Step 6: Commit**

```bash
git add src/mcp_server.py tests/test_mcp_server.py
git commit -m "$(cat <<'EOF'
feat: add assess_qa_maturity MCP tool

Deterministic-only tool (no LLM, matching the MCP lens) that calls
maturity_core.assess_maturity() and resolves each finding's
citation_queries via LocalIndex, same pattern as review_qa_document.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_0144znX3oCn8cGtUrB88a1ZM
EOF
)"
```

---

## Task 5: Streamlit mode `render_maturity_assessment()` in `src/app.py`

**Files:**
- Modify: `src/app.py`
- Test: `tests/test_app_maturity.py`

**Interfaces:**
- Consumes: `maturity_core.assess_maturity`, `maturity_core.MIN_CONTENT_CHARS` (Tasks 1-2); `maturity_generator.MATURITY_SYSTEM_PROMPT`, `build_maturity_prompt`, `build_maturity_report_markdown`, `save_maturity_report` (Task 3); existing `ledger_components.signal_ledger_html`, `output_screen_style.build_content_polish_css`/`build_output_eyebrow_html`/`build_doc_review_input_tray_css`, `ai_disclosure.pdf_meta_html`/`pdf_icon_html`/`with_ai_footer`, `pdf_export.markdown_to_pdf`.
- Produces: `MATURITY_MODE_STATE_KEYS: list`, `_reset_maturity_mode_state()`, `render_maturity_assessment()`; wires `current_step == "maturity"` into the main dispatcher; adds a sidebar entry point; adds `_reset_maturity_mode_state()` + its own keys to both "Start Over" and "Generate Another Strategy" cleanup blocks.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_app_maturity.py
"""
Tests for src/app.py's "Assess QA Maturity" mode (v3.5) — session-state
cleanup-list membership and the reset helper's key-clearing behavior.
Mirrors tests/test_app_v03.py's Streamlit integration style: import app.py
with sys.path set up, exercise pure helpers and session-state dict logic
directly rather than driving a real Streamlit runtime.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

import app  # noqa: E402


def test_maturity_mode_state_keys_defined():
    assert isinstance(app.MATURITY_MODE_STATE_KEYS, list)
    assert "maturity_result" in app.MATURITY_MODE_STATE_KEYS
    assert "maturity_narrative" in app.MATURITY_MODE_STATE_KEYS
    assert "maturity_pdf_bytes" in app.MATURITY_MODE_STATE_KEYS


def test_reset_maturity_mode_state_clears_all_keys(monkeypatch):
    fake_state = {key: "x" for key in app.MATURITY_MODE_STATE_KEYS}
    fake_state["maturity_input_text"] = "some text"
    monkeypatch.setattr(app.st, "session_state", fake_state)

    app._reset_maturity_mode_state()

    for key in app.MATURITY_MODE_STATE_KEYS:
        assert key not in fake_state


def test_start_over_cleanup_includes_maturity_reset():
    import inspect
    source = inspect.getsource(app.render_sidebar)
    assert "_reset_maturity_mode_state()" in source


def test_generate_another_strategy_cleanup_includes_maturity_reset():
    import inspect
    source = inspect.getsource(app.render_strategy)
    assert "_reset_maturity_mode_state()" in source
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_app_maturity.py -v`
Expected: FAIL with `AttributeError: module 'app' has no attribute 'MATURITY_MODE_STATE_KEYS'`

- [ ] **Step 3: Add imports, state keys, and the reset helper**

```python
# add to src/app.py's import block, alongside the existing review_core/review_generator imports (line ~28-34)
from maturity_core import MIN_CONTENT_CHARS as MATURITY_MIN_CONTENT_CHARS, assess_maturity
from maturity_generator import (
    MATURITY_SYSTEM_PROMPT,
    build_maturity_prompt,
    build_maturity_report_markdown,
    save_maturity_report,
)
```

```python
# add to src/app.py, right after REVIEW_MODE_STATE_KEYS / _reset_review_mode_state() (after line ~159)

# Session-state keys owned by the "Assess QA Maturity" mode — same shared-
# list convention as REVIEW_MODE_STATE_KEYS (see CLAUDE.md's session-state
# cleanup gotcha).
MATURITY_MODE_STATE_KEYS = [
    "maturity_input_text", "maturity_source_label", "maturity_result",
    "maturity_narrative", "maturity_narrative_sources", "maturity_output_path",
    "maturity_pdf_bytes",
]


def _reset_maturity_mode_state():
    for key in MATURITY_MODE_STATE_KEYS:
        if key in st.session_state:
            del st.session_state[key]
    st.session_state.pop("maturity_uploader", None)
    st.session_state.pop("maturity_pasted_text", None)
```

- [ ] **Step 4: Run tests to verify the first two pass (cleanup-list tests still fail — expected until Steps 5-6)**

Run: `python -m pytest tests/test_app_maturity.py -v`
Expected: `test_maturity_mode_state_keys_defined` and `test_reset_maturity_mode_state_clears_all_keys` PASS; the two cleanup-block tests still FAIL.

- [ ] **Step 5: Wire `_reset_maturity_mode_state()` into both cleanup handlers**

In `render_sidebar()`'s "🔄 Start Over" button block (line ~290-308), add the call right after `_reset_review_mode_state()`:

```python
            _reset_review_mode_state()
            _reset_maturity_mode_state()
```

In `render_strategy()`'s "🔄 Generate Another Strategy" button block (line ~1084-1102), add the same call right after `_reset_review_mode_state()`:

```python
        _reset_review_mode_state()
        _reset_maturity_mode_state()
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python -m pytest tests/test_app_maturity.py -v`
Expected: PASS (all 4 tests)

- [ ] **Step 7: Implement `render_maturity_assessment()` and wire it into the app's navigation**

Add `current_step` value `"maturity"` to the comment at line ~121 (`# intro | dialogue | review | strategy | doc_review | maturity`).

Add a sidebar entry point in `render_sidebar()`, right after the existing "🔌 Use QAI in your AI tools (MCP)" expander (after line ~274):

```python
        if st.button("📈 Assess QA Maturity", use_container_width=True):
            st.session_state.current_step = "maturity"
            st.rerun()
```

Add the function itself, right after `render_doc_review()` (after line ~1373), mirroring its structure closely:

```python
def render_maturity_assessment():
    """v3.5: QA Process Maturity Assessment. Step 1 (deterministic, instant)
    scores a free-text process description or pasted document via
    maturity_core.assess_maturity() — no LLM call. Step 2 (button) writes an
    LLM narrative around those already-computed findings and saves an
    Article-50(2)-marked report, mirroring render_doc_review()'s save/PDF
    conventions."""
    MAX_RUNS_PER_SESSION = 3  # mirrors render_doc_review()'s per-session cap

    from output_screen_style import build_content_polish_css, build_output_eyebrow_html
    from theme import DARK_TOKENS, LIGHT_TOKENS

    _maturity_tokens = DARK_TOKENS if st.context.theme.type == "dark" else LIGHT_TOKENS
    st.markdown(build_content_polish_css(_maturity_tokens), unsafe_allow_html=True)
    st.markdown(build_output_eyebrow_html(_maturity_tokens, "maturity assessment sequence"), unsafe_allow_html=True)
    st.markdown("## 📈 Assess QA Maturity")
    st.markdown(
        "Describe your team's testing process (policy, planning, tracking, environment, "
        "training, reviews, ...) — or paste an existing Test Strategy/Risk Register — for "
        "a deterministic, TMMi-grounded process maturity signal. If the description mentions "
        "an AI/ML system, EU AI Act Articles 9-15 readiness is also assessed."
    )
    st.markdown("---")

    if st.session_state.get("maturity_result") is None:
        from output_screen_style import build_doc_review_input_tray_css
        st.markdown(build_doc_review_input_tray_css(_maturity_tokens), unsafe_allow_html=True)

        with st.container(key="maturity-input"):
            uploaded = st.file_uploader(
                "Upload a description or document (.md, .txt)", type=["md", "txt"], key="maturity_uploader",
            )
            st.caption("...or paste your process description below")
            pasted = st.text_area(
                "Process description", key="maturity_pasted_text", height=300, label_visibility="collapsed",
            )

        description_text = ""
        source_label = "Assessment"
        if uploaded is not None:
            description_text = uploaded.read().decode("utf-8", errors="ignore")
            source_label = Path(uploaded.name).stem
        elif pasted.strip():
            description_text = pasted

        if st.button(
            "🔍 Assess Maturity", use_container_width=True, type="primary",
            disabled=not description_text.strip(),
        ):
            st.session_state.maturity_input_text = description_text
            st.session_state.maturity_source_label = source_label
            st.session_state.maturity_result = assess_maturity(description_text)
            st.rerun()

        if not description_text.strip():
            st.info("Upload a file or paste a description above, then click **Assess Maturity**.")

        if st.button("← Back to Home", key="maturity_back_to_home_pre"):
            st.session_state.current_step = "intro"
            st.rerun()
        return

    result = st.session_state.maturity_result

    if result.status == "insufficient_content":
        st.warning(
            f"⚠️ Description is too short to assess ({result.stats.get('char_count', 0)} "
            f"characters after cleanup — need at least {MATURITY_MIN_CONTENT_CHARS})."
        )
        if st.button("← Try another description", use_container_width=True):
            _reset_maturity_mode_state()
            st.rerun()
        return

    from ledger_components import signal_ledger_html

    _maturity_animate_class = " animate" if not st.session_state.get("maturity_intro_animated") else ""
    st.session_state.maturity_intro_animated = True

    st.markdown(
        '<div class="output-tiles{}">{}</div>'.format(
            _maturity_animate_class,
            signal_ledger_html("Indicative TMMi Level", result.indicative_tmmi_level, sub="1-3 · never 4-5"),
        ),
        unsafe_allow_html=True,
    )
    st.caption(result.disclaimer)

    st.markdown("### TMMi Process Area Scores")
    tmmi_cols = st.columns(len(result.tmmi_dimension_scores))
    for col, (dim, score) in zip(tmmi_cols, result.tmmi_dimension_scores.items()):
        with col:
            st.markdown(signal_ledger_html(dim.replace("_", " ").title(), score), unsafe_allow_html=True)

    if result.ai_act_relevant:
        st.markdown("### EU AI Act Readiness (Articles 9-15)")
        ai_cols = st.columns(len(result.ai_act_dimension_scores))
        for col, (dim, score) in zip(ai_cols, result.ai_act_dimension_scores.items()):
            with col:
                st.markdown(signal_ledger_html(dim.replace("_", " ").title(), score), unsafe_allow_html=True)

    st.markdown("### Findings")
    if not result.findings:
        st.success("No findings — every mechanical check in the rubric passed.")
    else:
        _severity_icon = {"critical": "🔴", "major": "🟠", "minor": "🟡"}
        for finding in result.findings:
            icon = _severity_icon.get(finding.severity, "⚪")
            title = f"{icon} [{finding.framework}/{finding.dimension.replace('_', ' ').title()}] {finding.message}"
            with st.expander(title):
                st.markdown(f"**Severity:** {finding.severity}")
                st.markdown(f"**Evidence:** {finding.evidence}")

    st.markdown("---")

    # Step 2: LLM narrative — an LLM call, so it consumes run_count like render_doc_review().
    if st.session_state.get("maturity_narrative") is None:
        if st.session_state.get("run_count", 0) >= MAX_RUNS_PER_SESSION:
            st.warning(
                f"⚠️ You've used all {MAX_RUNS_PER_SESSION} free runs for this session. "
                "Refresh the page to start a new session."
            )
        elif st.button("🤖 Generate narrative assessment", use_container_width=True, type="primary"):
            st.session_state.run_count += 1
            agent = st.session_state.get("agent")

            queries = []
            seen_queries = set()
            for finding in result.findings:
                for q in finding.citation_queries:
                    if q not in seen_queries:
                        seen_queries.add(q)
                        queries.append(q)

            with st.spinner("⚡ Retrieving grounding sources..."):
                chunks = []
                for q in queries[:5]:
                    chunks.extend(agent.retrieve_knowledge(q, k=1))
                if not chunks:
                    chunks = agent.retrieve_knowledge("TMMi test process maturity assessment", k=5)
            knowledge_context = agent.format_knowledge_context(chunks)

            prompt = build_maturity_prompt(result, knowledge_context)
            try:
                narrative = clean_markdown_html(st.write_stream(
                    agent.ask_streaming(prompt, system_prompt=MATURITY_SYSTEM_PROMPT)
                ))
            except (StopException, RerunException):
                raise
            except Exception as exc:
                logger.error("Maturity narrative generation failed: %s", exc)
                st.error(f"❌ Narrative generation failed: {exc}")
                narrative = ""

            st.session_state.maturity_narrative = narrative
            st.session_state.maturity_narrative_sources = list({
                f"[{(c.metadata or {}).get('category', 'N/A')}] {(c.metadata or {}).get('filename', 'N/A')}"
                for c in chunks
            })
            st.rerun()
    else:
        if st.session_state.maturity_narrative:
            st.markdown("### 🤖 Narrative Assessment")
            st.markdown(st.session_state.maturity_narrative)
            with st.expander("📚 Knowledge Sources Used"):
                for source in st.session_state.get("maturity_narrative_sources", []):
                    st.markdown(f'<div class="source-item">• {source}</div>', unsafe_allow_html=True)

        if st.session_state.get("maturity_pdf_bytes") is None:
            report_md = build_maturity_report_markdown(result, st.session_state.maturity_narrative or "")
            st.session_state.maturity_output_path = save_maturity_report(
                report_md, st.session_state.get("maturity_source_label") or "Assessment",
            )
            _ai_pdf_meta = pdf_meta_html(MISTRAL_MODEL)
            _ai_pdf_icon = pdf_icon_html()
            st.session_state.maturity_pdf_bytes = markdown_to_pdf(
                with_ai_footer(report_md), "QA Maturity Assessment", _ai_pdf_meta, _ai_pdf_icon,
            )

        report_md = build_maturity_report_markdown(result, st.session_state.maturity_narrative or "")
        st.markdown("---")
        dl_col1, dl_col2 = st.columns(2)
        with dl_col1:
            st.download_button(
                label="⬇️ Download (.md)",
                data=with_ai_footer(report_md),
                file_name="maturity_assessment.md",
                mime="text/markdown",
                use_container_width=True,
            )
        with dl_col2:
            pdf_bytes = st.session_state.maturity_pdf_bytes
            st.download_button(
                label="⬇️ Download (.pdf)",
                data=pdf_bytes or b"",
                file_name="maturity_assessment.pdf",
                mime="application/pdf",
                use_container_width=True,
                disabled=pdf_bytes is None,
            )

    st.markdown("###")
    if st.button("🔄 Assess Another Description", use_container_width=True):
        _reset_maturity_mode_state()
        st.rerun()
    if st.button("← Back to Home"):
        _reset_maturity_mode_state()
        st.session_state.current_step = "intro"
        st.rerun()
```

Finally, wire the dispatcher: find the `elif step == "doc_review": render_doc_review()` block (line ~1443-1444) and add:

```python
    elif step == "maturity":
        render_maturity_assessment()
```

- [ ] **Step 8: Run the full app test suite to check for regressions**

Run: `python -m pytest tests/test_app_maturity.py tests/test_app_v03.py tests/test_app_feedback_loop.py -v`
Expected: PASS (no regressions)

- [ ] **Step 9: Manual verification**

Run: `streamlit run src/app.py` — click "📈 Assess QA Maturity" in the sidebar, paste `_LEVEL2_PROCESS_TEXT`-style text from Task 4's tests, confirm the TMMi tiles render, then paste AI-relevant text (e.g. Task 2's `_AI_RELEVANT_TEXT`) and confirm the EU AI Act section appears. This is the manual check called for in the spec's Testing section — do not skip it before marking this task done.

- [ ] **Step 10: Commit**

```bash
git add src/app.py tests/test_app_maturity.py
git commit -m "$(cat <<'EOF'
feat: add Assess QA Maturity mode to Streamlit app

render_maturity_assessment() mirrors render_doc_review()'s two-step shape
(instant deterministic score, then an optional LLM narrative + PDF/.md
download). MATURITY_MODE_STATE_KEYS wired into both Start Over and
Generate Another Strategy cleanup, plus its own reset button.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_0144znX3oCn8cGtUrB88a1ZM
EOF
)"
```

---

## Task 6: `--maturity PATH` flag in `src/cli.py`

**Files:**
- Modify: `src/cli.py`
- Test: `tests/test_cli_flags.py`

**Interfaces:**
- Consumes: `maturity_core.assess_maturity`, `maturity_core.MIN_CONTENT_CHARS` (Tasks 1-2); `maturity_generator.MATURITY_SYSTEM_PROMPT`, `build_maturity_prompt`, `build_maturity_report_markdown`, `save_maturity_report` (Task 3).
- Produces: `--maturity PATH` argparse flag, `run_maturity_mode(agent: QAIAgent, path: str) -> None`.

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_cli_flags.py

def test_parse_args_maturity_default_is_none():
    args = cli.parse_args([])
    assert args.maturity is None


def test_parse_args_maturity_with_path():
    args = cli.parse_args(["--maturity", "description.txt"])
    assert args.maturity == "description.txt"


def test_run_maturity_mode_file_not_found_exits():
    with pytest.raises(SystemExit):
        cli.run_maturity_mode(MagicMock(), "Z:/does/not/exist.txt")


def test_run_maturity_mode_insufficient_content_returns_without_prompting(monkeypatch):
    tmp_dir = Path(tempfile.mkdtemp())
    try:
        doc_path = tmp_dir / "short.txt"
        doc_path.write_text("Too short.", encoding="utf-8")

        def _fail_if_called(*args, **kwargs):
            raise AssertionError("Prompt.ask must not be called for insufficient_content")

        monkeypatch.setattr(cli.Prompt, "ask", _fail_if_called)

        cli.run_maturity_mode(MagicMock(), str(doc_path))  # must not raise
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_cli_flags.py -k maturity -v`
Expected: FAIL with `AttributeError: 'Namespace' object has no attribute 'maturity'`

- [ ] **Step 3: Add the argparse flag**

```python
# in src/cli.py's parse_args(), after the --results argument (after line ~268)
    parser.add_argument(
        "--maturity", metavar="PATH",
        help="Assess QA process maturity from a text description or pasted document "
             "(deterministic TMMi + conditional EU AI Act score), then exit.",
    )
```

- [ ] **Step 4: Implement `run_maturity_mode()`**

```python
# in src/cli.py, after run_review_mode() (after line ~389)

def run_maturity_mode(agent: QAIAgent, path: str) -> None:
    """`--maturity PATH`: deterministic TMMi + conditional EU AI Act score
    via rich tables (maturity_core.assess_maturity(), no LLM), then an
    optional narrative assessment streamed and saved via
    maturity_generator.py's conventions — the same save path the interactive
    flow uses."""
    from maturity_core import assess_maturity, MIN_CONTENT_CHARS
    from maturity_generator import (
        MATURITY_SYSTEM_PROMPT, build_maturity_prompt,
        build_maturity_report_markdown, save_maturity_report,
    )

    doc_path = Path(path)
    if not doc_path.exists():
        console.print(f"[bold red]❌ File not found:[/bold red] {path}")
        sys.exit(1)

    text = doc_path.read_text(encoding="utf-8", errors="ignore")
    result = assess_maturity(text)

    if result.status == "insufficient_content":
        console.print(
            f"[yellow]⚠️  Description is too short to assess "
            f"({result.stats.get('char_count', 0)} characters after cleanup — "
            f"need at least {MIN_CONTENT_CHARS}).[/yellow]"
        )
        return

    console.print(Panel(
        f"[bold]QA Maturity Assessment[/bold]\n[dim]{doc_path.name} — "
        f"indicative TMMi level: {result.indicative_tmmi_level}[/dim]",
        border_style="cyan",
    ))
    console.print(f"[dim]{result.disclaimer}[/dim]\n")

    tmmi_table = Table(title="TMMi Process Area Scores", border_style="cyan", show_header=True)
    tmmi_table.add_column("Process Area", style="bold cyan")
    tmmi_table.add_column("Score", style="white")
    for dim, score in result.tmmi_dimension_scores.items():
        tmmi_table.add_row(dim.replace("_", " ").title(), f"{score}/100")
    console.print(tmmi_table)

    if result.ai_act_relevant:
        ai_table = Table(title="EU AI Act Readiness (Articles 9-15)", border_style="cyan", show_header=True)
        ai_table.add_column("Article Area", style="bold cyan")
        ai_table.add_column("Score", style="white")
        for dim, score in result.ai_act_dimension_scores.items():
            ai_table.add_row(dim.replace("_", " ").title(), f"{score}/100")
        console.print(ai_table)

    if result.findings:
        severity_style = {"critical": "bold red", "major": "yellow", "minor": "dim"}
        findings_table = Table(title="Findings", border_style="yellow", show_header=True)
        findings_table.add_column("Severity", style="bold")
        findings_table.add_column("Framework/Dimension")
        findings_table.add_column("Message")
        for finding in result.findings:
            style = severity_style.get(finding.severity, "white")
            findings_table.add_row(
                f"[{style}]{finding.severity}[/{style}]",
                f"{finding.framework}/{finding.dimension.replace('_', ' ').title()}",
                finding.message,
            )
        console.print(findings_table)
    else:
        console.print("[bold green]✅ No findings — every mechanical check in the rubric passed.[/bold green]")

    narrative = ""
    generate_narrative = Prompt.ask(
        "\n[bold]Generate a narrative assessment grounded in the QA knowledge base?[/bold]",
        choices=["yes", "no"], default="yes",
    )
    if generate_narrative == "yes":
        queries, seen = [], set()
        for finding in result.findings:
            for q in finding.citation_queries:
                if q not in seen:
                    seen.add(q)
                    queries.append(q)

        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
            progress.add_task("⚡ Retrieving grounding sources...", total=None)
            chunks = []
            for q in queries[:5]:
                chunks.extend(agent.retrieve_knowledge(q, k=1))
            if not chunks:
                chunks = agent.retrieve_knowledge("TMMi test process maturity assessment", k=5)
        knowledge_context = agent.format_knowledge_context(chunks)
        prompt = build_maturity_prompt(result, knowledge_context)

        console.print(Panel("[bold cyan]🤖 Generating Narrative Assessment...[/bold cyan]", border_style="cyan"))
        buffer = []
        with Live(console=console, refresh_per_second=8) as live:
            for chunk in agent.ask_streaming(prompt, system_prompt=MATURITY_SYSTEM_PROMPT):
                buffer.append(chunk)
                live.update(Text("".join(buffer)))
        narrative = clean_markdown_html("".join(buffer))

    report_md = build_maturity_report_markdown(result, narrative)
    output_path = save_maturity_report(report_md, doc_path.stem)
    console.print(f"\n[bold green]💾 Maturity Assessment saved to:[/bold green] [cyan]{output_path}[/cyan]")
```

- [ ] **Step 5: Wire the flag into `main()`**

Find the `if args.review:` block (line ~440-444) and add an equivalent block right after it:

```python
    if args.maturity:
        agent = _load_agent()
        console.print("[bold green]✅ Knowledge base ready![/bold green]\n")
        run_maturity_mode(agent, args.maturity)
        return
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python -m pytest tests/test_cli_flags.py -v`
Expected: PASS (all tests, including the pre-existing `--review`/`--results` ones — no regressions)

- [ ] **Step 7: Commit**

```bash
git add src/cli.py tests/test_cli_flags.py
git commit -m "$(cat <<'EOF'
feat: add --maturity PATH flag to CLI

run_maturity_mode() mirrors run_review_mode()'s shape: rich tables for
the deterministic score, then an optional narrative assessment streamed
and saved via maturity_generator.py.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_0144znX3oCn8cGtUrB88a1ZM
EOF
)"
```

---

## Task 7: Eval module `evals/maturity_integrity.py`

**Files:**
- Create: `evals/maturity_integrity.py`
- Create: `evals/maturity_golden.jsonl`
- Create: `evals/fixtures/maturity/level1_no_process.txt`
- Create: `evals/fixtures/maturity/level3_strong.txt`
- Modify: `evals/run.py`
- Modify: `evals/thresholds.py`

**Interfaces:**
- Consumes: `maturity_core.assess_maturity` (Tasks 1-2); `evals.ensure_src_on_path` (existing, `evals/__init__.py`); `evals.thresholds` (existing module, extended here).
- Produces: `evals.maturity_integrity.run_all() -> list[CheckOutcome]`, `evals.maturity_integrity.format_table(outcomes) -> str`, `evals.maturity_integrity.main() -> int`; `evals.thresholds.MATURITY_LEVEL_ORDERING_MIN_LEVEL: int`.

- [ ] **Step 1: Create the fixture files**

```text
# evals/fixtures/maturity/level1_no_process.txt
We write some code and then people click around the app to see if it
works before we ship it. Nobody has ever written a test plan or tracked
defects anywhere. If something breaks in production we fix it and move
on. There is no test environment separate from production.
```

```text
# evals/fixtures/maturity/level3_strong.txt
Our team maintains a documented test policy and test strategy defining
our test objectives, with risk-based prioritization as our generic test
approach. Every release has a test plan with estimates, a schedule, and
risk-based testing. We track defects in a defect log and report status
against the plan, taking corrective action when needed. Test design
follows structured test design techniques with clear entry criteria and
exit criteria; requirements are tracked as REQ-101, REQ-102, REQ-103. We
run everything in a dedicated test environment that is representative of
production.

We have an independent test team led by a test manager, with defined
roles and responsibilities. New testers go through a formal training
program and onboarding. A master test plan integrates test activities
from the requirements phase onward. Beyond functional checks we run
performance test, security test, and usability test cycles. Every change
goes through a peer review, including requirements review and design
review.
```

- [ ] **Step 2: Create the golden dataset**

```json
{"id": "level1_no_process", "kind": "description", "file": "maturity/level1_no_process.txt", "expect_max_level": 1}
{"id": "level3_strong", "kind": "description", "file": "maturity/level3_strong.txt", "expect_min_level": 3}
{"id": "insufficient_short_text", "kind": "description", "text": "Too short.", "expect_status": "insufficient_content"}
{"id": "ai_relevant", "kind": "description", "text": "We are building a machine learning model for loan screening, trained on historical applicant data, with a documented risk management process covering the full lifecycle.", "expect_ai_act_relevant": true}
{"id": "non_ai", "kind": "description", "text": "We test a standard e-commerce checkout flow with unit and integration tests across several sprints.", "expect_ai_act_relevant": false}
```

- [ ] **Step 3: Add the threshold constant**

```python
# add to evals/thresholds.py, after the review_integrity section

# ── maturity_integrity (v3.5 — src/maturity_core.py TMMi + EU AI Act rubric) ──
# A strongly-evidenced Level 2+3 description must reach at least this indicative
# level; a no-process description must never exceed Level 1.
MATURITY_LEVEL_ORDERING_MIN_LEVEL = 3
```

- [ ] **Step 4: Write `evals/maturity_integrity.py`**

```python
# evals/maturity_integrity.py
"""Maturity-integrity gate: deterministic checks over QAI Consultant's real shipped
src/maturity_core.py TMMi + EU AI Act rubric — nothing re-implemented. Issues surface
as failing checks, not prose; a green table means the rubric scores honestly. Keyless
and instant (no LLM, no keys, no heavy deps — maturity_core.py is stdlib-only), so it
drops straight into CI.

    python -m evals.maturity_integrity          # exits non-zero if any check fails

Golden cases live in ``maturity_golden.jsonl``; description fixtures live under
``fixtures/maturity/*.txt``.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

from . import ensure_src_on_path
from . import thresholds as T

_DIR = Path(__file__).resolve().parent


def _load_target():
    """maturity_core.py is dependency-free (stdlib only) — no stubbing needed,
    unlike estimate_integrity.py's agent.py stub."""
    ensure_src_on_path()
    from maturity_core import assess_maturity  # noqa: PLC0415
    return assess_maturity


# ── Result types ──────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Finding:
    case: str
    expected: str
    actual: str


@dataclass(frozen=True)
class CheckOutcome:
    name: str
    findings: tuple[Finding, ...]

    @property
    def passed(self) -> bool:
        return not self.findings


def _golden() -> list[dict]:
    cases = []
    for line in (_DIR / "maturity_golden.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and "id" in obj:
            cases.append(obj)
    return cases


def _case_text(case: dict) -> str:
    if "text" in case:
        return case["text"]
    return (_DIR / "fixtures" / case["file"]).read_text(encoding="utf-8")


def _cases_by_id() -> dict:
    return {c["id"]: c for c in _golden()}


# ── Checks ───────────────────────────────────────────────────────────────────────

def check_level_ordering(assess_maturity) -> tuple[Finding, ...]:
    """A strongly-evidenced description must reach at least
    T.MATURITY_LEVEL_ORDERING_MIN_LEVEL; a no-process description must never
    exceed Level 1."""
    cases = _cases_by_id()
    findings = []

    strong = cases.get("level3_strong")
    if strong:
        result = assess_maturity(_case_text(strong))
        if result.indicative_tmmi_level < T.MATURITY_LEVEL_ORDERING_MIN_LEVEL:
            findings.append(Finding(
                case="level3_strong",
                expected=f"indicative_tmmi_level >= {T.MATURITY_LEVEL_ORDERING_MIN_LEVEL}",
                actual=f"indicative_tmmi_level={result.indicative_tmmi_level}",
            ))
    else:
        findings.append(Finding("level_ordering", "level3_strong case in maturity_golden.jsonl", "missing"))

    weak = cases.get("level1_no_process")
    if weak:
        result = assess_maturity(_case_text(weak))
        if result.indicative_tmmi_level > 1:
            findings.append(Finding(
                case="level1_no_process",
                expected="indicative_tmmi_level == 1",
                actual=f"indicative_tmmi_level={result.indicative_tmmi_level}",
            ))
    else:
        findings.append(Finding("level_ordering", "level1_no_process case in maturity_golden.jsonl", "missing"))

    return tuple(findings)


def check_no_level_skip(assess_maturity) -> tuple[Finding, ...]:
    """Level-3-only keyword evidence with zero Level-2 evidence must still
    resolve to indicative level 1 — the no-skip logic must never be
    bypassable by Level-3 keyword stuffing alone."""
    level3_keywords_no_level2 = (
        "We have an independent test team, a test manager, a training program, "
        "a master test plan, performance test and security test cycles, and "
        "every change goes through a peer review and design review. " * 3
    )
    result = assess_maturity(level3_keywords_no_level2)
    if result.indicative_tmmi_level != 1:
        return (Finding(
            case="level3_keywords_no_level2",
            expected="indicative_tmmi_level == 1 (no-skip rule)",
            actual=f"indicative_tmmi_level={result.indicative_tmmi_level}",
        ),)
    return ()


def check_ai_act_gating(assess_maturity) -> tuple[Finding, ...]:
    """An AI-relevant case must populate ai_act_dimension_scores; a non-AI
    case must leave it empty — guards against false-positive compliance
    noise on ordinary projects."""
    cases = _cases_by_id()
    findings = []

    ai_case = cases.get("ai_relevant")
    if ai_case:
        result = assess_maturity(_case_text(ai_case))
        if result.ai_act_relevant is not True or not result.ai_act_dimension_scores:
            findings.append(Finding(
                case="ai_relevant",
                expected="ai_act_relevant=True with a populated ai_act_dimension_scores",
                actual=f"ai_act_relevant={result.ai_act_relevant}, "
                       f"scores={result.ai_act_dimension_scores}",
            ))
    else:
        findings.append(Finding("ai_act_gating", "ai_relevant case in maturity_golden.jsonl", "missing"))

    non_ai_case = cases.get("non_ai")
    if non_ai_case:
        result = assess_maturity(_case_text(non_ai_case))
        if result.ai_act_relevant is not False or result.ai_act_dimension_scores:
            findings.append(Finding(
                case="non_ai",
                expected="ai_act_relevant=False with an empty ai_act_dimension_scores",
                actual=f"ai_act_relevant={result.ai_act_relevant}, "
                       f"scores={result.ai_act_dimension_scores}",
            ))
    else:
        findings.append(Finding("ai_act_gating", "non_ai case in maturity_golden.jsonl", "missing"))

    return tuple(findings)


def check_determinism(assess_maturity) -> tuple[Finding, ...]:
    """assess_maturity() must return an identical MaturityResult across
    repeated calls on the same input."""
    case = _cases_by_id().get("level3_strong")
    if not case:
        return (Finding("determinism", "a level3_strong case in maturity_golden.jsonl", "missing"),)

    text = _case_text(case)
    first = assess_maturity(text)
    second = assess_maturity(text)
    if first != second:
        return (Finding(
            case="level3_strong scored twice",
            expected="identical MaturityResult on both calls",
            actual=f"first={first}, second={second}",
        ),)
    return ()


def check_insufficient_content_handling(assess_maturity) -> tuple[Finding, ...]:
    """Content under the minimum length must return
    status='insufficient_content' with level 0 — never an exception or a
    fabricated assessment of near-empty text."""
    out: list[Finding] = []
    for case in (c for c in _golden() if c.get("expect_status") == "insufficient_content"):
        result = assess_maturity(_case_text(case))
        if result.status != "insufficient_content" or result.indicative_tmmi_level != 0:
            out.append(Finding(
                case=case.get("id", "insufficient_content case"),
                expected="status='insufficient_content', indicative_tmmi_level=0",
                actual=f"status='{result.status}', indicative_tmmi_level={result.indicative_tmmi_level}",
            ))
    return tuple(out)


# ── Runner ───────────────────────────────────────────────────────────────────────

def run_all() -> list[CheckOutcome]:
    assess_maturity = _load_target()
    return [
        CheckOutcome("level_ordering", check_level_ordering(assess_maturity)),
        CheckOutcome("no_level_skip", check_no_level_skip(assess_maturity)),
        CheckOutcome("ai_act_gating", check_ai_act_gating(assess_maturity)),
        CheckOutcome("determinism", check_determinism(assess_maturity)),
        CheckOutcome("insufficient_content_handling", check_insufficient_content_handling(assess_maturity)),
    ]


def format_table(outcomes: list[CheckOutcome]) -> str:
    lines = ["", f"{'Check':<32} Result   Defects", f"{'-' * 32} -------  -------"]
    for o in outcomes:
        lines.append(f"{o.name:<32} {'pass' if o.passed else 'FAIL':<8} {len(o.findings)}")
    lines.append("")
    for o in outcomes:
        for f in o.findings:
            lines.append(f"  [{o.name}] {f.case}")
            lines.append(f"      expected: {f.expected}")
            lines.append(f"      actual:   {f.actual}")
    return "\n".join(lines)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        outcomes = run_all()
    except Exception as exc:  # noqa: BLE001 — missing/corrupt golden or fixture → report, not traceback
        print(f"\nmaturity_integrity errored (did not run): {type(exc).__name__}: {exc}")
        return 1
    print(format_table(outcomes))
    ok = all(o.passed for o in outcomes)
    total_defects = sum(len(o.findings) for o in outcomes)
    print(f"\nRelease gate: {'PASS' if ok else 'FAIL'} ({total_defects} defect(s) across "
          f"{sum(1 for o in outcomes if not o.passed)} check(s))")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Run the eval standalone to verify it passes**

Run: `python -m evals.maturity_integrity`
Expected: `Release gate: PASS (0 defect(s) across 0 check(s))` — if any check fails, fix the rubric or the fixture (whichever is wrong), never loosen the check itself just to get green.

- [ ] **Step 6: Wire `maturity_integrity` into `evals/run.py`'s always-run section**

`evals/run.py` currently reads (in full, 87 lines) with the `results_integrity` block ending at line 49, `rag_ok`/`local_index_ok` initialized at lines 51-52, and the final gate at lines 75-81. Make these three edits:

1. Insert this block immediately after line 49 (`results_ok = False`) and before line 51 (`rag_ok = True`):

```python
    from . import maturity_integrity
    print("\n══ maturity_integrity (deterministic, keyless) ══")
    try:
        maturity_outcomes = maturity_integrity.run_all()
        print(maturity_integrity.format_table(maturity_outcomes))
        maturity_ok = all(o.passed for o in maturity_outcomes)
    except Exception as exc:  # noqa: BLE001 — same rationale as estimate_integrity above
        print(f"[maturity_integrity] tier errored (did not run): {type(exc).__name__}: {exc}")
        maturity_ok = False
```

2. Replace line 75:

```python
    overall = det_ok and review_ok and results_ok and rag_ok and local_index_ok
```

with:

```python
    overall = det_ok and review_ok and results_ok and maturity_ok and rag_ok and local_index_ok
```

3. Replace lines 76-81:

```python
    print(f"\nRelease gate: {'PASS' if overall else 'FAIL'} "
          f"(deterministic {'pass' if det_ok else 'FAIL'}"
          f", review {'pass' if review_ok else 'FAIL'}"
          f", results {'pass' if results_ok else 'FAIL'}"
          + ("" if det_only else f", rag {'pass' if rag_ok else 'FAIL'}"
                                  f", local_index_parity {'pass' if local_index_ok else 'FAIL'}") + ")")
```

with:

```python
    print(f"\nRelease gate: {'PASS' if overall else 'FAIL'} "
          f"(deterministic {'pass' if det_ok else 'FAIL'}"
          f", review {'pass' if review_ok else 'FAIL'}"
          f", results {'pass' if results_ok else 'FAIL'}"
          f", maturity {'pass' if maturity_ok else 'FAIL'}"
          + ("" if det_only else f", rag {'pass' if rag_ok else 'FAIL'}"
                                  f", local_index_parity {'pass' if local_index_ok else 'FAIL'}") + ")")
```

- [ ] **Step 7: Run the full det-tier gate to verify wiring**

Run: `python -m evals.run --det`
Expected: `maturity_integrity` section appears in the output, `PASS`, and the overall det-tier exit code is 0.

- [ ] **Step 8: Commit**

```bash
git add evals/maturity_integrity.py evals/maturity_golden.jsonl evals/fixtures/maturity/ evals/run.py evals/thresholds.py
git commit -m "$(cat <<'EOF'
feat: add maturity_integrity tier-1 eval

Guards maturity_core.py's rubric: level ordering, the no-skip rule,
EU AI Act relevance gating, determinism, and insufficient-content
handling. Wired into evals/run.py's always-run section, so it runs
under the existing evals-det CI gate with no workflow changes.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_0144znX3oCn8cGtUrB88a1ZM
EOF
)"
```

---

## Task 8: Release Checklist — v3.5.0

**Files:**
- Modify: `src/version.py`
- Modify: `pyproject.toml`
- Modify: `CHANGELOG.md`
- Modify: `README.md`
- Modify: `README_MCP.md`
- Modify: `CLAUDE.md`
- Modify: `tests/test_packaging.py`

**Interfaces:**
- Consumes: nothing new — this task only updates metadata/docs to reflect Tasks 1-7's shipped code.
- Produces: a coherent v3.5.0 release matching the existing Release Checklist convention.

- [ ] **Step 1: Bump `src/version.py`**

```python
__version__ = "3.5.0"
__release_date__ = "<today's actual date, YYYY-MM-DD>"
```

- [ ] **Step 2: Update `pyproject.toml`**

Bump `[project] version` to `"3.5.0"` (line ~7). Add `"maturity_core"` to the `py-modules` list (line ~173-177), keeping the existing alphabetical-ish grouping style:

```toml
py-modules = [
    "mcp_server", "dialogue", "effort_core", "local_index",
    "telemetry", "prompts", "kb_config", "logger", "version",
    "review_core", "results_core", "maturity_core",
]
```

Do NOT add `maturity_generator` here — it stays Streamlit/CLI-only, same as `review_generator`/`risk_analyzer`/etc., none of which are in this list.

- [ ] **Step 3: Update `tests/test_packaging.py`'s whitelist**

```python
_EXPECTED_PY_MODULES = {
    "mcp_server.py", "dialogue.py", "effort_core.py", "local_index.py",
    "telemetry.py", "prompts.py", "kb_config.py", "logger.py", "version.py",
    "review_core.py", "results_core.py", "maturity_core.py",
}
```

Run: `python -m pytest tests/test_packaging.py -v`
Expected: PASS (the wheel-build test now expects `maturity_core.py` and finds it, since Step 2 added it to `py-modules`)

- [ ] **Step 4: Add the `CHANGELOG.md` entry**

Add at the top, following the exact format of the existing `v3.4.4` entry immediately below it:

```markdown
## [3.5.0] - <today's actual date, YYYY-MM-DD>

### Added
- **QA Maturity Assessment** (`assess_qa_maturity`) — a deterministic, dependency-free process-maturity signal, closing the gap left open when this tool was deferred in v3.1 (see `MCP_PLAN.md` §2). Scores 10 TMMi process areas (Level 2 Managed + Level 3 Defined) from a free-text process description or a pasted existing document, and returns an *informal, indicative* TMMi level (1-3 — never a certified 4 or 5, per TMMi's own no-skip rule). When the description signals an AI/ML system, also scores 7 EU AI Act Articles 9-15 readiness checks; otherwise that dimension is omitted rather than falsely scored. Available as:
  - an MCP tool (`assess_qa_maturity`, deterministic-only, no LLM)
  - a Streamlit mode ("📈 Assess QA Maturity", with an LLM narrative + PDF/.md download, mirroring Document Review)
  - a CLI flag (`--maturity PATH`)
- New tier-1 eval `maturity_integrity` (level ordering, no-skip rule, EU AI Act gating, determinism, insufficient-content handling), wired into the existing `evals-det` CI gate.
```

- [ ] **Step 5: Update `README.md`**

Line 21 — replace the version badge:

```markdown
![Version](https://img.shields.io/badge/version-3.5.0-green.svg)
```

Line 231 (the `analyze_test_results` row, last row of the tools table) — insert a new row immediately after it:

```markdown
| `assess_qa_maturity` | Deterministic indicative TMMi process-maturity level (1-3, never a certified 4-5) from a free-text description, plus a conditional EU AI Act Articles 9-15 readiness score when the input signals an AI/ML system |
```

Line 272 (after the `v3.1.4` bullet, before whatever `v3.1.5`/next bullet follows it) — insert a new roadmap bullet in the same style:

```markdown
- **v3.5.0** ✅ QA Maturity Assessment (`assess_qa_maturity`) — deterministic TMMi process-maturity signal (10 process areas, indicative level 1-3) plus a conditional EU AI Act Articles 9-15 readiness score for AI/ML projects; available in the web app ("📈 Assess QA Maturity"), CLI (`--maturity`), and the MCP server (`assess_qa_maturity`)
```

- [ ] **Step 6: Update `README_MCP.md`**

Line 15 — the description paragraph already ends in "...QA document quality review, and test-results health analysis"; extend it:

```markdown
A local, fully keyless [MCP](https://modelcontextprotocol.io) server: standards-grounded QA knowledge retrieval (ISTQB, OWASP, IEEE, ISO, EU AI Act), deterministic QA effort estimation, QA document quality review, test-results health analysis, and QA process maturity assessment — callable directly from Claude Code, Claude Desktop, or claude.ai.
```

Line 54 (the `analyze_test_results` row, last row of the tools table) — insert a new row immediately after it:

```markdown
| `assess_qa_maturity` | Deterministic indicative TMMi process-maturity level (1-3, never a certified 4-5) from a free-text description or pasted document, plus a conditional 7-check EU AI Act Articles 9-15 readiness score when the input signals an AI/ML system — no LLM anywhere in this tool |
```

Also update `src/mcp_server.py`'s `pyproject.toml` `[project] description` (line 8, already partially covers this — confirm it still reads naturally after Task 4's tool addition; if it enumerates specific tool behaviors rather than staying generic, append "and QA process maturity assessment" to match the pattern above).

- [ ] **Step 7: Update `CLAUDE.md`**

Add two new rows to the `### Source Files (src/)` architecture table (in the same relative position as `review_core.py`/`review_generator.py`'s rows, i.e. near `results_core.py`):

```markdown
| `maturity_core.py` | (v3.5) Deterministic, dependency-free QA process-maturity assessment: `assess_maturity(text)` scores 10 TMMi Level 2/3 process areas from a free-text description or pasted document, returning an indicative TMMi level (1-3, never 4-5 per TMMi's own no-skip/no-certification rule) plus a conditional 7-check EU AI Act Articles 9-15 readiness dimension (only scored when the input signals an AI/ML system — otherwise omitted, not scored as a false 0). Findings carry `citation_queries`, resolved to KB citations by the caller (MCP via `LocalIndex`, Streamlit/CLI via `retrieve_knowledge()`). No LLM, no agent import — same import-graph tier as `review_core.py`/`results_core.py` |
| `maturity_generator.py` | (v3.5) LLM narrative + save() for `maturity_core.py`'s output — mirrors `review_generator.py`'s shape (`build_maturity_prompt()`, `build_maturity_report_markdown()`, `save_maturity_report()`) so `cli.py --maturity` and `app.py`'s maturity mode share one prompt/save path. Streamlit/CLI only, not in the MCP server's import graph |
```

In the `mcp_server.py` architecture-table row, append to the tool list: ", and `assess_qa_maturity` (deterministic TMMi + conditional EU AI Act readiness assessment, resolves `citation_queries` via `LocalIndex`)". In the `app.py` row, append: "; v3.5 adds a `maturity` step (`render_maturity_assessment()`) with its own `MATURITY_MODE_STATE_KEYS` cleanup list wired the same way as `REVIEW_MODE_STATE_KEYS`". In the `cli.py` row, append: "`--maturity path/to/description.txt` (v3.5) mirrors `--review`'s shape for the QA Maturity Assessment".

Add this bullet to the Roadmap section, immediately after the `v3.4.4` entry:

```markdown
- **v3.5.0** ✅ QA Maturity Assessment (`assess_qa_maturity`) — the tool `MCP_PLAN.md` §2 deferred in v3.1 for lacking a specified rubric now ships: `src/maturity_core.py` (deterministic, dependency-free, no LLM) scores 10 TMMi process areas (Level 2 Managed + Level 3 Defined) from a free-text process description or pasted document, returning an *informal, indicative* TMMi level (1-3 — never a certified 4 or 5, per `TMMi_Test_Maturity_Model.md`'s own no-skip/no-certification rule) plus a conditional 7-check EU AI Act Articles 9-15 readiness dimension, gated on AI/ML relevance detection so non-AI projects never see a false compliance-gap score (`risk_management`/`human_oversight` findings are `critical`, the rest `major`, per `EU_AI_Act_Overview.md`). `src/maturity_generator.py` mirrors `review_generator.py`'s shape (LLM narrative + `save()`, Streamlit/CLI only). Shipped on all three surfaces: an MCP tool (`assess_qa_maturity`, deterministic-only — no LLM, per the "MCP lens"), a Streamlit mode ("📈 Assess QA Maturity", mirroring `render_doc_review()`'s two-step instant-score-then-narrative shape), and a CLI flag (`--maturity PATH`). New tier-1 eval `evals/maturity_integrity.py` (level ordering, the no-skip rule, EU AI Act gating, determinism, insufficient-content handling) wired into `evals/run.py`'s always-run section, so it runs under the existing `evals-det` CI gate with no workflow changes. Design spec: `docs/superpowers/specs/2026-09-09-assess-qa-maturity-design.md`.
```

Replace `MCP_PLAN.md`'s entire §2 section (currently: `## 2. Deferred: QA maturity audit tool` followed by the `assess_qa_maturity(project_description, focus_areas=None)` paragraph and the "Acceptance" line) with:

```markdown
## 2. Shipped: QA maturity audit tool

`assess_qa_maturity` shipped in v3.5.0 — see CLAUDE.md's Roadmap entry for that version for what was actually built. The rubric (TMMi process areas + a conditional EU AI Act Articles 9-15 dimension) and the full design rationale live in `docs/superpowers/specs/2026-09-09-assess-qa-maturity-design.md`.
```

- [ ] **Step 8: Run the full test suite**

Run: `python -m pytest tests/ -v`
Expected: PASS, no regressions (in particular `tests/test_changelog.py` must pass, confirming `version.py`'s `__version__` matches `CHANGELOG.md`'s top heading)

- [ ] **Step 9: Run the full det-tier eval gate**

Run: `python -m evals.run --det`
Expected: PASS

- [ ] **Step 10: Commit**

```bash
git add src/version.py pyproject.toml CHANGELOG.md README.md README_MCP.md CLAUDE.md MCP_PLAN.md tests/test_packaging.py
git commit -m "$(cat <<'EOF'
chore: release v3.5.0 — QA Maturity Assessment (assess_qa_maturity)

Full Release Checklist: version.py, pyproject.toml (version +
maturity_core.py added to the MCP py-modules whitelist), CHANGELOG.md,
README.md, README_MCP.md, CLAUDE.md, and MCP_PLAN.md's deferred-tool
note updated to point at the shipped feature.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_0144znX3oCn8cGtUrB88a1ZM
EOF
)"
```

**Not done here (left for explicit user confirmation, per this repo's standing convention for every prior release):** git tag, GitHub release, and PyPI publish of `qai-consultant-mcp`. Push to a remote branch and PR creation are also left for the user to request explicitly.
