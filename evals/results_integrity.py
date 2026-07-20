"""Results-integrity gate: deterministic checks over QAI Consultant's real shipped
src/results_core.py test-results health analysis (flaky / ever-failing / failure
clustering / malformed input / CSV-XML parity) — nothing re-implemented. Issues
surface as failing checks, not prose; a green table means the analysis is honest.
Keyless and instant (no LLM, no keys, no heavy deps — results_core.py is
stdlib-only), so it drops straight into CI.

    python -m evals.results_integrity          # exits non-zero if any check fails

Golden cases live in ``results_golden.jsonl``; JUnit XML/CSV fixtures live under
``fixtures/results/*``.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

from . import ensure_src_on_path

_DIR = Path(__file__).resolve().parent


def _load_target():
    """results_core.py is dependency-free (stdlib only) — no stubbing needed,
    unlike estimate_integrity.py's agent.py stub."""
    ensure_src_on_path()
    from results_core import analyze, parse_junit_xml, parse_results_csv  # noqa: PLC0415
    return analyze, parse_junit_xml, parse_results_csv


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
    """Parse results_golden.jsonl once; skip blank and malformed lines rather than
    letting one bad appended line crash every check."""
    cases = []
    for line in (_DIR / "results_golden.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and "kind" in obj:
            cases.append(obj)
    return cases


def _read_fixture(rel_path: str) -> str:
    return (_DIR / "fixtures" / rel_path).read_text(encoding="utf-8")


def _case(kind: str) -> dict | None:
    return next((c for c in _golden() if c.get("kind") == kind), None)


# ── Checks ───────────────────────────────────────────────────────────────────────

def check_flaky_and_ever_failing_boundaries(analyze, parse_junit_xml) -> tuple[Finding, ...]:
    """Hand-computed pass rates across 3 runs must classify each test identity
    correctly: flaky (pass rate strictly inside the band, >=3 executions),
    ever-failing (zero passes, >=3 executions), or neither — a test with only
    1 execution is insufficient data, not flaky (Testomat.io semantics)."""
    case = _case("multi_run")
    if case is None:
        return (Finding(
            case="flaky_and_ever_failing_boundaries",
            expected="a 'multi_run' case in results_golden.jsonl",
            actual="missing",
        ),)

    records = []
    for i, rel_path in enumerate(case["files"], start=1):
        records.extend(parse_junit_xml(_read_fixture(rel_path), run_id=f"run{i}"))
    analysis = analyze(records)

    flaky_ids = {f["test"] for f in analysis.flaky}
    ever_failing_ids = {f["test"] for f in analysis.ever_failing}
    out: list[Finding] = []

    for expected_id in case["expect_flaky"]:
        if expected_id not in flaky_ids:
            out.append(Finding(
                case=f"expected flaky: {expected_id}",
                expected="present in flaky[]",
                actual=f"flaky={sorted(flaky_ids)}",
            ))
    for expected_id in case["expect_ever_failing"]:
        if expected_id not in ever_failing_ids:
            out.append(Finding(
                case=f"expected ever-failing: {expected_id}",
                expected="present in ever_failing[]",
                actual=f"ever_failing={sorted(ever_failing_ids)}",
            ))
    for not_flagged_id in case.get("expect_not_flagged", []):
        if not_flagged_id in flaky_ids or not_flagged_id in ever_failing_ids:
            out.append(Finding(
                case=f"expected NOT flagged: {not_flagged_id}",
                expected="absent from both flaky[] and ever_failing[]",
                actual=f"flaky={sorted(flaky_ids)}, ever_failing={sorted(ever_failing_ids)}",
            ))
    return tuple(out)


def check_cluster_count(analyze, parse_junit_xml) -> tuple[Finding, ...]:
    """A fixture with N distinct failure-message families must cluster into
    exactly N failure_clusters — the deterministic string-normalization
    signature (numbers/hex/paths/quotes replaced with placeholders) must
    group same-family messages together and keep different families apart."""
    case = _case("clusters")
    if case is None:
        return (Finding(
            case="cluster_count",
            expected="a 'clusters' case in results_golden.jsonl",
            actual="missing",
        ),)

    records = parse_junit_xml(_read_fixture(case["file"]), run_id="run1")
    analysis = analyze(records)

    expected = case["expect_cluster_count"]
    actual = len(analysis.failure_clusters)
    if actual != expected:
        return (Finding(
            case=case.get("id", "cluster fixture"),
            expected=f"{expected} failure clusters",
            actual=f"{actual} failure clusters: {[c['signature'] for c in analysis.failure_clusters]}",
        ),)
    return ()


def check_malformed_input_never_crashes(analyze, parse_junit_xml) -> tuple[Finding, ...]:
    """Malformed XML must never raise to the caller — parse_junit_xml()
    returns [] and analyze() on an empty list returns a zeroed, valid
    ResultsAnalysis rather than crashing the whole pipeline."""
    case = _case("malformed")
    if case is None:
        return (Finding(
            case="malformed_input_never_crashes",
            expected="a 'malformed' case in results_golden.jsonl",
            actual="missing",
        ),)

    try:
        records = parse_junit_xml(_read_fixture(case["file"]), run_id="run1")
        analysis = analyze(records)
    except Exception as exc:  # noqa: BLE001 — this IS the defect being checked for
        return (Finding(
            case=case.get("id", "malformed fixture"),
            expected="no exception; empty/zeroed ResultsAnalysis",
            actual=f"{type(exc).__name__}: {exc}",
        ),)

    if records or analysis.executions != 0:
        return (Finding(
            case=case.get("id", "malformed fixture"),
            expected="0 records parsed from malformed XML",
            actual=f"{len(records)} records, {analysis.executions} executions",
        ),)
    return ()


def check_csv_xml_parity(analyze, parse_junit_xml, parse_results_csv) -> tuple[Finding, ...]:
    """The same logical test-execution data expressed as JUnit XML vs CSV
    must produce an identical analyze() result — the two parsers must agree,
    not just individually look reasonable."""
    case = _case("parity")
    if case is None:
        return (Finding(
            case="csv_xml_parity",
            expected="a 'parity' case in results_golden.jsonl",
            actual="missing",
        ),)

    xml_records = parse_junit_xml(_read_fixture(case["xml_file"]), run_id="run1")
    csv_records = parse_results_csv(_read_fixture(case["csv_file"]))
    xml_analysis = analyze(xml_records)
    csv_analysis = analyze(csv_records)

    if xml_analysis != csv_analysis:
        return (Finding(
            case=case.get("id", "parity fixture"),
            expected="analyze(xml_records) == analyze(csv_records)",
            actual=f"xml={xml_analysis}, csv={csv_analysis}",
        ),)
    return ()


# ── Runner ───────────────────────────────────────────────────────────────────────

def run_all() -> list[CheckOutcome]:
    analyze, parse_junit_xml, parse_results_csv = _load_target()
    return [
        CheckOutcome("flaky_and_ever_failing_boundaries",
                      check_flaky_and_ever_failing_boundaries(analyze, parse_junit_xml)),
        CheckOutcome("cluster_count", check_cluster_count(analyze, parse_junit_xml)),
        CheckOutcome("malformed_input_never_crashes",
                      check_malformed_input_never_crashes(analyze, parse_junit_xml)),
        CheckOutcome("csv_xml_parity", check_csv_xml_parity(analyze, parse_junit_xml, parse_results_csv)),
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
        print(f"\nresults_integrity errored (did not run): {type(exc).__name__}: {exc}")
        return 1
    print(format_table(outcomes))
    ok = all(o.passed for o in outcomes)
    total_defects = sum(len(o.findings) for o in outcomes)
    print(f"\nRelease gate: {'PASS' if ok else 'FAIL'} ({total_defects} defect(s) across "
          f"{sum(1 for o in outcomes if not o.passed)} check(s))")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
