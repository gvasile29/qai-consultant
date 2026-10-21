"""Unit tests for .claude/hooks/guard_commands.py (ingest deny + publish ask)."""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parents[3] / ".claude" / "hooks" / "guard_commands.py"
_spec = importlib.util.spec_from_file_location("guard_commands", HOOK)
guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(guard)


@pytest.mark.parametrize("cmd", [
    "python src/ingest.py",
    "python src/ingest.py --help",
    "python3 -u src\\ingest.py",
    "cd C:/Personal/qai-consultant && python ./src/ingest.py",
    'PYTHONIOENCODING=utf-8 python "src/ingest.py"',
    "python -m qai_consultant.rag.ingest",
    "py -m ingest",
])
def test_ingest_is_denied(cmd):
    assert guard.evaluate(cmd)[0] == "deny"


@pytest.mark.parametrize("cmd", [
    "git add src/ingest.py",
    "ruff check src/ingest.py",
    "python -m ruff check src/ingest.py",
    "grep -rn ingest.py CLAUDE.md",
    "python -m pytest tests/unit/rag/test_ingest.py",
    "python -c \"from qai_consultant.rag import ingest; print(ingest.main)\"",
    "git status",
])
def test_ingest_lookalikes_are_allowed(cmd):
    assert guard.evaluate(cmd) == (None, "")


@pytest.mark.parametrize("cmd", [
    "twine upload dist/*",
    '"/tmp/mcp-publisher-install/mcp-publisher.exe" publish',
    "gh release create v3.9.1 --notes x",
    "git push origin master",
    "git push --force origin feature",
    "git push -f",
])
def test_publish_steps_ask(cmd):
    assert guard.evaluate(cmd)[0] == "ask"


@pytest.mark.parametrize("cmd", ["git push -u origin chore/x", "twine check dist/*", "gh pr create --title x"])
def test_ordinary_commands_pass(cmd):
    assert guard.evaluate(cmd) == (None, "")


def _run(command):
    return subprocess.run(
        [sys.executable, "-I", str(HOOK)],
        input=json.dumps({"tool_input": {"command": command}}),
        capture_output=True, text=True,
    )


def test_deny_exits_2_with_reason():
    r = _run("python src/ingest.py")
    assert r.returncode == 2 and "PRODUCTION" in r.stderr


def test_ask_emits_permission_json():
    r = _run("twine upload dist/*")
    assert r.returncode == 0
    assert json.loads(r.stdout)["hookSpecificOutput"]["permissionDecision"] == "ask"


def test_bad_payload_is_allowed():
    r = subprocess.run([sys.executable, "-I", str(HOOK)], input="not json", capture_output=True, text=True)
    assert r.returncode == 0
