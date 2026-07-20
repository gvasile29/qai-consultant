"""
Tests for src/cli.py — the `--review` and `--results` flags (v3.1 F1/F2).

Keeps to what's safely testable without a live LLM/interactive prompt:
argparse wiring, load_results_summary()'s pure parsing behavior, and
run_review_mode()'s file-not-found / insufficient-content early exits
(no narrative, no agent calls needed for those paths).
"""

import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

import cli  # noqa: E402


# ── parse_args() ─────────────────────────────────────────────────────────────────

def test_parse_args_defaults_are_none():
    args = cli.parse_args([])
    assert args.review is None
    assert args.results is None
    assert args.doc_type == "auto"


def test_parse_args_review_with_doc_type():
    args = cli.parse_args(["--review", "doc.md", "--doc-type", "test_plan"])
    assert args.review == "doc.md"
    assert args.doc_type == "test_plan"


def test_parse_args_review_invalid_doc_type_exits():
    with pytest.raises(SystemExit):
        cli.parse_args(["--review", "doc.md", "--doc-type", "not_a_type"])


def test_parse_args_results_accepts_multiple_paths():
    args = cli.parse_args(["--results", "run1.xml", "run2.xml", "run3.csv"])
    assert args.results == ["run1.xml", "run2.xml", "run3.csv"]


def test_parse_args_no_flags_backward_compatible():
    """Invoking with zero flags (the pre-v3.1 usage) must still parse cleanly."""
    args = cli.parse_args([])
    assert args.review is None
    assert args.results is None


# ── load_results_summary() ───────────────────────────────────────────────────────

_JUNIT_XML = """<testsuite>
    <testcase classname="pkg.A" name="test_pass" time="0.5"/>
    <testcase classname="pkg.A" name="test_fail" time="0.1">
        <failure message="boom">Traceback...</failure>
    </testcase>
</testsuite>"""

_RESULTS_CSV = "name,classname,status,duration_s\ntest_one,pkg.C,passed,1.0\ntest_two,pkg.C,failed,2.0\n"


def test_load_results_summary_parses_xml_file():
    tmp_dir = Path(tempfile.mkdtemp())
    try:
        xml_path = tmp_dir / "run1.xml"
        xml_path.write_text(_JUNIT_XML, encoding="utf-8")

        analysis, summary = cli.load_results_summary([str(xml_path)])

        assert analysis is not None
        assert analysis.runs == 1
        assert analysis.executions == 2
        assert "Runs: 1" in summary
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_load_results_summary_parses_csv_file():
    tmp_dir = Path(tempfile.mkdtemp())
    try:
        csv_path = tmp_dir / "results.csv"
        csv_path.write_text(_RESULTS_CSV, encoding="utf-8")

        analysis, summary = cli.load_results_summary([str(csv_path)])

        assert analysis is not None
        assert analysis.total_tests == 2
        assert summary is not None
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_load_results_summary_combines_multiple_files():
    tmp_dir = Path(tempfile.mkdtemp())
    try:
        xml1 = tmp_dir / "run1.xml"
        xml1.write_text(_JUNIT_XML, encoding="utf-8")
        xml2 = tmp_dir / "run2.xml"
        xml2.write_text(_JUNIT_XML, encoding="utf-8")

        analysis, summary = cli.load_results_summary([str(xml1), str(xml2)])

        assert analysis.runs == 2
        assert analysis.executions == 4
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_load_results_summary_skips_missing_file_without_raising():
    analysis, summary = cli.load_results_summary(["Z:/definitely/does/not/exist.xml"])
    assert analysis is None
    assert summary is None


def test_load_results_summary_returns_none_for_empty_records():
    tmp_dir = Path(tempfile.mkdtemp())
    try:
        xml_path = tmp_dir / "empty.xml"
        xml_path.write_text("<not valid xml", encoding="utf-8")

        analysis, summary = cli.load_results_summary([str(xml_path)])

        assert analysis is None
        assert summary is None
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ── run_review_mode(): early-exit paths (no LLM/agent interaction needed) ───────

def test_run_review_mode_file_not_found_exits():
    with pytest.raises(SystemExit):
        cli.run_review_mode(MagicMock(), "Z:/does/not/exist.md", "auto")


def test_run_review_mode_insufficient_content_returns_without_prompting(monkeypatch):
    tmp_dir = Path(tempfile.mkdtemp())
    try:
        doc_path = tmp_dir / "short.md"
        doc_path.write_text("Too short.", encoding="utf-8")

        def _fail_if_called(*args, **kwargs):
            raise AssertionError("Prompt.ask must not be called for insufficient_content")

        monkeypatch.setattr(cli.Prompt, "ask", _fail_if_called)

        cli.run_review_mode(MagicMock(), str(doc_path), "auto")  # must not raise
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ── generate_strategy(): results_summary passthrough ────────────────────────────

def test_generate_strategy_accepts_results_summary_parameter():
    import inspect
    sig = inspect.signature(cli.generate_strategy)
    assert "results_summary" in sig.parameters
    assert sig.parameters["results_summary"].default is None
