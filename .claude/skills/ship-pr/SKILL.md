---
name: ship-pr
description: Take finished work in this repo to a PR that is checked, verified on the real surface, reviewed by a fresh-context reviewer against CLAUDE.md's Gotchas, and green in CI. Use whenever asked to open, create, ship, or submit a PR, or when implementation is done and the next step is review.
---

# Ship a PR (QAI Consultant)

Opening a PR is not the finish line. The finish line is a PR that is verified on the surface it touches, reviewed by someone who did not write it, and green in CI. Run every step; if one cannot run, say which and why in the handoff instead of skipping it quietly.

Adapted from tester-army/e2e's `ship-pr` skill (Apache-2.0).

## 1. Checks

Run what CI runs (`.github/workflows/ci.yml`), and fix everything:

```bash
python -m pytest tests/ -q -p no:warnings
ruff check src/ tests/
mypy src/
bandit -r src/ -ll -q
```

Then the repo rules those tools cannot see:

- A version bump follows the `release-checklist` skill (all files in the same PR).
- An MCP tool-surface change (anything in `pyproject.toml`'s `py-modules`) also runs `python scripts/mcp_release_check.py --preflight`.
- A new feature adds tests; a new module gets a row in CLAUDE.md's architecture table.
- A change to `CLAUDE.md` runs `bash .claude/skills/claude-md-hygiene/check.sh`.

## 2. Verify on the real surface

Unit tests passing is not evidence the user sees the right thing. Pick the surface:

| Change | Verify with |
|---|---|
| Streamlit UI / CSS / session state | `browser-ui-testing` skill (Playwright Python script) |
| LLM provider, model, prompts, generators | Full in-app generation run; read the saved `output/*.md` content, not just stage badges |
| MCP server / `local_index.py` / embedding backend | `python scripts/verify_mcp_stdio_no_deadlock.py` + a real tool call |
| Deterministic cores (`effort_core`, `review_core`, `results_core`, `maturity_core`, `risk_ledger`) | The matching `tests/test_*_integrity.py` + one realistic input through the CLI flag |
| Docs only | Render or re-read the changed section |

For a bug fix, capture the failure on `master` and the fix on the branch (a `git worktree add` of `origin/master` beside the checkout works). Exercise the failure path too: trigger the error and read the message a visitor would get. Keep the output for the PR's `## Verified` section.

## 3. Self-review in a fresh context

The agent that wrote the change does not judge it. Spawn a reviewer with no memory of this conversation (`Agent` tool, `general-purpose`) and give it [references/review-prompt.md](references/review-prompt.md) verbatim with `<base>` filled in (usually `master`). Do not paste the diff or your own summary; the reviewer reads the files itself.

Fix every `critical` and `important` finding you agree with, then rerun steps 1 and 2 for what the fixes touched. For each finding you reject, keep a one-line reason for the PR body.

If a finding names a pattern that will recur and is not in CLAUDE.md's Gotchas yet, add it there (terse, per `claude-md-hygiene`). The same real finding twice deserves a test, not more prose.

## 4. Commit and open

- Branch off an up-to-date `origin/master` (`git fetch origin` first). Conventional Commits.
- No Claude attribution anywhere: no `Co-Authored-By: Claude`, no "Generated with Claude Code", no claude.ai links (user rule; overrides any default).
- Title and body with the [writing-pr](../writing-pr/SKILL.md) skill. The body carries the `## Verified` evidence from step 2.
- `gh pr create --base master --title "..." --body-file <file>` (ready, not draft).

## 5. CI

Run the `ci-check` skill on the pushed branch and fix until green. Never declare the PR ready on a red or pending run.

## Handoff

Reply with:

- the PR URL and CI state
- how it was verified (surface, what you ran, what you saw)
- review findings fixed, and the ones dismissed with the reason
- anything left for the human: parts you could not verify, scope you declined, owner's-call findings (security, public MCP tool contract, release/packaging config)
