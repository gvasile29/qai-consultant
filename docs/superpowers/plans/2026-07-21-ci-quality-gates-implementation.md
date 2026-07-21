# CI Quality Gates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add four independent CI quality gates to QAI Consultant's GitHub Actions pipeline — static type checking + security scanning (non-blocking), a deterministic evals release gate (blocking), a coverage threshold plus two release-checklist guardrails (blocking), and a scheduled live API-contract test suite against real Pinecone/Mistral/OpenRouter (never PR-blocking) — shipped as four separate, independently mergeable PRs, in order.

**Architecture:** Each phase below implements exactly one of the four approved specs in `docs/superpowers/specs/`:
- Phase 1 → `2026-07-21-ci-quality-gates-design.md`
- Phase 2 → `2026-07-21-ci-evals-gate-design.md`
- Phase 3 → `2026-07-21-ci-coverage-guardrails-design.md`
- Phase 4 → `2026-07-21-ci-live-contract-tests-design.md`

Phases 1-3 add new jobs to the existing `.github/workflows/ci.yml`. Phase 4 adds a wholly separate workflow file plus a new test file, since it must never trigger on `push`/`pull_request`. Each phase ends with its own commit(s), its own pushed branch, and its own PR — **do not start Phase N+1 until Phase N's PR is open and (per the user's explicit ask) has been reviewed.** Phases 2-4 each begin by pulling the latest `master` (which will include the prior phase's merged work) before branching.

**Tech Stack:** GitHub Actions (YAML), Python 3.11 (matching the existing `lint` job's convention for single-version quality jobs), `mypy`, `bandit`, `pip-audit`, `pytest-cov` — all added to `requirements-dev.txt` so they're runnable identically locally and in CI.

## Global Constraints

- New single-version quality jobs (as opposed to the existing 3-way `test` matrix) run on Python **3.11**, matching the existing `lint` job — copy that job's `actions/checkout@v4` / `actions/setup-python@v5` / `cache: "pip"` pattern exactly.
- All new dev-only tool dependencies go in `requirements-dev.txt` (never `requirements.txt`, which is what Streamlit Cloud installs for the production app) and use exact version pins (`==`), matching the file's existing `ruff==0.4.4` / `pytest==9.0.3` / `pytest-mock==3.14.0` style.
- Every new job writes a human-readable report to `$GITHUB_STEP_SUMMARY` in addition to whatever exits normally to the job log — this is a project convention being introduced by this plan, keep it consistent across all phases.
- **No version bump is needed for any of these four PRs.** `CLAUDE.md`'s Release Checklist triggers off a new `__version__` in `src/version.py` — none of these tasks touch `src/version.py`, `pyproject.toml`'s `[project] version`, or `CHANGELOG.md`. This is CI infrastructure, not an app feature.
- Every phase's final task updates `CLAUDE.md` to document what was added — this repo treats `CLAUDE.md` as living documentation of exactly this kind of infrastructure decision (see its existing "Gotchas" and "Evals" sections for the tone/density to match).
- Branch naming: `ci/<short-phase-name>` (e.g. `ci/mypy-bandit-pip-audit`), matching the repo's existing `feat/...`/`fix/...` convention but with a `ci/` prefix since none of these are app features or bug fixes.
- This repo's `master` branch has required PR reviews (branch protection) — every phase's final step is "push the branch and open the PR," not "merge." Wait for the user to merge (as happened for the recent v3.1.1/v3.1.2/v3.1.3 PRs) before starting the next phase.

---

## Phase 1: Static Type Checking + Static Security (non-blocking)

Implements `docs/superpowers/specs/2026-07-21-ci-quality-gates-design.md`.

### Task 1.1: Add mypy, bandit, pip-audit to requirements-dev.txt and verify they install

**Files:**
- Modify: `requirements-dev.txt`

**Interfaces:**
- Produces: `mypy`, `bandit`, `pip-audit` importable/runnable in any environment that runs `pip install -r requirements-dev.txt` — every later task in this phase depends on this.

- [ ] **Step 1: Create the branch**

```bash
git checkout master
git pull origin master
git checkout -b ci/mypy-bandit-pip-audit
```

- [ ] **Step 2: Add the three new dev dependencies**

Current `requirements-dev.txt`:
```
# Development dependencies - not needed for running QAI Consultant
-r requirements.txt
ruff==0.4.4
pytest==9.0.3
pytest-mock==3.14.0

# MCP server (v3.0) — needed to run/test src/mcp_server.py locally. Not part of
# requirements.txt: the MCP server is a separate package (pyproject.toml, step 8),
# not something the Streamlit Cloud deploy needs.
mcp>=1.8.0
build>=1.0.0
setuptools>=67.0
```

Edit it to:
```
# Development dependencies - not needed for running QAI Consultant
-r requirements.txt
ruff==0.4.4
pytest==9.0.3
pytest-mock==3.14.0
mypy==2.3.0
bandit==1.9.4
pip-audit==2.10.1

# MCP server (v3.0) — needed to run/test src/mcp_server.py locally. Not part of
# requirements.txt: the MCP server is a separate package (pyproject.toml, step 8),
# not something the Streamlit Cloud deploy needs.
mcp>=1.8.0
build>=1.0.0
setuptools>=67.0
```

- [ ] **Step 3: Verify they install**

Run: `pip install -r requirements-dev.txt`
Expected: no errors; ends with something like `Successfully installed ... mypy-2.3.0 bandit-1.9.4 pip-audit-2.10.1 ...` (or "Requirement already satisfied" for each if already present from a prior step in this same session).

- [ ] **Step 4: Commit**

```bash
git add requirements-dev.txt
git commit -m "ci: add mypy, bandit, pip-audit dev dependencies"
```

### Task 1.2: Add mypy configuration to pyproject.toml

**Files:**
- Modify: `pyproject.toml`

**Interfaces:**
- Produces: `mypy src/` run from the repo root uses `ignore_missing_imports = true` automatically, both locally and in CI (Task 1.4 relies on this).

- [ ] **Step 1: Add the `[tool.mypy]` section**

In `pyproject.toml`, immediately after the `[project.scripts]` block (before the `# ── uv: pin torch to the CPU wheel index...` comment), insert:

```toml
[tool.mypy]
ignore_missing_imports = true
```

So the file reads (showing the surrounding context, only the new block is added):
```toml
[project.scripts]
qai-consultant-mcp = "mcp_server:main"

[tool.mypy]
ignore_missing_imports = true

# ── uv: pin torch to the CPU wheel index, scoped ONLY to torch ──────────────────
```

- [ ] **Step 2: Verify mypy runs and picks up the config**

Run: `mypy src/`
Expected: it runs to completion (no crash) and reports a findings count — as of this plan being written, the actual codebase reports `Found 53 errors in 12 files (checked 25 source files)`. That number is expected to be non-zero right now; this task is about wiring the tool, not fixing it (see Global Constraints and Task 1.4 — non-blocking is deliberate).

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "ci: add mypy configuration (ignore_missing_imports)"
```

### Task 1.3: Verify bandit and pip-audit run against this codebase

**Files:** none (verification-only task; no commit)

**Interfaces:** none new — confirms the exact commands Task 1.4's CI job will run.

- [ ] **Step 1: Run bandit**

Run: `bandit -r src/ -ll`
Expected: runs to completion, reports findings (as of this plan being written: 2 medium-severity findings — an `xml.etree.ElementTree.fromstring` usage in `src/results_core.py` and a `urllib.request.urlopen` usage in `src/telemetry.py` — both pre-existing, out of scope to fix here) and exits with a non-zero exit code. Confirm with `echo $?` after the command — should print `1`.

- [ ] **Step 2: Run pip-audit**

Run: `pip-audit -r requirements.txt --desc`
Expected: runs to completion, reports known vulnerabilities in transitive dependencies (as of this plan being written: 10 known vulnerabilities across `langchain`, `nltk`, `langchain-core`, `langchain-text-splitters`, `transformers` — all pre-existing, out of scope to fix here) and exits with a non-zero exit code. Confirm with `echo $?` — should print `1`.

This confirms the premise behind Task 1.4's `continue-on-error: true`: both tools currently fail on real, pre-existing findings unrelated to any specific PR.

### Task 1.4: Add the three new CI jobs to ci.yml

**Files:**
- Modify: `.github/workflows/ci.yml`

**Interfaces:**
- Consumes: `requirements-dev.txt` (Task 1.1), `pyproject.toml`'s `[tool.mypy]` (Task 1.2).
- Produces: three new PR-checks-list entries — `Type Check (mypy)`, `Security (bandit)`, `Security (pip-audit)` — all non-blocking.

- [ ] **Step 1: Add the three jobs**

Current `.github/workflows/ci.yml` ends with the `lint` job (after the `test` job). Append these three new top-level jobs after `lint` (same indentation level as `test:` and `lint:`):

```yaml
  typecheck:
    name: Type Check (mypy)
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

      - name: Run mypy
        continue-on-error: true
        run: |
          echo "## mypy (src/)" >> "$GITHUB_STEP_SUMMARY"
          echo '```' >> "$GITHUB_STEP_SUMMARY"
          mypy src/ | tee -a "$GITHUB_STEP_SUMMARY"
          echo '```' >> "$GITHUB_STEP_SUMMARY"
        # Non-blocking by design — promote to blocking once the pre-existing
        # backlog is cleared. See CLAUDE.md's CI section.

  security-bandit:
    name: Security (bandit)
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

      - name: Run bandit
        continue-on-error: true
        run: |
          echo "## bandit (src/, medium+ severity)" >> "$GITHUB_STEP_SUMMARY"
          echo '```' >> "$GITHUB_STEP_SUMMARY"
          bandit -r src/ -ll | tee -a "$GITHUB_STEP_SUMMARY"
          echo '```' >> "$GITHUB_STEP_SUMMARY"
        # Non-blocking by design — see CLAUDE.md's CI section.

  security-pip-audit:
    name: Security (pip-audit)
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

      - name: Run pip-audit
        continue-on-error: true
        run: |
          echo "## pip-audit (requirements.txt)" >> "$GITHUB_STEP_SUMMARY"
          echo '```' >> "$GITHUB_STEP_SUMMARY"
          pip-audit -r requirements.txt --desc | tee -a "$GITHUB_STEP_SUMMARY"
          echo '```' >> "$GITHUB_STEP_SUMMARY"
        # Non-blocking by design — see CLAUDE.md's CI section.
```

- [ ] **Step 2: Verify the YAML is well-formed**

Run: `python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))" `
Expected: no output, no exception (a parse error would raise `yaml.YAMLError` with a line number).

If `pyyaml` isn't installed, run `pip install pyyaml` first (it's already a transitive dependency of `langchain`, so this should already be available).

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: add non-blocking mypy/bandit/pip-audit jobs"
```

### Task 1.5: Document the CI policy in CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

**Interfaces:** none — documentation only.

- [ ] **Step 1: Add a new "## CI" section**

In `CLAUDE.md`, find this exact text (the end of the "Evals" section, right before "## Roadmap"):

```
> **Skip semantics:** judged metrics SKIP (never fail) when the judge backend is unreachable; the whole RAG tier SKIPs when `sentence-transformers` is absent — so a bare CI box still runs the full deterministic tier. Add a case by appending a line to the relevant `*.jsonl`; the datasets *are* the suites.

## Roadmap
```

Replace it with (inserting a new "## CI" section between them):

```
> **Skip semantics:** judged metrics SKIP (never fail) when the judge backend is unreachable; the whole RAG tier SKIPs when `sentence-transformers` is absent — so a bare CI box still runs the full deterministic tier. Add a case by appending a line to the relevant `*.jsonl`; the datasets *are* the suites.

## CI

GitHub Actions (`.github/workflows/ci.yml`) runs on every push/PR to `main`/`master`:

| Job | Blocking? | What it checks |
|-----|-----------|-----------------|
| `test` | Yes | `pytest tests/` on Python 3.10/3.11/3.12 |
| `lint` | Yes | `ruff check src/ tests/` |
| `typecheck` | **No** | `mypy src/` — non-blocking because the codebase has partial, inconsistent type-annotation coverage; a strict pass surfaces ~53 pre-existing errors unrelated to any given PR. Promote to blocking once that backlog is addressed. |
| `security-bandit` | **No** | `bandit -r src/ -ll` — non-blocking; currently reports 2 pre-existing medium-severity findings (`results_core.py`'s `ET.fromstring`, `telemetry.py`'s `urlopen`). |
| `security-pip-audit` | **No** | `pip-audit -r requirements.txt --desc` — non-blocking; currently reports known CVEs in transitive dependencies (`langchain`, `nltk`, `transformers`, etc.) that aren't immediately fixable without upstream upgrades. |

All three non-blocking jobs use `continue-on-error: true` (not a shell-level `|| true`) so their findings stay visible as a neutral/warning status in the PR checks list and in each job's `$GITHUB_STEP_SUMMARY`, without blocking merge. Promoting any of them to blocking is a deliberate future decision — not an oversight — once the pre-existing backlog each surfaces is actually cleared.

## Roadmap
```

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: document CI policy for mypy/bandit/pip-audit"
```

### Task 1.6: Push and open the PR

- [ ] **Step 1: Push the branch**

```bash
git push -u origin ci/mypy-bandit-pip-audit
```

- [ ] **Step 2: Open the PR**

```bash
gh pr create --base master --head ci/mypy-bandit-pip-audit \
  --title "ci: add non-blocking mypy/bandit/pip-audit checks" \
  --body "$(cat <<'EOF'
## Summary
- Adds three new, non-blocking CI jobs: `Type Check (mypy)`, `Security (bandit)`, `Security (pip-audit)`.
- All use `continue-on-error: true` and write a report to each job's Job Summary — none can block a merge.
- Non-blocking is deliberate: the codebase currently has ~53 pre-existing mypy findings, 2 bandit findings, and 10 known dependency CVEs, none introduced by this PR. See CLAUDE.md's new "CI" section for the promotion-to-blocking policy.
- Design spec: docs/superpowers/specs/2026-07-21-ci-quality-gates-design.md

## Test plan
- [x] `mypy src/` runs locally, reports findings (expected, non-blocking)
- [x] `bandit -r src/ -ll` runs locally, reports findings (expected, non-blocking)
- [x] `pip-audit -r requirements.txt --desc` runs locally, reports findings (expected, non-blocking)
- [x] ci.yml parses as valid YAML
- [ ] Confirm all three new jobs appear in this PR's checks list and none block merge

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 3: Wait for CI, confirm the three new jobs appear and are non-blocking**

Run: `gh pr checks <PR number>` (repeat until no longer pending)
Expected: `Type Check (mypy)`, `Security (bandit)`, `Security (pip-audit)` all appear in the list. They may show as `fail` (bandit/pip-audit/mypy's own exit codes) but the PR's overall mergeability must not be blocked by them — confirm via `gh pr view <PR number> --json mergeable,mergeStateStatus` that blocking comes only from the (expected) required-review policy, not from these three jobs.

**Stop here. Do not proceed to Phase 2 until the user has reviewed and merged this PR**, per the user's explicit request for a review checkpoint before each phase.

---

## Phase 2: Deterministic Evals as a Real CI Gate (blocking)

Implements `docs/superpowers/specs/2026-07-21-ci-evals-gate-design.md`. **Prerequisite: Phase 1's PR must already be merged to `master`.**

### Task 2.1: Add the evals-det CI job

**Files:**
- Modify: `.github/workflows/ci.yml`

**Interfaces:**
- Produces: a new PR-checks-list entry, `Evals (deterministic)`, **blocking**.

- [ ] **Step 1: Create the branch from up-to-date master**

```bash
git checkout master
git pull origin master
git checkout -b ci/evals-gate
```

- [ ] **Step 2: Verify the eval gate currently passes**

Run: `python -m evals.run --det`
Expected: ends with `Release gate: PASS (deterministic pass, review pass, results pass)` and exit code `0` (`echo $?` prints `0`). No new dependencies needed — this already runs cleanly with what's in `requirements-dev.txt`.

- [ ] **Step 3: Add the new job**

Append this new top-level job to `.github/workflows/ci.yml` (after the jobs added in Phase 1 — `typecheck`, `security-bandit`, `security-pip-audit`):

```yaml
  evals-det:
    name: Evals (deterministic)
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

      - name: Run deterministic eval gate
        run: |
          echo "## evals/run --det" >> "$GITHUB_STEP_SUMMARY"
          echo '```' >> "$GITHUB_STEP_SUMMARY"
          python -m evals.run --det | tee -a "$GITHUB_STEP_SUMMARY"
          echo '```' >> "$GITHUB_STEP_SUMMARY"
```

Note: no `continue-on-error` here — a non-zero exit blocks the job and the PR, by design (see the spec's "Why blocking" section).

- [ ] **Step 4: Verify the YAML is well-formed**

Run: `python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"`
Expected: no output, no exception.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: wire evals/run --det into CI as a blocking gate"
```

### Task 2.2: Document the new gate in CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Add a row to the CI table**

In `CLAUDE.md`'s "## CI" table (added in Phase 1), find this exact row (the last row of the table):

```
| `security-pip-audit` | **No** | `pip-audit -r requirements.txt --desc` — non-blocking; currently reports known CVEs in transitive dependencies (`langchain`, `nltk`, `transformers`, etc.) that aren't immediately fixable without upstream upgrades. |
```

Add a new row immediately after it (still inside the table, before the blank line that follows):

```
| `security-pip-audit` | **No** | `pip-audit -r requirements.txt --desc` — non-blocking; currently reports known CVEs in transitive dependencies (`langchain`, `nltk`, `transformers`, etc.) that aren't immediately fixable without upstream upgrades. |
| `evals-det` | Yes | `python -m evals.run --det` — the tier-1 deterministic eval suite described in the "Evals" section above, now actually enforced on every PR instead of only run manually. |
```

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: document the evals-det CI gate"
```

### Task 2.3: Push and open the PR

- [ ] **Step 1: Push the branch**

```bash
git push -u origin ci/evals-gate
```

- [ ] **Step 2: Open the PR**

```bash
gh pr create --base master --head ci/evals-gate \
  --title "ci: run evals/run --det as a blocking CI gate" \
  --body "$(cat <<'EOF'
## Summary
- Adds a new, blocking CI job, "Evals (deterministic)", running `python -m evals.run --det`.
- Currently passes cleanly (12/12 checks across estimate_integrity/review_integrity/results_integrity) — no pre-existing backlog to work around, unlike Phase 1's mypy/bandit/pip-audit, so this one is blocking from day one.
- Design spec: docs/superpowers/specs/2026-07-21-ci-evals-gate-design.md

## Test plan
- [x] `python -m evals.run --det` passes locally (exit 0)
- [x] ci.yml parses as valid YAML
- [ ] Confirm the new job appears in this PR's checks list and passes

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 3: Wait for CI, confirm the new job passes**

Run: `gh pr checks <PR number>` (repeat until no longer pending)
Expected: `Evals (deterministic)` shows `pass`, alongside the existing `test`/`lint` jobs and Phase 1's three jobs.

**Stop here. Do not proceed to Phase 3 until the user has reviewed and merged this PR.**

---

## Phase 3: Coverage Threshold + Release Guardrails (blocking)

Implements `docs/superpowers/specs/2026-07-21-ci-coverage-guardrails-design.md`. **Prerequisite: Phase 2's PR must already be merged to `master`.**

### Task 3.1: Add pytest-cov and verify the coverage baseline

**Files:**
- Modify: `requirements-dev.txt`

**Interfaces:**
- Produces: `pytest --cov=src` runnable in any environment installing `requirements-dev.txt`.

- [ ] **Step 1: Create the branch from up-to-date master**

```bash
git checkout master
git pull origin master
git checkout -b ci/coverage-guardrails
```

- [ ] **Step 2: Add pytest-cov**

In `requirements-dev.txt`, add `pytest-cov==7.0.0` after `pytest-mock==3.14.0`:

```
# Development dependencies - not needed for running QAI Consultant
-r requirements.txt
ruff==0.4.4
pytest==9.0.3
pytest-mock==3.14.0
pytest-cov==7.0.0
mypy==2.3.0
bandit==1.9.4
pip-audit==2.10.1

# MCP server (v3.0) — needed to run/test src/mcp_server.py locally. Not part of
# requirements.txt: the MCP server is a separate package (pyproject.toml, step 8),
# not something the Streamlit Cloud deploy needs.
mcp>=1.8.0
build>=1.0.0
setuptools>=67.0
```

(`mypy`/`bandit`/`pip-audit` lines already exist here from Phase 1 — this step only adds the `pytest-cov` line among them.)

- [ ] **Step 3: Verify the coverage baseline**

Run: `python -m pytest tests/ -q --cov=src --cov-report=term-missing`
Expected: ends with `TOTAL ... 61%` (3110 statements, 1201 missed, as measured when this plan was written) and `484 passed`. This confirms `--cov-fail-under=61` (used in Task 3.2) currently passes.

- [ ] **Step 4: Commit**

```bash
git add requirements-dev.txt
git commit -m "ci: add pytest-cov dev dependency"
```

### Task 3.2: Add the coverage CI job

**Files:**
- Modify: `.github/workflows/ci.yml`

**Interfaces:**
- Consumes: `requirements-dev.txt`'s `pytest-cov` (Task 3.1).
- Produces: a new PR-checks-list entry, `Coverage (pytest-cov)`, **blocking**.

- [ ] **Step 1: Add the new job**

Append this new top-level job to `.github/workflows/ci.yml` (after `evals-det`, added in Phase 2):

```yaml
  coverage:
    name: Coverage (pytest-cov)
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

      - name: Run tests with coverage
        run: |
          echo "## Coverage (src/)" >> "$GITHUB_STEP_SUMMARY"
          echo '```' >> "$GITHUB_STEP_SUMMARY"
          python -m pytest tests/ -q --cov=src --cov-report=term-missing --cov-fail-under=61 | tee -a "$GITHUB_STEP_SUMMARY"
          echo '```' >> "$GITHUB_STEP_SUMMARY"
```

No `continue-on-error` — blocking, per the user's choice.

- [ ] **Step 2: Verify the YAML is well-formed**

Run: `python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"`
Expected: no output, no exception.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: add blocking coverage threshold job (61%)"
```

### Task 3.3: Add the two release-checklist guardrail tests

**Files:**
- Modify: `tests/test_changelog.py`

**Interfaces:**
- Consumes: `REPO_ROOT`, `CHANGELOG_PATH`, `__version__`, and the `re` import already present at the top of `tests/test_changelog.py`.
- Produces: two new pytest test functions, run automatically by the existing blocking `test` CI job (no new CI wiring).

- [ ] **Step 1: Write the two new tests**

Current end of `tests/test_changelog.py`:
```python
def test_changelog_top_version_matches_version_py():
    """The newest (topmost) CHANGELOG.md version heading must exactly match
    version.py's __version__ — catches bumping one but forgetting the other,
    without hardcoding '2.5.0' as a second magic string."""
    text = CHANGELOG_PATH.read_text(encoding="utf-8")
    match = re.search(r"## \[(\d+\.\d+\.\d+)\]", text)
    assert match, "No '## [X.Y.Z]' version heading found in CHANGELOG.md"
    assert match.group(1) == __version__, (
        f"CHANGELOG.md's top heading is [{match.group(1)}] but "
        f"version.py's __version__ is {__version__!r} — they must match."
    )
    print(f"  PASS: CHANGELOG.md top heading [{match.group(1)}] matches __version__")
```

Append these two new functions after it (end of file):

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
        f"version.py's __version__ is {__version__!r} — they must match."
    )
    print(f"  PASS: pyproject.toml version {match.group(1)!r} matches __version__")


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
        "The topmost CHANGELOG.md entry has no '- ' bullet content — "
        "looks like a bare heading with nothing describing the change."
    )
    print("  PASS: topmost CHANGELOG.md entry has bullet content")
```

- [ ] **Step 2: Run the new tests**

Run: `python -m pytest tests/test_changelog.py -v`
Expected: all tests pass, including the two new ones — `test_pyproject_version_matches_version_py PASSED` and `test_changelog_top_entry_has_content PASSED` (since `pyproject.toml`/`version.py`/`CHANGELOG.md` are already correctly in sync at the time of this plan).

- [ ] **Step 3: Negative-path sanity check (not committed)**

Temporarily edit `pyproject.toml`'s `version = "..."` to a different value (e.g. append `-test`), run `python -m pytest tests/test_changelog.py::test_pyproject_version_matches_version_py -v`, confirm it now FAILS with a message naming both mismatched values. Revert the temporary edit (`git checkout -- pyproject.toml`).

Temporarily replace the top CHANGELOG.md entry's bullet line(s) with nothing (just the heading), run `python -m pytest tests/test_changelog.py::test_changelog_top_entry_has_content -v`, confirm it now FAILS. Revert (`git checkout -- CHANGELOG.md`).

- [ ] **Step 4: Commit**

```bash
git add tests/test_changelog.py
git commit -m "test: add pyproject/version.py drift guard and CHANGELOG content guard"
```

### Task 3.4: Document the new gate and guardrails in CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Add a row to the CI table**

Find this exact row in the "## CI" table (the last row, added in Phase 2):

```
| `evals-det` | Yes | `python -m evals.run --det` — the tier-1 deterministic eval suite described in the "Evals" section above, now actually enforced on every PR instead of only run manually. |
```

Add a new row immediately after it:

```
| `evals-det` | Yes | `python -m evals.run --det` — the tier-1 deterministic eval suite described in the "Evals" section above, now actually enforced on every PR instead of only run manually. |
| `coverage` | Yes | `pytest --cov=src --cov-fail-under=61` — the coverage floor is the measured baseline at the time this gate was added; it can only be raised over time, never silently regress. |
```

- [ ] **Step 2: Add a note about the release guardrails**

In `CLAUDE.md`'s "## Testing" section, find the existing test-files table (it lists files like `test_llm_client.py`, `test_agent.py`, etc.) and its surrounding text. After that table (and before the `> **Baseline (v3.0.0):**` blockquote that follows it, if present — otherwise at the end of the section), add:

```
`tests/test_changelog.py` also guards the release checklist itself: `test_pyproject_version_matches_version_py` fails if `pyproject.toml`'s version drifts from `src/version.py`'s `__version__`, and `test_changelog_top_entry_has_content` fails if a version bump adds a bare CHANGELOG heading with no actual bullet content underneath it.
```

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: document coverage gate and release guardrail tests"
```

### Task 3.5: Push and open the PR

- [ ] **Step 1: Push the branch**

```bash
git push -u origin ci/coverage-guardrails
```

- [ ] **Step 2: Open the PR**

```bash
gh pr create --base master --head ci/coverage-guardrails \
  --title "ci: add coverage threshold (61%) and release-checklist guardrails" \
  --body "$(cat <<'EOF'
## Summary
- Adds a new, blocking CI job, "Coverage (pytest-cov)", enforcing `--cov-fail-under=61` (the measured baseline — 61.39% today, rounded down for a small buffer).
- Adds two new guardrail tests to tests/test_changelog.py: pyproject.toml <-> version.py drift guard, and a "CHANGELOG top entry has real content" guard. Both run automatically in the existing `test` job, no new CI wiring needed.
- Design spec: docs/superpowers/specs/2026-07-21-ci-coverage-guardrails-design.md

## Test plan
- [x] `pytest tests/ --cov=src --cov-fail-under=61` passes locally (61.39% >= 61%)
- [x] Both new guardrail tests pass locally against the current, correctly in-sync files
- [x] Negative-path check: both guardrail tests fail loudly when the invariant is broken (verified locally, not committed)
- [x] ci.yml parses as valid YAML
- [ ] Confirm the new Coverage job appears in this PR's checks list and passes

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 3: Wait for CI, confirm the new job and tests pass**

Run: `gh pr checks <PR number>` (repeat until no longer pending)
Expected: `Coverage (pytest-cov)` shows `pass`; the existing `test` job also passes (now including the two new guardrail tests).

**Stop here. Do not proceed to Phase 4 until the user has reviewed and merged this PR.**

---

## Phase 4: Live API-Contract Tests (scheduled, never PR-blocking)

Implements `docs/superpowers/specs/2026-07-21-ci-live-contract-tests-design.md`. **Prerequisite: Phase 3's PR must already be merged to `master`.**

**Manual prerequisite the user must handle separately (not a task below, per the spec: "Entering credentials is something only the user does themselves"):** add `MISTRAL_API_KEY`, `OPENROUTER_API_KEY`, `PINECONE_API_KEY`, `PINECONE_INDEX_NAME` as GitHub Actions repository secrets (Settings → Secrets and variables → Actions). Until this is done, the workflow built below still runs (on schedule or manual dispatch) and all three tests SKIP silently rather than failing — the job shows green, but the gate isn't active yet.

### Task 4.1: Write the live contract tests

**Files:**
- Create: `tests/test_live_contracts.py`

**Interfaces:**
- Consumes: `agent._get_secret`, `agent.MISTRAL_MODEL`, `agent.OPENROUTER_MODEL` (all already exist in `src/agent.py`); the `pinecone.Pinecone`, `mistralai.client.Mistral`, `openai.OpenAI` classes (already dependencies via `requirements.txt`, already imported the same way in `src/agent.py`).
- Produces: three pytest tests — `test_pinecone_roundtrip`, `test_mistral_completion`, `test_openrouter_completion` — each skipping (not failing) when its required secret(s) are absent, following the exact pattern already used in `tests/test_risk_analyzer.py`'s `agent()` fixture.

- [ ] **Step 1: Create the branch from up-to-date master**

```bash
git checkout master
git pull origin master
git checkout -b ci/live-contract-tests
```

- [ ] **Step 2: Write the test file**

Create `tests/test_live_contracts.py`:

```python
"""
Live API-contract tests against real Pinecone/Mistral/OpenRouter -- see
docs/superpowers/specs/2026-07-21-ci-live-contract-tests-design.md.

These hit real external APIs and SKIP (not fail, not error) when the
relevant API key(s) aren't configured, following the same pattern already
used by test_risk_analyzer.py and test_app_v03.py for live-LLM tests. Only
the scheduled/dispatched .github/workflows/live-contract-tests.yml workflow
injects real secrets and actually executes these; a bare `pytest tests/`
run (locally or in the existing `test` CI job) continues to skip them
silently, exactly like the existing live-LLM tests already do.
"""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from agent import _get_secret, MISTRAL_MODEL, OPENROUTER_MODEL
from pinecone import Pinecone
from mistralai.client import Mistral
from openai import OpenAI

NAMESPACE = "ci-contract-tests"
VECTOR_ID = "ci-contract-test-vector"
VECTOR_DIM = 384
TEST_VECTOR = [1.0] + [0.0] * (VECTOR_DIM - 1)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def pinecone_index():
    try:
        api_key = _get_secret("PINECONE_API_KEY")
        index_name = _get_secret("PINECONE_INDEX_NAME")
    except Exception as exc:
        pytest.skip(f"Pinecone credentials unavailable ({type(exc).__name__}: {exc})")
    pc = Pinecone(api_key=api_key)
    return pc.Index(index_name)


@pytest.fixture
def mistral_client():
    try:
        api_key = _get_secret("MISTRAL_API_KEY")
    except Exception as exc:
        pytest.skip(f"Mistral credentials unavailable ({type(exc).__name__}: {exc})")
    return Mistral(api_key=api_key)


@pytest.fixture
def openrouter_client():
    try:
        api_key = _get_secret("OPENROUTER_API_KEY")
    except Exception as exc:
        pytest.skip(f"OpenRouter credentials unavailable ({type(exc).__name__}: {exc})")
    return OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_pinecone_roundtrip(pinecone_index):
    """Upsert a real, non-zero vector, fetch it back, verify metadata, then
    delete it -- the exact shape of test that would have caught the
    v3.1.1 all-zero-vector rejection before it reached production."""
    try:
        pinecone_index.upsert(
            vectors=[{
                "id": VECTOR_ID,
                "values": TEST_VECTOR,
                "metadata": {"marker": "ci-contract-test"},
            }],
            namespace=NAMESPACE,
        )
        fetch_result = pinecone_index.fetch(ids=[VECTOR_ID], namespace=NAMESPACE)
        vectors = getattr(fetch_result, "vectors", None) or {}
        fetched = vectors.get(VECTOR_ID)
        assert fetched is not None, "Upserted vector was not found on fetch"
        assert fetched.metadata.get("marker") == "ci-contract-test"
    finally:
        pinecone_index.delete(ids=[VECTOR_ID], namespace=NAMESPACE)


def test_mistral_completion(mistral_client):
    """A real Mistral completion call -- catches auth breakage, a
    renamed/deprecated model, or a changed response shape upstream."""
    response = mistral_client.chat.complete(
        model=MISTRAL_MODEL,
        messages=[{"role": "user", "content": "Reply with the single word OK."}],
        max_tokens=10,
        temperature=0.0,
    )
    content = response.choices[0].message.content
    assert content and content.strip(), "Mistral returned an empty response"


def test_openrouter_completion(openrouter_client):
    """Same contract check against the OpenRouter fallback path -- catches
    the fallback itself being broken, which otherwise only surfaces in
    production during an actual Mistral outage."""
    response = openrouter_client.chat.completions.create(
        model=OPENROUTER_MODEL,
        messages=[{"role": "user", "content": "Reply with the single word OK."}],
        max_tokens=10,
        temperature=0.0,
    )
    content = response.choices[0].message.content
    assert content and content.strip(), "OpenRouter returned an empty response"
```

- [ ] **Step 3: Verify locally**

Run: `python -m pytest tests/test_live_contracts.py -v`

Expected, depending on what's in your local `.env`:
- If `MISTRAL_API_KEY`/`OPENROUTER_API_KEY`/`PINECONE_API_KEY`/`PINECONE_INDEX_NAME` are all present (as they are in this project's own local dev `.env`): all three tests PASS, making real API calls.
- If any are absent: the corresponding test(s) SKIP with a message like `Pinecone credentials unavailable (...)` — never FAIL, never ERROR.

Either outcome is correct; a FAIL or ERROR (as opposed to PASS or SKIP) means something is wrong and must be investigated before continuing.

- [ ] **Step 4: Verify the existing `test` job still only skips these**

Run: `python -m pytest tests/ -q -p no:warnings 2>&1 | tail -5`
Expected: still `484 passed` plus however many of the 3 new live-contract tests execute given your local `.env` (if your local environment has the same 4 keys configured, they'll pass too, not skip — that's fine locally; the point being verified here is that adding this file didn't break the existing suite's collection or introduce an ERROR state for anyone lacking those keys).

- [ ] **Step 5: Commit**

```bash
git add tests/test_live_contracts.py
git commit -m "test: add live API-contract tests for Pinecone/Mistral/OpenRouter"
```

### Task 4.2: Create the scheduled workflow

**Files:**
- Create: `.github/workflows/live-contract-tests.yml`

**Interfaces:**
- Consumes: `tests/test_live_contracts.py` (Task 4.1).
- Produces: a new, separate GitHub Actions workflow that never appears in any PR's checks list.

- [ ] **Step 1: Write the workflow file**

Create `.github/workflows/live-contract-tests.yml`:

```yaml
name: Live API Contract Tests

on:
  schedule:
    - cron: '0 3 * * *'
  workflow_dispatch: {}

jobs:
  live-contracts:
    name: Live Contracts (Pinecone/Mistral/OpenRouter)
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

      - name: Run live contract tests
        env:
          MISTRAL_API_KEY: ${{ secrets.MISTRAL_API_KEY }}
          OPENROUTER_API_KEY: ${{ secrets.OPENROUTER_API_KEY }}
          PINECONE_API_KEY: ${{ secrets.PINECONE_API_KEY }}
          PINECONE_INDEX_NAME: ${{ secrets.PINECONE_INDEX_NAME }}
        run: |
          echo "## Live API contract tests" >> "$GITHUB_STEP_SUMMARY"
          echo '```' >> "$GITHUB_STEP_SUMMARY"
          python -m pytest tests/test_live_contracts.py -v | tee -a "$GITHUB_STEP_SUMMARY"
          echo '```' >> "$GITHUB_STEP_SUMMARY"
```

Note: no `on: push`/`on: pull_request` triggers at all — this is what structurally guarantees it can never block a PR, rather than relying on `continue-on-error`.

- [ ] **Step 2: Verify the YAML is well-formed**

Run: `python -c "import yaml; yaml.safe_load(open('.github/workflows/live-contract-tests.yml'))"`
Expected: no output, no exception.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/live-contract-tests.yml
git commit -m "ci: add scheduled live API-contract test workflow"
```

### Task 4.3: Document this in CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Add a note to the CI section**

At the end of `CLAUDE.md`'s "## CI" table block (after the `coverage` row added in Phase 3, still inside the same section, after the table), add:

```

A separate workflow, `.github/workflows/live-contract-tests.yml`, runs nightly (and via manual `workflow_dispatch`) against real Pinecone/Mistral/OpenRouter — `tests/test_live_contracts.py`'s `test_pinecone_roundtrip`/`test_mistral_completion`/`test_openrouter_completion`. It never triggers on `push`/`pull_request`, so it can never block a PR by construction. It needs `MISTRAL_API_KEY`/`OPENROUTER_API_KEY`/`PINECONE_API_KEY`/`PINECONE_INDEX_NAME` configured as GitHub Actions repository secrets (separate from Streamlit Cloud's own secrets store) — until they're added, every test in it SKIPs silently rather than failing. The Pinecone test writes only to a dedicated `ci-contract-tests` namespace, isolated from `knowledge-base` and `app-metrics`, and cleans up after itself.
```

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: document the live API-contract test workflow"
```

### Task 4.4: Push and open the PR

- [ ] **Step 1: Push the branch**

```bash
git push -u origin ci/live-contract-tests
```

- [ ] **Step 2: Open the PR**

```bash
gh pr create --base master --head ci/live-contract-tests \
  --title "ci: add scheduled live API-contract tests (Pinecone/Mistral/OpenRouter)" \
  --body "$(cat <<'EOF'
## Summary
- Adds tests/test_live_contracts.py: 3 tests exercising real Pinecone (upsert/fetch/delete roundtrip in an isolated ci-contract-tests namespace), real Mistral, and real OpenRouter completions -- each SKIPs (not fails) without its required key(s), matching the existing test_risk_analyzer.py live-test pattern.
- Adds .github/workflows/live-contract-tests.yml: nightly cron + workflow_dispatch only -- never push/pull_request, so this can never block a PR by construction.
- Design spec: docs/superpowers/specs/2026-07-21-ci-live-contract-tests-design.md

**Manual follow-up needed (not part of this PR):** add MISTRAL_API_KEY, OPENROUTER_API_KEY, PINECONE_API_KEY, PINECONE_INDEX_NAME as GitHub Actions repository secrets, then trigger the workflow manually (`gh workflow run live-contract-tests.yml`) to confirm it actually exercises the real APIs rather than skipping.

## Test plan
- [x] All 3 new tests pass locally (this repo's local .env already has the 4 required keys)
- [x] Existing `pytest tests/` suite unaffected (still 484+ passed)
- [x] Both new/modified workflow YAML files parse correctly
- [ ] After secrets are added: manually dispatch the workflow, confirm all 3 tests execute (not skip) and pass, confirm the ci-contract-tests Pinecone namespace is empty again afterward

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 3: Wait for CI, confirm nothing new appears in the PR's checks list**

Run: `gh pr checks <PR number>`
Expected: only the pre-existing jobs (`test`, `lint`, `typecheck`, `security-bandit`, `security-pip-audit`, `evals-det`, `coverage`) appear — **no** "Live Contracts" job, confirming the scheduled-only trigger design worked as intended.

**This is the last phase.** After this PR is reviewed and merged, remind the user (out of band, not as part of this plan) that the 4 GitHub Actions secrets still need to be added manually before the nightly job actually exercises anything, per Task 4's manual-prerequisite note above.
