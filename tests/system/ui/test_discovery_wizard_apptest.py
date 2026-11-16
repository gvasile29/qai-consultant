"""
Drives the discovery wizard with Streamlit's AppTest (agent load, visit
counter and adoption fetch stubbed): one phase of inputs at a time, Next
validates only that phase, Back keeps what was typed (Streamlit drops an
unrendered widget's key, so the wizard re-seeds it), and the last phase
submits all eleven answers plus the optional context to the review screen.
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

PHASE_KEYS = (
    ("project_name", "project_description", "project_type", "tech_stack"),
    ("team_qa_size", "team_dev_size", "timeline", "methodology"),
    ("known_risks", "existing_automation", "compliance_requirements"),
)


@pytest.fixture
def at(tmp_path, monkeypatch):
    monkeypatch.chdir(REPO_ROOT)
    script = tmp_path / "app_under_test.py"
    script.write_text(_SCRIPT, encoding="utf-8")
    test = AppTest.from_file(str(script), default_timeout=60)
    test.session_state["current_step"] = "dialogue"
    return test.run()


def _click(at, key):
    # Navigation is on_click callbacks, not st.rerun(): an in-script rerun
    # leaves AppTest's tree holding the aborted pass's widgets, which then
    # break the next interaction (KeyError on an input_<key> no longer set).
    return at.button(key=key).click().run()


def _input_keys(at) -> set:
    return {w.key for w in at.main.text_input}


def _apply_web_template(at):
    at.selectbox(key="template_selector").set_value("web_app").run()
    _click(at, "apply_template")


def test_first_phase_shows_only_its_four_inputs(at):
    assert not at.exception
    assert _input_keys(at) == {f"input_{k}" for k in PHASE_KEYS[0]}
    assert at.button(key="discovery_back").disabled


def test_next_with_empty_answers_stays_and_warns(at):
    _click(at, "discovery_next")
    assert _input_keys(at) == {f"input_{k}" for k in PHASE_KEYS[0]}
    assert at.main.warning


def test_back_keeps_answers_typed_in_an_earlier_phase(at):
    _apply_web_template(at)
    at.text_input(key="input_project_name").input("Orbit Tracker").run()
    _click(at, "discovery_next")
    assert _input_keys(at) == {f"input_{k}" for k in PHASE_KEYS[1]}
    _click(at, "discovery_back")
    assert at.text_input(key="input_project_name").value == "Orbit Tracker"


def test_value_typed_and_next_clicked_in_one_run_is_kept(at):
    # A browser sends the typed value with the click when the field was
    # never blurred: one run, in which the callback has already moved on and
    # this phase's widgets do not render. Staging both before run() is that.
    _apply_web_template(at)
    at.text_input(key="input_project_name").input("Orbit Tracker")
    at.button(key="discovery_next").click()
    at.run()
    assert at.session_state["answers"]["project_name"] == "Orbit Tracker"
    _click(at, "discovery_back")
    assert at.text_input(key="input_project_name").value == "Orbit Tracker"


def test_context_typed_and_back_clicked_in_one_run_is_kept(at):
    _apply_web_template(at)
    _click(at, "discovery_next")
    _click(at, "discovery_next")
    at.text_area(key="input_additional_context").input("Legacy SOAP backend")
    at.button(key="discovery_back").click()
    at.run()
    _click(at, "discovery_next")
    assert at.text_area(key="input_additional_context").value == "Legacy SOAP backend"


def test_optional_context_survives_leaving_the_last_phase(at):
    _apply_web_template(at)
    _click(at, "discovery_next")
    _click(at, "discovery_next")
    at.text_area(key="input_additional_context").input("Legacy SOAP backend").run()
    _click(at, "discovery_back")
    _click(at, "discovery_next")
    assert at.text_area(key="input_additional_context").value == "Legacy SOAP backend"


def test_full_wizard_submits_all_answers_to_review(at):
    _apply_web_template(at)
    _click(at, "discovery_next")
    _click(at, "discovery_next")
    assert _input_keys(at) == {f"input_{k}" for k in PHASE_KEYS[2]}
    at.text_area(key="input_additional_context").input("Legacy SOAP backend").run()
    _click(at, "discovery_submit")
    assert not at.exception
    assert at.session_state["current_step"] == "review"
    context = at.session_state["dialogue"].get_context()
    assert context.project_name == "SaaS Web Application"
    assert context.team_qa_size == "2"
    assert context.compliance_requirements
    assert context.additional_context == "Legacy SOAP backend"


def test_start_over_clears_the_wizard_phase(at):
    _apply_web_template(at)
    _click(at, "discovery_next")
    at.sidebar.button[[b.label for b in at.sidebar.button].index("🔄 Start Over")].click().run()
    assert "discovery_phase" not in at.session_state


def test_submit_revalidates_an_earlier_phase(at):
    # A template or an edit can leave phase 1 invalid after its Next passed.
    # Submit must check all eleven answers, not only the last phase's.
    _apply_web_template(at)
    _click(at, "discovery_next")
    _click(at, "discovery_next")
    at.session_state["answers"]["project_name"] = ""
    at.session_state["input_project_name"] = ""
    _click(at, "discovery_submit")
    assert not at.exception
    assert at.session_state["current_step"] == "dialogue"
    assert at.main.warning


def test_next_with_an_invalid_nonempty_value_stays_and_warns(at):
    _apply_web_template(at)
    _click(at, "discovery_next")
    at.text_input(key="input_team_qa_size").input("abc").run()
    _click(at, "discovery_next")
    assert _input_keys(at) == {f"input_{k}" for k in PHASE_KEYS[1]}
    assert at.main.warning
