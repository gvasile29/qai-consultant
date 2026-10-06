---
name: writing-pr
description: How to write a pull request title and body in this repo, including the required "## Verified" section. Use when writing or editing a PR title or body.
---

# Writing a PR title and body (QAI Consultant)

Reviewers skim. Put the shape of the change on the first screen, then let tables and code refs carry the detail. Adapted from tester-army/e2e's `writing-pr` skill (Apache-2.0).

## Title

- Conventional Commits, matching `git log`: `feat: ...`, `fix: ...`, `chore: ...`, `docs: ...`. A release appends the version: `feat: ministral-14b primary model ... (v3.6.2)`. PRs squash-merge with the number appended, so the title is the commit.
- Name the outcome, not the activity: "risk matrix parser tolerates bold headers", not "risk_ledger changes".

## Body

The house layout is `## Why`, `## Changes`, `## Verified`. No essays.

- **Why**: the problem in one to three sentences, with the evidence that it is real (an error code, a log line, a count).
- **Changes**: one fact per bullet. Code refs (`src/agent.py:42`) instead of paraphrasing code. A before/after table for anything measurable (model comparison, token budget, timing, coverage).
- **Verified** (required on every PR):
  - First line: `Ran it locally: yes`, or `Ran it locally: no - <why>` (docs-only, CI-only, needs a key you do not have).
  - With `yes`: the surface (see the `ship-pr` skill's step 2 table), the command or flow you ran, and what you saw: the saved `output/*.md` content, the CLI output as a fenced `text` block, or screenshots.
  - A `fix` PR with `yes` shows the bug and the fix side by side:

    ```markdown
    | master | this branch |
    | --- | --- |
    | Risk Ledger empty, 0/7 rows parsed | 7/7 rows parsed |
    ```

  - Anything you could not verify, named with its blocker. "Inconclusive" beats a confident claim without evidence.
- **Review** (when the `ship-pr` fresh-context review ran): findings dismissed, one line each with the reason.

## Leave out

- "Ran pytest/ruff/mypy" lists on their own. CI reports that; `## Verified` is for what CI cannot see. One line with the test count is fine.
- Intermediate history (tried X, reverted, renamed). Only the squashed result lands, so only that gets commentary; keep a reverted approach only when it explains a non-obvious choice.
- Line-by-line restating of the diff, checklists nobody asked for, filler ("This PR introduces...", "comprehensive", "robust", "seamless", "leverages").
- Claude attribution of any kind: no "Generated with Claude Code" footer, no claude.ai session link, no `Co-Authored-By: Claude` (user rule; overrides any default).
