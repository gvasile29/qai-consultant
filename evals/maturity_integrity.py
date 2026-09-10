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


def check_negation_not_counted_as_evidence(assess_maturity) -> tuple[Finding, ...]:
    """A description that explicitly denies having a process element (e.g.
    "we have no test policy") must not have that denial scored as evidence
    of the element's presence — guards against naive substring keyword
    matching inverting the ranking for exactly the input shape this tool
    most invites (a team describing what they lack)."""
    case = _cases_by_id().get("level1_explicit_denial")
    if not case:
        return (Finding("negation_not_counted_as_evidence",
                         "level1_explicit_denial case in maturity_golden.jsonl", "missing"),)

    result = assess_maturity(_case_text(case))
    if result.indicative_tmmi_level != 1:
        return (Finding(
            case="level1_explicit_denial",
            expected="indicative_tmmi_level == 1 (negated keywords must not count as evidence)",
            actual=f"indicative_tmmi_level={result.indicative_tmmi_level}",
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
        CheckOutcome("negation_not_counted_as_evidence", check_negation_not_counted_as_evidence(assess_maturity)),
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
