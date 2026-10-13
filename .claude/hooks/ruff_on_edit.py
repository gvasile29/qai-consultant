"""PostToolUse hook: run `ruff check --fix` on a Python file Claude just edited.

Reads the hook payload from stdin. Silent when the file is clean (or not .py);
otherwise reports the remaining findings back to Claude via exit code 2, so they
get fixed in the same turn instead of surfacing later in CI's `quality` job.
"""

import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    file_path = (payload.get("tool_input") or {}).get("file_path") or ""
    path = Path(file_path).resolve()
    if path.suffix != ".py" or not path.is_file() or not path.is_relative_to(PROJECT_ROOT):
        return 0  # only lint this repo's files, under this repo's ruff.toml
    try:
        # `python -m ruff` via the running interpreter, not a bare `ruff`: Windows
        # process search includes the cwd, so a planted ruff.exe would run.
        result = subprocess.run(
            [sys.executable, "-m", "ruff", "check", "--fix", "--quiet", str(path)],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return 0  # ruff unavailable/slow: never block editing over tooling
    if result.returncode == 0:
        return 0
    print(f"ruff findings remain in {path.name}:\n{result.stdout}{result.stderr}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
