"""
Tests for QAI Consultant release version bump + CHANGELOG.md
regression guards.

Covers:
1. version.py is bumped to 2.5.2 / 2026-07-14
2. CHANGELOG.md exists, is non-empty, and has all expected version headings
3. CHANGELOG.md's top heading matches version.py's __version__ (drift guard)
"""

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from version import __version__, __release_date__

CHANGELOG_PATH = REPO_ROOT / "CHANGELOG.md"

_EXPECTED_HEADING_SUBSTRINGS = [
    "[2.5.2]", "[2.5.1]", "[2.5.0]", "[2.0.2]", "[2.0.1]", "[2.0.0]", "[1.0.0]",
    "v0.6", "v0.5", "v0.4", "v0.3", "v0.2", "v0.1",
]


def test_version_bumped_to_2_5_2():
    """version.py must be bumped for the EU AI Act transparency patch ship."""
    assert __version__ == "2.5.2", f"Expected __version__ == '2.5.2', got {__version__!r}"
    assert __release_date__ == "2026-07-14", \
        f"Expected __release_date__ == '2026-07-14', got {__release_date__!r}"
    print("  PASS: version.py bumped to 2.5.2 / 2026-07-14")


def test_changelog_exists_and_nonempty():
    """CHANGELOG.md exists at the repo root and is non-empty."""
    assert CHANGELOG_PATH.exists(), "CHANGELOG.md is missing from the repo root"
    text = CHANGELOG_PATH.read_text(encoding="utf-8")
    assert text.strip(), "CHANGELOG.md exists but is empty"
    print("  PASS: CHANGELOG.md exists and is non-empty")


def test_changelog_has_all_backfilled_version_headings():
    """CHANGELOG.md contains a heading for 2.5.0 and every backfilled version."""
    text = CHANGELOG_PATH.read_text(encoding="utf-8")
    missing = [s for s in _EXPECTED_HEADING_SUBSTRINGS if s not in text]
    assert not missing, f"CHANGELOG.md is missing headings for: {missing}"
    print(f"  PASS: CHANGELOG.md has all {len(_EXPECTED_HEADING_SUBSTRINGS)} expected version headings")


def test_changelog_top_version_matches_version_py():
    """The newest (topmost) CHANGELOG.md version heading must exactly match
    version.py's __version__ — catches bumping one but forgetting the other,
    without hardcoding '2.5.0' as a second magic string."""
    text = CHANGELOG_PATH.read_text(encoding="utf-8")
    match = re.search(r"## \[(\d+\.\d+\.\d+)\]", text)
    assert match, "No '## [X.Y.Z]' version heading found in CHANGELOG.md"
    assert match.group(1) == __version__, (
        f"CHANGELOG.md's top heading is [{match.group(1)}] but "
        f"version.py's __version__ is {__version__!r} — they must match."
    )
    print(f"  PASS: CHANGELOG.md top heading [{match.group(1)}] matches __version__")
