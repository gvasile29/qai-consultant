---
name: ci-check
description: Verify GitHub Actions CI is green after a git push to this repo. Use immediately after any push to master or a PR branch, before declaring the work done.
---

# CI check

After every `git push` to this repo, run the check script once instead of re-deriving `gh` commands from scratch:

```bash
bash .claude/skills/ci-check/check.sh          # latest run on the current branch
bash .claude/skills/ci-check/check.sh <run_id> # a specific run
```

It waits for the run to finish, prints a `name: conclusion` line per job, and exits non-zero if the run failed. One tool call, no raw streaming output.

**Never declare a task done after a push without this passing.** If it fails, read the failing job's log (`gh run view <run_id> --log-failed --job=<job_id>`), fix, push again, re-run the check. See `feedback_pipeline_check.md` in memory for the origin of this rule.
