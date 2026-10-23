"""Quiet consumption of an LLM stream with throttled progress callbacks.

Dependency-free (no Streamlit import) so the throttling and formatting are unit-testable. The caller wires
`on_update` to its own placeholders; exceptions from the stream or the callback (including Streamlit's
StopException/RerunException) propagate untouched.
"""
import time
from typing import Callable, Iterable

UPDATE_INTERVAL_SECONDS = 0.5


def consume_stream(
    chunks: Iterable[str],
    on_update: Callable[[str, float], None],
    min_interval: float = UPDATE_INTERVAL_SECONDS,
    clock: Callable[[], float] = time.monotonic,
) -> str:
    """Join `chunks` into one string, calling `on_update(text_so_far, elapsed_seconds)` at most every
    `min_interval` seconds and once more with the final text."""
    parts: list[str] = []
    started = clock()
    last_update = started
    for chunk in chunks:
        if not isinstance(chunk, str):
            continue
        parts.append(chunk)
        now = clock()
        if now - last_update >= min_interval:
            on_update("".join(parts), now - started)
            last_update = now
    text = "".join(parts)
    on_update(text, clock() - started)
    return text


def format_elapsed(seconds: float) -> str:
    total = max(0, int(seconds))
    return f"{total // 60}:{total % 60:02d}"


def format_chars(count: int) -> str:
    return f"{count / 1000:.1f}k" if count >= 1000 else str(count)


def writing_caption(label: str, text: str, elapsed: float) -> str:
    """Honest per-stage status: what has actually arrived, not a guessed percentage."""
    return f"Writing {label}: {format_chars(len(text))} characters, {format_elapsed(elapsed)} elapsed"
