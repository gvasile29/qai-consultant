"""Detect drift between pyproject.toml's pinned MCP dependencies and a
fresh `uv pip compile` resolution.

Since v3.4.4, [project] dependencies in pyproject.toml is a full
exact-pinned transitive lock. `uv` treats `==` as a hard constraint, so
it will never substitute a newer version just because one was published
-- the residual risk this script guards against is a *currently* pinned
artifact becoming un-installable from a clean environment (a yanked
PyPI release, a wheel no longer built for some Python version/platform),
not new releases appearing. See
docs/superpowers/specs/2026-09-03-dependency-drift-canary-design.md.

Usage:
    uv pip compile pyproject.toml --universal --python-version 3.10 \\
        --extra-index-url https://download.pytorch.org/whl/cpu \\
        -o /tmp/compiled.txt
    python scripts/check_dependency_drift.py --check --compiled /tmp/compiled.txt
    python scripts/check_dependency_drift.py --write --compiled /tmp/compiled.txt

Parsed with regex/text splitting, not a TOML library -- this repo's CI
matrix includes Python 3.10, which has no stdlib `tomllib` (added in
3.11), the same reason tests/test_packaging.py's exact-pin test avoids
one.
"""

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT_PATH = REPO_ROOT / "pyproject.toml"

_DEPENDENCIES_BLOCK_RE = re.compile(r"dependencies\s*=\s*\[(.*?)\]", re.DOTALL)
_COMPILED_LINE_RE = re.compile(r"^([A-Za-z0-9_.-]+)==([\w.+]+)(?:\s*;\s*(.+))?$")


def parse_pyproject_dependencies(pyproject_text: str) -> list[str]:
    """Extract the raw dependency-entry strings from [project] dependencies."""
    match = _DEPENDENCIES_BLOCK_RE.search(pyproject_text)
    if not match:
        raise ValueError("Could not find a [project] dependencies list in pyproject.toml")
    entries = []
    for line in match.group(1).splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        line = line.rstrip(",").strip()
        # Remove outer quotes (either single or double) without stripping inner quotes
        if (line.startswith('"') and line.endswith('"')) or (line.startswith("'") and line.endswith("'")):
            line = line[1:-1]
        entries.append(line)
    return entries


def parse_compiled_output(compiled_text: str) -> list[str]:
    """Normalize `uv pip compile` stdout into 'name==version[ ; marker]' entries.

    Lines that don't match a requirement (blank lines, `# via ...`
    comments, anything malformed) are silently skipped -- this must
    never crash on unexpected input, since it runs unattended in CI.
    """
    entries = []
    for raw_line in compiled_text.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        match = _COMPILED_LINE_RE.match(line)
        if not match:
            continue
        name, version, marker = match.groups()
        entry = f"{name}=={version}"
        if marker:
            entry += f" ; {marker.strip()}"
        entries.append(entry)
    return entries


def diff_dependencies(current: list[str], compiled: list[str]) -> tuple[list[str], list[str]]:
    """Return (only_in_current, only_in_compiled), both sorted, order-independent."""
    current_set = set(current)
    compiled_set = set(compiled)
    return sorted(current_set - compiled_set), sorted(compiled_set - current_set)


def format_dependencies_block(entries: list[str]) -> str:
    """Render entries into the same `dependencies = [...]` shape already in pyproject.toml."""
    lines = ",\n".join(f'    "{entry}"' for entry in sorted(entries))
    return f"dependencies = [\n{lines},\n]"


def write_dependencies(pyproject_text: str, entries: list[str]) -> str:
    """Replace the existing dependencies array in pyproject_text with a freshly formatted one."""
    new_block = format_dependencies_block(entries)
    return _DEPENDENCIES_BLOCK_RE.sub(lambda _match: new_block, pyproject_text, count=1)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiled", required=True, type=Path, help="Path to `uv pip compile` output")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="Diff only (default)")
    mode.add_argument("--write", action="store_true", help="Overwrite pyproject.toml with the compiled set")
    args = parser.parse_args(argv)

    pyproject_text = PYPROJECT_PATH.read_text(encoding="utf-8")
    compiled_text = args.compiled.read_text(encoding="utf-8")

    current = parse_pyproject_dependencies(pyproject_text)
    compiled = parse_compiled_output(compiled_text)
    only_current, only_compiled = diff_dependencies(current, compiled)

    if not only_current and not only_compiled:
        print(f"No drift: {len(current)} dependencies match the freshly compiled set.")
        return 0

    print(f"Drift detected: {len(only_current)} stale pin(s), {len(only_compiled)} new/changed pin(s).")
    for entry in only_current:
        print(f"  - {entry}")
    for entry in only_compiled:
        print(f"  + {entry}")

    if args.write:
        new_text = write_dependencies(pyproject_text, compiled)
        PYPROJECT_PATH.write_text(new_text, encoding="utf-8")
        print(f"Wrote {len(compiled)} dependencies to {PYPROJECT_PATH}")
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
