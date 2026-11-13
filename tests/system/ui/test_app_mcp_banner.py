"""
Tests for src/app.py's MCP announcement: the sidebar's "Use QAI in your AI
tools (MCP)" panel and its copy. The one-time st.info banner it once had is
gone: every session starts on the landing page, whose component carries the
MCP section (tests/unit/ui/test_landing.py).
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
APP_SRC = REPO_ROOT / "src"
APP_PY = APP_SRC / "app.py"


def read_app_source() -> str:
    return APP_PY.read_text(encoding="utf-8")


def extract_function(source: str, fn_name: str) -> str:
    """Return the source lines of a top-level function (same helper as test_app_v03.py)."""
    import re
    pattern = rf'\ndef {fn_name}\('
    match = re.search(pattern, source)
    assert match, f"Could not find 'def {fn_name}(' in app.py"
    start = match.start() + 1
    next_def = re.search(r'\ndef \w+\(', source[start + len(f"def {fn_name}("):])
    end = start + len(f"def {fn_name}(") + next_def.start() if next_def else len(source)
    return source[start:end]


def test_sidebar_has_mcp_expander():
    fn = extract_function(read_app_source(), "render_sidebar")
    assert 'st.expander("🔌 Use QAI in your AI tools (MCP)")' in fn, \
        "render_sidebar() is missing the MCP expander"
    assert "MCP_ANNOUNCEMENT_BODY" in fn, \
        "render_sidebar() must render MCP_ANNOUNCEMENT_BODY"


def test_mcp_announcement_body_mentions_install_and_tools():
    import app
    body = app.MCP_ANNOUNCEMENT_BODY
    assert "uvx qai-consultant-mcp" in body
    assert "retrieve_qa_knowledge" in body
    assert "estimate_qa_effort" in body


def test_mcp_announcement_body_links_to_registries():
    # Same three distribution links already carried in README.md/README_MCP.md
    # (official MCP registry, Glama, Awesome MCP Servers) -- now surfaced in
    # the app itself, not just the repo docs.
    import app
    body = app.MCP_ANNOUNCEMENT_BODY
    assert "https://registry.modelcontextprotocol.io" in body
    assert "https://glama.ai/mcp/servers/gvasile29/qai-consultant" in body
    assert "https://github.com/punkpeye/awesome-mcp-servers" in body
