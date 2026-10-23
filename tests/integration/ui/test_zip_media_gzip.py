"""A .zip served through Streamlit's gzip middleware must not 500.

Starlette >= 1.8 breaks Streamlit 1.59.1's media-aware gzip override for
content types Starlette excludes from compression: the live "Download all 4
documents (.zip)" button returned HTTP 500 while PDFs and markdown worked.
requirements.txt pins starlette; this fails if a bump reintroduces the bug.
"""
import os
import zipfile
from io import BytesIO

import pytest

pytest.importorskip("starlette.testclient")
pytest.importorskip("httpx")

from starlette.applications import Starlette
from starlette.responses import Response
from starlette.routing import Route
from starlette.testclient import TestClient

from streamlit.web.server.starlette.starlette_gzip_middleware import MediaAwareGZipMiddleware


def _zip_bytes() -> bytes:
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("a.md", os.urandom(200_000))
    return buf.getvalue()


def _client(body: bytes, media_type: str) -> TestClient:
    async def endpoint(_request):
        return Response(body, media_type=media_type, headers={"Content-Length": str(len(body))})

    app = Starlette(routes=[Route("/f", endpoint)])
    app.add_middleware(MediaAwareGZipMiddleware)
    return TestClient(app, raise_server_exceptions=False)


@pytest.mark.parametrize("media_type", ["application/zip", "application/pdf"])
def test_download_through_gzip_middleware_is_served(media_type):
    body = _zip_bytes() if media_type == "application/zip" else b"%PDF" + b"x" * 50_000
    response = _client(body, media_type).get("/f", headers={"Accept-Encoding": "gzip"})
    assert response.status_code == 200
    assert len(response.content) == len(body)
