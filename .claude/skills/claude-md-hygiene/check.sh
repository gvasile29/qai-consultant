#!/usr/bin/env bash
# claude-md-hygiene/check.sh — report CLAUDE.md size and flag bloated Roadmap/Gotchas bullets.
# Usage: check.sh [path-to-CLAUDE.md]   (defaults to ./CLAUDE.md)
set -uo pipefail

FILE="${1:-CLAUDE.md}"
MAX_BYTES=51200       # ~50KB / ~12K tokens guideline
MAX_LINE_CHARS=600

if [ ! -f "$FILE" ]; then
  echo "No $FILE found." >&2
  exit 1
fi

BYTES=$(wc -c < "$FILE" | tr -d ' ')
EST_TOKENS=$(( BYTES / 4 ))

echo "$FILE: $BYTES bytes (~$EST_TOKENS tokens)"
if [ "$BYTES" -gt "$MAX_BYTES" ]; then
  echo "OVER the ~50KB guideline — trim Roadmap/Gotchas narrative into CHANGELOG.md/docs/postmortems before adding more."
else
  echo "Within the ~50KB guideline."
fi

echo
echo "--- Bullet lines over $MAX_LINE_CHARS chars in Roadmap/Gotchas (candidates to trim or move to a linked doc) ---"

awk -v maxlen="$MAX_LINE_CHARS" '
  /^## / { insection = ($0 ~ /^## (Roadmap|Gotchas)/) ? 1 : 0; next }
  insection && /^- / && length($0) > maxlen {
    printf "%s:%d: %d chars — %s...\n", FILENAME, FNR, length($0), substr($0, 1, 80)
  }
' "$FILE"

echo
echo "(No lines listed above the blank line means no oversized bullets found.)"
