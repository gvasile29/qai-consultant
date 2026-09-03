# MCP Dependency Drift Canary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Catch a `qai-consultant-mcp` dependency pin that's stopped being installable from a clean environment (yanked release, unavailable wheel) before a live user hits it, and stop GitHub's automatic Dependabot security-update PRs from silently corrupting the exact-pinned transitive dependency tree.

**Architecture:** A new weekly GitHub Actions workflow re-runs the existing pin-regeneration command (`uv pip compile pyproject.toml --universal ...`) from a clean runner and hands the output to a small, stdlib-only comparison script. Three outcomes: the compile itself fails (job fails loudly), the resolved set differs from what's committed (workflow opens a PR for human review), or it matches (silent no-op). The same workflow run also closes any open Dependabot PR touching `pyproject.toml`, since a single-line bump can't safely edit a fully exact-pinned transitive tree.

**Tech Stack:** GitHub Actions, Python 3 stdlib (`re`, `argparse`, `pathlib`) for the comparison script, `uv` (pinned in `requirements-dev.txt`) for the actual dependency resolution, `gh` CLI (preinstalled on GitHub-hosted runners) for PR create/close.

**Spec:** `docs/superpowers/specs/2026-09-03-dependency-drift-canary-design.md`

## Global Constraints

- The comparison script (`scripts/check_dependency_drift.py`) must be stdlib-only — no `tomllib` (this repo's CI test matrix includes Python 3.10, which lacks it in the standard library) and no third-party TOML parser. Parse `pyproject.toml`'s `dependencies` array with the same regex approach `tests/test_packaging.py::test_all_dependencies_are_exact_pinned` already uses.
- This change ships no new `qai-consultant-mcp` version — no `src/version.py` bump, no `pyproject.toml` `[project] version` change, no `CHANGELOG.md` entry. The Release Checklist does not apply.
- The new workflow must trigger only on `schedule` and `workflow_dispatch` — never `push` or `pull_request` — so it can never block a PR by construction (same rule `live-contract-tests.yml` already follows).
- Any `run:` step whose exit code must be trusted follows this repo's standing rule: `set -o pipefail` as the first line (see the CLAUDE.md gotcha on `tee` swallowing exit codes).
- Any CI job that needs a dev tool installs it via `pip install -r requirements-dev.txt` — never a bespoke unpinned `pip install <tool>` (see the CLAUDE.md gotcha on the ruff version-drift incident).
- Nothing in this design auto-merges. The workflow only ever opens a PR for a human to review.

---

### Task 1: Dependency drift comparison script

**Files:**
- Create: `scripts/check_dependency_drift.py`
- Test: `tests/test_check_dependency_drift.py`

**Interfaces:**
- Produces (consumed by Task 2's workflow, invoked as a CLI):
  - `python scripts/check_dependency_drift.py --check --compiled <path>` — exit `0` if the compiled file's dependency set matches `pyproject.toml`'s committed `dependencies` array, exit `1` if it differs, prints a human-readable diff either way.
  - `python scripts/check_dependency_drift.py --write --compiled <path>` — same diff, but also overwrites `pyproject.toml`'s `dependencies` array in place with the compiled set (sorted, formatted like the existing array) and exits `0`.
- Produces (consumed by any future test/tooling that wants the parsing logic directly): module-level functions `parse_pyproject_dependencies(text: str) -> list[str]`, `parse_compiled_output(text: str) -> list[str]`, `diff_dependencies(current: list[str], compiled: list[str]) -> tuple[list[str], list[str]]`, `format_dependencies_block(entries: list[str]) -> str`, `write_dependencies(pyproject_text: str, entries: list[str]) -> str`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_check_dependency_drift.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_check_dependency_drift.py -v`
Expected: `ModuleNotFoundError: No module named 'check_dependency_drift'` (the script doesn't exist yet).

- [ ] **Step 3: Write the implementation**

Create `scripts/check_dependency_drift.py`:

```python
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
    return [
        line.strip().rstrip(",").strip('"').strip("'")
        for line in match.group(1).splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_check_dependency_drift.py -v`
Expected: all tests PASS.

- [ ] **Step 5: Lint and type-check**

Run: `ruff check scripts/check_dependency_drift.py tests/test_check_dependency_drift.py`
Run: `mypy scripts/check_dependency_drift.py`
Expected: both clean. If mypy complains about the `sys.path.insert`/import pattern in the test file, add `# type: ignore` on that one import line rather than restructuring — this mirrors how a standalone `scripts/` module already gets imported by its own verification scripts in this repo (no `scripts/__init__.py` exists, and none should be added).

- [ ] **Step 6: Manually sanity-check against a real `uv pip compile` run (if `uv` is available locally)**

Run:
```bash
uv pip compile pyproject.toml --universal --python-version 3.10 \
  --extra-index-url https://download.pytorch.org/whl/cpu \
  -o /tmp/compiled.txt
python scripts/check_dependency_drift.py --check --compiled /tmp/compiled.txt
```
Expected: `No drift` (since `pyproject.toml` hasn't changed). If this instead reports drift or the script errors out, the real `uv pip compile` output format differs from the fixtures above in some way the parser doesn't handle — fix `parse_compiled_output` before proceeding to Task 2, since Task 2's workflow depends on this actually working against real output, not just the fixtures.

- [ ] **Step 7: Commit**

```bash
git add scripts/check_dependency_drift.py tests/test_check_dependency_drift.py
git commit -m "feat: add dependency drift comparison script"
```

---

### Task 2: Dependency Drift Canary workflow

**Files:**
- Modify: `requirements-dev.txt`
- Create: `.github/workflows/dependency-drift-check.yml`

**Interfaces:**
- Consumes: `scripts/check_dependency_drift.py`'s `--check`/`--write` CLI from Task 1.
- Produces: nothing consumed by another task — this is the end-user-facing deliverable (the scheduled workflow itself).

- [ ] **Step 1: Pin `uv` in requirements-dev.txt**

This repo's standing rule ("every CI job must install dev tools via `pip install -r requirements-dev.txt`, never a bespoke unpinned `pip install <tool>`") applies here — `uv` is a new dev tool this workflow needs.

Add to `requirements-dev.txt` (append after the existing `playwright==1.62.0` line):

```
# uv (v3.4.4+) -- runs the pin-regeneration command used both by
# .github/workflows/dependency-drift-check.yml and by anyone manually
# regenerating pyproject.toml's dependencies array per the comment above it.
uv==0.11.28
```

- [ ] **Step 2: Write the workflow**

Create `.github/workflows/dependency-drift-check.yml`:

```yaml
name: Dependency Drift Canary

on:
  schedule:
    - cron: '0 4 * * 0'
  workflow_dispatch: {}

permissions:
  contents: write
  pull-requests: write

jobs:
  drift-check:
    name: Dependency Drift Canary
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: "pip"

      - name: Install dependencies
        run: pip install -r requirements-dev.txt

      - name: Compile dependencies fresh
        run: |
          set -o pipefail
          uv pip compile pyproject.toml --universal --python-version 3.10 \
            --extra-index-url https://download.pytorch.org/whl/cpu \
            -o /tmp/compiled.txt

      - name: Check for drift
        id: drift
        run: |
          set -o pipefail
          if python scripts/check_dependency_drift.py --check --compiled /tmp/compiled.txt; then
            echo "found=false" >> "$GITHUB_OUTPUT"
          else
            echo "found=true" >> "$GITHUB_OUTPUT"
          fi

      - name: Open pull request with regenerated pins
        if: steps.drift.outputs.found == 'true'
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          set -o pipefail
          python scripts/check_dependency_drift.py --write --compiled /tmp/compiled.txt
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          BRANCH="deps/drift-canary-$(date -u +%Y%m%d)"
          git checkout -b "$BRANCH"
          git add pyproject.toml
          git commit -m "chore: regenerate MCP dependency pins (drift canary)"
          git push origin "$BRANCH"
          gh pr create \
            --title "chore: regenerate MCP dependency pins (drift canary)" \
            --body "Automated weekly canary found the resolved dependency set no longer matches pyproject.toml's committed pins. Requires human review before merging -- see docs/superpowers/specs/2026-09-03-dependency-drift-canary-design.md." \
            --base master \
            --head "$BRANCH"

      - name: Close stale Dependabot PRs touching pyproject.toml
        if: always()
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          set -o pipefail
          for pr in $(gh pr list --author "app/dependabot" --state open --json number --jq '.[].number'); do
            files=$(gh pr view "$pr" --json files --jq '.files[].path')
            if echo "$files" | grep -qx "pyproject.toml"; then
              gh pr close "$pr" --comment "Closing: pyproject.toml's [project] dependencies is a full exact-pinned transitive lock (~99 entries, see the v3.4.4 gotcha in CLAUDE.md). A single-package security bump can't safely edit one line of that array without recomputing the whole tree -- see docs/superpowers/specs/2026-09-03-dependency-drift-canary-design.md. The weekly Dependency Drift Canary workflow (.github/workflows/dependency-drift-check.yml) is the sole trusted mechanism for changing this file."
            fi
          done
```

- [ ] **Step 3: Validate the workflow YAML parses**

Run: `python -c "import yaml, sys; yaml.safe_load(open('.github/workflows/dependency-drift-check.yml'))" ` (uses `pyyaml`, already a transitive dependency of this repo's toolchain — if unavailable locally, skip this step and rely on GitHub's own validation on push).
Expected: no exception.

- [ ] **Step 4: Commit**

```bash
git add requirements-dev.txt .github/workflows/dependency-drift-check.yml
git commit -m "feat: add weekly dependency drift canary workflow"
```

- [ ] **Step 5: After merging to master, trigger a manual dry run**

Via the GitHub UI (Actions tab → "Dependency Drift Canary" → "Run workflow") or `gh workflow run dependency-drift-check.yml`. Confirm it completes green with no PR opened (the pins should still be current immediately after merge). This is the spec's required manual verification before relying on the weekly schedule — do not skip it.

---

### Task 3: CLAUDE.md documentation

**Files:**
- Modify: `CLAUDE.md`

**Interfaces:**
- None — documentation only, no code consumes this.

- [ ] **Step 1: Add a paragraph describing the new workflow to the CI section**

In `CLAUDE.md`, find this existing paragraph (immediately after the CI jobs table):

```
A separate workflow, `.github/workflows/live-contract-tests.yml`, runs nightly (`0 3 * * *`) and via manual `workflow_dispatch` against real Pinecone/Mistral/OpenRouter — `tests/test_live_contracts.py`'s `test_pinecone_roundtrip`/`test_mistral_completion`/`test_openrouter_fallback`. It never triggers on `push`/`pull_request`, so it can never block a PR by construction. It needs `MISTRAL_API_KEY`/`OPENROUTER_API_KEY`/`PINECONE_API_KEY`/`PINECONE_INDEX_NAME` configured as GitHub Actions repository secrets (separate from Streamlit Cloud's own secrets store) — until they're added, every test in it SKIPs silently rather than failing. The Pinecone test writes only to a dedicated `ci-contract-tests` namespace, isolated from `knowledge-base` and `app-metrics`, and cleans up after itself; the fetch retries up to 3 times (1.5s apart) to absorb serverless-index eventual consistency without masking a real contract break. The Mistral and OpenRouter tests go through the real `agent.LLMClient` code path (not raw SDK calls) — `test_openrouter_fallback` mocks `llm_client._mistral.chat.complete` to raise, forcing the real Mistral-to-OpenRouter fallback branch to execute against the real OpenRouter API — so a break in message-building, response extraction, or the fallback logic itself is caught here too, not just an auth/model-name/endpoint break. The workflow's `run:` block starts with `set -o pipefail`, per the `tee`-swallows-exit-code gotcha documented below — without it, this job would report green even on a real contract break.
```

Immediately after it, insert a new paragraph:

```
Another separate workflow, `.github/workflows/dependency-drift-check.yml`, runs weekly (`0 4 * * 0`, Sunday) and via manual `workflow_dispatch` — never `push`/`pull_request`, same construction as `live-contract-tests.yml`. It re-runs `pyproject.toml`'s documented pin-regeneration command (`uv pip compile pyproject.toml --universal ...`) from a clean runner and diffs the result against the committed `[project] dependencies` array via `scripts/check_dependency_drift.py`. Three outcomes: the compile itself fails (job fails red, GitHub's default email to watchers fires — the currently-published pins may no longer install cleanly, e.g. a yanked release), the resolved set differs (a PR is opened with the regenerated array for human review — nothing here auto-merges), or it matches (silent no-op, the common case). The same run also closes any open Dependabot PR touching `pyproject.toml` — see the gotcha below for why. Design spec: `docs/superpowers/specs/2026-09-03-dependency-drift-canary-design.md`.
```

- [ ] **Step 2: Add a new gotcha**

At the end of the `## Gotchas` section (after the `transformers` CVE gotcha, which is currently the last entry), append:

```
- **A single-package Dependabot security-update PR can silently corrupt the full exact-pinned transitive tree — close it, don't merge it.** `pyproject.toml`'s `[project] dependencies` (v3.4.4) is a *fully resolved* lock: every entry was chosen together by one `uv pip compile` run, so the versions are mutually consistent. GitHub's automatic Dependabot security updates operate per vulnerable package, not per full resolution — one such PR (#84) bumped a single pinned line without recomputing the rest, which would have desynchronized that entry from the versions the other ~98 entries were actually resolved against, risking exactly the kind of inconsistency the v3.4.4 fix eliminated. Closed manually at the time; the weekly Dependency Drift Canary workflow (`.github/workflows/dependency-drift-check.yml`, added alongside this gotcha) now does this automatically every run — any Dependabot PR touching `pyproject.toml` gets closed with an explanatory comment, not merged. This only applies to `pyproject.toml`'s dependencies array; Dependabot PRs against `requirements.txt` (the Streamlit app's dependencies, no full-transitive-pin fragility there) are unaffected and still fine to review/merge normally. Design spec: `docs/superpowers/specs/2026-09-03-dependency-drift-canary-design.md`.
```

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: document the dependency drift canary workflow and Dependabot-PR gotcha"
```
