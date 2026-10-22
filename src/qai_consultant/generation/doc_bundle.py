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
                # Fixed timestamp: the bytes must be identical on every Streamlit
                # rerun, or the download button's media URL changes mid-click and
                # the browser cancels the download.
                info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                zf.writestr(info, data)
    return buf.getvalue()
