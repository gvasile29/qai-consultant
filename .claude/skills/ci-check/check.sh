#!/usr/bin/env bash
# ci-check/check.sh — wait for a GitHub Actions run to finish and report per-job results.
# Usage: check.sh [run_id]   (defaults to the latest run on the current branch)
set -uo pipefail

BRANCH=$(git rev-parse --abbrev-ref HEAD)
RUN_ID="${1:-}"

if [ -z "$RUN_ID" ]; then
  RUN_ID=$(gh run list --branch "$BRANCH" --workflow CI --limit 1 --json databaseId -q '.[0].databaseId')
fi

echo "Watching run $RUN_ID on branch $BRANCH (this can take a few minutes)..."
gh run watch "$RUN_ID" --exit-status > /dev/null 2>&1
STATUS=$?

echo "--- Job results ---"
gh run view "$RUN_ID" --json jobs -q '.jobs[] | "\(.name): \(.conclusion)"'

exit $STATUS
