"""
QAI Consultant — Deterministic Test Results Analysis Core (v3.1).

Dependency-free (stdlib only: xml.etree.ElementTree, csv, io, re, dataclasses,
collections) so this module is importable from the MCP server path (no
agent.py/Pinecone/Streamlit in its import graph) and trivially unit-testable.

No file I/O here — callers read files (or receive them over MCP) and pass
the raw string content in; this module only parses strings and computes
metrics (Testomat.io-inspired: flaky / never-run / ever-failing / slowest /
failure clustering), fully deterministic — same input always yields the
same output.
"""

from __future__ import annotations

import csv
import io
import re
import xml.etree.ElementTree as ET  # ET.ParseError only -- parsing itself uses defusedxml below (B314)
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional, cast

import defusedxml.ElementTree as DefusedET

VALID_STATUSES = ("passed", "failed", "error", "skipped")


@dataclass
class TestRecord:
    """One test executed in one run."""
    run_id: str
    name: str
    classname: str
    status: str          # "passed" | "failed" | "error" | "skipped"
    duration_s: float
    message: str = ""     # failure/error message, "" otherwise


@dataclass
class ResultsAnalysis:
    runs: int
    total_tests: int              # distinct test identities
    executions: int
    overall_pass_rate: float      # passed / (passed + failed + error); skipped executions are excluded
    flaky: list = field(default_factory=list)             # [{"test", "pass_rate", "runs"}]
    ever_failing: list = field(default_factory=list)       # [{"test", "runs"}]
    never_run: list = field(default_factory=list)          # [{"test"}] — only when reference_tests given
    slowest: list = field(default_factory=list)            # [{"test", "mean_s", "max_s"}]
    failure_clusters: list = field(default_factory=list)   # [{"signature", "count", "sample_tests", "sample_message"}]
    per_run: list = field(default_factory=list)            # [{"run_id", "passed", "failed", "skipped", "duration_s"}]
    warnings: list = field(default_factory=list)           # parsing issues, ignored files, etc.
    skipped_executions: int = 0                              # executions with status "skipped" (never counted as failures)
    skipped: list = field(default_factory=list)            # [{"test", "skipped", "runs"}] tests with >= 1 skipped execution
    mixed_outcome: list = field(default_factory=list)      # [{"test", "passed", "failed", "runs", "pass_rate", "note"}] passed AND failed, not (yet) classified flaky


# ── Test identity normalization ───────────────────────────────────────────────

_PARAM_SUFFIX_RE = re.compile(r"\[[^\]]*\]\s*$")


def _normalize_identity_string(raw: str) -> str:
    """Strip a trailing parametrized-test `[...]` block and normalize whitespace,
    so `test_foo[case1]` and `test_foo[case2]` group under the same identity."""
    stripped = _PARAM_SUFFIX_RE.sub("", raw.strip())
    return " ".join(stripped.split())


def _test_identity(record: TestRecord) -> str:
    """classname + '::' + name, normalized (see _normalize_identity_string)."""
    classname = " ".join(record.classname.split())
    name = _normalize_identity_string(record.name)
    return f"{classname}::{name}" if classname else name


# ── JUnit XML parsing ──────────────────────────────────────────────────────────

def parse_junit_xml(content: str, run_id: str) -> list[TestRecord]:
    """Parse a JUnit XML report (accepts both <testsuites> and a bare
    <testsuite> root) into a list of TestRecord for the given run_id.

    Never raises: malformed/unparseable XML returns an empty list. A
    <testcase> missing its `time` attribute defaults to duration_s=0.0.
    Use parse_junit_xml_detailed() to also get the reason when empty.
    """
    return parse_junit_xml_detailed(content, run_id)[0]


def parse_junit_xml_detailed(content: str, run_id: str) -> tuple[list[TestRecord], list[str]]:
    """Like parse_junit_xml() but also returns human-readable warnings, so a
    caller can tell "valid report with zero tests" from "not a JUnit report
    at all" (e.g. an HTML error page) instead of seeing an empty success."""
    if not (content or "").strip():
        return [], [f"Run {run_id!r}: the XML input is empty."]
    try:
        root = DefusedET.fromstring(content)
    except ET.ParseError as exc:
        return [], [f"Run {run_id!r}: the input is not well-formed XML ({exc})."]
    except Exception as exc:  # defusedxml raises its own types for entity bombs etc.
        return [], [f"Run {run_id!r}: the XML was rejected ({type(exc).__name__})."]

    records: list[TestRecord] = []
    for tc in root.iter("testcase"):
        name = tc.get("name", "") or ""
        classname = tc.get("classname", tc.get("class", "")) or ""
        try:
            duration_s = float(tc.get("time", "0") or "0")
        except ValueError:
            duration_s = 0.0

        failure = tc.find("failure")
        error = tc.find("error")
        skipped = tc.find("skipped")
        if failure is not None:
            status = "failed"
            message = failure.get("message") or (failure.text or "").strip()
        elif error is not None:
            status = "error"
            message = error.get("message") or (error.text or "").strip()
        elif skipped is not None:
            status = "skipped"
            message = skipped.get("message") or ""
        else:
            status = "passed"
            message = ""

        records.append(TestRecord(
            run_id=run_id, name=name, classname=classname,
            status=status, duration_s=duration_s, message=message,
        ))

    warnings: list[str] = []
    if not records:
        warnings.append(
            f"Run {run_id!r}: well-formed XML but no <testcase> elements were found "
            f"(root element: <{root.tag}>). Expected a JUnit <testsuites>/<testsuite> report."
        )
    return records, warnings


# ── CSV parsing ────────────────────────────────────────────────────────────────

_COLUMN_ALIASES = {
    "name": ("name", "test_name", "testname", "test", "testcase", "test_case", "case",
             "title", "scenario", "test_title"),
    "classname": ("classname", "class_name", "class", "suite", "test_suite", "test_class",
                  "module", "file"),
    "status": ("status", "result", "outcome", "state", "test_status", "test_result", "verdict"),
    "duration": ("duration_s", "duration", "time", "time_s", "elapsed", "elapsed_s",
                 "time_taken", "duration_sec", "seconds"),
    "duration_ms": ("duration_ms", "time_ms", "elapsed_ms", "millis", "milliseconds"),
    "run_id": ("run_id", "run", "build", "build_id", "run_name"),
    "message": ("message", "error_message", "failure_message", "error", "details",
                "reason", "stack_trace", "failure"),
}

_STATUS_SYNONYMS = {
    "passed": ("pass", "passed", "ok", "success", "successful", "succeeded", "green"),
    "failed": ("fail", "failed", "failure", "ko", "red"),
    "error": ("err", "error", "errored", "broken", "exception", "crashed"),
    "skipped": ("skip", "skipped", "ignored", "ignore", "pending", "not_run", "notrun",
                "disabled", "xfail"),
}
_STATUS_LOOKUP = {syn: canon for canon, syns in _STATUS_SYNONYMS.items() for syn in syns}

_DURATION_RE = re.compile(
    r"^\s*([0-9]*\.?[0-9]+)\s*(ms|msec|s|sec|secs|seconds?|m|min)?\s*$", re.IGNORECASE,
)


def _norm_header(raw: str) -> str:
    return re.sub(r"[\s\-./]+", "_", (raw or "").strip().lower()).strip("_")


def _map_columns(fieldnames: list) -> tuple[dict[str, str], list[str]]:
    """Map canonical field -> original header (alias priority decides, not
    column order); also return the headers that matched nothing."""
    by_norm: dict[str, str] = {}
    for original in fieldnames:
        if original is None:
            continue
        by_norm.setdefault(_norm_header(original), original)
    mapping: dict[str, str] = {}
    for canon, aliases in _COLUMN_ALIASES.items():
        for alias in aliases:
            if alias in by_norm:
                mapping[canon] = by_norm[alias]
                break
    used = set(mapping.values())
    unrecognised = [h for h in fieldnames if h is not None and h not in used]
    return mapping, unrecognised


def _parse_duration(raw: object, assume_ms: bool) -> float:
    text = str(raw or "").strip()
    if not text:
        return 0.0
    m = _DURATION_RE.match(text)
    if not m:
        return 0.0
    value = float(m.group(1))
    unit = (m.group(2) or "").lower()
    if unit in ("ms", "msec") or (not unit and assume_ms):
        return value / 1000.0
    if unit in ("m", "min"):
        return value * 60.0
    return value


def normalize_status(raw: object) -> Optional[str]:
    """Map a free-form status string to passed/failed/error/skipped, or None."""
    key = re.sub(r"[\s\-]+", "_", str(raw or "").strip().lower())
    return _STATUS_LOOKUP.get(key)


def parse_results_csv(content: str) -> list[TestRecord]:
    """Parse a CSV of test results into TestRecords; see
    parse_results_csv_detailed() for the tolerant column/status contract and
    the warnings explaining dropped rows. Never raises."""
    return parse_results_csv_detailed(content)[0]


def parse_results_csv_detailed(content: str) -> tuple[list[TestRecord], list[str]]:
    """Parse a CSV of test results, returning (records, warnings).

    Headers are matched tolerantly (case/space/dash-insensitive, with
    aliases; see _COLUMN_ALIASES): test name = name|test_name|test|testcase|
    title, status = status|result|outcome, duration = duration_s|duration|
    time|elapsed (seconds; a `*_ms` header or an `ms` suffix means
    milliseconds), classname|suite, run_id|run|build, message|error|details.
    Status values are matched via synonyms (pass/ok/success, fail/failure/ko,
    err, skip/ignored/pending ...). Only the test-name and status columns are
    required; classname, run_id (default "csv"), duration and message are
    optional. `,` `;` and tab delimiters are detected.

    Never raises. Dropped rows and unrecognised columns are listed in the
    returned warnings; an empty record list always comes with a warning
    explaining why.
    """
    text = (content or "").lstrip("﻿")
    if not text.strip():
        return [], ["The CSV input is empty."]

    first_line = text.lstrip().splitlines()[0]
    delimiter = ","
    if "," not in first_line:
        if ";" in first_line:
            delimiter = ";"
        elif "\t" in first_line:
            delimiter = "\t"

    try:
        reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
        fieldnames = list(reader.fieldnames or [])
    except Exception as exc:
        return [], [f"The CSV could not be read ({type(exc).__name__})."]
    if not fieldnames:
        return [], ["The CSV has no header row."]

    mapping, unrecognised = _map_columns(fieldnames)
    missing = [c for c in ("name", "status") if c not in mapping]
    if missing:
        labels = {"name": "a test-name column (name/test_name/test/testcase/title)",
                  "status": "a status column (status/result/outcome)"}
        return [], [
            "The CSV is missing " + " and ".join(labels[m] for m in missing)
            + f". Columns found: {', '.join(repr(f) for f in fieldnames)}."
        ]

    warnings: list[str] = []
    if unrecognised:
        warnings.append(
            "Ignored unrecognised CSV column(s): " + ", ".join(repr(u) for u in unrecognised) + ".",
        )

    ms_header = "duration_ms" in mapping and "duration" not in mapping
    dur_col = mapping.get("duration_ms") if ms_header else mapping.get("duration")

    records: list[TestRecord] = []
    empty_name = 0
    bad_status: dict[str, int] = {}
    for row in reader:
        try:
            name = (row.get(mapping["name"]) or "").strip()
            raw_status = (row.get(mapping["status"]) or "").strip()
            if not name and not raw_status:
                continue  # blank line
            if not name:
                empty_name += 1
                continue
            status = normalize_status(raw_status)
            if status is None:
                label = raw_status or "<empty>"
                bad_status[label] = bad_status.get(label, 0) + 1
                continue
            classname = (row.get(mapping["classname"]) or "").strip() if "classname" in mapping else ""
            run_id = (row.get(mapping["run_id"]) or "").strip() if "run_id" in mapping else ""
            duration_s = _parse_duration(row.get(dur_col), ms_header) if dur_col else 0.0
            message = (row.get(mapping["message"]) or "") if "message" in mapping else ""
            records.append(TestRecord(
                run_id=run_id or "csv", name=name, classname=classname,
                status=status, duration_s=duration_s, message=message,
            ))
        except Exception:
            continue

    if empty_name:
        warnings.append(f"Dropped {empty_name} row(s) with an empty test name.")
    if bad_status:
        shown = ", ".join(f"{k!r} x{v}" for k, v in sorted(bad_status.items())[:10])
        warnings.append(
            f"Dropped {sum(bad_status.values())} row(s) with an unrecognised status: {shown}. "
            "Recognised: pass/passed/ok/success, fail/failed/failure/ko, error/err, "
            "skip/skipped/ignored/pending.",
        )
    if not records:
        warnings.append("No test rows could be parsed from the CSV (header-only file or no usable rows).")
    return records, warnings


# ── Failure clustering ─────────────────────────────────────────────────────────

_HEX_RE = re.compile(r"\b0x[0-9a-fA-F]+\b")
_PATH_RE = re.compile(r"(?:[A-Za-z]:)?(?:[\\/][\w.\-]+){2,}")
_QUOTED_RE = re.compile(r"'[^']*'|\"[^\"]*\"")
_NUM_RE = re.compile(r"\d+(?:\.\d+)?")
_CLUSTER_SIG_MAX_LEN = 200


def _cluster_signature(message: str) -> str:
    """Deterministic string normalization (NOT an LLM): replace numbers, hex
    ids, quoted strings, file paths, and durations with placeholders, so
    "TimeoutError waiting for #btn-42 after 3.2s" and "...#btn-57 after 1.1s"
    cluster under one signature."""
    sig = message
    sig = _HEX_RE.sub("<HEX>", sig)
    sig = _PATH_RE.sub("<PATH>", sig)
    sig = _QUOTED_RE.sub("<STR>", sig)
    sig = _NUM_RE.sub("<NUM>", sig)
    sig = " ".join(sig.split())
    return sig[:_CLUSTER_SIG_MAX_LEN]


# ── Analysis ───────────────────────────────────────────────────────────────────

def _slowest_sort_key(entry: dict[str, object]) -> float:
    """Sort key for `slowest` entries: `mean_s` is always a float (set via
    `round(mean_s, 4)` above), narrower than the dict's `object` value type."""
    return cast(float, entry["mean_s"])


def analyze(
    records: list[TestRecord],
    reference_tests: Optional[list[str]] = None,
    flaky_min: float = 0.2,
    flaky_max: float = 0.8,
    min_runs_for_verdict: int = 3,
    slowest_n: int = 10,
) -> ResultsAnalysis:
    """Compute deterministic health metrics from a flat list of TestRecord
    spanning one or more runs.

    Flaky (Testomat.io semantics): pass_rate strictly inside
    (flaky_min, flaky_max) AND executions >= min_runs_for_verdict — a test
    with 1 fail out of 2 runs is "insufficient data", not flaky.
    Ever-failing: >= min_runs_for_verdict executions and zero passes.

    Skipped executions are not failures and carry no pass/fail signal: they
    are excluded from pass rates, the flaky and ever-failing verdicts and the
    minimum-execution counts, and reported separately (`skipped`,
    `skipped_executions`). pass,pass,skip is therefore a stable test, not
    "flaky at 0.67".
    """
    groups: dict[str, list[TestRecord]] = defaultdict(list)
    for r in records:
        groups[_test_identity(r)].append(r)

    executions = len(records)
    passed_count = sum(1 for r in records if r.status == "passed")
    skipped_total = sum(1 for r in records if r.status == "skipped")
    verdict_executions = executions - skipped_total
    overall_pass_rate = round(passed_count / verdict_executions, 4) if verdict_executions else 0.0

    flaky = []
    ever_failing = []
    slowest = []
    skipped: list[dict] = []
    for identity, recs in groups.items():
        n_skipped = sum(1 for r in recs if r.status == "skipped")
        n = len(recs) - n_skipped  # executions that carry a pass/fail signal
        p = sum(1 for r in recs if r.status == "passed")
        pass_rate = p / n if n else 0.0
        if n_skipped:
            skipped.append({"test": identity, "skipped": n_skipped, "runs": len(recs)})

        if n >= min_runs_for_verdict and flaky_min < pass_rate < flaky_max:
            flaky.append({"test": identity, "pass_rate": round(pass_rate, 4), "runs": n})

        if n >= min_runs_for_verdict and p == 0:
            ever_failing.append({"test": identity, "runs": n})

        durations = [r.duration_s for r in recs]
        mean_s = sum(durations) / len(durations) if durations else 0.0
        slowest.append({
            "test": identity,
            "mean_s": round(mean_s, 4),
            "max_s": round(max(durations), 4) if durations else 0.0,
        })

    skipped.sort(key=lambda e: (-e["skipped"], e["test"]))
    slowest.sort(key=_slowest_sort_key, reverse=True)
    slowest = slowest[:slowest_n]

    warnings: list[str] = []
    flaky_ids = {f["test"] for f in flaky}

    never_run = []
    if reference_tests:
        seen = set(groups.keys())
        seen_normalized = {_normalize_identity_string(s) for s in seen}
        by_bare: dict[str, set] = defaultdict(set)
        for ident in seen:
            by_bare[ident.rsplit("::", 1)[-1]].add(ident)
        ambiguous: list[str] = []
        unmatched: list[str] = []
        for ref in reference_tests:
            norm_ref = _normalize_identity_string(ref)
            if ref in seen or norm_ref in seen_normalized:
                continue
            candidates = by_bare.get(norm_ref.rsplit("::", 1)[-1], set()) if "::" not in norm_ref else set()
            if len(candidates) == 1:
                continue  # bare test name, unambiguous: matches the one executed test with that name
            if len(candidates) > 1:
                ambiguous.append(f"{ref!r} (matches {', '.join(sorted(candidates)[:3])}"
                                 f"{', ...' if len(candidates) > 3 else ''})")
            else:
                unmatched.append(ref)
            never_run.append({"test": ref})
        if ambiguous:
            warnings.append(
                "reference_tests: bare test name(s) matched more than one executed test, so they were "
                "NOT guessed and are listed under never_run; use the full 'classname::name' form: "
                + "; ".join(ambiguous[:10]) + ".",
            )
        if unmatched:
            warnings.append(
                f"reference_tests: {len(unmatched)} entr{'y' if len(unmatched) == 1 else 'ies'} matched no "
                "executed test (e.g. " + ", ".join(repr(u) for u in unmatched[:3]) + "). Identities are "
                "'classname::name' (or just 'name' when the results have no classname; a bare name is "
                "accepted only when exactly one executed test has it). Parametrized suffixes like "
                "'[case]' are ignored.",
            )

    cluster_map: dict[str, dict] = {}
    for r in records:
        if r.status in ("failed", "error") and r.message:
            sig = _cluster_signature(r.message)
            entry = cluster_map.setdefault(sig, {
                "signature": sig, "count": 0, "sample_tests": [], "sample_message": r.message[:_CLUSTER_SIG_MAX_LEN],
            })
            entry["count"] += 1
            ident = _test_identity(r)
            if ident not in entry["sample_tests"]:
                entry["sample_tests"].append(ident)
    failure_clusters = sorted(cluster_map.values(), key=lambda c: c["count"], reverse=True)

    run_ids = sorted({r.run_id for r in records})
    per_run = []
    for rid in run_ids:
        run_recs = [r for r in records if r.run_id == rid]
        per_run.append({
            "run_id": rid,
            "passed": sum(1 for r in run_recs if r.status == "passed"),
            "failed": sum(1 for r in run_recs if r.status in ("failed", "error")),
            "skipped": sum(1 for r in run_recs if r.status == "skipped"),
            "duration_s": round(sum(r.duration_s for r in run_recs), 4),
        })

    mixed_outcome = []
    for identity, recs in groups.items():
        n_pass = sum(1 for r in recs if r.status == "passed")
        n_fail = sum(1 for r in recs if r.status in ("failed", "error"))
        if n_pass and n_fail and identity not in flaky_ids:
            total = n_pass + n_fail
            mixed_outcome.append({
                "test": identity, "passed": n_pass, "failed": n_fail, "runs": total,
                "pass_rate": round(n_pass / total, 4),
                "note": "mixed outcome (needs more runs)" if total < min_runs_for_verdict
                else "mixed outcome (pass rate outside the flaky band)",
            })
    mixed_outcome.sort(key=lambda e: (e["pass_rate"], e["test"]))

    if len(run_ids) < min_runs_for_verdict:
        warnings.append(
            f"Only {len(run_ids)} run(s) supplied; flaky and ever-failing verdicts need at least "
            f"{min_runs_for_verdict} executions of a test, so fewer runs cannot establish flakiness "
            "(a test that passed once and failed once is NOT reported as flaky). Tests with both "
            "outcomes are listed under mixed_outcome (needs more runs).",
        )
    if any(r.status in ("failed", "error") for r in records) and not any(
        r.message for r in records if r.status in ("failed", "error")
    ):
        warnings.append(
            "failure_clusters is empty because no failed/error execution carries a failure message. "
            "Clustering needs one: CSV column message (also accepted: "
            + ", ".join(a for a in _COLUMN_ALIASES["message"] if a != "message")
            + "), or a message attribute / text on the JUnit <failure>/<error> element.",
        )

    return ResultsAnalysis(
        runs=len(run_ids),
        total_tests=len(groups),
        executions=executions,
        overall_pass_rate=overall_pass_rate,
        flaky=flaky,
        ever_failing=ever_failing,
        never_run=never_run,
        slowest=slowest,
        failure_clusters=failure_clusters,
        per_run=per_run,
        warnings=warnings,
        skipped_executions=skipped_total,
        skipped=skipped[:50],
        mixed_outcome=mixed_outcome[:50],
    )


# ── Prompt summary ─────────────────────────────────────────────────────────────

def summarize_for_prompt(analysis: ResultsAnalysis, max_chars: int = 1500) -> str:
    """Short, deterministic text block for grounding an LLM prompt (e.g. the
    Risk Register generation) in real execution data — no LLM call here."""
    lines = [
        f"Runs: {analysis.runs}, distinct tests: {analysis.total_tests}, "
        f"executions: {analysis.executions}, overall pass rate: {analysis.overall_pass_rate:.1%}",
    ]
    if analysis.flaky:
        top = ", ".join(f"{f['test']} ({f['pass_rate']:.0%} over {f['runs']} runs)" for f in analysis.flaky[:5])
        lines.append(f"Flaky tests ({len(analysis.flaky)}): {top}")
    if analysis.ever_failing:
        top = ", ".join(f["test"] for f in analysis.ever_failing[:5])
        lines.append(f"Ever-failing tests ({len(analysis.ever_failing)}): {top}")
    if analysis.never_run:
        top = ", ".join(f["test"] for f in analysis.never_run[:5])
        lines.append(f"Never-run reference tests ({len(analysis.never_run)}): {top}")
    if analysis.failure_clusters:
        top = "; ".join(f"{c['signature']} (x{c['count']})" for c in analysis.failure_clusters[:3])
        lines.append(f"Top failure clusters: {top}")
    if analysis.slowest:
        top = ", ".join(f"{s['test']} ({s['mean_s']:.1f}s avg)" for s in analysis.slowest[:3])
        lines.append(f"Slowest tests: {top}")

    text = "\n".join(lines)
    if len(text) > max_chars:
        text = text[:max(0, max_chars - 3)] + "..."
    return text
