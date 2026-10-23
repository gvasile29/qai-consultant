"""Regression tests for the v3.9.2 analyze_test_results usability findings (N3-N7)."""
import json

from qai_consultant.core import results_core
from qai_consultant.mcp import server


def _xml(cases):
    body = ""
    for classname, name, status in cases:
        inner = ""
        if status == "failed":
            inner = '<failure message="boom 42"/>'
        body += f'<testcase classname="{classname}" name="{name}" time="1.0">{inner}</testcase>'
    return f'<testsuite name="s">{body}</testsuite>'


def _call(**kw):
    return server.analyze_test_results(**kw)


def test_happy_path_three_runs_unchanged_and_no_usability_warnings():
    runs = [
        {"run_id": f"r{i}", "xml": _xml([("A", "t_flaky", "failed" if i == 1 else "passed"),
                                         ("A", "t_ok", "passed")])}
        for i in range(3)
    ]
    out = _call(junit_xml=runs)
    assert out["runs"] == 3 and out["executions"] == 6
    assert [f["test"] for f in out["flaky"]] == ["A::t_flaky"]
    assert out["flaky"][0]["pass_rate"] == 0.6667
    assert out["warnings"] == []
    assert out["mixed_outcome"] == []


def test_two_runs_warns_and_lists_mixed_outcome():
    runs = [
        {"run_id": "a", "xml": _xml([("A", "t1", "passed")])},
        {"run_id": "b", "xml": _xml([("A", "t1", "failed")])},
    ]
    out = _call(junit_xml=runs)
    assert out["flaky"] == [] and out["ever_failing"] == []
    assert any("at least 3" in w and "cannot establish flakiness" in w for w in out["warnings"])
    assert out["mixed_outcome"][0]["test"] == "A::t1"
    assert "needs more runs" in out["mixed_outcome"][0]["note"]


def test_plain_list_of_xml_strings_real_list_and_json_string():
    xmls = [_xml([("A", "t", "passed")]), _xml([("A", "t", "passed")]), _xml([("A", "t", "failed")])]
    for arg in (xmls, json.dumps(xmls)):
        out = _call(junit_xml=arg)
        assert "error" not in out
        assert out["runs"] == 3
        assert [r["run_id"] for r in out["per_run"]] == ["run-1", "run-2", "run-3"]


def test_documented_object_form_still_works():
    out = _call(junit_xml=json.dumps([{"run_id": "x", "xml": _xml([("A", "t", "passed")])}]))
    assert out["runs"] == 1 and out["per_run"][0]["run_id"] == "x"


def test_duplicate_run_ids_kept_separate_with_warning():
    runs = [{"run_id": "same", "xml": _xml([("A", "t", "passed")])} for _ in range(3)]
    out = _call(junit_xml=runs)
    assert out["runs"] == 3
    assert any("Duplicate run_id" in w and "'same'" in w for w in out["warnings"])


def test_bare_reference_name_matches_when_unambiguous():
    xml = _xml([("suite.A", "test_ok_0", "passed")])
    out = _call(junit_xml=xml, reference_tests=["test_ok_0", "missing_one"])
    assert [n["test"] for n in out["never_run"]] == ["missing_one"]
    assert any("matched no executed test" in w for w in out["warnings"])


def test_ambiguous_bare_reference_not_guessed():
    xml = _xml([("suite.A", "test_x", "passed"), ("suite.B", "test_x", "passed")])
    out = _call(junit_xml=xml, reference_tests=["test_x"])
    assert [n["test"] for n in out["never_run"]] == ["test_x"]
    assert any("more than one" in w and "classname::name" in w for w in out["warnings"])


def test_csv_without_message_column_warns_about_clustering():
    csv_text = "name,status\nt1,failed\nt2,passed\n"
    out = _call(csv_text=csv_text)
    assert out["failure_clusters"] == []
    assert any("failure_clusters is empty" in w and "error_message" in w for w in out["warnings"])


def test_no_cluster_warning_without_failures_or_with_messages():
    ok = results_core.analyze(results_core.parse_results_csv("name,status\nt1,passed\n"))
    assert not any("failure_clusters" in w for w in ok.warnings)
    msg = results_core.analyze(results_core.parse_results_csv("name,status,message\nt1,failed,boom\n"))
    assert not any("failure_clusters" in w for w in msg.warnings)
