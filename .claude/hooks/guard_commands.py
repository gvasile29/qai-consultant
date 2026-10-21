"""PreToolUse hook (Bash/PowerShell): guard commands that are hard to undo.

- DENY   running the Pinecone ingest entry point. `src/ingest.py` has no argparse, so ANY
         invocation (even `--help`) deletes and re-uploads the production `knowledge-base`
         namespace. Verify it by import or mocks, never by running it.
- ASK    publishing steps that leave the machine: `twine upload`, `mcp-publisher publish`,
         `gh release create`, and `git push` to master/main, a force/delete push, or a bare
         `git push` while master/main is checked out.

Commands are split into segments (`;`, `&&`, `||`, `|`, `&`, newline, `(`; not inside quotes) and only the segment's
own program and arguments are inspected, so a commit message or `echo` that merely mentions
`python src/ingest.py` is not blocked. Shell wrappers (`bash -c`, `powershell -Command`) are
unwrapped one level at a time.

Deny = exit 2 (reason on stderr). Ask = exit 0 with a permissionDecision JSON on stdout, so the
user is prompted even under auto mode. An unreadable payload is allowed through (this guards
accidents, it is not a security boundary; protect_files.py covers the file-edit tools).
"""

import json
import os
import re
import subprocess
import sys

_TOKEN = re.compile(r'"[^"]*"|\'[^\']*\'|\S+')
_PY = re.compile(r"^(?:python[\d.]*|py)$")
_SHELLS = {"bash", "sh", "zsh", "cmd", "powershell", "pwsh"}
_SHELL_FLAGS = {"-c", "-lc", "-command", "-c:", "/c", "-encodedcommand"}
_INGEST_MODULES = {"qai_consultant.rag.ingest", "src.ingest", "ingest"}
_INGEST_CODE = re.compile(r"ingest\.py|ingest\.main\s*\(|import\s+main\b[^;]*;\s*main\s*\(", re.IGNORECASE)
_PROTECTED = {"main", "master"}
_PY_VALUE_OPTS = {"-X", "-W", "-Q"}
_UV_VALUE_OPTS = {"--with", "--python", "-p", "--project", "--directory", "--extra", "--group", "-w", "--env-file"}

DENY_REASON = (
    "Blocked: running ingest wipes and re-uploads the PRODUCTION Pinecone knowledge-base "
    "namespace (no --help or dry-run exists). Verify by import or mocks; ask the user to run it."
)


_HEREDOC = re.compile(r"<<-?\s*(['\"]?)(\w+)\1[^\n]*\n.*?^\s*\2\s*$", re.DOTALL | re.MULTILINE)


def _strip_heredocs(command: str) -> str:
    """Drop here-document bodies (e.g. a PR description) so their text is not parsed as commands."""
    return _HEREDOC.sub(lambda m: m.group(0).split("\n", 1)[0], command)


def _split_segments(command: str) -> list[str]:
    """Split on ; && || | & newline ( outside quotes, so `python -c "a; b"` stays one segment."""
    segments, buf, quote = [], [], ""
    for ch in command:
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = ""
        elif ch in "\"'":
            quote = ch
            buf.append(ch)
        elif ch in ";&|\n(":
            segments.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    segments.append("".join(buf))
    return segments


def _unquote(tok: str) -> str:
    # Also drops stray quotes left when a `bash -c "a && b"` string was split on the `&&` inside it.
    return tok[1:-1] if len(tok) >= 2 and tok[0] == tok[-1] and tok[0] in "\"'" else tok.strip("\"'")


def _program(tok: str) -> str:
    name = re.split(r"[\\/]", _unquote(tok))[-1].casefold()
    return name[:-4] if name.endswith(".exe") else name


def _tokens(segment: str) -> list[str]:
    toks = [_unquote(t) for t in _TOKEN.findall(segment)]
    while toks and (toks[0] == "&" or re.match(r"^[A-Za-z_]\w*=", toks[0])):
        toks.pop(0)  # PowerShell call operator, VAR=value prefixes
    return toks


def _is_ingest_python(args: list[str]) -> bool:
    """args = tokens after the interpreter. True if they run the ingest entry point."""
    i = 0
    while i < len(args):
        a = args[i]
        if a == "-m":
            return i + 1 < len(args) and args[i + 1] in _INGEST_MODULES
        if a == "-c":
            return i + 1 < len(args) and bool(_INGEST_CODE.search(args[i + 1]))
        if a in _PY_VALUE_OPTS:
            i += 2
            continue
        if a.startswith("-"):
            i += 1
            continue
        return _program(a) == "ingest.py" or re.split(r"[\\/]", a)[-1].casefold() == "ingest.py"
    return False


def _is_ingest(toks: list[str]) -> bool:
    prog = _program(toks[0])
    if _PY.match(prog):
        return _is_ingest_python(toks[1:])
    if prog == "uv" and len(toks) > 1 and toks[1] == "run":
        i = 2
        while i < len(toks) and toks[i].startswith("-"):
            i += 2 if toks[i] in _UV_VALUE_OPTS else 1
        rest = toks[i:]
        if not rest:
            return False
        if _PY.match(_program(rest[0])):
            return _is_ingest_python(rest[1:])
        return re.split(r"[\\/]", rest[0])[-1].casefold() == "ingest.py"
    return False


def _current_branch() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True, timeout=3,
            cwd=os.environ.get("CLAUDE_PROJECT_DIR") or None,
        )
        return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def _push_decision(args: list[str], branch_fn) -> str | None:
    """args = tokens after `git`. Return an ask-reason for a risky push, else None."""
    i = 0
    while i < len(args) and args[i].startswith("-"):  # git global options, e.g. -C path, -c k=v
        i += 2 if args[i] in {"-C", "-c"} else 1
    if i >= len(args) or args[i] != "push":
        return None
    rest = args[i + 1:]
    positional = [a for a in rest if not a.startswith("-")]
    for a in rest:
        if a in {"--force", "--delete", "--mirror"} or a.startswith("--force-with-lease") or a.startswith("--force-if-includes"):
            return "git push with a force/delete/mirror flag"
        if re.fullmatch(r"-[A-Za-z]*[fd][A-Za-z]*", a):
            return "git push with a force/delete flag"
    for a in positional:
        if a.startswith("+"):
            return "git push with a +refspec (forced update)"
        parts = a.lstrip("+").replace("refs/heads/", "").split(":")
        if any(p in _PROTECTED for p in parts):
            return "git push to master/main"
    if len(positional) <= 1 and branch_fn() in _PROTECTED:
        return "bare git push while master/main is checked out"
    return None


def _segment_decision(segment: str, branch_fn, depth: int = 0):
    toks = _tokens(segment)
    if not toks:
        return None, ""
    prog = _program(toks[0])
    if prog in _SHELLS and depth < 3:
        for j, t in enumerate(toks[1:], start=1):
            if t.casefold() in _SHELL_FLAGS:
                return evaluate(" ".join(toks[j + 1:]), branch_fn, depth + 1)
        return None, ""
    if _is_ingest(toks):
        return "deny", DENY_REASON
    if prog == "twine" and "upload" in toks[1:2]:
        return "ask", "Hard to undo: twine upload publishes to PyPI. Confirm before running."
    if prog == "mcp-publisher" and "publish" in toks[1:2]:
        return "ask", "Hard to undo: mcp-publisher publish updates the MCP registry. Confirm before running."
    if prog == "gh" and toks[1:3] == ["release", "create"]:
        return "ask", "Hard to undo: gh release create publishes a GitHub release. Confirm before running."
    if prog == "git":
        why = _push_decision(toks[1:], branch_fn)
        if why:
            return "ask", f"Hard to undo: {why}. Confirm before running."
    return None, ""


def evaluate(command: str, branch_fn=_current_branch, depth: int = 0):
    """Return ("deny"|"ask"|None, reason). A deny anywhere in the command wins over an ask."""
    result = (None, "")
    for segment in _split_segments(_strip_heredocs(command)):
        decision = _segment_decision(segment, branch_fn, depth)
        if decision[0] == "deny":
            return decision
        if decision[0] == "ask" and result[0] is None:
            result = decision
    return result


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
