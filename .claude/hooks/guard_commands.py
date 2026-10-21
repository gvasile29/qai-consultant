"""PreToolUse hook (Bash/PowerShell): guard commands that are hard to undo.

- DENY   running the Pinecone ingest entry point. `src/ingest.py` has no argparse, so ANY
         invocation (even `--help`) deletes and re-uploads the production `knowledge-base`
         namespace. Verify it by import or mocks, never by running it.
- ASK    publishing steps that leave the machine: `twine upload`, `mcp-publisher publish`,
         `gh release create`, and `git push` to master/main or with a force flag.

Deny = exit 2 (reason on stderr). Ask = exit 0 with a permissionDecision JSON on stdout, so the
user is prompted even under auto mode. An unreadable payload is allowed through (this guards
accidents, it is not a security boundary; protect_files.py covers the file-edit tools).
"""

import json
import re
import sys

_PY = r"(?:python[\d.]*|py)(?:\.exe)?"
_INGEST_SCRIPT = re.compile(
    _PY + r"""["']?\s+(?:-[A-Za-z]+\s+)*["']?[\w./\\:~-]*\bingest\.py\b""", re.IGNORECASE
)
_INGEST_MODULE = re.compile(r"\s-m\s+(?:qai_consultant\.rag\.ingest|src\.ingest|ingest)\b", re.IGNORECASE)

_ASK_RULES = [
    (re.compile(r"\btwine(?:\.exe)?\s+upload\b", re.IGNORECASE), "twine upload publishes to PyPI"),
    (re.compile(r"\bmcp-publisher(?:\.exe)?[\"']?\s+publish\b", re.IGNORECASE), "mcp-publisher publish updates the MCP registry"),
    (re.compile(r"\bgh\s+release\s+create\b", re.IGNORECASE), "gh release create publishes a GitHub release"),
    (re.compile(r"\bgit\s+push\b[^|;&\n]*(?:\b(?:master|main)\b|\s--force\b|\s--force-with-lease\b|\s-f\b)", re.IGNORECASE),
     "git push to master/main or with a force flag"),
]


def evaluate(command: str):
    """Return ("deny"|"ask"|None, reason)."""
    if _INGEST_SCRIPT.search(command) or (_INGEST_MODULE.search(command) and re.search(_PY, command, re.IGNORECASE)):
        return "deny", (
            "Blocked: running ingest wipes and re-uploads the PRODUCTION Pinecone knowledge-base "
            "namespace (no --help or dry-run exists). Verify by import or mocks; ask the user to run it."
        )
    for pattern, reason in _ASK_RULES:
        if pattern.search(command):
            return "ask", f"Hard to undo: {reason}. Confirm before running."
    return None, ""


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        command = (payload.get("tool_input") or {}).get("command") or ""
    except (json.JSONDecodeError, AttributeError):
        return 0
    decision, reason = evaluate(command)
    if decision == "deny":
        print(reason, file=sys.stderr)
        return 2
    if decision == "ask":
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": reason,
        }}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
