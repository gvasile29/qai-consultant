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


def decide(cmd, branch="feature"):
    return guard.evaluate(cmd, branch_fn=lambda: branch)[0]


@pytest.mark.parametrize("cmd", [
    "python src/ingest.py",
    "python src/ingest.py --help",
    "python3 -u src\\ingest.py",
    "python -X utf8 src\\ingest.py",
    "python -u -X utf8 src/ingest.py",
    "python -Xutf8 src/ingest.py",
    "python -W ignore src/ingest.py",
    "py -3 src/ingest.py",
    "py -3.11 src/ingest.py",
    "uv run src/ingest.py",
    "uv run --with pinecone python src/ingest.py",
    "cd C:/Personal/qai-consultant && python ./src/ingest.py",
    "cd src; python ingest.py",
    'PYTHONIOENCODING=utf-8 python "src/ingest.py"',
    "& python src\\ingest.py",
    "C:\\Python311\\python.exe src\\ingest.py",
    'bash -c "cd x && python src/ingest.py"',
    'powershell -Command "python src/ingest.py"',
    "python -m qai_consultant.rag.ingest",
    "py -m ingest",
    "python -c \"import runpy; runpy.run_path('src/ingest.py')\"",
    "python -c \"from qai_consultant.rag.ingest import main; main()\"",
])
def test_ingest_is_denied(cmd):
    assert decide(cmd) == "deny", cmd


@pytest.mark.parametrize("cmd", [
    "git add src/ingest.py",
    "ruff check src/ingest.py",
    "python -m ruff check src/ingest.py",
    "python -m ruff check -m ingest",
    "python scripts/foo.py ingest.py",
    "grep -rn ingest.py CLAUDE.md",
    "python -m pytest tests/unit/rag/test_ingest.py",
    "python -c \"from qai_consultant.rag import ingest; print(ingest.main)\"",
    "git commit -m 'run python src/ingest.py'",
    "echo python src/ingest.py",
    "uv run ruff check src/ingest.py",
    "git status",
])
def test_ingest_lookalikes_are_allowed(cmd):
    assert decide(cmd) is None, cmd


@pytest.mark.parametrize("cmd", [
    "twine upload dist/*",
    '"/tmp/mcp-publisher-install/mcp-publisher.exe" publish',
    "gh release create v3.9.1 --notes x",
    "git push origin master",
    "git push origin HEAD:master",
    "git push origin feature:main",
    "git push --force origin feature",
    "git push -f",
    "git push -uf origin feature",
    "git push origin +feature",
    "git push --delete origin x",
    "git push --force-with-lease origin feature",
    "git -C . push origin master",
])
def test_publish_steps_ask(cmd):
    assert decide(cmd) == "ask", cmd


def test_bare_push_asks_only_on_protected_branch():
    assert decide("git push", branch="master") == "ask"
    assert decide("git push origin", branch="main") == "ask"
    assert decide("git push", branch="chore/x") is None


@pytest.mark.parametrize("cmd", [
    "git push -u origin chore/x",
    "git push origin chore/main",
    "git push origin feature/main-fix",
    "twine check dist/*",
    "gh pr create --title x",
    "git commit -m 'git push origin master'",
])
def test_ordinary_commands_pass(cmd):
    assert decide(cmd, branch="master") is None, cmd


def test_heredoc_body_is_not_parsed_as_commands():
    body = "git commit -q -m x\ncat > f.md <<'EOF'\nran: python src/ingest.py --help\n| twine upload dist/*\nEOF\ngit status"
    assert decide(body) is None


def test_command_after_heredoc_is_still_checked():
    assert decide("cat <<EOF\nhello\nEOF\npython src/ingest.py") == "deny"


def test_deny_wins_over_ask():
    assert decide("git push origin master && python src/ingest.py") == "deny"


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
