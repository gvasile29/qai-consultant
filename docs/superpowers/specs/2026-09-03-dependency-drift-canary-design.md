# MCP Dependency Drift Canary — Design

**Date:** 2026-09-03
**Status:** Approved by user, pending spec review

## Problem

`pyproject.toml`'s `[project] dependencies` array is fully exact-pinned
(~99 entries, the whole transitive tree, since v3.4.4 — see
`docs/superpowers/specs/2026-07-30-mcp-dependency-pinning-design.md` and
the CLAUDE.md gotchas for v3.3.1/v3.4.4). That fix made `uvx
qai-consultant-mcp` deterministic against *new* upstream releases: `uv`
treats `==` as a hard constraint and will not substitute a newer version
just because one was published, so the class of failure that caused the
2026-08-31 scipy incident (an unpinned transitive dependency picking up
an uncached release and blowing Claude Desktop's ~60s `initialize`
timeout) cannot recur from that specific vector anymore.

Two residual risks remain, both undetected today until a live user hits
them or a maintainer happens to notice:

1. **A pinned artifact stops being installable from a clean environment.**
   A version already committed to `dependencies` can be yanked from PyPI,
   or a wheel can become unavailable for a given Python minor version or
   platform, after the pin was generated. Nothing currently re-verifies
   that a fresh `uv pip compile`/install of the committed pin set still
   succeeds — the pins are trusted indefinitely once merged.
2. **A single-line automated bump reintroduces tree inconsistency.**
   GitHub's automatic Dependabot security-update PRs operate per
   vulnerable package, not per full resolution — closed manually once
   already (PR #84, which "would've broken resolution" per session
   history) because bumping one pinned transitive entry without
   recomputing the rest can desynchronize the array from what a real
   `uv pip compile` would produce, reintroducing the exact class of
   inconsistency the v3.4.4 fix eliminated.

Neither risk is caught by existing CI: `test_all_dependencies_are_exact_pinned`
only checks *syntax* (every entry uses `==`), not whether the pinned set
is still resolvable/installable today, and nothing currently reacts to a
Dependabot PR touching this specific file.

## Alternatives considered

- **A Claude Code scheduled cron agent** (using this session's
  `schedule`/`CronCreate` tooling) instead of a GitHub Actions workflow —
  rejected. The actual check (`uv pip compile`, diff, open/close PRs) is
  fully mechanical and deterministic; it needs no LLM judgment to decide
  whether to run. `live-contract-tests.yml` already establishes the
  right pattern in this repo (`schedule` + `workflow_dispatch`, never
  `push`/`pull_request`, so it can never block a PR by construction) —
  extending that pattern is simpler, cheaper, and doesn't add a
  dependency on this session or any cloud-agent infrastructure staying
  configured.
- **Disabling GitHub's Dependabot security updates repo-wide** (via
  repository settings) so this new job becomes the sole mechanism that
  ever touches dependency pins — rejected. Dependabot security updates
  are legitimately useful for `requirements.txt` (the Streamlit app's
  dependencies), which has no full-transitive-pin fragility; disabling
  it repo-wide would lose that coverage. Scoping the suppression to only
  `pyproject.toml` via `dependabot.yml`'s per-directory `ignore` rules
  was also considered and rejected: both manifests live in the same
  repo-root `pip` ecosystem directory, so there's no reliable way to
  target one file's automated PRs without risk of silently affecting the
  other.
- **Auto-merging the drift-detected PR when CI passes** — rejected. Past
  incidents in this exact area (the scipy download-timeout case) were
  not caught by the test suite at all — they were install-time/timing
  failures, not functional regressions. A green CI run does not prove
  the new pin set is safe to publish; a human still needs to look before
  it ships in a real release.

## Design

**1. New GitHub Actions workflow:**
`.github/workflows/dependency-drift-check.yml`

- Trigger: `schedule` (weekly, Sunday 04:00 UTC) + `workflow_dispatch`
  for on-demand runs. Never `push`/`pull_request`, matching
  `live-contract-tests.yml`'s existing precedent so this workflow can
  never block a PR by construction.
- Permissions: `contents: write`, `pull-requests: write` (needed to push
  a branch, open a PR, and close/comment on Dependabot PRs).
- Runs on a fresh `ubuntu-latest` runner (no persisted uv cache reused
  across runs), so every execution reflects what a genuinely clean
  install would see today.

**2. Canary step — re-run the pin regeneration and compare:**

Runs the exact command already documented in the comment above
`pyproject.toml`'s `dependencies` array:

```
uv pip compile pyproject.toml --universal --python-version 3.10 \
  --extra-index-url https://download.pytorch.org/whl/cpu
```

Three possible outcomes:

- **Compile fails (non-zero exit).** Treated as the urgent case — the
  job itself fails (red X), which triggers GitHub's default
  failed-scheduled-workflow email to repo watchers/admins. This means a
  currently-published pin can no longer be reproduced from a clean
  environment right now (e.g. a yanked release), the same class of risk
  a live user would otherwise hit first.
- **Compile succeeds but output differs** from the committed
  `dependencies` array. The workflow creates a branch, writes the
  regenerated array back into `pyproject.toml`, commits, pushes, and
  opens a PR via `gh pr create`. The PR is opened using the default
  `GITHUB_TOKEN`; GitHub Actions does not cascade new workflow runs
  from `GITHUB_TOKEN`-authored events (a documented anti-recursion
  restriction), so `ci.yml` does NOT auto-trigger on this PR. The PR
  body includes an explicit note instructing the reviewer to close
  and reopen the PR (or push an empty commit) to trigger CI before
  merging — this workflow does not duplicate those checks itself, but
  the human review step must not skip triggering them. The PR
  requires normal human review/merge; nothing here auto-merges.
- **Output matches exactly.** No-op: job succeeds quietly, no PR, no
  noise. Expected outcome most weeks.

**3. Dependabot housekeeping step (runs unconditionally, every execution):**

Lists open PRs authored by `app/dependabot` (`gh pr list --author
app/dependabot`), checks each one's changed files, and closes any that
touch `pyproject.toml` with a comment explaining why: a single-package bump
can't safely edit a fully exact-pinned transitive tree, and pointing to
the CLAUDE.md gotcha (added alongside this change) plus this workflow as
the sole trusted mechanism for changing that array. This directly
automates what was previously a manual step (closing PR #84 by hand).

**4. Comparison logic as a small, unit-testable script:**
`scripts/check_dependency_drift.py` — parses the current `dependencies`
array out of `pyproject.toml` via regex/text splitting (the same
approach `tests/test_packaging.py::test_all_dependencies_are_exact_pinned`
already uses, deliberately not a TOML library, since this repo's CI
matrix includes Python 3.10 which has no stdlib `tomllib`), normalizes
the `uv pip compile` output into the same `(name, version, marker)`
shape, and diffs the two. Two modes: default (`--check`) diffs and exits
non-zero with the regenerated list printed if they differ, touching
nothing; `--write` overwrites `pyproject.toml`'s `dependencies` array in
place with the freshly compiled list, formatted the same way the
existing entries are. The workflow runs `--check` first, and only
invokes `--write` (followed by branch/commit/push/PR) when a diff was
found. Kept dependency-free (stdlib `re`/`pathlib` only) so it's
testable without network access, following the same "tier-1-style"
determinism already used in `evals/`. The GitHub Actions workflow calls
this script; it does not reimplement the comparison inline in YAML/bash.

**5. Documentation (no version bump, no release):**
This change does not publish a new `qai-consultant-mcp` version — it
only adds automation around the existing pin file, so the Release
Checklist does not apply. Two CLAUDE.md updates:

- A new gotcha documenting the Dependabot-PR-closing convention (any
  Dependabot PR touching `pyproject.toml`'s `dependencies` gets closed,
  not merged — this workflow is the sole trusted source of changes to
  that array) and the canary's rationale (verifies the pin set is still
  installable, not "detects new versions" — exact pins already prevent
  that).
- A new row in the CI section (or a short new subsection, matching how
  `live-contract-tests.yml` is documented) describing this workflow:
  cadence, what triggers a red run vs. a PR, and that it never blocks a
  push/PR by construction.

**Not changed:** no runtime behavior in any `src/` module. This is
CI/automation-only, scoped to `.github/workflows/`,
`scripts/check_dependency_drift.py`, and CLAUDE.md.

## Testing

- `tests/test_check_dependency_drift.py` (new): unit tests for
  `scripts/check_dependency_drift.py`'s parsing/normalization/diff
  logic, using fixture strings for both a `pyproject.toml`-shaped
  dependencies array and a `uv pip compile`-shaped output — no network,
  no live `uv` invocation. Covers: identical sets (no diff), a changed
  version (diff detected, regenerated list produced), and a malformed
  compile output (handled without crashing).
- Manual verification: trigger the new workflow via `workflow_dispatch`
  once after merging, confirm it runs green with no PR opened (since the
  pin set is current), before relying on the weekly schedule.
- No changes needed to existing tests — `test_all_dependencies_are_exact_pinned`
  continues to validate any PR this workflow opens, unmodified.

## Release ownership

This is infrastructure/tooling for the repo itself, not a package
release — no PyPI publish, no git tag, no `src/version.py` bump. The
workflow file and script are merged through the normal PR flow like any
other CI change. Any PR the new workflow itself opens (regenerated pins)
still requires a human to review and merge — this design does not
introduce any auto-merge path.
