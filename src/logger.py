"""
QAI Consultant — Centralized Logging
All modules import get_logger() from here instead of using raw logging or print().
"""

import logging
import sys
from pathlib import Path

# ── Config ─────────────────────────────────────────────────────────────────────
LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_FILE = LOG_DIR / "qai_consultant.log"
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s:%(lineno)d - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_initialized = False


def setup_logging(level: str = "INFO") -> None:
    """
    Initialize logging for QAI Consultant.
    Creates logs/ directory and sets up file + console handlers.
    Should be called once at application startup.

    Args:
        level: Log level string ("DEBUG", "INFO", "WARNING", "ERROR"). Default: "INFO".
    """
    global _initialized
    if _initialized:
        return

    LOG_DIR.mkdir(exist_ok=True)

    numeric_level = getattr(logging, level.upper(), logging.INFO)

    # Root logger
    root = logging.getLogger("qai")
    root.setLevel(numeric_level)

    # ── File handler — always DEBUG level for full detail ──────────────────────
    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))

    # ── Console handler — WARNING+ only (don't spam the terminal) ──────────────
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(logging.Formatter(
        "%(levelname)s: %(message)s"
    ))

    root.addHandler(file_handler)
    root.addHandler(console_handler)

    _initialized = True
    root.info(f"Logging initialized — writing to {LOG_FILE}")


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger for a module.
    Always call setup_logging() once at startup before using loggers.

    Args:
        name: Module name, typically __name__.

    Returns:
        A Logger instance scoped under 'qai.<name>'.

    Example:
        logger = get_logger(__name__)
        logger.info("Agent loaded successfully")
    """
    if not _initialized:
        setup_logging()
    return logging.getLogger(f"qai.{name}")
