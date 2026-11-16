"""
Behavioral tests for the in-page mode switcher (render_page_nav), the only mode
switcher now that the sidebar is a drawer. Same AppTest harness as
test_app_mode_nav_apptest.py (agent load, visit counter and adoption fetch
stubbed, nothing else).
"""
import sys
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

MODES = ("strategy", "doc_review", "maturity")
CHIPS = ("home",) + MODES  # the Home chip leads the row
_STEP_FOR_MODE = {"strategy": "dialogue", "doc_review": "doc_review", "maturity": "maturity"}


@pytest.fixture
def at(tmp_path, monkeypatch):
    monkeypatch.chdir(REPO_ROOT)
    script = tmp_path / "app_under_test.py"
    script.write_text(_SCRIPT, encoding="utf-8")
    return AppTest.from_file(str(script), default_timeout=60).run()


def _open(at, mode_id):
    """AppTest cannot click inside the landing component, so enter a mode by state."""
    at.session_state["current_step"] = _STEP_FOR_MODE[mode_id]
    return at.run()


def _page(at, mode_id):
    return at.button(key=f"pagenav-{mode_id}")


def _has_page_nav(at) -> bool:
    return any(b.key == "pagenav-strategy" for b in at.button)


def test_landing_has_no_page_nav(at):
    """The landing component carries its own navigation."""
    assert not at.exception
    assert not _has_page_nav(at)


def test_page_nav_switches_mode(at):
    _open(at, "doc_review")
    assert _has_page_nav(at)
    _page(at, "maturity").click().run()
    assert not at.exception
    assert at.session_state["current_step"] == "maturity"


def test_active_mode_is_disabled_in_page_nav(at):
    _open(at, "maturity")
    assert _page(at, "maturity").disabled
    assert not _page(at, "doc_review").disabled
    assert not _page(at, "strategy").disabled


def test_strategy_chip_opens_the_dialogue(at):
    _open(at, "doc_review")
    _page(at, "strategy").click().run()
    assert at.session_state["current_step"] == "dialogue"
    assert _page(at, "strategy").disabled


def test_strategy_resumes_where_it_was_left_via_page_nav(at):
    _open(at, "strategy")
    at.session_state["current_step"] = "review"
    at.run()
    _page(at, "maturity").click().run()
    _page(at, "strategy").click().run()
    assert at.session_state["current_step"] == "review"


def test_pasted_text_survives_a_round_trip_through_page_nav(at):
    _open(at, "doc_review")
    at.text_area(key="review_doc_pasted_text").input("My test plan draft").run()
    _page(at, "maturity").click().run()
    _page(at, "doc_review").click().run()
    assert not at.exception
    assert at.text_area(key="review_doc_pasted_text").value == "My test plan draft"


def test_maturity_text_survives_a_round_trip_through_page_nav(at):
    _open(at, "maturity")
    at.text_area(key="maturity_pasted_text").input("We run regression weekly").run()
    _page(at, "strategy").click().run()
    _page(at, "maturity").click().run()
    assert at.text_area(key="maturity_pasted_text").value == "We run regression weekly"


def test_pending_narrative_locks_page_nav_too(at):
    _open(at, "doc_review")
    at.session_state["review_narrative_pending"] = True
    at.session_state["run_count"] = 99  # renderer then shows the run-cap warning, no LLM call
    at.run()
    assert all(_page(at, m).disabled for m in CHIPS)
    assert any("generation in progress" in md.value for md in at.main.markdown)


def test_page_nav_locks_whenever_a_generation_is_in_progress(tmp_path, monkeypatch):
    """render_page_nav() must follow _generation_in_progress() as a whole (a
    strategy run, a review narrative, a maturity narrative), not one flag of
    it: a click would interrupt a stream after the run was already charged.
    monkeypatch.setattr (not an assignment in the AppTest script) so the shared
    `app` module is restored for every other test."""
    sys.path.insert(0, str(REPO_ROOT / "src"))
    import app

    monkeypatch.setattr(app, "_generation_in_progress", lambda: True)
    monkeypatch.chdir(REPO_ROOT)
    script = tmp_path / "app_locked.py"
    script.write_text(_SCRIPT, encoding="utf-8")
    locked = AppTest.from_file(str(script), default_timeout=60)
    locked.session_state["current_step"] = "doc_review"
    locked.run()
    assert not locked.exception
    assert all(_page(locked, m).disabled for m in CHIPS)


def test_unblurred_dialogue_text_survives_a_click_on_page_nav(at):
    """A value typed and then a chip clicked with no blur arrives in the click's
    own run; without committing the phase's widgets first, it is lost."""
    _open(at, "strategy")
    assert at.session_state["current_step"] == "dialogue"
    at.text_input(key="input_project_name").input("Orbit")  # no .run(): the click's run carries it
    _page(at, "maturity").click().run()
    assert at.session_state["current_step"] == "maturity"
    _page(at, "strategy").click().run()
    assert not at.exception
    assert at.text_input(key="input_project_name").value == "Orbit"


@pytest.mark.parametrize("mode_id", MODES)
def test_every_mode_screen_has_an_enabled_home_chip_first(at, mode_id):
    _open(at, mode_id)
    chips = [b.key for b in at.button if str(b.key).startswith("pagenav-")]
    assert chips[0] == "pagenav-home", chips
    assert not _page(at, "home").disabled


def test_home_chip_returns_to_the_landing_page(at):
    _open(at, "doc_review")
    _page(at, "home").click().run()
    assert not at.exception
    assert at.session_state["current_step"] == "intro"
    assert not _has_page_nav(at), "the landing page has its own navigation"
    names = [getattr(e.proto, "component_name", "") for e in at.main if type(e).__name__ == "UnknownElement"]
    assert any(name.endswith("qai_mission_landing") for name in names), names


def test_home_keeps_the_strategy_step_to_resume_at(at):
    _open(at, "strategy")
    at.session_state["current_step"] = "review"
    at.run()
    _page(at, "home").click().run()
    assert at.session_state["strategy_resume_step"] == "review"


def test_home_keeps_unblurred_dialogue_text(at):
    """Going Home must not cost what was typed: the click's run carries the value,
    and _go_to() commits it before the dialogue stops rendering."""
    _open(at, "strategy")
    at.text_input(key="input_project_name").input("Orbit")  # no .run()
    _page(at, "home").click().run()
    assert at.session_state["current_step"] == "intro"
    assert at.session_state["answers"]["project_name"] == "Orbit"


def test_home_keeps_pasted_text_of_a_mode(at):
    _open(at, "doc_review")
    at.text_area(key="review_doc_pasted_text").input("My test plan draft").run()
    _page(at, "home").click().run()
    _open(at, "doc_review")
    assert at.text_area(key="review_doc_pasted_text").value == "My test plan draft"
