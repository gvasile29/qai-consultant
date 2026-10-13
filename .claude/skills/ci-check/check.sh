#!/usr/bin/env bash
# ci-check/check.sh — wait for a GitHub Actions run to finish and report per-job results.
# Usage: check.sh [run_id]   (defaults to the CI run for the current HEAD commit)
set -uo pipefail

BRANCH=$(git rev-parse --abbrev-ref HEAD)
HEAD_SHA=$(git rev-parse HEAD)
RUN_ID="${1:-}"
TARGET="run ${RUN_ID:-} (explicit id)"
# How long to wait for GitHub to register the run after a push (seconds).
REGISTER_TIMEOUT="${CI_CHECK_REGISTER_TIMEOUT:-120}"

if [ -z "$RUN_ID" ]; then
  # Pick the run for this exact commit, never just "the latest run on the
  # branch": right after a push the new run isn't registered yet, and the
  # latest run is the previous commit's — a green result for the wrong code.
  # Filter on the commit only (works for push and pull_request runs, and in
  # detached HEAD). gh has no "wait until a run exists" primitive, hence the poll.
  DEADLINE=$((SECONDS + REGISTER_TIMEOUT))
  while :; do
    if ! RUN_ID=$(gh run list --workflow CI --commit "$HEAD_SHA" --limit 1 \
        --json databaseId -q '.[0].databaseId // empty' 2>&1); then
      echo "gh run list failed (auth/network?): $RUN_ID" >&2
      exit 2
    fi
    [ -n "$RUN_ID" ] && break
    if [ "$SECONDS" -ge "$DEADLINE" ]; then
      echo "No CI run found for HEAD ${HEAD_SHA:0:7} ($BRANCH) after ${REGISTER_TIMEOUT}s." >&2
      echo "CI runs only on pushes to master and on PRs into it: was the commit pushed, and does the branch have a PR yet?" >&2
      echo "For an older run, pass its id: check.sh <run_id>" >&2
      exit 2
    fi
    sleep 5
  done
  TARGET="run $RUN_ID (HEAD ${HEAD_SHA:0:7} on $BRANCH)"
fi

echo "Watching $TARGET, this can take a few minutes..."
gh run watch "$RUN_ID" --exit-status > /dev/null 2>&1
STATUS=$?

echo "--- Job results ---"
gh run view "$RUN_ID" --json jobs -q '.jobs[] | "\(.name): \(.conclusion)"'

exit $STATUS
