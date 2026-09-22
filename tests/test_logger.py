"""
Tests for src/logger.py — RotatingFileHandler (architecture-review Minor
finding #7). Previously a plain logging.FileHandler with no rotation, so
logs/qai_consultant.log grew forever for CLI/local usage.

These tests mutate the process-global "qai" logger (a singleton, like the
module under test), so each one carefully saves and restores the real
handlers/_initialized flag in a finally block to avoid leaking state into
other tests in the same pytest session.
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

import logger as logger_module


def _detach_qai_logger():
    """Save the real 'qai' logger state and strip its handlers so a test
    can reinitialize cleanly. Returns (original_handlers, original_initialized)."""
    root = logging.getLogger("qai")
    original_handlers = list(root.handlers)
    original_initialized = logger_module._initialized
    for h in list(root.handlers):
        root.removeHandler(h)
    return root, original_handlers, original_initialized


def _restore_qai_logger(root, original_handlers, original_initialized):
    for h in list(root.handlers):
        root.removeHandler(h)
        h.close()
    for h in original_handlers:
        root.addHandler(h)
    logger_module._initialized = original_initialized


def test_setup_logging_uses_rotating_file_handler_with_bounded_size(tmp_path, monkeypatch):
    root, original_handlers, original_initialized = _detach_qai_logger()
    monkeypatch.setattr(logger_module, "LOG_DIR", tmp_path)
    monkeypatch.setattr(logger_module, "LOG_FILE", tmp_path / "qai_consultant.log")
    monkeypatch.setattr(logger_module, "_initialized", False)

    try:
        logger_module.setup_logging()

        file_handlers = [h for h in root.handlers if isinstance(h, RotatingFileHandler)]
        assert len(file_handlers) == 1, "setup_logging() must attach a RotatingFileHandler"
        fh = file_handlers[0]
        assert fh.maxBytes == logger_module.LOG_MAX_BYTES
        assert fh.backupCount == logger_module.LOG_BACKUP_COUNT
        assert Path(fh.baseFilename) == (tmp_path / "qai_consultant.log")
    finally:
        _restore_qai_logger(root, original_handlers, original_initialized)


def test_rotating_file_handler_actually_rotates_at_small_size(tmp_path, monkeypatch):
    """Behavioral: with a tiny maxBytes, writing enough log records produces
    a .log.1 backup file — confirms real rotation, not just handler wiring."""
    root, original_handlers, original_initialized = _detach_qai_logger()
    log_file = tmp_path / "qai_consultant.log"
    monkeypatch.setattr(logger_module, "LOG_DIR", tmp_path)
    monkeypatch.setattr(logger_module, "LOG_FILE", log_file)
    monkeypatch.setattr(logger_module, "LOG_MAX_BYTES", 500)
    monkeypatch.setattr(logger_module, "LOG_BACKUP_COUNT", 2)
    monkeypatch.setattr(logger_module, "_initialized", False)

    try:
        logger_module.setup_logging()
        log = logger_module.get_logger("test_rotation")
        for i in range(200):
            log.info("x" * 50 + f" line {i}")

        assert log_file.exists()
        assert (tmp_path / "qai_consultant.log.1").exists(), \
            "expected at least one rotated backup file given the tiny maxBytes"
    finally:
        _restore_qai_logger(root, original_handlers, original_initialized)
