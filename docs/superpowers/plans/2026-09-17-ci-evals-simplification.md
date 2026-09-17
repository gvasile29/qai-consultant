# CI/Evals Simplification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cut CI/evals process overhead flagged by the 2026-09-16 over-engineering audit: reduce the test job's 3-way Python matrix to the one version actually used in production, merge 3 redundant static-analysis jobs into one, migrate the 4 deterministic "tier-1" eval modules into ordinary pytest tests (removing a bespoke second test-runner convention), and delete the now-redundant `evals-det` CI job.

**Architecture:** `.github/workflows/ci.yml`'s `test` job drops its matrix (Python 3.11 only, matching `runtime.txt`'s Streamlit Cloud version — every other job already only tested 3.11). `lint`/`typecheck`/`security-bandit` become sequential steps in one new `quality` job (same checkout/setup/install paid once instead of three times). `evals/estimate_integrity.py`, `review_integrity.py`, `results_integrity.py`, `maturity_integrity.py` keep their `run_all()`/`Finding`/`CheckOutcome`/`format_table()` logic exactly as-is (no reimplementation) but lose their standalone `main()`/CLI entry points; four new thin pytest wrapper files call `run_all()` once per module (module-scoped fixture) and assert each named `CheckOutcome.passed`. `evals/run.py` drops the migrated tier-1 imports and the now-meaningless `--det` flag, becoming a 2-module (rag + local_index_parity) aggregate. The `evals-det` CI job is deleted since `pytest tests/` (already run by `test`) now covers what it checked. **Branch protection's required status check list must be updated to match** — this is done as its own explicitly-confirmed step, sequenced to avoid ever blocking a PR from merging (see Task 4).

**Tech Stack:** GitHub Actions YAML, pytest, `gh` CLI (for the branch-protection update).

**Spec:** None — this plan implements audit findings the user already approved via AskUserQuestion in this conversation (no separate design spec was written; the findings below are the requirements).

## Global Constraints

- Every existing assertion/threshold in the 4 migrated eval modules must be preserved exactly — this is a test-runner migration, not a rewrite of what's checked. `evals/thresholds.py` is unchanged and still imported by `estimate_integrity.py`, `review_integrity.py`, and `maturity_integrity.py` (confirmed: `results_integrity.py` does not import it — no `thresholds` reference in that file).
- `runtime.txt` pins Streamlit Cloud to `python-3.11` — this is the version every single-version CI job (`lint`, `typecheck`, `security-bandit`, `security-pip-audit`, `evals-det`, `coverage`) already used; only `test`'s matrix included 3.10/3.12 additionally. `pyproject.toml`'s `requires-python = ">=3.10"` floor for the MCP package is unaffected by this CI change (it was never what the matrix was verifying against in the first place — the MCP package has its own packaging tests).
- **Branch protection on `master` currently requires these exact status check contexts** (verified via `gh api repos/gvasile29/qai-consultant/branches/master/protection --jq '.required_status_checks.contexts'`, `strict: false`): `["Evals (deterministic)", "Lint (ruff)", "Tests (Python 3.10)", "Tests (Python 3.11)", "Tests (Python 3.12)", "Type Check (mypy)", "Security (bandit)", "Coverage (pytest-cov)"]`. Any job whose `name:` disappears from this list stops reporting forever, which permanently blocks every future PR until branch protection is updated — this is a real, shared-infrastructure change requiring explicit user confirmation before it runs (see Task 4's callout).
- `security-pip-audit` is untouched (out of scope) — it stays its own job, non-blocking (`continue-on-error: true`), not part of this plan.

---

## File Structure

| File | Change |
|---|---|
| `.github/workflows/ci.yml` | `test` job: single Python 3.11, no matrix. `lint`+`typecheck`+`security-bandit` merged into new `quality` job. `evals-det` job deleted. |
| `tests/test_estimate_integrity.py` | New — thin pytest wrapper over `evals.estimate_integrity.run_all()` |
| `tests/test_review_integrity.py` | New — thin pytest wrapper over `evals.review_integrity.run_all()` |
| `tests/test_results_integrity.py` | New — thin pytest wrapper over `evals.results_integrity.run_all()` |
| `tests/test_maturity_integrity.py` | New — thin pytest wrapper over `evals.maturity_integrity.run_all()` |
| `evals/estimate_integrity.py` | Remove `main()` + `if __name__ == "__main__"` block only; all check logic unchanged |
| `evals/review_integrity.py` | Same |
| `evals/results_integrity.py` | Same |
| `evals/maturity_integrity.py` | Same |
| `evals/run.py` | Drop the 4 tier-1 imports and the `--det` flag; becomes a 2-module (rag + local_index_parity) aggregate |
| `evals/__init__.py` | Docstring update — no more "three tiers" framing |
| `CLAUDE.md` | Evals section, CI table, Gotchas — updated to reflect the new commands/job names |

---

### Task 1: Reduce the CI Python matrix and merge static-analysis jobs

**Files:**
- Modify: `.github/workflows/ci.yml` (whole file restructure of the `test`, `lint`, `typecheck`, `security-bandit` jobs)

**Interfaces:**
- Produces: a `test` job named `Tests (Python 3.11)` (was matrixed `Tests (Python ${{ matrix.python-version }})`) and a new `quality` job named `Quality (ruff + mypy + bandit)`. Task 4 depends on these exact names.

- [ ] **Step 1: Replace the `test` job's matrix with a single Python version**

In `.github/workflows/ci.yml`, replace the `test` job (current lines 10-40) with:

```yaml
  test:
    name: Tests (Python 3.11)
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python 3.11
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: "pip"

      - name: Install dependencies
        run: pip install -r requirements-dev.txt

      - name: Run tests
        env:
          ANONYMIZED_TELEMETRY: "False"
          CHROMA_TELEMETRY: "False"
        run: |
          python -m pytest tests/ -v -p no:warnings
        # Live-LLM tests (test_risk_analyzer.py, test_app_v03.py::test_both_documents_...,
        # test_effort_estimator.py::test_full_estimate_bmw) SKIP themselves via the
        # `agent` fixture when no API keys are configured — no ignore/deselect needed.
        #
        # Single Python version (was a 3.10/3.11/3.12 matrix): 3.11 matches
        # runtime.txt (Streamlit Cloud's actual deploy version), and every other
        # job in this file already only tested 3.11 — the matrix was the one
        # outlier. pyproject.toml's requires-python ">=3.10" floor for the MCP
        # package is verified by its own packaging tests, not by this matrix.
```

- [ ] **Step 2: Replace the `lint`, `typecheck`, and `security-bandit` jobs with one `quality` job**

Delete the `lint` job (current lines 42-62), the `typecheck` job (current lines 64-92), and the `security-bandit` job (current lines 94-120). In their place, insert:

```yaml
  quality:
    name: Quality (ruff + mypy + bandit)
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

      - name: Run ruff
        run: |
          ruff check src/ tests/ \
            --ignore E501,E402,F401,W291,W293

      - name: Run mypy
        run: |
          set -o pipefail
          echo "## mypy (src/)" >> "$GITHUB_STEP_SUMMARY"
          echo '```' >> "$GITHUB_STEP_SUMMARY"
          mypy src/ | tee -a "$GITHUB_STEP_SUMMARY"
          echo '```' >> "$GITHUB_STEP_SUMMARY"
        # Blocking since PR #63 — the pre-existing 53-error backlog was cleared
        # in PR #61. `set -o pipefail` is required — see CLAUDE.md's Gotchas
        # section (bash's default pipe exit status is the LAST command's, tee,
        # always 0 — this silently masked mypy's real exit code until PR #67).

      - name: Run bandit
        run: |
          set -o pipefail
          echo "## bandit (src/, medium+ severity)" >> "$GITHUB_STEP_SUMMARY"
          echo '```' >> "$GITHUB_STEP_SUMMARY"
          bandit -r src/ -ll | tee -a "$GITHUB_STEP_SUMMARY"
          echo '```' >> "$GITHUB_STEP_SUMMARY"
        # Blocking since PR #63 — the pre-existing 2-finding backlog was
        # cleared in PR #61. Same pipefail requirement as the mypy step above.
    # Three static-analysis tools that were previously three separate jobs
    # (each paying its own checkout+setup-python+pip-install), now three
    # steps in one job. Accepted trade-off: a ruff failure stops mypy/bandit
    # from running in that same CI pass (steps run sequentially, no
    # continue-on-error) — a developer sees one failure per push instead of
    # all three at once. Judged worth it for removing the redundant
    # checkout/setup/install boilerplate; revisit if this trade-off proves
    # annoying in practice.
```

- [ ] **Step 3: Verify the YAML is well-formed**

Run: `python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"`
Expected: no output (valid YAML), no exception.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "$(cat <<'EOF'
ci: drop 3.10/3.12 from the test matrix, merge lint/typecheck/bandit

test now runs only Python 3.11 (matches runtime.txt's Streamlit Cloud
version; every other job already only tested 3.11). lint/typecheck/
security-bandit merge into one quality job to stop paying redundant
checkout+setup-python+pip-install three times over.

NOTE: branch protection's required status checks still list the old
job names at this point — see the follow-up plan task that updates
them, sequenced to avoid ever blocking a PR from merging.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_013xJEqRuCdtixjGy8hpg3jB
EOF
)"
```

---

### Task 2: Migrate `estimate_integrity` and `review_integrity` to pytest

**Files:**
- Create: `tests/test_estimate_integrity.py`
- Create: `tests/test_review_integrity.py`
- Modify: `evals/estimate_integrity.py` (remove `main()` + `__main__` block only)
- Modify: `evals/review_integrity.py` (same)

**Interfaces:**
- Consumes: `evals.estimate_integrity.run_all() -> list[CheckOutcome]`, `evals.estimate_integrity.format_table(list[CheckOutcome]) -> str` (unchanged signatures); same for `evals.review_integrity`.
- Produces: nothing new consumed elsewhere — these are leaf test files.

- [ ] **Step 1: Write `tests/test_estimate_integrity.py`**

```python
"""Pytest wrapper over evals/estimate_integrity.py's real shipped-code checks.

Migrated from a standalone `python -m evals.estimate_integrity` CLI (removed)
per the 2026-09-17 CI/evals simplification — the check logic (run_all(),
Finding, CheckOutcome) still lives in evals/estimate_integrity.py unchanged;
this file only adapts it to pytest so a second test-runner convention isn't
needed alongside the rest of tests/.
"""
import pytest

from evals import estimate_integrity as EI


@pytest.fixture(scope="module")
def outcomes():
    return {o.name: o for o in EI.run_all()}


def _msg(outcome):
    return EI.format_table([outcome])


def test_duration_bounds(outcomes):
    o = outcomes["duration_bounds"]
    assert o.passed, _msg(o)


def test_team_restatement_invariance(outcomes):
    o = outcomes["team_restatement_invariance"]
    assert o.passed, _msg(o)


def test_name_display_fidelity(outcomes):
    o = outcomes["name_display_fidelity"]
    assert o.passed, _msg(o)


def test_confidence_magnitude_sanity(outcomes):
    o = outcomes["confidence_magnitude_sanity"]
    assert o.passed, _msg(o)


def test_no_fabricated_versions(outcomes):
    o = outcomes["no_fabricated_versions"]
    assert o.passed, _msg(o)
```

- [ ] **Step 2: Run the new test file to verify it passes against the still-unmodified module**

Run: `python -m pytest tests/test_estimate_integrity.py -v`
Expected: PASS — 5 tests, all green (this exercises `evals.estimate_integrity.run_all()` exactly as `python -m evals.estimate_integrity` did before).

- [ ] **Step 3: Remove `evals/estimate_integrity.py`'s now-redundant CLI entry point**

Delete the `main()` function (lines 258-271) and the `if __name__ == "__main__":` block (lines 274-275) from `evals/estimate_integrity.py`. Leave everything else (`Finding`, `CheckOutcome`, `_golden()`, all `check_*` functions, `run_all()`, `format_table()`) untouched.

- [ ] **Step 4: Re-run to confirm the test file doesn't depend on the removed CLI code**

Run: `python -m pytest tests/test_estimate_integrity.py -v`
Expected: PASS (unchanged — `format_table`/`run_all()` are not part of what was removed).

- [ ] **Step 5: Write `tests/test_review_integrity.py`**

```python
"""Pytest wrapper over evals/review_integrity.py's real shipped-code checks.
Same migration rationale as tests/test_estimate_integrity.py."""
import pytest

from evals import review_integrity as RI


@pytest.fixture(scope="module")
def outcomes():
    return {o.name: o for o in RI.run_all()}


def _msg(outcome):
    return RI.format_table([outcome])


def test_score_ordering(outcomes):
    o = outcomes["score_ordering"]
    assert o.passed, _msg(o)


def test_dimension_attribution(outcomes):
    o = outcomes["dimension_attribution"]
    assert o.passed, _msg(o)


def test_determinism(outcomes):
    o = outcomes["determinism"]
    assert o.passed, _msg(o)


def test_insufficient_content_handling(outcomes):
    o = outcomes["insufficient_content_handling"]
    assert o.passed, _msg(o)
```

- [ ] **Step 6: Run it, then remove `evals/review_integrity.py`'s CLI entry point**

Run: `python -m pytest tests/test_review_integrity.py -v`
Expected: PASS — 4 tests.

Delete `evals/review_integrity.py`'s `main()` function (lines 200-213) and `if __name__ == "__main__":` block (lines 216-217). Leave everything else untouched. Re-run the same command to confirm it still passes.

- [ ] **Step 7: Commit**

```bash
git add tests/test_estimate_integrity.py tests/test_review_integrity.py evals/estimate_integrity.py evals/review_integrity.py
git commit -m "$(cat <<'EOF'
test: migrate estimate_integrity and review_integrity to pytest

Thin pytest wrappers over the unchanged run_all()/CheckOutcome logic
in evals/estimate_integrity.py and evals/review_integrity.py. Removes
each module's standalone main()/CLI entry point now that pytest is
the sole way to run them — was a second, bespoke test-runner
convention alongside tests/.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_013xJEqRuCdtixjGy8hpg3jB
EOF
)"
```

---

### Task 3: Migrate `results_integrity`/`maturity_integrity`, simplify `evals/run.py`, delete `evals-det`

**Files:**
- Create: `tests/test_results_integrity.py`
- Create: `tests/test_maturity_integrity.py`
- Modify: `evals/results_integrity.py` (remove CLI entry point)
- Modify: `evals/maturity_integrity.py` (same)
- Modify: `evals/run.py` (drop tier-1 imports and `--det` flag)
- Modify: `evals/__init__.py` (docstring)
- Modify: `.github/workflows/ci.yml` (delete `evals-det` job)

**Interfaces:**
- Consumes: `evals.results_integrity.run_all()`/`format_table()` (4 outcomes: `flaky_and_ever_failing_boundaries`, `cluster_count`, `malformed_input_never_crashes`, `csv_xml_parity`); `evals.maturity_integrity.run_all()`/`format_table()` (6 outcomes: `level_ordering`, `no_level_skip`, `ai_act_gating`, `determinism`, `negation_not_counted_as_evidence`, `insufficient_content_handling`).
- Produces: `evals/run.py`'s `main(argv)` with no `--det` branch — always runs `rag` + `local_index_parity` and combines their exit codes.

- [ ] **Step 1: Write `tests/test_results_integrity.py`**

```python
"""Pytest wrapper over evals/results_integrity.py's real shipped-code checks.
Same migration rationale as tests/test_estimate_integrity.py."""
import pytest

from evals import results_integrity as RI


@pytest.fixture(scope="module")
def outcomes():
    return {o.name: o for o in RI.run_all()}


def _msg(outcome):
    return RI.format_table([outcome])


def test_flaky_and_ever_failing_boundaries(outcomes):
    o = outcomes["flaky_and_ever_failing_boundaries"]
    assert o.passed, _msg(o)


def test_cluster_count(outcomes):
    o = outcomes["cluster_count"]
    assert o.passed, _msg(o)


def test_malformed_input_never_crashes(outcomes):
    o = outcomes["malformed_input_never_crashes"]
    assert o.passed, _msg(o)


def test_csv_xml_parity(outcomes):
    o = outcomes["csv_xml_parity"]
    assert o.passed, _msg(o)
```

- [ ] **Step 2: Run it, then remove `evals/results_integrity.py`'s CLI entry point**

Run: `python -m pytest tests/test_results_integrity.py -v`
Expected: PASS — 4 tests.

Delete `results_integrity.py`'s `main()` function (lines 238-251) and `if __name__ == "__main__":` block (lines 254-255). Leave `Finding`, `CheckOutcome`, `_golden()`, `_read_fixture()`, `_case()`, all `check_*` functions, `run_all()`, `format_table()` untouched. Re-run to confirm still PASS.

- [ ] **Step 3: Write `tests/test_maturity_integrity.py`**

```python
"""Pytest wrapper over evals/maturity_integrity.py's real shipped-code checks.
Same migration rationale as tests/test_estimate_integrity.py."""
import pytest

from evals import maturity_integrity as MI


@pytest.fixture(scope="module")
def outcomes():
    return {o.name: o for o in MI.run_all()}


def _msg(outcome):
    return MI.format_table([outcome])


def test_level_ordering(outcomes):
    o = outcomes["level_ordering"]
    assert o.passed, _msg(o)


def test_no_level_skip(outcomes):
    o = outcomes["no_level_skip"]
    assert o.passed, _msg(o)


def test_ai_act_gating(outcomes):
    o = outcomes["ai_act_gating"]
    assert o.passed, _msg(o)


def test_determinism(outcomes):
    o = outcomes["determinism"]
    assert o.passed, _msg(o)


def test_negation_not_counted_as_evidence(outcomes):
    o = outcomes["negation_not_counted_as_evidence"]
    assert o.passed, _msg(o)


def test_insufficient_content_handling(outcomes):
    o = outcomes["insufficient_content_handling"]
    assert o.passed, _msg(o)
```

- [ ] **Step 4: Run it, then remove `evals/maturity_integrity.py`'s CLI entry point**

Run: `python -m pytest tests/test_maturity_integrity.py -v`
Expected: PASS — 6 tests (outcome names confirmed against `evals/maturity_integrity.py`'s actual `run_all()`, lines 226-235).

Delete `maturity_integrity.py`'s `main()` function (lines 251-264) and `if __name__ == "__main__":` block (lines 267-268). Re-run to confirm still PASS.

- [ ] **Step 5: Simplify `evals/run.py`**

Replace the entire file with:

```python
"""Release gate: run the remaining eval tier (rag + local_index_parity),
exit non-zero if either fails.

The 4 deterministic "tier-1" checks (estimate_integrity, review_integrity,
results_integrity, maturity_integrity) moved to ordinary pytest tests
(tests/test_estimate_integrity.py etc.) in the 2026-09-17 CI/evals
simplification — they no longer need a separate runner or the --det flag
that used to select them. Both surviving modules already SKIP (not fail)
without the embedding stack / an LLM key, so no flag is needed to make this
safe to run on a keyless box.

    python -m evals.run
"""

from __future__ import annotations

import sys


def main(argv: list[str]) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # non-ASCII headers/findings; don't crash on cp1252/ascii

    from . import rag
    print("══ rag (classical RAG metrics, local) ══")
    try:
        rag_metrics = rag.run_all()
        print(rag.format_table(rag_metrics))
        rag_ok = all(m.passed for m in rag_metrics)
    except Exception as exc:  # noqa: BLE001 — infra failures already SKIP inside run_all;
        # an unexpected crash here fails the gate rather than passing silently.
        print(f"\n[rag] tier errored (did not run): {type(exc).__name__}: {exc}")
        rag_ok = False

    from . import local_index_parity
    print("\n══ local_index_parity (served LocalIndex vs. rag_golden.jsonl) ══")
    try:
        local_index_metrics = local_index_parity.run_all()
        print(local_index_parity.format_table(local_index_metrics))
        local_index_ok = all(m.passed for m in local_index_metrics)
    except Exception as exc:  # noqa: BLE001 — same rationale as the rag tier above
        print(f"\n[local_index_parity] tier errored (did not run): {type(exc).__name__}: {exc}")
        local_index_ok = False

    overall = rag_ok and local_index_ok
    print(f"\nRelease gate: {'PASS' if overall else 'FAIL'} "
          f"(rag {'pass' if rag_ok else 'FAIL'}"
          f", local_index_parity {'pass' if local_index_ok else 'FAIL'})")
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
```

- [ ] **Step 6: Update `evals/__init__.py`'s docstring**

Replace the module docstring (lines 1-21) with:

```python
"""Evals for QAI Consultant — a release gate over classical RAG metrics.

  - rag (classical RAG metrics, local) — over a local doc-level embedding index of
    ``knowledge_base/*.md`` (no Pinecone). Context Recall@k and Precision (MRR) are
    keyless; Faithfulness, Answer Relevance and Source Attribution need a generated
    answer via the app's LLMClient (production Mistral) and SKIP without a key.
  - local_index_parity (keyless) — the same Recall@k/MRR metrics against the
    MCP server's actual served ``LocalIndex`` (chunk-level, 1000/200 — matches
    production retrieval granularity, unlike rag's coarser doc-level index).

    python -m evals.run                  # both
    python -m evals.rag                  # RAG (doc-level eval index) only
    python -m evals.local_index_parity   # served LocalIndex parity only

``thresholds.py`` is the gate spec; ``rag_golden.jsonl`` is the shared dataset
(append a line to add a case).

Note: the deterministic "tier-1" checks that used to live here (estimate_integrity,
review_integrity, results_integrity, maturity_integrity) moved to ordinary pytest
tests in tests/ as of 2026-09-17 — see CLAUDE.md's Evals section.
"""
```

(keep the unchanged `ensure_src_on_path()` function below it as-is)

- [ ] **Step 7: Delete the `evals-det` job from `ci.yml`**

Remove the entire `evals-det` job block from `.github/workflows/ci.yml` (the block starting `evals-det:` / `name: Evals (deterministic)` through its final step).

- [ ] **Step 8: Run the full suite to confirm nothing else references the removed CLI entry points or the old `evals.run --det` flag**

Run: `grep -rn "evals\.run.*--det\|evals\.estimate_integrity\b.*main\|evals\.review_integrity\b.*main" . --include="*.py" --include="*.yml" --include="*.md" 2>/dev/null`
Expected: no matches outside of `CLAUDE.md` (updated separately, not part of this task) and this plan file itself.

Run: `python -m pytest tests/ -v -p no:warnings`
Expected: PASS — all tests including the 4 new migrated files.

Run: `python -m evals.run`
Expected: runs only `rag` + `local_index_parity`, PASS or SKIP (never crashes) depending on whether `MISTRAL_API_KEY`/the embedding stack are available locally.

- [ ] **Step 9: Commit**

```bash
git add tests/test_results_integrity.py tests/test_maturity_integrity.py evals/results_integrity.py evals/maturity_integrity.py evals/run.py evals/__init__.py .github/workflows/ci.yml
git commit -m "$(cat <<'EOF'
test: migrate results_integrity/maturity_integrity to pytest, simplify evals/run.py

Same migration as the previous commit's estimate_integrity/review_integrity.
evals/run.py drops the now-empty tier-1/--det concept, becoming a
2-module (rag + local_index_parity) aggregate. Deletes the evals-det
CI job (pytest tests/, already run by the test job, now covers what
it checked).

NOTE: branch protection's required status checks still list "Evals
(deterministic)" at this point — updated in the next task, sequenced
to avoid ever blocking a PR from merging.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_013xJEqRuCdtixjGy8hpg3jB
EOF
)"
```

---

### Task 4: Update branch protection's required status checks (explicit confirmation required)

**⚠️ This task changes what GitHub requires before ANY future PR on this repo can merge. Per this project's own risk posture (CLAUDE.md/CLAUDE-level guidance on shared-infrastructure changes), do not run Step 2 without the user explicitly confirming first — show them Step 1's current-state output and the exact command in Step 2, and wait for a clear go-ahead.**

**Files:** None (GitHub repo setting, not a file in this repository).

**Interfaces:**
- Consumes: the exact job `name:` values Tasks 1 and 3 produced (`Tests (Python 3.11)`, `Quality (ruff + mypy + bandit)`, `Coverage (pytest-cov)` — unchanged from before) and removed (`Tests (Python 3.10)`, `Tests (Python 3.12)`, `Lint (ruff)`, `Type Check (mypy)`, `Security (bandit)`, `Evals (deterministic)`).

- [ ] **Step 1: Re-confirm the current required status checks (they may have changed since this plan was written)**

Run: `gh api repos/gvasile29/qai-consultant/branches/master/protection --jq "{strict: .required_status_checks.strict, contexts: .required_status_checks.contexts}"`
Expected output (as of this plan's writing): `{"strict":false,"contexts":["Evals (deterministic)","Lint (ruff)","Tests (Python 3.10)","Tests (Python 3.11)","Tests (Python 3.12)","Type Check (mypy)","Security (bandit)","Coverage (pytest-cov)"]}`. If this differs (e.g. someone changed branch protection since), stop and reconcile with the user before proceeding — the exact list in Step 2 assumes this starting state.

- [ ] **Step 2: Update the required status checks (run this BEFORE opening/merging the PR containing Tasks 1-3's commits, not after — updating first means the PR's new job names already satisfy the requirement the moment they report; updating after would leave the PR permanently blocked in between)**

**Get explicit user confirmation before running this.** Then run:

```bash
gh api -X PATCH repos/gvasile29/qai-consultant/branches/master/protection/required_status_checks \
  --input - <<'EOF'
{
  "strict": false,
  "contexts": ["Tests (Python 3.11)", "Quality (ruff + mypy + bandit)", "Coverage (pytest-cov)"]
}
EOF
```

- [ ] **Step 3: Verify the update**

Run: `gh api repos/gvasile29/qai-consultant/branches/master/protection --jq ".required_status_checks.contexts"`
Expected: `["Tests (Python 3.11)","Quality (ruff + mypy + bandit)","Coverage (pytest-cov)"]`

- [ ] **Step 4: Open the PR containing Tasks 1-3's commits (if not already open) and confirm all three required checks report and pass**

Run: `gh pr checks <PR-number>` (or check the PR page directly)
Expected: `Tests (Python 3.11)`, `Quality (ruff + mypy + bandit)`, and `Coverage (pytest-cov)` all show as passing, and the PR reports as mergeable with no missing required checks.

---

### Task 5 (documentation only, no code): Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

**Interfaces:** None — prose only.

- [ ] **Step 1: Update the Evals section**

Locate the "Evals (`evals/` — release gate)" section (anchor: `## Evals (`evals/` — release gate)`). Replace its description of "Two independent tiers" with a description of the single remaining rag/local_index_parity tier, and update the command list (remove `python -m evals.run --det`, `python -m evals.estimate_integrity`, `python -m evals.review_integrity`, `python -m evals.results_integrity`, `python -m evals.maturity_integrity`; note these now run via `pytest tests/test_estimate_integrity.py` etc.). Update the "Tier 1 (deterministic...)" paragraph to note these moved to `tests/` on 2026-09-17, with a one-line pointer to this plan's date for history.

- [ ] **Step 2: Update the CI table**

Locate the CI section's job table (anchor: `| Job | Blocking? | What it checks |`). Replace the `test`, `lint`, `typecheck`, `security-bandit`, `evals-det` rows with:

```markdown
| `test` | Yes | `pytest tests/` on Python 3.11 (single version as of 2026-09-17 — see Gotchas; this also runs the former evals-det tier-1 checks, now ordinary pytest tests) |
| `quality` | Yes | `ruff check src/ tests/`, `mypy src/`, `bandit -r src/ -ll` — merged into one job as of 2026-09-17 (was 3 separate jobs: `lint`, `typecheck`, `security-bandit`) |
```

Delete the standalone `evals-det` row entirely (folded into `test` above).

- [ ] **Step 3: Add a Gotchas entry**

Append to the Gotchas section:

```markdown
- **Renaming or merging a CI job's `name:` requires updating branch protection's required status checks in the same change, sequenced BEFORE the job-name change lands, not after.** Found while simplifying CI on 2026-09-17: `master`'s branch protection required exact status-check-context strings (`Tests (Python 3.10)`, `Lint (ruff)`, `Type Check (mypy)`, `Security (bandit)`, `Evals (deterministic)`, among others) matching the workflow's old job `name:` fields. Reducing the test matrix and merging `lint`/`typecheck`/`security-bandit` into one `quality` job made those old names stop reporting forever, which would have permanently blocked every future PR until branch protection was updated — avoided by updating `gh api .../branches/master/protection/required_status_checks` FIRST (relaxing the requirement before the job names actually changed), so the PR carrying the workflow change satisfied the already-updated requirement the moment its new-named jobs reported. Any future CI job rename/merge/deletion needs this same check-then-update-first sequencing, not an update-after-the-fact.
```

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md
git commit -m "$(cat <<'EOF'
docs: update CLAUDE.md for the CI/evals simplification

Evals section, CI table, and a new Gotchas entry about sequencing
branch-protection updates before (not after) a CI job rename/merge.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_013xJEqRuCdtixjGy8hpg3jB
EOF
)"
```

---

## Coverage gate: no change (documented decision, not a task)

The audit flagged `--cov-fail-under=60`'s precision (chosen to match a measured `ubuntu-latest` baseline of 60.88%, rounded down) as possibly disproportionate effort for a solo project. Re-reading `.github/workflows/ci.yml`'s `coverage` job and `CLAUDE.md`'s own account of how that number was derived: the actual disproportionate cost the audit was reacting to was the one-time *debugging* effort to discover the `tee`/`pipefail` bug that let the gate report false-green for months — not the number `60` itself, which is already a reasonable, real, measured floor with headroom (61.36% Windows-measured, 60.88% Linux-measured, floor set at 60). That debugging cost was already paid and is not recurring. Rounding to a rounder number like 50 would only reduce the gate's protective value without saving any ongoing maintenance effort. **Decision: leave `--cov-fail-under=60` unchanged.** No task created for this per the writing-plans skill's guidance not to manufacture a task just to have one.
