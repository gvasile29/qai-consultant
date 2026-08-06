# Claude collaboration rules — design

**Date:** 2026-08-06
**Status:** Approved

## Problem

Existing collaboration rules (memory) hadn't been revisited since they were set ~7 days ago, and one of them (`feedback_efficiency_agents.md`'s "every task gets a subagent, no exceptions") was actively working against the stated goal of reducing token consumption — a fresh subagent starts cold and re-derives context, which costs more than doing a small sequential task inline. Separately, the user wants two new standing behaviors: never agree without justification, and use a multi-agent judge panel for uncertain/trade-off recommendations.

## Decisions

1. **Subagent/fork rule, rewritten on criteria (replaces the blanket "no exceptions" rule):**
   - Use an agent/fork when the task is parallelizable, independent of other in-flight work, or its raw output (large diffs, logs, exploratory search) doesn't need to live in the main conversation's context.
   - Do the task directly when it's small/sequential, or when restating context to a fresh agent would cost more than just doing it (e.g. a 1-2 file edit, a git commit/push, a single verification command).
   - Model-selection-by-complexity (haiku/sonnet/opus) is unchanged — it still applies whenever an agent is used.

2. **New rule — AI council (Workflow judge-panel):** trigger a Workflow with 2-3 independent judge agents whenever a recommendation has a real trade-off or genuine uncertainty — not only for irreversible/architectural decisions. This is a deliberate quality-over-token-minimization choice for this specific case, made explicitly by the user after the cost trade-off was flagged.

3. **New rule — no blind agreement:** every time Claude states something as fact or agrees with a user proposal, it must include the reasoning — not just an acknowledgment. Applies to any technical recommendation or evaluation of a user idea.

4. **New project skill — `.claude/skills/ci-check/`:** fixes the exact command sequence for post-push CI verification (`gh run list` → `gh run watch --exit-status` → per-job report) as a real script (`check.sh`), invoked with one tool call, rather than prose instructions the assistant re-executes as 3 separate commands each time.

5. **New rule — scriptify repetition:** any multi-step command sequence that has been run before, or is clearly going to recur, gets written as a committed script and invoked directly, instead of being re-derived and re-run ad hoc. Raised by the user mid-implementation of decision 4, once it became clear the first draft of `ci-check` was prose-only and still cost 3 tool calls.

## Persistence

- Decisions 1-3 are about how Claude and the user work together, not about the codebase — they go into the user's memory store (`feedback` type), matching the existing precedent (`feedback_efficiency_agents.md`, `feedback_pipeline_check.md`) rather than `CLAUDE.md`, which is repo-committed guidance read by any Claude Code session working on this repo, with or without this user's collaboration context.
- Decision 4 is a repo-local dev tool, committed alongside `CLAUDE.md` like the rest of the project's `.claude/` configuration.

## Non-goals

- Not touching the existing `skills/qai-marketing/` directory (untracked, unrelated marketing skill already in progress).
- Not changing global (cross-project) Claude Code settings — everything here is scoped to this project's memory store and this repo's `.claude/skills/`.
