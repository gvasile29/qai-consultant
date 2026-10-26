"""
QAI Consultant -- deterministic validation of the generated documents.

`output_guards.lint_output` checks one document's prose for honesty problems.
This module checks what it cannot see: whether a generated Strategy / Test Plan
is structurally sound (scored by the project's own `review_core` rubric) and
whether the four documents agree with each other (risk IDs, risk levels,
effort totals). Pure stdlib plus the dependency-free core modules; no LLM.

Signal note: the generators already strip unknown Test Plan risk IDs and rewrite
Strategy effort totals after generation, so those two checks are regression guards
for that post-processing. The Strategy unknown-ID, re-rating and Critical-coverage
checks, and the review score, are the ones that judge raw model output.

Used by `scripts/llm_e2e_smoke.py` as the live release gate. The thresholds
were calibrated on real saved runs (strategies 79-85, test plans 81-90 overall;
structure_completeness 92-100, risk_coverage 100).
"""

import re
from typing import Optional

from qai_consultant.core.review_core import review_document
from qai_consultant.generation.consistency import effort_facts, enforce_effort_totals, risk_ledger

# Floors sit ~9 points under the lowest real run so judge-free rubric noise does not
# flap the gate, while a stripped-down document (the failure we care about) still fails.
MIN_OVERALL_SCORE = 70
# Only dimensions that are stable at 90+ on real output get a floor of their own.
# traceability scores 0 on every real Strategy and measurability varies 60-100, so
# gating on them would fail good documents.
MIN_DIMENSION_SCORES = {"structure_completeness": 80, "risk_coverage": 60}

_LEVELS = ("critical", "high", "medium", "low")
_ID_RE = re.compile(r"\bR\d{2}\b")
_LEVEL_WORD = r"(Critical|High|Medium|Low)"
# Only unambiguous level assertions: "R03 (High)" or "R03 ... rated/level: High". A bare
# "R02: High availability" or a table priority cell is not a re-rating.
_INLINE_LEVEL_RE = re.compile(
    rf"\b(R\d{{2}})\b(?:\s*\(\s*{_LEVEL_WORD}\s*\)|[^\n|.;]{{0,40}}?\b(?:rated|rating|level)\s*[:=]?\s*{_LEVEL_WORD}\b)",
    re.IGNORECASE,
)
_LEVEL_HEADER_RE = re.compile(r"^(?:risk\s+)?level$", re.IGNORECASE)


def review_problems(text: str, doc_type: str) -> list:
    """Problems found by scoring `text` with the review rubric. [] when it passes."""
    result = review_document(text or "", doc_type)
    if result.status != "ok":
        return [f"review rubric could not score it: {result.status}"]
    problems = []
    if result.overall_score < MIN_OVERALL_SCORE:
        weakest = sorted(result.dimension_scores.items(), key=lambda kv: kv[1])[:2]
        problems.append(
            f"review score {result.overall_score} < {MIN_OVERALL_SCORE} "
            f"(weakest: {', '.join(f'{k}={v}' for k, v in weakest)})"
        )
    for dim, floor in MIN_DIMENSION_SCORES.items():
        score = result.dimension_scores[dim]
        if score < floor:
            problems.append(f"{dim} {score} < {floor}")
    return problems


def _ledger_levels(ledger: list) -> dict:
    return {r["risk_id"]: r["risk_level"].strip().lower() for r in ledger if r.get("risk_id")}


def _table_row_id(line: str) -> Optional[str]:
    """The risk ID leading a markdown table row, if any."""
    if not line.lstrip().startswith("|"):
        return None
    cells = [c.strip(" *") for c in line.strip().strip("|").split("|")]
    return cells[0] if cells and _ID_RE.fullmatch(cells[0]) else None


def _rerating_problems(label: str, text: str, levels: dict) -> list:
    """A Strategy/Plan must not re-rate a risk the register rated. Two shapes are
    checked, both low false-positive: an ID with its level asserted beside it, and an
    ID-led table row whose cell under a "Risk Level" header differs from the register."""
    problems = []
    for match in _INLINE_LEVEL_RE.finditer(text):
        rid, level = match.group(1), match.group(2) or match.group(3)
        expected = levels.get(rid)
        if expected and level.lower() != expected:
            problems.append(f"{label}: {rid} written as {level} but the Risk Register rates it {expected.title()}")
    level_col = None  # column index of the "Risk Level" header of the table being read
    for line in text.splitlines():
        if not line.lstrip().startswith("|"):
            level_col = None
            continue
        cells = [c.strip(" *") for c in line.strip().strip("|").split("|")]
        header = [i for i, c in enumerate(cells) if _LEVEL_HEADER_RE.match(c)]
        if header:
            level_col = header[0]
            continue
        expected = levels.get(_table_row_id(line) or "")
        if expected and level_col is not None and level_col < len(cells):
            shown = cells[level_col].lower()
            if shown in _LEVELS and shown != expected:
                problems.append(f"{label}: table row for {cells[0]} shows {cells[level_col]} but the Risk Register rates it {expected.title()}")
    return problems


def consistency_problems(risk_register: str, strategy: str, test_plan: str, effort_data=None) -> list:
    """Cross-document disagreements. Skips a check, never fails it, when its input
    is missing (a failed pipeline step must not also read as an inconsistency)."""
    problems = []
    ledger = risk_ledger(risk_register)
    levels = _ledger_levels(ledger)
    if levels:
        for label, text in (("Strategy", strategy), ("Test Plan", test_plan)):
            if not text:
                continue
            unknown = sorted(set(_ID_RE.findall(text)) - set(levels))
            if unknown:
                problems.append(f"{label}: risk ID(s) not in the Risk Register: {', '.join(unknown)}")
            problems += _rerating_problems(label, text, levels)
        if test_plan:
            plan_ids = set(_ID_RE.findall(test_plan))
            missing = sorted(rid for rid, lvl in levels.items() if lvl == "critical" and rid not in plan_ids)
            if missing:
                problems.append(f"Test Plan: Critical risk(s) never referenced: {', '.join(missing)}")
    facts = effort_facts(effort_data)
    if facts and strategy and enforce_effort_totals(strategy, facts) != strategy:
        problems.append("Strategy: a QA total in Resources differs from the Effort report's PERT/range/capacity figures")
    return problems
