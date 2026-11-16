"""requirements.txt (what Streamlit Cloud installs) must pin every package exactly.

A reboot of the Cloud app does a clean install. With `mistralai>=1.2.0` it pulled
mistralai 3.x, which fails at import on Python 3.11 (`SyntaxError: Forward
reference must be an expression`) and took the live app down, while every test
and CI run, resolved earlier, stayed green. pyproject.toml already has the same
rule for the wheel (test_packaging.py::test_all_dependencies_are_exact_pinned).
"""
import re
from pathlib import Path

REQUIREMENTS = Path(__file__).resolve().parents[3] / "requirements.txt"


def _requirement_lines() -> list[str]:
    lines = []
    for raw in REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if line and not line.startswith("-"):  # blank, comment, or an option like --extra-index-url
            lines.append(line)
    return lines


def test_requirements_has_packages_to_check():
    assert len(_requirement_lines()) > 10


def test_every_requirement_is_exact_pinned():
    loose = [line for line in _requirement_lines() if not re.fullmatch(r"[A-Za-z0-9._\-\[\]]+==[A-Za-z0-9.\-+!]+", line)]
    assert not loose, f"requirements.txt must use exact pins (==), found: {loose}"
