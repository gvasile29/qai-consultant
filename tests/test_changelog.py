"""
Tests for QAI Consultant v2.5.0 release — version bump + CHANGELOG.md
regression guards.

Covers:
1. version.py is bumped to 2.5.0 / 2026-07-07
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
    "[2.5.0]", "[2.0.2]", "[2.0.1]", "[2.0.0]", "[1.0.0]",
    "v0.6", "v0.5", "v0.4", "v0.3", "v0.2", "v0.1",
]


def test_version_bumped_to_2_5_0():
    """version.py must be bumped for the Release Notes feature ship."""
    assert __version__ == "2.5.0", f"Expected __version__ == '2.5.0', got {__version__!r}"
    assert __release_date__ == "2026-07-07", \
        f"Expected __release_date__ == '2026-07-07', got {__release_date__!r}"
    print("  PASS: version.py bumped to 2.5.0 / 2026-07-07")
