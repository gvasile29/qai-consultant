"""Regenerate qai-consultant-mcp's fully-pinned [project.dependencies] array in
pyproject.toml via `uv pip compile`, then verify the exact-pin test and run
pip-audit against the freshly resolved lock in one command instead of three
manual steps. See pyproject.toml's own comment above `dependencies = [` for why
this must be a full transitive lock, not just the direct imports, and the
"single-package Dependabot PR" Gotcha in CLAUDE.md for why this must be
regenerated as one atomic block rather than hand-edited line by line.

Usage:
    python scripts/regenerate_mcp_lock.py            # regenerate, show diff, write
    python scripts/regenerate_mcp_lock.py --dry-run  # regenerate, show diff, don't write
"""
import argparse
import difflib
import re
import subprocess
import sys
import tempfile
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_PYPROJECT = _REPO_ROOT / "pyproject.toml"
_PYTHON_FLOOR = "3.10"


def _compile_lock() -> list[str]:
    result = subprocess.run(
        ["uv", "pip", "compile", str(_PYPROJECT), "--universal", "--python-version", _PYTHON_FLOOR],
        capture_output=True, text=True, cwd=_REPO_ROOT,
    )
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        raise SystemExit(result.returncode)
    return [
        line.strip() for line in result.stdout.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def _replace_dependencies_block(text: str, new_deps: list[str]) -> str:
    pattern = re.compile(r"(dependencies = \[\n)(.*?)(\n\])", re.DOTALL)
    match = pattern.search(text)
    if not match:
        raise RuntimeError("Could not find `dependencies = [ ... ]` block in pyproject.toml")
    body = "\n".join(f'    "{dep}",' for dep in new_deps)
    return text[: match.start()] + match.group(1) + body + match.group(3) + text[match.end():]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="show the diff but don't write pyproject.toml")
    args = parser.parse_args()

    print(f"Running: uv pip compile pyproject.toml --universal --python-version {_PYTHON_FLOOR}")
    new_deps = _compile_lock()

    old_text = _PYPROJECT.read_text(encoding="utf-8")
    new_text = _replace_dependencies_block(old_text, new_deps)

    diff = list(difflib.unified_diff(
        old_text.splitlines(keepends=True), new_text.splitlines(keepends=True),
        fromfile="pyproject.toml (old)", tofile="pyproject.toml (new)",
    ))
    if not diff:
        print("No changes - pyproject.toml's dependencies already match the resolved lock.")
        return 0

    print("".join(diff))

    if args.dry_run:
        print("--dry-run: not writing pyproject.toml.")
        return 0

    _PYPROJECT.write_text(new_text, encoding="utf-8")
    print(f"Wrote {len(new_deps)} pinned dependencies to pyproject.toml.")

    print("\nVerifying: pytest tests/test_packaging.py::test_all_dependencies_are_exact_pinned")
    check = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_packaging.py::test_all_dependencies_are_exact_pinned", "-q"],
        cwd=_REPO_ROOT,
    )
    if check.returncode != 0:
        print("FAIL: exact-pin test failed after regeneration — do not commit this change as-is.", file=sys.stderr)
        return check.returncode

    print("\nRunning pip-audit against the new lock (informational, non-blocking)...")
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, dir=_REPO_ROOT) as tmp:
        tmp.write("\n".join(new_deps) + "\n")
        tmp_path = tmp.name
    try:
        subprocess.run([sys.executable, "-m", "pip_audit", "-r", tmp_path, "--desc"], cwd=_REPO_ROOT)
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
