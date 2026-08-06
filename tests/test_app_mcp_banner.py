"""
Tests for src/app.py — v3.0 step 9 MCP announcement (sidebar panel + one-time
banner), following the exact v2.5.0 Release Notes pattern
(test_app_v03.py's test_banner_exists_and_gates_on_release_notes_seen /
test_sidebar_has_release_notes_expander / test_cleanup_blocks_do_not_clear_*).

Covers:
1. render_sidebar() has a "Use QAI in your AI tools (MCP)" expander
2. main() shows a one-time banner gated on session_state.mcp_announcement_seen,
   running before render_sidebar()
3. Neither "Start Over" (render_sidebar) nor "Generate Another Strategy"
   (render_strategy) clears mcp_announcement_seen — it's a session-wide
   "have you seen this" flag, not per-run state
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
APP_SRC = REPO_ROOT / "src"
APP_PY = APP_SRC / "app.py"
sys.path.insert(0, str(APP_SRC))


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


def test_banner_exists_and_gates_on_mcp_announcement_seen():
    fn = extract_function(read_app_source(), "main")
    assert 'st.session_state.get("mcp_announcement_seen")' in fn, \
        "main() does not check st.session_state.get('mcp_announcement_seen')"
    assert "st.session_state.mcp_announcement_seen = True" in fn, \
        "main() does not set mcp_announcement_seen = True"
    assert "st.info(" in fn and "MCP server" in fn, \
        "main() does not show the MCP announcement banner via st.info(...)"


def test_mcp_banner_appears_before_render_sidebar_call():
    fn = extract_function(read_app_source(), "main")
    banner_pos = fn.find('st.session_state.get("mcp_announcement_seen")')
    sidebar_pos = fn.find("render_sidebar()")
    assert banner_pos != -1, "MCP banner gate not found in main()"
    assert sidebar_pos != -1, "render_sidebar() call not found in main()"
    assert banner_pos < sidebar_pos, \
        "the mcp_announcement_seen banner must run before render_sidebar() is called"


def test_cleanup_blocks_do_not_clear_mcp_announcement_seen():
    source = read_app_source()
    for fn_name in ["render_sidebar", "render_strategy"]:
        fn = extract_function(source, fn_name)
        assert '"mcp_announcement_seen"' not in fn, \
            f"{fn_name}() must NOT clear mcp_announcement_seen"
