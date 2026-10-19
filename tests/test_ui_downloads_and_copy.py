"""Regression tests for the v3.7.2 live-QA UI fixes (downloads, templates,
Generate Another, time estimate, MCP panel copy). Source-inspection style, like
the other test_app_*.py files: app.py is not importable without Streamlit."""

import ast
import re
import sys
import textwrap
from pathlib import Path
from types import SimpleNamespace

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

APP = (REPO / "src" / "app.py").read_text(encoding="utf-8")
TOKENS = {k: "#000" for k in ("surface", "line", "ink", "ink_dim", "accent", "pass_", "hold", "fail")}


def _func_source(name: str) -> str:
    tree = ast.parse(APP)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return ast.get_source_segment(APP, node)
    raise AssertionError(name)


def test_download_labels_name_the_document():
    labels = re.findall(r'label="⬇️ Download ([^"]+)"', APP)
    for doc in ("Risk Register", "Effort Estimation", "Test Strategy", "Test Plan"):
        assert f"{doc} (.md)" in labels and f"{doc} (.pdf)" in labels


def test_download_file_names_use_sanitized_project_name():
    assert "{project_name}" not in "".join(re.findall(r'file_name=f"[^"]*"', APP))
    assert 're.sub(r"[^\\w\\-.]", "_", project_name.strip())' in APP


def test_pdf_never_generated_inside_tab_render():
    start = APP.index("tab1, tab2, tab3, tab4 = st.tabs")
    end = APP.index("# Generate Another button")
    assert "markdown_to_pdf" not in APP[start:end]


class _State(dict):
    __getattr__ = dict.get


def _run_apply_template(state, key):
    from templates import TEMPLATES

    ns = {"st": SimpleNamespace(session_state=state), "TEMPLATES": TEMPLATES}
    exec(textwrap.dedent(_func_source("_apply_template")), ns)  # noqa: S102
    ns["_apply_template"](key)


def test_template_preserves_entered_project_name_in_both_layers():
    state = _State(answers={"project_name": "Acme Portal"}, input_project_name="Acme Portal")
    _run_apply_template(state, "mobile_app")
    assert state.answers["project_name"] == "Acme Portal"
    assert state["input_project_name"] == "Acme Portal"
    assert state.answers["project_type"] == "Mobile Application"
    assert state["input_project_type"] == "Mobile Application"


def test_template_fills_project_name_when_empty():
    state = _State(answers={})
    _run_apply_template(state, "mobile_app")
    assert state.answers["project_name"] == "Mobile Application"


def test_generate_another_keeps_answers_and_start_over_clears_them():
    fn = _func_source("render_strategy")
    keep = fn[fn.index("if _again:"):fn.index("if _start_over:")]
    assert '"answers",' not in keep
    assert '"results_complete"' in keep and '"generation_started"' in keep
    assert "risk_pdf_bytes" in keep and "test_plan_pdf_bytes" in keep
    assert '"run_count"' not in keep
    assert 'current_step = "dialogue"' in keep
    reset = fn[fn.index("if _start_over:"):]
    assert '"answers"' in reset and 'current_step = "intro"' in reset


def test_time_estimate_is_centralized_and_honest():
    import components

    assert components.GENERATION_TIME_ESTIMATE == "~5-10 min"
    html = components.build_landing_deliverables_html(TOKENS)
    assert "~5-10 min" in html and "~5-10 minutes" in html
    for stale in ("3-5", "3-6", "~2 min"):
        assert stale not in html and stale not in APP


def test_progress_step_indicator_present():
    assert "Step {_active_idx} of {len(order)}" in _func_source("render_strategy")


def test_mcp_panel_copy_is_accurate_and_discloses_telemetry():
    body = re.search(r'MCP_ANNOUNCEMENT_BODY = """(.*?)"""', APP, re.S).group(1)
    assert "offline" not in body.lower()
    assert "one-time embedding model" in body
    for needle in ("telemetry", "on by default", "QAI_TELEMETRY=0", "DO_NOT_TRACK=1",
                   "tool name", "random per-run ID"):
        assert needle in body, needle


def test_deliverable_cards_have_uniform_style():
    import components

    css = components.build_landing_deliverables_html(TOKENS)
    card_delays = [float(d) for d in re.findall(r"\.pom-card:nth-child\(\d\) \{ animation-delay: ([\d.]+)s", css)]
    assert len(card_delays) == 4 and max(card_delays) < 2.6
