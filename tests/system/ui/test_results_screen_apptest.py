"""
Drives the real strategy results screen with Streamlit's AppTest from a
seeded "generation finished" session (no LLM, no Pinecone): the Mission
Control readout tiles, the risk map in the Risk Register tab, the detailed
readout behind its expander, and a timeline without the mission clock.
The generating screen's ticking clock is browser-only and is checked by the
phase 2 render harness, not here.
"""
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent

pytest.importorskip("streamlit.testing.v1")
from streamlit.testing.v1 import AppTest  # noqa: E402

_SCRIPT = """
import app
app.load_agent = lambda: (object(), None)
app.get_and_increment_visit_count = lambda: 1
app._adoption_snapshot = lambda: {}
app.main()
"""

_RISK = """# Risk Register

## Risk Matrix Overview

| Risk ID | Risk Description | Likelihood | Impact | Risk Level | Priority |
|---------|------------------|------------|--------|------------|----------|
| R01 | Payment failure | High | High | Critical | 1 |
| R02 | Auth bypass | Medium | High | High | 2 |
| R03 | Slow reports | Low | Low | Low | 3 |
"""


@pytest.fixture
def at(tmp_path, monkeypatch):
    from qai_consultant.core.dialogue import DialogueManager
    from qai_consultant.core.effort_core import EstimationData

    monkeypatch.chdir(REPO_ROOT)
    script = tmp_path / "app_under_test.py"
    script.write_text(_SCRIPT, encoding="utf-8")
    test = AppTest.from_file(str(script), default_timeout=60)

    effort = EstimationData()
    effort.final_effort_min, effort.final_effort_max = 42.0, 51.5
    effort.pert_total_expected, effort.available_person_days = 46.2, 36.0
    effort.capacity_gap, effort.confidence_level, effort.confidence_score = -10.2, "Medium", 59
    dialogue = DialogueManager()
    dialogue.context.project_name = "Seeded"

    seeded = {
        "current_step": "strategy", "generation_started": True, "generation_started_at": 1.0,
        "results_complete": True, "run_count": 1, "dialogue": dialogue,
        "risk_register": _RISK, "risk_sources": [], "risk_path": None,
        "effort_report": "# Effort", "effort_path": None, "effort_data": effort,
        "strategy": "# Strategy", "sources": [], "output_path": None,
        "test_plan": "# Plan", "test_plan_path": None, "test_plan_sources": [],
        "risk_pdf_bytes": b"%PDF", "effort_pdf_bytes": b"%PDF",
        "strategy_pdf_bytes": b"%PDF", "test_plan_pdf_bytes": b"%PDF",
    }
    for key, value in seeded.items():
        test.session_state[key] = value
    return test.run()


def _html_blobs(at) -> str:
    parts = [md.value for md in at.main.markdown]
    parts += [getattr(e.proto, "body", "") for e in at.main if type(e).__name__ in ("Html", "UnknownElement")]
    return "\n".join(parts)


def test_results_screen_renders_without_exception(at):
    assert not at.exception, at.exception


def test_results_screen_shows_readout_tiles_and_address_first(at):
    html = _html_blobs(at)
    assert 'class="mission-readout"' in html
    assert "Expected QA effort" in html and "Deficit" in html
    assert "Address first" in html


def test_detailed_readout_sits_behind_an_expander(at):
    labels = [e.label for e in at.main.expander]
    assert "How these numbers are computed" in labels


def test_risk_register_tab_shows_the_risk_map(at):
    html = _html_blobs(at)
    assert 'class="risk-map"' in html
    assert html.count('class="rm-cell') == 9


def test_finished_timeline_has_no_running_clock(at):
    html = _html_blobs(at)
    assert 'class="stage-sequence"' in html
    assert 'class="mc-clock"' not in html
    assert html.count('class="stage-item done"') == 4
