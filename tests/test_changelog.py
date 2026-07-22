"""
Tests for QAI Consultant release version bump + CHANGELOG.md
regression guards.

Covers:
1. version.py is bumped to 3.1.3 / 2026-07-21
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
    "[3.1.0]", "[3.0.0]", "[2.6.0]", "[2.5.2]", "[2.5.1]", "[2.5.0]", "[2.0.2]", "[2.0.1]", "[2.0.0]", "[1.0.0]",
    "v0.6", "v0.5", "v0.4", "v0.3", "v0.2", "v0.1",
]


def test_version_bumped_to_3_1_3():
    """version.py must be bumped for the visit-counter label fix release."""
    assert __version__ == "3.1.3", f"Expected __version__ == '3.1.3', got {__version__!r}"
    assert __release_date__ == "2026-07-21", \
        f"Expected __release_date__ == '2026-07-21', got {__release_date__!r}"
    print("  PASS: version.py bumped to 3.1.3 / 2026-07-21")


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


def test_pyproject_version_matches_version_py():
    """pyproject.toml's [project] version must match src/version.py's
    __version__ -- these were kept in sync by hand 3 times in one day
    (v3.1.1/3.1.2/3.1.3) with nothing catching a slip."""
    text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'(?m)^version\s*=\s*"([^"]+)"', text)
    assert match, "No 'version = \"X.Y.Z\"' line found in pyproject.toml"
    assert match.group(1) == __version__, (
        f"pyproject.toml's version is {match.group(1)!r} but "
        f"version.py's __version__ is {__version__!r} -- they must match."
    )
    print(f"  PASS: pyproject.toml version {match.group(1)!r} matches __version__")


def test_changelog_top_entry_has_content():
    """The newest CHANGELOG.md entry must have substantive content (at
    least one bullet line) between its heading and the next version
    heading (or end of file) -- catches a version bump that adds the
    heading but forgets to fill in what actually changed."""
    text = CHANGELOG_PATH.read_text(encoding="utf-8")
    headings = list(re.finditer(r"(?m)^## \[", text))
    assert headings, "No '## [X.Y.Z]' version heading found in CHANGELOG.md"
    start = headings[0].end()
    end = headings[1].start() if len(headings) > 1 else len(text)
    body = text[start:end]
    assert re.search(r"(?m)^- ", body), (
        "The topmost CHANGELOG.md entry has no '- ' bullet content -- "
        "looks like a bare heading with nothing describing the change."
    )
    print("  PASS: topmost CHANGELOG.md entry has bullet content")
