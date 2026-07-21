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
    overall_pass_rate: float
    flaky: list = field(default_factory=list)             # [{"test", "pass_rate", "runs"}]
    ever_failing: list = field(default_factory=list)       # [{"test", "runs"}]
    never_run: list = field(default_factory=list)          # [{"test"}] — only when reference_tests given
    slowest: list = field(default_factory=list)            # [{"test", "mean_s", "max_s"}]
    failure_clusters: list = field(default_factory=list)   # [{"signature", "count", "sample_tests", "sample_message"}]
    per_run: list = field(default_factory=list)            # [{"run_id", "passed", "failed", "skipped", "duration_s"}]
    warnings: list = field(default_factory=list)           # parsing issues, ignored files, etc.


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
    """
    try:
        root = DefusedET.fromstring(content)
    except ET.ParseError:
        return []

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
    return records


# ── CSV parsing ────────────────────────────────────────────────────────────────

def parse_results_csv(content: str) -> list[TestRecord]:
    """Parse a CSV of test results.

    Column contract:
      - required: `name`, `classname`, `status` (one of passed/failed/error/skipped)
      - optional: `run_id` (default "csv" — use this when the whole file is one run),
                  `duration_s` (default 0.0), `message` (default "")

    Rows missing a required column, an empty name, or an unrecognized status
    are skipped. Never raises — a completely malformed CSV just yields [].
    """
    try:
        reader = csv.DictReader(io.StringIO(content))
    except Exception:
        return []
    if not reader.fieldnames:
        return []

    records: list[TestRecord] = []
    for row in reader:
        try:
            name = (row.get("name") or "").strip()
            if not name:
                continue
            status = (row.get("status") or "").strip().lower()
            if status not in VALID_STATUSES:
                continue
            classname = (row.get("classname") or "").strip()
            run_id = (row.get("run_id") or "").strip() or "csv"
            try:
                duration_s = float(row.get("duration_s") or 0.0)
            except (TypeError, ValueError):
                duration_s = 0.0
            message = row.get("message") or ""
            records.append(TestRecord(
                run_id=run_id, name=name, classname=classname,
                status=status, duration_s=duration_s, message=message,
            ))
        except Exception:
            continue
    return records


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
    """
    groups: dict[str, list[TestRecord]] = defaultdict(list)
    for r in records:
        groups[_test_identity(r)].append(r)

    executions = len(records)
    passed_count = sum(1 for r in records if r.status == "passed")
    overall_pass_rate = round(passed_count / executions, 4) if executions else 0.0

    flaky = []
    ever_failing = []
    slowest = []
    for identity, recs in groups.items():
        n = len(recs)
        p = sum(1 for r in recs if r.status == "passed")
        pass_rate = p / n if n else 0.0

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

    slowest.sort(key=_slowest_sort_key, reverse=True)
    slowest = slowest[:slowest_n]

    never_run = []
    if reference_tests:
        seen = set(groups.keys())
        seen_normalized = {_normalize_identity_string(s) for s in seen}
        for ref in reference_tests:
            norm_ref = _normalize_identity_string(ref)
            if ref not in seen and norm_ref not in seen_normalized:
                never_run.append({"test": ref})

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
        warnings=[],
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
