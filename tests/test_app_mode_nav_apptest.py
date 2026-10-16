"""
Behavioral tests for the sidebar mode switcher, driving the real app with
Streamlit's AppTest (agent load, visit counter and adoption fetch stubbed,
nothing else). Complements tests/test_app_mode_nav.py's unit checks: these
render the sidebar and widgets for real, so they catch Streamlit dropping
an unrendered widget's key on a mode round trip, and a lock that never
renders.
"""
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"

pytest.importorskip("streamlit.testing.v1")
from streamlit.testing.v1 import AppTest  # noqa: E402

_SCRIPT = f"""
import sys
sys.path.insert(0, {str(SRC_DIR)!r})
import app
app.load_agent = lambda: (object(), None)
app.get_and_increment_visit_count = lambda: 1
app._adoption_snapshot = lambda: {{}}
app.main()
"""


@pytest.fixture
def at(tmp_path, monkeypatch):
    monkeypatch.chdir(REPO_ROOT)
    script = tmp_path / "app_under_test.py"
    script.write_text(_SCRIPT, encoding="utf-8")
    return AppTest.from_file(str(script), default_timeout=60).run()


def _nav(at, mode_id):
    return at.button(key=f"nav-{mode_id}")


def test_landing_renders_all_mode_buttons_enabled(at):
    assert not at.exception
    for mode_id in ("strategy", "doc_review", "maturity"):
        assert not _nav(at, mode_id).disabled
        assert at.button(key=f"cta-{mode_id}") is not None


def test_active_mode_is_disabled_in_sidebar(at):
    _nav(at, "maturity").click().run()
    assert at.session_state["current_step"] == "maturity"
    assert _nav(at, "maturity").disabled
    assert not _nav(at, "doc_review").disabled


def test_pasted_review_text_survives_a_mode_round_trip(at):
    _nav(at, "doc_review").click().run()
    at.text_area(key="review_doc_pasted_text").input("My test plan draft").run()
    _nav(at, "maturity").click().run()
    _nav(at, "doc_review").click().run()
    assert not at.exception
    assert at.text_area(key="review_doc_pasted_text").value == "My test plan draft"


def test_maturity_text_survives_a_mode_round_trip(at):
    _nav(at, "maturity").click().run()
    at.text_area(key="maturity_pasted_text").input("We run regression weekly").run()
    _nav(at, "strategy").click().run()
    _nav(at, "maturity").click().run()
    assert at.text_area(key="maturity_pasted_text").value == "We run regression weekly"


def test_pending_narrative_locks_every_nav_button(at):
    _nav(at, "doc_review").click().run()
    at.session_state["review_narrative_pending"] = True
    at.session_state["run_count"] = 99  # renderer then shows the run-cap warning, no LLM call
    at.run()
    assert all(_nav(at, m).disabled for m in ("strategy", "doc_review", "maturity"))
