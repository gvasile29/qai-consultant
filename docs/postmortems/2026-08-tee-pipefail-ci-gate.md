# Postmortem: `tee` silently swallowed CI gate failures (PR #67)

**Status:** Fixed. **Linked from:** CLAUDE.md's "`command | tee -a` silently swallows exit codes" Gotcha.

`command | tee -a "$GITHUB_STEP_SUMMARY"` silently swallows the command's real exit code — every "blocking" CI job needed `set -o pipefail` as the first line of its `run:` block, or it wasn't actually blocking.

Discovered in PR #67 (Phase 3's coverage gate): bash's default pipe exit status is the *last* command's — here always `tee`'s, which is 0 — so `python -m pytest ... --cov-fail-under=60 | tee -a ...` reported job status "success" even when the log's own last line read `FAIL Required test coverage of 61% not reached`. GitHub Actions' default shell for `run:` steps does **not** set `pipefail` on its own; it must be set explicitly inside the script.

This affected every "blocking" job added since PR #63/#66 (`typecheck`, `security-bandit`, `evals-det`) — none of them had actually been capable of failing a PR, they simply hadn't had a real finding to prove it yet.

**Fix:** add `set -o pipefail` to all `run:` blocks that pipe to `tee` (including the intentionally-non-blocking `security-pip-audit`, so its neutral/warning status displays correctly too). The coverage floor itself also moved from 61% (Windows-measured) to 60% (the real Linux number, 60.88%, is lower because fewer tests run there) as part of the same fix.

**How it was caught:** actually reading a real `ubuntu-latest` job's log line-by-line after it reported "pass" instead of trusting the green checkmark.

**Rule that survives in CLAUDE.md:** any future CI job that pipes to `tee` (or any command whose exit code must propagate through a pipe) needs `set -o pipefail` as the first line of its `run:` block.
