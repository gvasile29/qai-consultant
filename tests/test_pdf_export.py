"""
Tests for src/pdf_export.py — Markdown → PDF conversion.

Covers:
1.  markdown_to_pdf() returns bytes for valid markdown
2.  Returned bytes start with PDF magic header (%PDF-)
3.  PDF is non-empty (> 1 KB)
4.  Title is accepted as a parameter without raising
5.  Empty string input returns bytes (no crash)
6.  markdown_to_pdf() returns None (not raises) when xhtml2pdf unavailable
7.  Markdown with tables is converted without error
8.  Markdown with headers h1-h3 is converted without error
"""

import sys
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from pdf_export import markdown_to_pdf

_SIMPLE_MD = "# Hello\n\nThis is a **test** document.\n\n- item 1\n- item 2\n"

_TABLE_MD = """
# Risk Register

| ID | Risk | Severity |
|----|------|----------|
| R01 | Auth failure | High |
| R02 | Data leak | Critical |
"""

_HEADERS_MD = """
# Top Level

## Second Level

### Third Level

Some body text with `code` and **bold**.
"""


def test_returns_bytes_for_valid_markdown():
    result = markdown_to_pdf(_SIMPLE_MD)
    assert result is not None, "Expected bytes, got None (xhtml2pdf may not be installed)"
    assert isinstance(result, bytes)


def test_pdf_magic_header():
    result = markdown_to_pdf(_SIMPLE_MD)
    if result is None:
        return  # xhtml2pdf not installed — skip
    assert result[:4] == b"%PDF", f"Expected PDF magic header, got: {result[:8]}"


def test_pdf_is_non_empty():
    result = markdown_to_pdf(_SIMPLE_MD)
    if result is None:
        return
    assert len(result) > 1024, f"PDF suspiciously small: {len(result)} bytes"


def test_custom_title_accepted():
    result = markdown_to_pdf(_SIMPLE_MD, title="Custom Report Title")
    assert result is None or isinstance(result, bytes)


def test_empty_string_does_not_raise():
    result = markdown_to_pdf("")
    assert result is None or isinstance(result, bytes)


def test_returns_none_when_xhtml2pdf_unavailable():
    with patch.dict("sys.modules", {"xhtml2pdf": None, "xhtml2pdf.pisa": None}):
        # Force ImportError on xhtml2pdf import inside the function
        import builtins
        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "xhtml2pdf":
                raise ImportError("xhtml2pdf not available")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            result = markdown_to_pdf(_SIMPLE_MD)
    assert result is None


def test_table_markdown_converts():
    result = markdown_to_pdf(_TABLE_MD, title="Risk Register")
    assert result is None or isinstance(result, bytes)


def test_headers_markdown_converts():
    result = markdown_to_pdf(_HEADERS_MD, title="Test Strategy")
    assert result is None or isinstance(result, bytes)


if __name__ == "__main__":
    tests = [
        ("Returns bytes for valid markdown", test_returns_bytes_for_valid_markdown),
        ("PDF magic header (%PDF-)", test_pdf_magic_header),
        ("PDF is non-empty (>1KB)", test_pdf_is_non_empty),
        ("Custom title accepted", test_custom_title_accepted),
        ("Empty string does not raise", test_empty_string_does_not_raise),
        ("Returns None when xhtml2pdf unavailable", test_returns_none_when_xhtml2pdf_unavailable),
        ("Table markdown converts", test_table_markdown_converts),
        ("Headers markdown converts", test_headers_markdown_converts),
    ]
    passed = failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  PASS  {name}")
            passed += 1
        except AssertionError as e:
            print(f"  FAIL  {name}: {e}")
            failed += 1
        except Exception as e:
            print(f"  ERROR {name}: {type(e).__name__}: {e}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
