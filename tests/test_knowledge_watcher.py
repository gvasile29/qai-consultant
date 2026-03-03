"""
Tests for src/knowledge_watcher.py — v0.5 Auto Re-ingest.

Covers:
1.  IngestManifest.build_from_existing() builds manifest without re-ingesting
2.  IngestManifest.is_new_or_changed() returns True for new files
3.  IngestManifest.is_new_or_changed() returns False for already-ingested files
4.  IngestManifest.is_new_or_changed() returns True for files modified after last ingest
5.  IngestManifest.get_new_or_changed_files() returns only new/changed files
6.  IngestManifest ignores IGNORED_PATTERNS (~$, .tmp, .gitkeep)
7.  SUPPORTED_EXTENSIONS = {.pdf, .md, .txt} only
8.  IngestManager.ingest_file() returns 0 for unsupported file types
9.  IngestManager.ingest_file() returns 0 for non-existent files
10. KnowledgeBaseWatcher.start() starts observer and is_running() = True
11. KnowledgeBaseWatcher.stop() stops observer and is_running() = False
12. get_watcher() returns same singleton instance on multiple calls
13. app.py has start_kb_watcher() defined with @st.cache_resource
14. app.py has check_kb_notification() that reads and deletes _NOTIFICATION_FILE
15. app.py main() calls start_kb_watcher()
16. app.py calls st.toast() when kb_msg is present
17. cli.py passes watcher to _run_main_loop()
18. cli.py calls watcher.ingest_manager.ingest_file() after feedback save
19. app.py calls watcher.ingest_manager.ingest_file() after feedback save
20. watchdog==4.0.0 present in requirements.txt
21. Integration: IngestManager.ingest_file() ingests new .md file and updates manifest
"""

import sys
import os
os.environ["ANONYMIZED_TELEMETRY"] = "False"
os.environ["CHROMA_TELEMETRY"] = "False"

import re
import json
import time
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
APP_PY = SRC_DIR / "app.py"
CLI_PY = SRC_DIR / "cli.py"
REQUIREMENTS_TXT = REPO_ROOT / "requirements.txt"

sys.path.insert(0, str(SRC_DIR))

from knowledge_watcher import (
    IngestManifest,
    IngestManager,
    KnowledgeBaseWatcher,
    get_watcher,
    KB_DIR,
    SUPPORTED_EXTENSIONS,
    IGNORED_PATTERNS,
    MANIFEST_PATH,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def read_app_source() -> str:
    return APP_PY.read_text(encoding="utf-8")


def read_cli_source() -> str:
    return CLI_PY.read_text(encoding="utf-8")


def extract_function(source: str, fn_name: str) -> str:
    """Return source lines of a top-level function."""
    pattern = rf'\ndef {fn_name}\('
    start = re.search(pattern, source)
    if not start:
        raise ValueError(f"Function '{fn_name}' not found")
    rest = source[start.start():]
    next_def = re.search(r'\ndef \w', rest[4:])
    if next_def:
        return rest[:next_def.start() + 4]
    return rest


def first_kb_md_file() -> Path:
    """Return the first .md file found in the knowledge base."""
    for f in KB_DIR.rglob("*.md"):
        if not any(p in f.name for p in IGNORED_PATTERNS):
            return f
    raise RuntimeError("No .md files found in knowledge_base/")


# ── 1. IngestManifest.build_from_existing() ──────────────────────────────────

def test_build_from_existing_no_reingest():
    """
    build_from_existing() records all KB files in the manifest without
    calling any ChromaDB operations. All entries get chunk_count=0.
    """
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        temp_path = Path(f.name)
    temp_path.unlink()  # Remove so manifest appears missing

    try:
        with patch("knowledge_watcher.MANIFEST_PATH", temp_path):
            manifest = IngestManifest()
            manifest.build_from_existing()

            assert manifest._data["files"], \
                "build_from_existing() should populate files when manifest is missing"

            # All entries must have chunk_count=0 — no actual ingest happened
            for key, info in manifest._data["files"].items():
                assert info["chunk_count"] == 0, \
                    f"chunk_count should be 0 for {key} (not re-ingested)"

            file_count = len(manifest._data["files"])

        print(f"  PASS: build_from_existing() recorded {file_count} files, all chunk_count=0 (no re-ingest)")
    finally:
        if temp_path.exists():
            temp_path.unlink()


def test_build_from_existing_skips_when_manifest_exists():
    """build_from_existing() does nothing if manifest already has entries."""
    manifest = IngestManifest()
    manifest._data["files"]["fake/file.md"] = {
        "last_modified": 12345.0,
        "chunk_count": 5,
        "ingested_at": "2026-01-01T00:00:00",
    }

    original_count = len(manifest._data["files"])

    # Patch MANIFEST_PATH so load() reads our fake data (writes but doesn't corrupt)
    with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False, encoding="utf-8") as f:
        json.dump(manifest._data, f)
        temp_path = Path(f.name)

    try:
        with patch("knowledge_watcher.MANIFEST_PATH", temp_path):
            manifest2 = IngestManifest()
            manifest2.build_from_existing()
            # Should not have added new files — returned early
            assert len(manifest2._data["files"]) == original_count, \
                "build_from_existing() should skip when manifest already has entries"
        print("  PASS: build_from_existing() skips when manifest already has entries")
    finally:
        temp_path.unlink()


# ── 2-4. IngestManifest.is_new_or_changed() ──────────────────────────────────

def test_is_new_or_changed_true_for_new_file():
    """is_new_or_changed() returns True for a file not in manifest."""
    manifest = IngestManifest()
    manifest._data = {"version": "1.0", "last_updated": "", "files": {}}

    test_file = first_kb_md_file()
    result = manifest.is_new_or_changed(test_file)
    assert result is True, \
        f"Expected True for file not in manifest, got {result}"
    print(f"  PASS: is_new_or_changed() = True for '{test_file.name}' (not in manifest)")


def test_is_new_or_changed_false_for_ingested():
    """is_new_or_changed() returns False for a file already in manifest with matching mtime."""
    manifest = IngestManifest()
    manifest._data = {"version": "1.0", "last_updated": "", "files": {}}

    test_file = first_kb_md_file()
    key = str(test_file.relative_to(KB_DIR))
    current_mtime = test_file.stat().st_mtime

    # Record file with its exact current mtime
    manifest._data["files"][key] = {
        "last_modified": current_mtime,
        "chunk_count": 10,
        "ingested_at": datetime.now().isoformat(),
    }

    result = manifest.is_new_or_changed(test_file)
    assert result is False, \
        f"Expected False for file with matching mtime, got {result}"
    print(f"  PASS: is_new_or_changed() = False for '{test_file.name}' (mtime matches manifest)")


def test_is_new_or_changed_true_for_modified():
    """is_new_or_changed() returns True for a file with newer mtime than manifest."""
    manifest = IngestManifest()
    manifest._data = {"version": "1.0", "last_updated": "", "files": {}}

    test_file = first_kb_md_file()
    key = str(test_file.relative_to(KB_DIR))
    old_mtime = test_file.stat().st_mtime - 86400  # 1 day ago

    manifest._data["files"][key] = {
        "last_modified": old_mtime,
        "chunk_count": 10,
        "ingested_at": "2025-01-01T00:00:00",
    }

    result = manifest.is_new_or_changed(test_file)
    assert result is True, \
        f"Expected True for file newer than manifest entry, got {result}"
    print(f"  PASS: is_new_or_changed() = True for '{test_file.name}' (file modified after manifest)")


# ── 5. IngestManifest.get_new_or_changed_files() ─────────────────────────────

def test_get_new_or_changed_files():
    """get_new_or_changed_files() returns only new/changed files."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        temp_path = Path(f.name)
    temp_path.unlink()  # No manifest = all files are new

    try:
        with patch("knowledge_watcher.MANIFEST_PATH", temp_path):
            manifest = IngestManifest()
            changed = manifest.get_new_or_changed_files()

        assert changed, "Should find new files when manifest is empty"
        # All returned files must be under KB_DIR and have supported extensions
        for f in changed:
            assert f.suffix in SUPPORTED_EXTENSIONS, \
                f"Unsupported extension returned: {f.suffix}"
            assert str(KB_DIR) in str(f), \
                f"File not under KB_DIR: {f}"
        print(f"  PASS: get_new_or_changed_files() found {len(changed)} new files (all supported extensions)")
    finally:
        if temp_path.exists():
            temp_path.unlink()


# ── 6. IGNORED_PATTERNS ───────────────────────────────────────────────────────

def test_ignored_patterns():
    """_should_ignore() returns True for files matching IGNORED_PATTERNS."""
    manifest = IngestManifest()

    # Should be ignored
    assert manifest._should_ignore(Path("~$temp_doc.md")), "~$ prefix should be ignored"
    assert manifest._should_ignore(Path("file.tmp")), ".tmp should be ignored"
    assert manifest._should_ignore(Path(".gitkeep")), ".gitkeep should be ignored"

    # Should NOT be ignored
    assert not manifest._should_ignore(Path("real_file.md")), "Normal .md should not be ignored"
    assert not manifest._should_ignore(Path("strategy.pdf")), "Normal .pdf should not be ignored"
    assert not manifest._should_ignore(Path("notes.txt")), "Normal .txt should not be ignored"

    print(f"  PASS: _should_ignore() correctly filters: {IGNORED_PATTERNS}")
    print("        Correctly passes: .md, .pdf, .txt files")


# ── 7. SUPPORTED_EXTENSIONS ───────────────────────────────────────────────────

def test_supported_extensions():
    """SUPPORTED_EXTENSIONS contains exactly .pdf, .md, .txt."""
    assert ".pdf" in SUPPORTED_EXTENSIONS, ".pdf should be supported"
    assert ".md" in SUPPORTED_EXTENSIONS, ".md should be supported"
    assert ".txt" in SUPPORTED_EXTENSIONS, ".txt should be supported"
    assert ".json" not in SUPPORTED_EXTENSIONS, ".json should NOT be supported"
    assert ".docx" not in SUPPORTED_EXTENSIONS, ".docx should NOT be supported"
    assert ".html" not in SUPPORTED_EXTENSIONS, ".html should NOT be supported"
    assert len(SUPPORTED_EXTENSIONS) == 3, \
        f"Expected exactly 3 supported extensions, got {len(SUPPORTED_EXTENSIONS)}: {SUPPORTED_EXTENSIONS}"
    print(f"  PASS: SUPPORTED_EXTENSIONS = {SUPPORTED_EXTENSIONS} (exactly 3 types)")


# ── 8-9. IngestManager.ingest_file() guards ───────────────────────────────────

def test_ingest_file_returns_0_for_unsupported():
    """ingest_file() returns 0 for unsupported file types without loading ChromaDB."""
    manager = IngestManager()
    result = manager.ingest_file(Path("/any/valid/path/file.json"))
    assert result == 0, f"Expected 0 for .json file, got {result}"
    result2 = manager.ingest_file(Path("/any/valid/path/document.docx"))
    assert result2 == 0, f"Expected 0 for .docx file, got {result2}"
    print("  PASS: ingest_file() returns 0 for unsupported file types (.json, .docx)")


def test_ingest_file_returns_0_for_nonexistent():
    """ingest_file() returns 0 for files that don't exist."""
    manager = IngestManager()
    result = manager.ingest_file(Path("/nonexistent/path/that/does/not/exist.md"))
    assert result == 0, f"Expected 0 for non-existent file, got {result}"
    print("  PASS: ingest_file() returns 0 for non-existent files")


# ── 10-11. KnowledgeBaseWatcher.start() / stop() ─────────────────────────────

def test_watcher_start_sets_running():
    """KnowledgeBaseWatcher.start() starts the observer and is_running() returns True."""
    watcher = KnowledgeBaseWatcher()
    assert not watcher.is_running(), "Watcher should not be running before start()"

    watcher.start(callback=None)
    try:
        assert watcher.is_running(), "Watcher should be running after start()"
        print("  PASS: KnowledgeBaseWatcher.start() -> is_running() = True")
    finally:
        watcher.stop()


def test_watcher_stop_sets_not_running():
    """KnowledgeBaseWatcher.stop() stops the observer and is_running() returns False."""
    watcher = KnowledgeBaseWatcher()
    watcher.start(callback=None)
    assert watcher.is_running(), "Precondition: watcher must be running"

    watcher.stop()
    assert not watcher.is_running(), "Watcher should not be running after stop()"
    print("  PASS: KnowledgeBaseWatcher.stop() -> is_running() = False")


def test_watcher_start_idempotent():
    """Calling start() twice does not start a second observer."""
    watcher = KnowledgeBaseWatcher()
    watcher.start(callback=None)
    observer1 = watcher._observer
    try:
        watcher.start(callback=None)  # second start
        observer2 = watcher._observer
        assert observer1 is observer2, "Second start() should not replace the observer"
        print("  PASS: start() is idempotent — calling twice doesn't create a second observer")
    finally:
        watcher.stop()


# ── 12. get_watcher() singleton ───────────────────────────────────────────────

def test_get_watcher_singleton():
    """get_watcher() returns the same KnowledgeBaseWatcher instance on multiple calls."""
    import knowledge_watcher
    original = knowledge_watcher._watcher

    try:
        knowledge_watcher._watcher = None  # reset for clean test
        w1 = get_watcher()
        w2 = get_watcher()
        assert w1 is w2, "get_watcher() should return the same instance"
        assert isinstance(w1, KnowledgeBaseWatcher), \
            "get_watcher() should return a KnowledgeBaseWatcher"
        print("  PASS: get_watcher() returns singleton KnowledgeBaseWatcher instance")
    finally:
        knowledge_watcher._watcher = original  # restore original singleton


# ── 13-16. app.py structural tests ───────────────────────────────────────────

def test_app_has_start_kb_watcher_cached():
    """app.py defines start_kb_watcher() decorated with @st.cache_resource."""
    source = read_app_source()

    # @st.cache_resource must appear immediately before def start_kb_watcher
    pattern = r'@st\.cache_resource[^\n]*\ndef start_kb_watcher\('
    assert re.search(pattern, source), \
        "start_kb_watcher() must be decorated with @st.cache_resource"
    print("  PASS: start_kb_watcher() defined with @st.cache_resource in app.py")


def test_app_has_check_kb_notification():
    """app.py defines check_kb_notification() that reads and deletes _NOTIFICATION_FILE."""
    source = read_app_source()
    fn = extract_function(source, "check_kb_notification")

    assert "_NOTIFICATION_FILE.exists()" in fn, \
        "_NOTIFICATION_FILE.exists() not found in check_kb_notification()"
    assert "unlink()" in fn, \
        "unlink() not found — _NOTIFICATION_FILE should be deleted after reading"
    assert "return" in fn, \
        "check_kb_notification() should return the message"
    print("  PASS: check_kb_notification() reads message from _NOTIFICATION_FILE and deletes it")


def test_app_main_calls_start_kb_watcher():
    """app.py main() calls start_kb_watcher() to start the watcher once per session."""
    source = read_app_source()
    fn = extract_function(source, "main")

    assert "start_kb_watcher()" in fn, \
        "main() should call start_kb_watcher()"
    print("  PASS: app.py main() calls start_kb_watcher()")


def test_app_calls_st_toast():
    """app.py main() calls st.toast() when kb_msg is present."""
    source = read_app_source()
    fn = extract_function(source, "main")

    assert "st.toast(" in fn, \
        "main() should call st.toast() to display KB update notifications"
    assert "kb_msg" in fn, \
        "st.toast() should be conditional on kb_msg"
    print("  PASS: app.py main() calls st.toast(kb_msg, ...) when notification is present")


# ── 17-19. CLI + app.py integration structural tests ─────────────────────────

def test_cli_passes_watcher_to_run_main_loop():
    """cli.py main() creates watcher and passes it to _run_main_loop()."""
    source = read_cli_source()
    fn = extract_function(source, "main")

    assert "_run_main_loop" in fn, \
        "main() should call _run_main_loop()"
    assert "watcher" in fn, \
        "main() should have a watcher variable"
    # watcher must be passed as argument to _run_main_loop
    assert re.search(r'_run_main_loop\s*\(.*watcher', fn) or \
           re.search(r'_run_main_loop\s*\(agent\s*,\s*watcher', fn), \
        "watcher should be passed as argument to _run_main_loop()"
    print("  PASS: cli.py main() passes watcher to _run_main_loop(agent, watcher)")


def test_cli_ingest_after_feedback():
    """cli.py calls watcher.ingest_manager.ingest_file() after saving feedback strategy."""
    source = read_cli_source()

    assert "watcher.ingest_manager.ingest_file(" in source, \
        "cli.py should call watcher.ingest_manager.ingest_file() after feedback save"
    print("  PASS: cli.py calls watcher.ingest_manager.ingest_file() after feedback save")


def test_app_ingest_after_feedback():
    """app.py calls watcher.ingest_manager.ingest_file() after saving feedback strategy."""
    source = read_app_source()
    fn = extract_function(source, "render_strategy")

    assert "watcher.ingest_manager.ingest_file(" in fn, \
        "render_strategy() should call watcher.ingest_manager.ingest_file() after feedback save"
    print("  PASS: app.py render_strategy() calls watcher.ingest_manager.ingest_file() after feedback")


# ── 20. requirements.txt ──────────────────────────────────────────────────────

def test_watchdog_in_requirements():
    """watchdog==4.0.0 is present in requirements.txt."""
    content = REQUIREMENTS_TXT.read_text(encoding="utf-8")
    assert "watchdog==4.0.0" in content, \
        "watchdog==4.0.0 not found in requirements.txt"
    print("  PASS: watchdog==4.0.0 present in requirements.txt")


# ── 21. Integration test (requires ChromaDB + embeddings) ────────────────────

def test_ingest_new_md_file():
    """
    Integration: IngestManager.ingest_file() ingests a new .md file into ChromaDB
    and updates the manifest with the correct chunk count.
    """
    articles_dir = KB_DIR / "articles"
    test_file = articles_dir / "_test_watcher_smoke_2026.md"

    try:
        # Write a recognizable test article
        test_file.write_text(
            "# Watcher Smoke Test Article\n\n"
            "This temporary article is used to verify that the v0.5 auto-ingest "
            "pipeline correctly ingests new files into ChromaDB and updates the manifest.\n\n"
            "## Key Points\n\n"
            "- Incremental ingest: only new files are processed\n"
            "- Manifest tracks last_modified timestamp per file\n"
            "- Chunk count is recorded in manifest after ingest\n",
            encoding="utf-8",
        )

        print(f"  Created test file: {test_file.name}")

        manager = IngestManager()
        chunks = manager.ingest_file(test_file)

        assert chunks > 0, \
            f"Expected > 0 chunks from test .md file, got {chunks}"

        # Verify manifest was updated
        key = str(test_file.relative_to(KB_DIR))
        manifest_files = manager._manifest._data["files"]
        assert key in manifest_files, \
            f"Manifest not updated for {key}"
        assert manifest_files[key]["chunk_count"] == chunks, \
            f"Manifest chunk_count mismatch: {manifest_files[key]['chunk_count']} != {chunks}"
        assert manifest_files[key]["last_modified"] > 0, \
            "Manifest should record last_modified timestamp"

        print(f"  PASS: ingest_file() ingested {chunks} chunks from '{test_file.name}'")
        print(f"        Manifest updated: key='{key}', chunk_count={chunks}")

    finally:
        if test_file.exists():
            test_file.unlink()
            print(f"  Cleaned up test file: {test_file.name}")


# ── Runner ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    static_tests = [
        ("build_from_existing() records KB files with chunk_count=0 (no re-ingest)",
            test_build_from_existing_no_reingest),
        ("build_from_existing() skips when manifest already has entries",
            test_build_from_existing_skips_when_manifest_exists),
        ("is_new_or_changed() = True for file not in manifest",
            test_is_new_or_changed_true_for_new_file),
        ("is_new_or_changed() = False for file with matching mtime",
            test_is_new_or_changed_false_for_ingested),
        ("is_new_or_changed() = True for file newer than manifest entry",
            test_is_new_or_changed_true_for_modified),
        ("get_new_or_changed_files() finds new files when manifest is empty",
            test_get_new_or_changed_files),
        ("_should_ignore() filters IGNORED_PATTERNS (~$, .tmp, .gitkeep)",
            test_ignored_patterns),
        ("SUPPORTED_EXTENSIONS = {.pdf, .md, .txt} only",
            test_supported_extensions),
        ("ingest_file() returns 0 for unsupported file types",
            test_ingest_file_returns_0_for_unsupported),
        ("ingest_file() returns 0 for non-existent files",
            test_ingest_file_returns_0_for_nonexistent),
        ("KnowledgeBaseWatcher.start() -> is_running() = True",
            test_watcher_start_sets_running),
        ("KnowledgeBaseWatcher.stop() -> is_running() = False",
            test_watcher_stop_sets_not_running),
        ("start() is idempotent — second call doesn't create new observer",
            test_watcher_start_idempotent),
        ("get_watcher() returns same singleton instance",
            test_get_watcher_singleton),
        ("app.py start_kb_watcher() decorated with @st.cache_resource",
            test_app_has_start_kb_watcher_cached),
        ("app.py check_kb_notification() reads and deletes _NOTIFICATION_FILE",
            test_app_has_check_kb_notification),
        ("app.py main() calls start_kb_watcher()",
            test_app_main_calls_start_kb_watcher),
        ("app.py main() calls st.toast() on kb_msg",
            test_app_calls_st_toast),
        ("cli.py main() passes watcher to _run_main_loop()",
            test_cli_passes_watcher_to_run_main_loop),
        ("cli.py calls watcher.ingest_manager.ingest_file() after feedback",
            test_cli_ingest_after_feedback),
        ("app.py calls watcher.ingest_manager.ingest_file() after feedback",
            test_app_ingest_after_feedback),
        ("watchdog==4.0.0 present in requirements.txt",
            test_watchdog_in_requirements),
    ]

    passed = failed = 0

    print("=" * 68)
    print("  QAI Consultant — Knowledge Base Watcher v0.5 Tests")
    print("=" * 68)

    for name, fn in static_tests:
        print(f"\n[TEST] {name}")
        try:
            fn()
            passed += 1
        except AssertionError as e:
            print(f"  FAIL: {e}")
            failed += 1
        except Exception as e:
            import traceback
            print(f"  ERROR: {type(e).__name__}: {e}")
            traceback.print_exc()
            failed += 1

    # Integration test (requires ChromaDB)
    print(f"\n{'=' * 68}")
    print("  Integration test (requires ChromaDB + HuggingFace embeddings)...")
    print(f"{'=' * 68}")

    print("\n[TEST] Integration: ingest new .md file, verify chunks + manifest")
    try:
        test_ingest_new_md_file()
        passed += 1
    except AssertionError as e:
        print(f"  FAIL: {e}")
        failed += 1
    except Exception as e:
        import traceback
        print(f"  ERROR: {type(e).__name__}: {e}")
        traceback.print_exc()
        failed += 1

    print(f"\n{'=' * 68}")
    print(f"  Results: {passed} passed, {failed} failed")
    print(f"{'=' * 68}")

    import sys as _sys
    _sys.exit(0 if failed == 0 else 1)
