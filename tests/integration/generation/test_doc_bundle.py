"""Download-all .zip bundle helper."""

import io
import sys
import zipfile
from pathlib import Path


from qai_consultant.generation.doc_bundle import build_zip  # noqa: E402


def test_zip_contains_nonempty_files_and_skips_empty_ones():
    data = build_zip({"plan.md": b"# Plan", "plan.pdf": b"", "risk.md": "é".encode("utf-8")})
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        assert sorted(zf.namelist()) == ["plan.md", "risk.md"]
        assert zf.read("risk.md").decode("utf-8") == "é"


def test_zip_bytes_are_deterministic_across_builds():
    """Streamlit rebuilds the bundle every rerun; changing bytes change the
    download button's media URL and the browser cancels an in-flight download."""
    import time

    files = {"a.md": b"# A", "b.md": b"# B"}
    first = build_zip(files)
    time.sleep(2.1)
    assert build_zip(files) == first
