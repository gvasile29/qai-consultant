---
name: claude-md-hygiene
description: Check CLAUDE.md's size and flag bloated Roadmap/Gotchas entries. Use before or after editing CLAUDE.md — especially during a release's Release Checklist step, or when asked to audit/clean up CLAUDE.md.
---

# CLAUDE.md hygiene

CLAUDE.md loads into context on every turn in this repo, so its size is a real token cost, not just documentation upkeep. On 2026-09-23 it had grown to ~94KB (~23K tokens), mostly from Roadmap/Gotchas entries carrying full incident narrative that already lived in `CHANGELOG.md`/`docs/postmortems/`; trimming it to ~50KB cut roughly half the per-turn cost with no loss of retrievable detail.

Run this after adding to CLAUDE.md (especially Roadmap/Gotchas entries during a release) instead of eyeballing it:

```bash
bash .claude/skills/claude-md-hygiene/check.sh
```

It reports:
- Total file size in bytes and an estimated token count (bytes/4).
- Any single bullet line in `## Roadmap` or `## Gotchas` over 600 characters — a sign it's carrying narrative that belongs in `CHANGELOG.md` or a `docs/postmortems/*.md` file instead, linked from a one-line pointer here.

**If it flags something:**
- Roadmap entries: cut to one line — what shipped, in a phrase. Full narrative (root cause, PR links) goes in `CHANGELOG.md` only.
- Gotchas entries: keep the rule + one line of *why* + a doc link if a postmortem/spec already exists. If a Gotcha needs more than ~3 lines to be useful, write (or point to) a `docs/postmortems/*.md` file and leave a one-line pointer here instead of the full story.
- Never delete the only copy of an actionable rule — move the detail to a linked doc, don't just cut it.

This mechanizes the "CLAUDE.md hygiene" convention documented in CLAUDE.md's own Release Checklist section — read that section for the full rationale.
