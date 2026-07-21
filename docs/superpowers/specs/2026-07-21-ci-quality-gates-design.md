# CI Quality Gates (Part 1: Static Type Checking + Static Security) — Design

**Date:** 2026-07-21
**Status:** Approved by user, pending spec review

## Problem

The project's GitHub Actions CI (`.github/workflows/ci.yml`) currently has two
jobs: a Python 3.10/3.11/3.12 test matrix and a `ruff` lint job. There is no
type checking and no static security scanning — neither in CI nor documented
as a local dev step. GitHub's native Dependabot alerts already flag 4
dependency vulnerabilities (2 high, 2 moderate), but that's a passive
security-tab notice, not a CI gate a PR is measured against.

## Scope

This is the first of four independent CI-improvement sub-projects identified
in a broader brainstorm (the others — wiring `evals/run --det` into CI,
coverage thresholds + a version.py/pyproject.toml drift guard, and live
API-contract tests against Pinecone/Mistral — are each their own future spec).
This spec covers only: adding `mypy`, `bandit`, and `pip-audit` as new,
non-blocking CI jobs.

## Why non-blocking initially

The codebase has partial, inconsistent type-annotation coverage (some newer
modules like `visit_counter.py`, `risk_analyzer.py`, `mcp_server.py` use
`Optional[...]` / dataclasses; `app.py` and `cli.py` are mostly untyped, as is
typical for Streamlit/Rich-based UI code). A strict `mypy` pass would surface
a large number of pre-existing findings on its very first run, unrelated to
whatever a given PR actually changes. Likewise `pip-audit` would fail
immediately against the 4 already-known dependency vulnerabilities. Making
these checks block merges from day one would either force an unrelated
cleanup sprint before this ships, or get the check disabled/ignored out of
frustration — both worse outcomes than starting non-blocking and promoting to
blocking once the pre-existing backlog is addressed (tracked as a deliberate
future step, not left implicit).

## CI job structure

Three new jobs added to the existing `.github/workflows/ci.yml`, alongside
the current `test` and `lint` jobs, following the same naming convention
(`name:` matching what shows in the PR checks list):

```yaml
  typecheck:
    name: Type Check (mypy)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
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
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
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
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
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

Each job installs `requirements-dev.txt` (same as the existing `test` job's
pattern) rather than a bespoke `pip install mypy bandit pip-audit`, so the
exact tool versions used in CI are pinned the same way `ruff`/`pytest` are —
and so a developer running `pip install -r requirements-dev.txt` locally gets
the identical toolset.

If a tool finds nothing, its own stdout already says so (mypy: "Success: no
issues found"; bandit: "No issues identified"; pip-audit: "No known
vulnerabilities found") — no extra scripting needed to distinguish "clean"
from "the step didn't run."

## Tool configuration

- **mypy:** new `[tool.mypy]` section in `pyproject.toml`:
  ```toml
  [tool.mypy]
  ignore_missing_imports = true
  ```
  `ignore_missing_imports = true` because several third-party dependencies
  (`langchain`, `pinecone`, `mistralai`, `streamlit`) either ship incomplete
  stubs or none at all — without this, mypy's own import-resolution noise
  would drown out real findings. No `--strict`, no per-module strictness
  overrides yet (a natural addition once this is promoted to blocking and the
  team wants to ratchet specific modules tighter, out of scope here). Config
  lives in `pyproject.toml` (not a CLI flag) so `mypy src/` run locally
  behaves identically to CI.

- **bandit:** `-r src/` scopes it to the same directory as mypy; `-ll` sets
  the reporting threshold to medium severity and above, filtering out
  low-severity noise (e.g. `assert` usage, which bandit flags by default but
  which is irrelevant here since `tests/` — where asserts are expected — is
  out of scope). No config file needed for this initial pass.

- **pip-audit:** `-r requirements.txt` (not `pyproject.toml`, which declares
  the separate `qai-consultant-mcp` package's dependencies, not the main
  app's runtime deps). `--desc` includes each CVE's description in the
  output, making the job summary self-contained without needing to click
  through to an external advisory.

All three added to `requirements-dev.txt`, next to the existing `ruff` and
`pytest` entries.

## Documentation

A new short "## CI" section in `CLAUDE.md` (or an addition to the existing
"Development Commands" section — whichever reads more naturally once
drafted) documents:
- The three new jobs and what each checks
- That they are intentionally non-blocking (`continue-on-error: true`) as of
  this release, with the rationale (pre-existing backlog, see above)
- That promoting any of them to blocking is a deliberate future decision,
  not an oversight — so a future session (or the user) reading `CLAUDE.md`
  understands *why* a PR can show a red-looking mypy/bandit/pip-audit summary
  and still merge cleanly.

## Testing / verification plan

No new automated tests are needed (this is CI infrastructure, not
application logic). Verification is: push a branch with these changes,
confirm all three new jobs appear in the PR's checks list, confirm each
produces a non-empty, readable Job Summary section, and confirm none of the
three block the PR from being mergeable even if they report findings (which,
given the current codebase state, they are expected to).

## Explicitly out of scope (future specs)

- Wiring `evals/run --det` into CI as a fourth job
- Coverage threshold reporting and a `version.py` / `pyproject.toml` drift
  guard (or any other CI-level guardrail)
- Live API-contract tests against real Pinecone/Mistral (would need CI
  secrets, a cadence decision — nightly vs. per-PR — and a plan for network
  flakiness)
- Promoting mypy/bandit/pip-audit from non-blocking to blocking, and any
  actual cleanup of the findings they surface
- Per-module mypy strictness overrides
- A `dependabot.yml` config file (Dependabot alerts already work via repo
  settings; a config file would change PR-creation behavior, which is a
  separate decision)
