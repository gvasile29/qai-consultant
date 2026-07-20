"""Review-integrity gate: deterministic checks over QAI Consultant's real shipped
src/review_core.py QA Document Quality Review rubric — nothing re-implemented.
Issues surface as failing checks, not prose; a green table means the rubric scores
honestly. Keyless and instant (no LLM, no keys, no heavy deps — review_core.py is
stdlib-only), so it drops straight into CI.

    python -m evals.review_integrity          # exits non-zero if any check fails

Golden cases live in ``review_golden.jsonl``; document fixtures live under
``fixtures/review/*.md``.
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
    """review_core.py is dependency-free (stdlib only) — no stubbing needed,
    unlike estimate_integrity.py's agent.py stub."""
    ensure_src_on_path()
    from review_core import review_document  # noqa: PLC0415
    return review_document


# ── Result types ──────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Finding:
    """One concrete defect: what was tried, what was expected, what came back."""

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
    """Parse review_golden.jsonl once; skip blank and malformed lines rather than
    letting one bad appended line crash every check."""
    cases = []
    for line in (_DIR / "review_golden.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and "kind" in obj:
            cases.append(obj)
    return cases


def _case_text(case: dict) -> str:
    if "text" in case:
        return case["text"]
    return (_DIR / "fixtures" / case["file"]).read_text(encoding="utf-8")


def _document_cases() -> dict:
    return {c["id"]: c for c in _golden() if c.get("kind") == "document"}


# ── Checks ───────────────────────────────────────────────────────────────────────

def check_score_ordering(review_document) -> tuple[Finding, ...]:
    """A strong, IEEE-829-shaped test plan must score at least
    T.REVIEW_SCORE_ORDERING_DELTA_MIN points above a deliberately weak one."""
    cases = _document_cases()
    strong, weak = cases.get("strong_test_plan"), cases.get("weak_test_plan")
    if not strong or not weak:
        return (Finding(
            case="score_ordering",
            expected="strong_test_plan and weak_test_plan cases in review_golden.jsonl",
            actual="one or both missing",
        ),)

    strong_result = review_document(_case_text(strong), doc_type=strong.get("doc_type", "auto"))
    weak_result = review_document(_case_text(weak), doc_type=weak.get("doc_type", "auto"))
    delta = strong_result.overall_score - weak_result.overall_score

    if delta < T.REVIEW_SCORE_ORDERING_DELTA_MIN:
        return (Finding(
            case="strong vs weak test plan",
            expected=f"strong score >= weak score + {T.REVIEW_SCORE_ORDERING_DELTA_MIN}",
            actual=f"strong={strong_result.overall_score}, weak={weak_result.overall_score} (delta={delta})",
        ),)
    return ()


def check_dimension_attribution(review_document) -> tuple[Finding, ...]:
    """A document whose expected-result statements are all vague must have
    measurability as its lowest-scoring dimension — the rubric must attribute
    the defect to the right dimension, not just dock the overall score."""
    case = _document_cases().get("vague_measurability")
    if not case:
        return (Finding(
            case="dimension_attribution",
            expected="a vague_measurability case in review_golden.jsonl",
            actual="missing",
        ),)

    result = review_document(_case_text(case), doc_type=case.get("doc_type", "auto"))
    expected_lowest = case["expect_lowest_dimension"]
    actual_lowest = min(result.dimension_scores, key=result.dimension_scores.get)

    if actual_lowest != expected_lowest:
        return (Finding(
            case="vague_measurability fixture",
            expected=f'lowest-scoring dimension = "{expected_lowest}"',
            actual=f'lowest-scoring dimension = "{actual_lowest}" (scores: {result.dimension_scores})',
        ),)
    return ()


def check_determinism(review_document) -> tuple[Finding, ...]:
    """review_document() must return an identical ReviewResult across repeated
    calls on the same input — determinism is the whole contract (V3.1_PLAN.md
    section 1: "same input, same score / same metrics, always")."""
    case = _document_cases().get("strong_test_plan")
    if not case:
        return (Finding(
            case="determinism",
            expected="a strong_test_plan case in review_golden.jsonl",
            actual="missing",
        ),)

    text = _case_text(case)
    doc_type = case.get("doc_type", "auto")
    first = review_document(text, doc_type=doc_type)
    second = review_document(text, doc_type=doc_type)

    if first != second:
        return (Finding(
            case="strong_test_plan scored twice",
            expected="identical ReviewResult on both calls",
            actual=f"first={first}, second={second}",
        ),)
    return ()


def check_insufficient_content_handling(review_document) -> tuple[Finding, ...]:
    """Content under the minimum length must return
    doc_type='insufficient_content' with a zero score — a structured result,
    never an exception or a fabricated review of near-empty text."""
    out: list[Finding] = []
    for case in (c for c in _golden() if c.get("expect_doc_type") == "insufficient_content"):
        result = review_document(_case_text(case), doc_type=case.get("doc_type", "auto"))
        if result.doc_type != "insufficient_content" or result.overall_score != 0:
            out.append(Finding(
                case=case.get("id", "insufficient_content case"),
                expected='doc_type="insufficient_content", overall_score=0',
                actual=f'doc_type="{result.doc_type}", overall_score={result.overall_score}',
            ))
    return tuple(out)


# ── Runner ───────────────────────────────────────────────────────────────────────

def run_all() -> list[CheckOutcome]:
    review_document = _load_target()
    return [
        CheckOutcome("score_ordering", check_score_ordering(review_document)),
        CheckOutcome("dimension_attribution", check_dimension_attribution(review_document)),
        CheckOutcome("determinism", check_determinism(review_document)),
        CheckOutcome("insufficient_content_handling", check_insufficient_content_handling(review_document)),
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
        sys.stdout.reconfigure(encoding="utf-8")  # findings contain non-ASCII; don't crash on cp1252/ascii
    try:
        outcomes = run_all()
    except Exception as exc:  # noqa: BLE001 — missing/corrupt golden or fixture → report, not traceback
        print(f"\nreview_integrity errored (did not run): {type(exc).__name__}: {exc}")
        return 1
    print(format_table(outcomes))
    ok = all(o.passed for o in outcomes)
    total_defects = sum(len(o.findings) for o in outcomes)
    print(f"\nRelease gate: {'PASS' if ok else 'FAIL'} ({total_defects} defect(s) across "
          f"{sum(1 for o in outcomes if not o.passed)} check(s))")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
