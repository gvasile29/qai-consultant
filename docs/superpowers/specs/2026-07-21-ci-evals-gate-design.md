# CI Quality Gates (Part 2: Deterministic Evals as a Real CI Gate) — Design

**Date:** 2026-07-21
**Status:** Approved by user, pending spec review

## Problem

`evals/run.py` already exists and is explicitly documented in `CLAUDE.md` as
"A release gate that treats the app like a model under test" — it runs
deterministic, keyless checks (`estimate_integrity`, `review_integrity`,
`results_integrity`) and exits non-zero if any fails. Despite that framing,
it is only ever run manually (`python -m evals.run --det`); nothing in
GitHub Actions invokes it. A real regression in any of these three modules
(e.g. a broken confidence-score calculation, or a review-rubric scoring bug)
would currently ship to `master` undetected by CI.

## Scope

Second of four CI-improvement sub-projects (see
`2026-07-21-ci-quality-gates-design.md` for the first — mypy/bandit/pip-audit
— and its "Explicitly out of scope" section for the full list). This spec
covers only: wiring `python -m evals.run --det` into `.github/workflows/ci.yml`
as a new, blocking job.

## Why blocking (unlike Part 1's mypy/bandit/pip-audit)

Verified locally: `python -m evals.run --det` currently passes cleanly (all
12 checks across the three tier-1 modules pass, runs in a few seconds, no
API keys or extra dependencies needed beyond what's already in
`requirements-dev.txt`). Unlike mypy/bandit/pip-audit, there is no
pre-existing backlog to work around — so there's no reason to start this one
non-blocking. `evals/run.py`'s own exit-code contract (0 = pass, 1 = fail)
was already designed with exactly this CI use in mind.

## CI job

New job in `.github/workflows/ci.yml`, alongside `test`/`lint` and the three
jobs from Part 1:

```yaml
  evals-det:
    name: Evals (deterministic)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
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

No `continue-on-error` — a non-zero exit from `evals.run --det` fails the
job and blocks the PR, the same way `test`/`lint` already behave. `tee -a`
(rather than a plain `>>` redirect) writes the output to both the job's raw
log (for quick debugging when something fails) and the Job Summary (for
quick, no-click-through visibility of the pass/fail table), matching Part
1's summary treatment even though this job is blocking rather than
report-only — the readability benefit of the summary applies regardless of
blocking status.

No changes needed to `requirements-dev.txt` — confirmed locally that
`evals.run --det` runs cleanly against what's already installed there; it
deliberately avoids `sentence-transformers`/`MISTRAL_API_KEY` (those only
gate the `rag` tier-2 module, which stays out of scope — see below).

## Explicitly out of scope

- Running the full `evals/run` (both tiers) in CI — the `rag` tier-2 module
  needs `sentence-transformers` (a large dependency, would slow every CI run
  downloading the embedding model) and, for its judged metrics, a
  `MISTRAL_API_KEY` secret (which CI does not currently have configured).
  Adding tier 2 to CI is bundled conceptually with sub-project 4 (live
  API-contract tests), which already needs to solve the "real secrets in CI"
  problem — better decided there than duplicated here.
- Adding `evals-det` as a required status check in the repo's branch
  protection settings — that's a GitHub repo-settings change, not a file
  change in this repo, and is a natural manual follow-up once this job has
  run successfully a few times on real PRs.
- Any of the other three sub-projects (mypy/bandit/pip-audit — Part 1;
  coverage/guardrails — Part 3; live API-contract tests — Part 4).

## Testing / verification plan

No new automated tests (CI infrastructure, not application logic).
Verification: push a branch with this change, confirm the "Evals
(deterministic)" job appears in the PR checks list, passes, and shows the
pass/fail table in its Job Summary. As a negative-path sanity check (not
committed, just a local verification step before merging), temporarily
break one `evals/*_integrity.py` assertion and confirm the job actually goes
red and blocks the PR as expected, then revert.
