"""Unit tests for scripts/check_dependency_drift.py.

No network access, no live `uv` invocation — these test the parsing/diff
logic against fixture strings shaped like real pyproject.toml and
`uv pip compile` output, per the "tier-1-style" determinism used
elsewhere in this repo (evals/, test_packaging.py).
"""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import check_dependency_drift as drift  # noqa: E402


SAMPLE_PYPROJECT = '''
[project]
name = "qai-consultant-mcp"
version = "3.4.4"
dependencies = [
    "anyio==4.14.2",
    "certifi==2026.1.1",
    "numpy==2.4.1 ; python_full_version < '3.11'",
    "numpy==2.5.0 ; python_full_version >= '3.11'",
]
classifiers = ["Programming Language :: Python :: 3"]
'''

SAMPLE_COMPILED_NO_DRIFT = """
anyio==4.14.2
    # via mcp
certifi==2026.1.1
    # via requests
numpy==2.4.1 ; python_full_version < '3.11'
    # via scikit-learn
numpy==2.5.0 ; python_full_version >= '3.11'
    # via scikit-learn
"""

SAMPLE_COMPILED_WITH_DRIFT = """
anyio==4.15.0
    # via mcp
certifi==2026.1.1
    # via requests
numpy==2.4.1 ; python_full_version < '3.11'
    # via scikit-learn
numpy==2.5.0 ; python_full_version >= '3.11'
    # via scikit-learn
"""

SAMPLE_COMPILED_MALFORMED = """
this is not a requirement line
==missing-a-name
anyio==4.14.2
"""


def test_parse_pyproject_dependencies_extracts_all_entries():
    entries = drift.parse_pyproject_dependencies(SAMPLE_PYPROJECT)
    assert entries == [
        "anyio==4.14.2",
        "certifi==2026.1.1",
        "numpy==2.4.1 ; python_full_version < '3.11'",
        "numpy==2.5.0 ; python_full_version >= '3.11'",
    ]


def test_parse_pyproject_dependencies_missing_block_raises():
    with pytest.raises(ValueError, match="dependencies"):
        drift.parse_pyproject_dependencies("[project]\nname = 'x'\n")


def test_parse_compiled_output_skips_via_comments():
    entries = drift.parse_compiled_output(SAMPLE_COMPILED_NO_DRIFT)
    assert entries == [
        "anyio==4.14.2",
        "certifi==2026.1.1",
        "numpy==2.4.1 ; python_full_version < '3.11'",
        "numpy==2.5.0 ; python_full_version >= '3.11'",
    ]


def test_parse_compiled_output_skips_malformed_lines_without_crashing():
    entries = drift.parse_compiled_output(SAMPLE_COMPILED_MALFORMED)
    assert entries == ["anyio==4.14.2"]


def test_diff_dependencies_identical_sets_report_no_drift():
    current = drift.parse_pyproject_dependencies(SAMPLE_PYPROJECT)
    compiled = drift.parse_compiled_output(SAMPLE_COMPILED_NO_DRIFT)
    only_current, only_compiled = drift.diff_dependencies(current, compiled)
    assert only_current == []
    assert only_compiled == []


def test_diff_dependencies_changed_version_reports_both_sides():
    current = drift.parse_pyproject_dependencies(SAMPLE_PYPROJECT)
    compiled = drift.parse_compiled_output(SAMPLE_COMPILED_WITH_DRIFT)
    only_current, only_compiled = drift.diff_dependencies(current, compiled)
    assert only_current == ["anyio==4.14.2"]
    assert only_compiled == ["anyio==4.15.0"]


def test_format_dependencies_block_renders_sorted_quoted_array():
    block = drift.format_dependencies_block(["certifi==2026.1.1", "anyio==4.14.2"])
    assert block == (
        'dependencies = [\n'
        '    "anyio==4.14.2",\n'
        '    "certifi==2026.1.1",\n'
        ']'
    )


def test_write_dependencies_replaces_array_in_place():
    new_text = drift.write_dependencies(SAMPLE_PYPROJECT, ["anyio==4.15.0"])
    assert 'dependencies = [\n    "anyio==4.15.0",\n]' in new_text
    assert 'name = "qai-consultant-mcp"' in new_text
    assert "anyio==4.14.2" not in new_text


def test_main_check_mode_exits_zero_when_no_drift(tmp_path, monkeypatch, capsys):
    pyproject_path = tmp_path / "pyproject.toml"
    pyproject_path.write_text(SAMPLE_PYPROJECT, encoding="utf-8")
    compiled_path = tmp_path / "compiled.txt"
    compiled_path.write_text(SAMPLE_COMPILED_NO_DRIFT, encoding="utf-8")
    monkeypatch.setattr(drift, "PYPROJECT_PATH", pyproject_path)

    exit_code = drift.main(["--check", "--compiled", str(compiled_path)])

    assert exit_code == 0
    assert "No drift" in capsys.readouterr().out


def test_main_check_mode_exits_one_when_drift_found(tmp_path, monkeypatch, capsys):
    pyproject_path = tmp_path / "pyproject.toml"
    pyproject_path.write_text(SAMPLE_PYPROJECT, encoding="utf-8")
    compiled_path = tmp_path / "compiled.txt"
    compiled_path.write_text(SAMPLE_COMPILED_WITH_DRIFT, encoding="utf-8")
    monkeypatch.setattr(drift, "PYPROJECT_PATH", pyproject_path)

    exit_code = drift.main(["--check", "--compiled", str(compiled_path)])

    out = capsys.readouterr().out
    assert exit_code == 1
    assert "Drift detected" in out
    assert "anyio==4.15.0" in out


def test_main_write_mode_updates_pyproject_and_exits_zero(tmp_path, monkeypatch):
    pyproject_path = tmp_path / "pyproject.toml"
    pyproject_path.write_text(SAMPLE_PYPROJECT, encoding="utf-8")
    compiled_path = tmp_path / "compiled.txt"
    compiled_path.write_text(SAMPLE_COMPILED_WITH_DRIFT, encoding="utf-8")
    monkeypatch.setattr(drift, "PYPROJECT_PATH", pyproject_path)

    exit_code = drift.main(["--write", "--compiled", str(compiled_path)])

    assert exit_code == 0
    written = pyproject_path.read_text(encoding="utf-8")
    assert "anyio==4.15.0" in written
    assert "anyio==4.14.2" not in written


def test_main_write_mode_refuses_empty_compiled_input(tmp_path, monkeypatch, capsys):
    pyproject_path = tmp_path / "pyproject.toml"
    original_content = SAMPLE_PYPROJECT
    pyproject_path.write_text(original_content, encoding="utf-8")
    compiled_path = tmp_path / "compiled.txt"
    compiled_path.write_text("", encoding="utf-8")  # Empty file
    monkeypatch.setattr(drift, "PYPROJECT_PATH", pyproject_path)

    exit_code = drift.main(["--write", "--compiled", str(compiled_path)])

    assert exit_code != 0
    stderr = capsys.readouterr().err.lower()
    assert "empty" in stderr or "no dependencies" in stderr
    # Verify pyproject.toml was not corrupted
    written = pyproject_path.read_text(encoding="utf-8")
    assert written == original_content
