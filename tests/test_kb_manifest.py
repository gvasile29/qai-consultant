"""
Regression/drift guard for src/kb_manifest.py.

Covers:
1. Full coverage — every top-level subfolder of knowledge_base/ (except
   generated_strategies/, which is deliberately excluded) is represented by
   at least one path in KB_MANIFEST. This is the test that would have
   caught the original bug: knowledge_base/evaluation_audit/ was added and
   ingested but never surfaced in the sidebar's hardcoded bullet list.
2. No stale entries — every path declared in KB_MANIFEST actually exists
   under knowledge_base/, catching the manifest drifting the other way
   (pointing at deleted/renamed content).
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from kb_manifest import KB_MANIFEST

KNOWLEDGE_BASE_DIR = REPO_ROOT / "knowledge_base"
EXCLUDED_TOP_LEVEL_FOLDERS = {"generated_strategies"}


def test_every_top_level_kb_subfolder_is_covered_by_manifest():
    """
    Every real top-level subfolder of knowledge_base/ (except
    generated_strategies/) must be covered by at least one manifest path —
    either directly (the subfolder itself) or via a path nested inside it
    (e.g. "standards/istqb" covers the "standards" subfolder).
    """
    top_level_folders = {
        p.name for p in KNOWLEDGE_BASE_DIR.iterdir() if p.is_dir()
    } - EXCLUDED_TOP_LEVEL_FOLDERS

    manifest_paths = [
        rel_path for entry in KB_MANIFEST for rel_path in entry["paths"]
    ]

    uncovered = []
    for folder in top_level_folders:
        covered = any(
            rel_path == folder or rel_path.startswith(f"{folder}/")
            for rel_path in manifest_paths
        )
        if not covered:
            uncovered.append(folder)

    assert not uncovered, (
        f"knowledge_base/ subfolder(s) {uncovered} exist on disk but are not "
        f"covered by any path in src/kb_manifest.py's KB_MANIFEST — the "
        f"sidebar will silently omit them. Add a manifest entry."
    )
    print(f"  PASS: all top-level knowledge_base/ subfolders "
          f"({sorted(top_level_folders)}) are covered by KB_MANIFEST")


def test_every_manifest_path_exists_on_disk():
    """
    Every path declared in KB_MANIFEST must exist under knowledge_base/ —
    catches the manifest going stale (pointing at deleted/renamed content).
    """
    missing = []
    for entry in KB_MANIFEST:
        for rel_path in entry["paths"]:
            full_path = KNOWLEDGE_BASE_DIR / rel_path
            if not full_path.exists():
                missing.append(f"{entry['label']!r} -> {rel_path}")

    assert not missing, (
        f"src/kb_manifest.py declares path(s) that don't exist under "
        f"knowledge_base/: {missing}"
    )
    print("  PASS: every KB_MANIFEST path exists on disk")


def test_generated_strategies_is_never_referenced_by_manifest():
    """
    knowledge_base/generated_strategies/ holds user-feedback-derived content,
    not a curated KB pillar — it must never be advertised in the sidebar.
    """
    manifest_paths = [
        rel_path for entry in KB_MANIFEST for rel_path in entry["paths"]
    ]
    offending = [
        rel_path for rel_path in manifest_paths
        if rel_path == "generated_strategies" or rel_path.startswith("generated_strategies/")
    ]
    assert not offending, (
        f"KB_MANIFEST must not reference generated_strategies/: {offending}"
    )
    print("  PASS: generated_strategies/ is not referenced by KB_MANIFEST")


if __name__ == "__main__":
    test_every_top_level_kb_subfolder_is_covered_by_manifest()
    test_every_manifest_path_exists_on_disk()
    test_generated_strategies_is_never_referenced_by_manifest()
    print("All kb_manifest tests passed.")
