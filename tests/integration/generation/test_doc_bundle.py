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
