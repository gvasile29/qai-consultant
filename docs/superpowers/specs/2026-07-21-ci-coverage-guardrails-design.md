# CI Quality Gates (Part 3: Coverage Threshold + Release Guardrails) — Design

**Date:** 2026-07-21
**Status:** Approved by user, pending spec review

## Problem

There is no code-coverage measurement or threshold anywhere in this project
(locally or in CI), so a PR that adds untested code paths has no automated
signal. Separately, the project has a manual, easy-to-forget release
checklist (`CLAUDE.md`'s "Release Checklist" section) requiring several files
to be updated together on every version bump; `tests/test_changelog.py`
already guards one piece of that (CHANGELOG.md's top heading matching
`src/version.py`'s `__version__`) but not `pyproject.toml`'s version field —
which was manually kept in sync 3 times in one day during this same session
(v3.1.1 → v3.1.2 → v3.1.3), each time by hand, with no automated check that
would have caught a slip.

## Scope

Third of four CI-improvement sub-projects (see
`2026-07-21-ci-quality-gates-design.md`'s "Explicitly out of scope" section
for the full list; Part 1 = mypy/bandit/pip-audit, Part 2 = evals gate).
This spec covers only: a coverage-threshold CI job, plus two new guardrail
tests added to the existing `tests/test_changelog.py`.

## Coverage baseline

Measured locally via `pytest tests/ --cov=src --cov-report=term-missing`:
**61% overall** (3110 statements, 1201 missed). Notably uneven: UI-heavy
modules are low (`app.py` 17%, `cli.py` 19% — expected, since these are
Streamlit/Rich presentation layers exercised by manual testing, not unit
tests) while most business-logic modules are high (`ai_disclosure.py`,
`kb_config.py`, `visit_counter.py`, `templates.py`, `kb_manifest.py` all
100%; `review_core.py` 99%; most others 80-97%).

## Coverage CI job

A new, single job — **not** added to the existing 3-way Python version test
matrix, since coverage percentage doesn't meaningfully vary across Python
3.10/3.11/3.12 and tripling the coverage-instrumented run would only add CI
time for no signal:

```yaml
  coverage:
    name: Coverage (pytest-cov)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: "pip"
      - name: Install dependencies
        run: pip install -r requirements-dev.txt
      - name: Run tests with coverage
        run: |
          echo "## Coverage (src/)" >> "$GITHUB_STEP_SUMMARY"
          echo '```' >> "$GITHUB_STEP_SUMMARY"
          python -m pytest tests/ -q --cov=src --cov-report=term-missing --cov-fail-under=61 | tee -a "$GITHUB_STEP_SUMMARY"
          echo '```' >> "$GITHUB_STEP_SUMMARY"
```

`--cov-fail-under=61` sets the floor at the measured baseline (61.39%
rounds down to 61, giving a small buffer against harmless single-line
fluctuations rather than pinning the exact decimal, which would be
needlessly brittle). No `continue-on-error` — per the user's choice, this
gate is blocking from day one: it can only get stricter over time (raising
the threshold as coverage improves), never silently regress.

`pytest-cov` needs adding to `requirements-dev.txt` (confirmed it's not
currently listed there, even though it happened to already be present in
this local dev environment from some other install).

## Release guardrails (added to `tests/test_changelog.py`)

Both guardrails are plain, dependency-free pytest tests, added to the
existing file rather than a new one or a separate CI job — they're pure
Python/regex checks over already-loaded file contents (`test_changelog.py`
already parses `CHANGELOG.md` and imports `version.py`), so they run
automatically inside the existing blocking `test` job on every PR, no new
CI wiring needed.

**1. `pyproject.toml` version drift guard:**

```python
def test_pyproject_version_matches_version_py():
    """pyproject.toml's [project] version must match src/version.py's
    __version__ -- these were kept in sync by hand 3 times in one day
    (v3.1.1/3.1.2/3.1.3) with nothing catching a slip."""
    text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'(?m)^version\s*=\s*"([^"]+)"', text)
    assert match, "No 'version = \"X.Y.Z\"' line found in pyproject.toml"
    assert match.group(1) == __version__, (
        f"pyproject.toml's version is {match.group(1)!r} but "
        f"version.py's __version__ is {__version__!r} -- they must match."
    )
```

**2. CHANGELOG top entry has real content, not just a bare heading:**

```python
def test_changelog_top_entry_has_content():
    """The newest CHANGELOG.md entry must have substantive content (at
    least one bullet line) between its heading and the next version
    heading (or end of file) -- catches a version bump that adds the
    heading but forgets to fill in what actually changed."""
    text = CHANGELOG_PATH.read_text(encoding="utf-8")
    headings = list(re.finditer(r"(?m)^## \[", text))
    assert headings, "No '## [X.Y.Z]' version heading found in CHANGELOG.md"
    start = headings[0].end()
    end = headings[1].start() if len(headings) > 1 else len(text)
    body = text[start:end]
    assert re.search(r"(?m)^- ", body), (
        "The topmost CHANGELOG.md entry has no '- ' bullet content -- "
        "looks like a bare heading with nothing describing the change."
    )
```

Both reuse `REPO_ROOT`, `CHANGELOG_PATH`, `__version__`, and the `re`/`sys`
imports already present at the top of `test_changelog.py` — no new imports
needed beyond what the file already has.

## Explicitly out of scope

- Raising the coverage threshold above the current baseline, or chasing
  specific low-coverage modules (`app.py`, `cli.py`, `ingest.py`) up —
  that's a real, separate testing-investment decision, not a CI-wiring one.
- The other guardrail ideas considered but deferred this round:
  `requirements.txt` ↔ `requirements-dev.txt` consistency, and "every new
  `src/*.py` module has a corresponding `tests/test_*.py`" — the user
  explicitly scoped this spec to just the two guardrails above.
- Part 1 (mypy/bandit/pip-audit) and Part 2 (evals gate) — separate specs.
- Part 4 (live API-contract tests against Pinecone/Mistral) — separate spec.

## Testing / verification plan

- Run the two new `test_changelog.py` tests locally before committing;
  confirm both pass against the current (correctly in-sync) `pyproject.toml`
  / `version.py` / `CHANGELOG.md`.
- As a negative-path sanity check (not committed): temporarily change
  `pyproject.toml`'s version to a mismatched value and confirm
  `test_pyproject_version_matches_version_py` fails with a clear message;
  revert. Same for temporarily blanking the top CHANGELOG entry's body and
  confirming `test_changelog_top_entry_has_content` fails; revert.
- Push a branch with the new `coverage` CI job, confirm it appears in the PR
  checks list, passes (since 61.39% ≥ 61), and shows the coverage table in
  its Job Summary.
