"""Bundle the generated documents into one .zip for the "Download all" button.

Stdlib only; Streamlit-only (not in the MCP wheel).
"""

import io
import zipfile
from typing import Mapping


def build_zip(files: Mapping[str, bytes]) -> bytes:
    """Zip ``files`` (archive name -> bytes). Entries with no content (e.g. a PDF
    still rendering) are skipped rather than stored empty."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in files.items():
            if data:
                zf.writestr(name, data)
    return buf.getvalue()
