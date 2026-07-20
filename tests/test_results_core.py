"""
Tests for src/results_core.py — deterministic test-results analysis (v3.1).

Pure stdlib module: JUnit XML / CSV parsing, flaky/ever-failing/never-run/
slowest detection, failure clustering, and a bounded prompt summary.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from results_core import (  # noqa: E402
    TestRecord,
    analyze,
    parse_junit_xml,
    parse_results_csv,
    summarize_for_prompt,
)


# ── parse_junit_xml ────────────────────────────────────────────────────────────

def test_parse_junit_xml_testsuites_root():
    xml = """<testsuites>
        <testsuite name="a">
            <testcase classname="pkg.A" name="test_one" time="1.5"/>
        </testsuite>
    </testsuites>"""
    records = parse_junit_xml(xml, "run1")
    assert len(records) == 1
    assert records[0].name == "test_one"
    assert records[0].classname == "pkg.A"
    assert records[0].duration_s == 1.5
    assert records[0].status == "passed"
    assert records[0].run_id == "run1"


def test_parse_junit_xml_bare_testsuite_root():
    xml = '<testsuite name="a"><testcase classname="pkg.A" name="test_one" time="1.0"/></testsuite>'
    records = parse_junit_xml(xml, "run1")
    assert len(records) == 1
    assert records[0].status == "passed"


def test_parse_junit_xml_failure_status_and_message():
    xml = """<testsuite>
        <testcase classname="pkg.B" name="test_fail" time="0.5">
            <failure message="AssertionError: boom">traceback...</failure>
        </testcase>
    </testsuite>"""
    records = parse_junit_xml(xml, "run1")
    assert records[0].status == "failed"
    assert "boom" in records[0].message


def test_parse_junit_xml_error_status():
    xml = """<testsuite>
        <testcase classname="pkg.B" name="test_err" time="0.1">
            <error message="ConnectionError">conn refused</error>
        </testcase>
    </testsuite>"""
    records = parse_junit_xml(xml, "run1")
    assert records[0].status == "error"
    assert records[0].message == "ConnectionError"


def test_parse_junit_xml_skipped_status():
    xml = """<testsuite>
        <testcase classname="pkg.B" name="test_skip" time="0.0">
            <skipped message="not implemented"/>
        </testcase>
    </testsuite>"""
    records = parse_junit_xml(xml, "run1")
    assert records[0].status == "skipped"


def test_parse_junit_xml_missing_time_defaults_zero():
    xml = '<testsuite><testcase classname="pkg.A" name="test_one"/></testsuite>'
    records = parse_junit_xml(xml, "run1")
    assert records[0].duration_s == 0.0


def test_parse_junit_xml_malformed_returns_empty_list_no_raise():
    records = parse_junit_xml("<not><valid</xml", "run1")
    assert records == []


def test_parse_junit_xml_empty_string_returns_empty_list():
    assert parse_junit_xml("", "run1") == []


def test_parse_junit_xml_multiple_testcases():
    xml = """<testsuites>
        <testsuite>
            <testcase classname="pkg.A" name="t1" time="1"/>
            <testcase classname="pkg.A" name="t2" time="2"/>
            <testcase classname="pkg.B" name="t3" time="3"/>
        </testsuite>
    </testsuites>"""
    records = parse_junit_xml(xml, "run1")
    assert len(records) == 3


# ── parse_results_csv ──────────────────────────────────────────────────────────

def test_parse_results_csv_basic():
    csv_text = "name,classname,status,duration_s\ntest_a,pkg.A,passed,1.2\ntest_b,pkg.B,failed,0.3\n"
    records = parse_results_csv(csv_text)
    assert len(records) == 2
    assert records[0].status == "passed"
    assert records[1].status == "failed"


def test_parse_results_csv_default_run_id_is_csv():
    csv_text = "name,classname,status\ntest_a,pkg.A,passed\n"
    records = parse_results_csv(csv_text)
    assert records[0].run_id == "csv"


def test_parse_results_csv_explicit_run_id():
    csv_text = "name,classname,status,run_id\ntest_a,pkg.A,passed,nightly-42\n"
    records = parse_results_csv(csv_text)
    assert records[0].run_id == "nightly-42"


def test_parse_results_csv_missing_duration_defaults_zero():
    csv_text = "name,classname,status\ntest_a,pkg.A,passed\n"
    records = parse_results_csv(csv_text)
    assert records[0].duration_s == 0.0


def test_parse_results_csv_invalid_status_skipped_row():
    csv_text = "name,classname,status\ntest_a,pkg.A,bogus_status\ntest_b,pkg.B,passed\n"
    records = parse_results_csv(csv_text)
    assert len(records) == 1
    assert records[0].name == "test_b"


def test_parse_results_csv_empty_name_skipped():
    csv_text = "name,classname,status\n,pkg.A,passed\n"
    records = parse_results_csv(csv_text)
    assert records == []


def test_parse_results_csv_empty_content_returns_empty_list():
    assert parse_results_csv("") == []


def test_parse_results_csv_message_column():
    csv_text = "name,classname,status,message\ntest_a,pkg.A,failed,boom\n"
    records = parse_results_csv(csv_text)
    assert records[0].message == "boom"


# ── analyze: identity grouping / parametrized stripping ───────────────────────

def _rec(name, classname="pkg.A", status="passed", duration_s=1.0, run_id="r1", message=""):
    return TestRecord(run_id=run_id, name=name, classname=classname, status=status,
                       duration_s=duration_s, message=message)


def test_analyze_groups_parametrized_names_under_one_identity():
    records = [
        _rec("test_foo[case1]", run_id="r1", status="passed"),
        _rec("test_foo[case2]", run_id="r2", status="passed"),
        _rec("test_foo[case3]", run_id="r3", status="passed"),
    ]
    analysis = analyze(records)
    assert analysis.total_tests == 1


def test_analyze_executions_and_total_tests_distinct():
    records = [_rec("t1", run_id="r1"), _rec("t1", run_id="r2"), _rec("t2", run_id="r1")]
    analysis = analyze(records)
    assert analysis.executions == 3
    assert analysis.total_tests == 2


def test_analyze_overall_pass_rate():
    records = [_rec("t1", status="passed"), _rec("t2", status="failed")]
    analysis = analyze(records)
    assert analysis.overall_pass_rate == 0.5


def test_analyze_empty_records_zero_pass_rate_no_crash():
    analysis = analyze([])
    assert analysis.executions == 0
    assert analysis.overall_pass_rate == 0.0
    assert analysis.total_tests == 0


# ── analyze: flaky / ever-failing boundaries ──────────────────────────────────

def test_analyze_flaky_within_band_and_min_runs():
    # pass_rate = 2/4 = 0.5, strictly inside (0.2, 0.8), 4 >= min_runs_for_verdict(3)
    records = [_rec("t1", run_id=f"r{i}", status=s) for i, s in enumerate(["passed", "passed", "failed", "failed"])]
    analysis = analyze(records, min_runs_for_verdict=3)
    assert len(analysis.flaky) == 1
    assert analysis.flaky[0]["test"] == "pkg.A::t1"


def test_analyze_insufficient_data_not_flaky():
    # 1 fail out of 2 runs — below min_runs_for_verdict(3), must NOT be flaky
    records = [_rec("t1", run_id="r0", status="passed"), _rec("t1", run_id="r1", status="failed")]
    analysis = analyze(records, min_runs_for_verdict=3)
    assert analysis.flaky == []


def test_analyze_pass_rate_at_flaky_boundary_excluded():
    # pass_rate exactly 0.8 (flaky_max) must be excluded — strictly inside the band
    records = ([_rec("t1", run_id=f"p{i}", status="passed") for i in range(4)]
               + [_rec("t1", run_id="f0", status="failed")])
    analysis = analyze(records, flaky_min=0.2, flaky_max=0.8, min_runs_for_verdict=3)
    assert analysis.flaky == []


def test_analyze_ever_failing_requires_min_runs_and_zero_passes():
    records = [_rec("t1", run_id=f"r{i}", status="failed") for i in range(3)]
    analysis = analyze(records, min_runs_for_verdict=3)
    assert len(analysis.ever_failing) == 1
    assert analysis.ever_failing[0]["test"] == "pkg.A::t1"


def test_analyze_ever_failing_excluded_below_min_runs():
    records = [_rec("t1", run_id="r0", status="failed"), _rec("t1", run_id="r1", status="failed")]
    analysis = analyze(records, min_runs_for_verdict=3)
    assert analysis.ever_failing == []


def test_analyze_never_failing_test_not_in_ever_failing():
    records = [_rec("t1", run_id=f"r{i}", status="passed") for i in range(3)]
    analysis = analyze(records, min_runs_for_verdict=3)
    assert analysis.ever_failing == []
    assert analysis.flaky == []


# ── analyze: never_run ─────────────────────────────────────────────────────────

def test_analyze_never_run_reports_missing_reference_tests():
    records = [_rec("t1")]
    analysis = analyze(records, reference_tests=["pkg.A::t1", "pkg.B::t2"])
    assert len(analysis.never_run) == 1
    assert analysis.never_run[0]["test"] == "pkg.B::t2"


def test_analyze_never_run_empty_when_no_reference_tests():
    records = [_rec("t1")]
    analysis = analyze(records, reference_tests=None)
    assert analysis.never_run == []


# ── analyze: slowest ───────────────────────────────────────────────────────────

def test_analyze_slowest_sorted_descending_by_mean_duration():
    records = [_rec("fast", duration_s=0.1), _rec("slow", duration_s=5.0), _rec("mid", duration_s=1.0)]
    analysis = analyze(records)
    names = [s["test"] for s in analysis.slowest]
    assert names[0] == "pkg.A::slow"
    assert names[-1] == "pkg.A::fast"


def test_analyze_slowest_respects_slowest_n_cap():
    records = [_rec(f"t{i}", duration_s=float(i)) for i in range(15)]
    analysis = analyze(records, slowest_n=5)
    assert len(analysis.slowest) == 5


# ── analyze: failure clustering ────────────────────────────────────────────────

def test_analyze_clusters_similar_messages_with_different_numbers():
    records = [
        _rec("t1", status="failed", message="TimeoutError waiting for #btn-42 after 3.2s"),
        _rec("t2", status="failed", message="TimeoutError waiting for #btn-57 after 1.1s"),
    ]
    analysis = analyze(records)
    assert len(analysis.failure_clusters) == 1
    assert analysis.failure_clusters[0]["count"] == 2


def test_analyze_clusters_distinct_message_families_separately():
    records = [
        _rec("t1", status="failed", message="TimeoutError waiting for element"),
        _rec("t2", status="error", message="ConnectionError: refused"),
        _rec("t3", status="failed", message="TimeoutError waiting for element"),
    ]
    analysis = analyze(records)
    assert len(analysis.failure_clusters) == 2
    counts = sorted(c["count"] for c in analysis.failure_clusters)
    assert counts == [1, 2]


def test_analyze_passed_tests_excluded_from_clustering():
    records = [_rec("t1", status="passed", message="")]
    analysis = analyze(records)
    assert analysis.failure_clusters == []


# ── analyze: per_run ───────────────────────────────────────────────────────────

def test_analyze_per_run_breakdown():
    records = [
        _rec("t1", run_id="r1", status="passed"),
        _rec("t2", run_id="r1", status="failed"),
        _rec("t3", run_id="r2", status="skipped"),
    ]
    analysis = analyze(records)
    by_run = {p["run_id"]: p for p in analysis.per_run}
    assert by_run["r1"]["passed"] == 1
    assert by_run["r1"]["failed"] == 1
    assert by_run["r2"]["skipped"] == 1
    assert analysis.runs == 2


# ── determinism ────────────────────────────────────────────────────────────────

def test_analyze_is_deterministic_across_repeated_calls():
    records = [_rec("t1", status="failed", message="X 42"), _rec("t1", run_id="r2", status="passed")]
    a1 = analyze(records)
    a2 = analyze(records)
    assert a1 == a2


# ── summarize_for_prompt ───────────────────────────────────────────────────────

def test_summarize_for_prompt_contains_pass_rate():
    records = [_rec("t1", status="passed"), _rec("t2", status="failed")]
    analysis = analyze(records)
    summary = summarize_for_prompt(analysis)
    assert "50.0%" in summary or "50%" in summary


def test_summarize_for_prompt_respects_max_chars():
    records = [_rec(f"t{i}", status="failed", message=f"error number {i} in module") for i in range(50)]
    analysis = analyze(records)
    summary = summarize_for_prompt(analysis, max_chars=100)
    assert len(summary) <= 100


def test_summarize_for_prompt_empty_analysis_no_crash():
    analysis = analyze([])
    summary = summarize_for_prompt(analysis)
    assert "Runs: 0" in summary
