"""PostToolUse hook: run `ruff check --fix` on a Python file Claude just edited.

Reads the hook payload from stdin. Silent when the file is clean (or not .py);
otherwise reports the remaining findings back to Claude via exit code 2, so they
get fixed in the same turn instead of surfacing later in CI's `quality` job.
"""

import json
import subprocess
import sys
from pathlib import Path


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    file_path = (payload.get("tool_input") or {}).get("file_path") or ""
    path = Path(file_path)
    if path.suffix != ".py" or not path.is_file():
        return 0
    try:
        result = subprocess.run(
            ["ruff", "check", "--fix", "--quiet", str(path)],
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
