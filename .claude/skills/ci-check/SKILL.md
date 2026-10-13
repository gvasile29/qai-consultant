---
name: ci-check
description: Verify GitHub Actions CI is green after a git push to this repo. Use immediately after any push to master or a PR branch, before declaring the work done.
---

# CI check

After every `git push` to this repo, run the check script once instead of re-deriving `gh` commands from scratch:

```bash
bash .claude/skills/ci-check/check.sh          # the CI run for the current HEAD commit
bash .claude/skills/ci-check/check.sh <run_id> # a specific run
```

It waits for the run to finish, prints a `name: conclusion` line per job, and exits non-zero if the run failed. One tool call, no raw streaming output.

Without a run id it waits (up to 120s; override with `CI_CHECK_REGISTER_TIMEOUT`) for the run whose commit is exactly `git rev-parse HEAD`. It never falls back to "the latest run on the branch": right after a push, that is the previous commit's run, and a green result for the wrong code. Exit 2 means no run could be found for HEAD. Usually the commit wasn't pushed, or it's a feature branch with no PR yet: CI triggers only on pushes to `master` and on PRs into it, so open the PR first. Exit 2 also covers a `gh` auth or network failure, which is reported immediately instead of waiting out the timeout.

**Never declare a task done after a push without this passing.** If it fails, read the failing job's log (`gh run view <run_id> --log-failed --job=<job_id>`), fix, push again, re-run the check. See `feedback_pipeline_check.md` in memory for the origin of this rule.

For other `gh`-JSON needs (listing PRs, recent workflow runs, a PR's head SHA), use `python scripts/gh_helpers.py <list-prs|workflow-runs|pr-head-sha>` instead of writing a throwaway `python3 -c "import json,sys; ..."` one-liner.
