import pytest

from qai_consultant.ui.streaming import consume_stream, format_chars, format_elapsed, writing_caption


def _clock(times):
    it = iter(times)
    return lambda: next(it)


def test_returns_joined_text_and_calls_final_update():
    calls = []
    out = consume_stream(iter(["a", "b", "c"]), lambda t, e: calls.append((t, e)), min_interval=10, clock=_clock([0, 1, 2, 3, 4]))
    assert out == "abc"
    assert calls == [("abc", 4)]


def test_updates_are_throttled_to_the_interval():
    calls = []
    # started=0; chunk times 0.1, 0.6 (>=0.5 since last update at 0), 0.7; final clock 0.8
    consume_stream(iter(["a", "b", "c"]), lambda t, e: calls.append(t), min_interval=0.5, clock=_clock([0, 0.1, 0.6, 0.7, 0.8]))
    assert calls == ["ab", "abc"]


def test_non_string_chunks_are_skipped():
    assert consume_stream(iter(["a", None, 3, "b"]), lambda t, e: None) == "ab"


def test_empty_stream_still_reports_once():
    calls = []
    assert consume_stream(iter([]), lambda t, e: calls.append(t)) == ""
    assert calls == [""]


def test_stream_errors_propagate():
    def boom():
        yield "a"
        raise RuntimeError("provider down")

    with pytest.raises(RuntimeError, match="provider down"):
        consume_stream(boom(), lambda t, e: None)


def test_callback_errors_propagate():
    # Streamlit raises StopException/RerunException from st.* calls inside the callback; they must not be swallowed.
    def cb(text, elapsed):
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        consume_stream(iter(["a"]), cb)


@pytest.mark.parametrize("seconds,expected", [(0, "0:00"), (59.9, "0:59"), (65, "1:05"), (-3, "0:00")])
def test_format_elapsed(seconds, expected):
    assert format_elapsed(seconds) == expected


@pytest.mark.parametrize("count,expected", [(0, "0"), (999, "999"), (1000, "1.0k"), (6250, "6.2k")])
def test_format_chars(count, expected):
    assert format_chars(count) == expected


def test_writing_caption_reports_real_counts_only():
    assert writing_caption("Test Plan", "x" * 1500, 62) == "Writing Test Plan: 1.5k characters, 1:02 elapsed"
