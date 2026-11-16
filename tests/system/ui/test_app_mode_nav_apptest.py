"""
Behavioral tests for what surrounds the mode switcher, driving the real app with
Streamlit's AppTest (agent load, visit counter and adoption fetch stubbed,
nothing else): the landing page, the reduced sidebar, and the EU AI Act
Article 50(1) notice that now sits in the page on every screen. The chips
themselves are covered in test_page_nav_apptest.py.
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


def _notice_blocks(at):
    return [md.value for md in at.main.markdown if 'class="ai-notice"' in md.value]


def test_landing_renders_the_component(at):
    # AppTest sees the landing component as an UnknownElement;
    # scripts/verify_landing_visual.py clicks it in a browser.
    assert not at.exception
    names = [getattr(e.proto, "component_name", "") for e in at.main if type(e).__name__ == "UnknownElement"]
    assert any(name.endswith("qai_mission_landing") for name in names), names


def test_landing_main_column_has_no_info_banner(at):
    # The component carries the version, the MCP section and the short AI notice.
    assert len(at.main.info) == 0


def test_sidebar_is_a_drawer_with_no_mode_switcher(at):
    """The three modes live in the page (render_page_nav); the sidebar keeps release
    notes, MCP, the knowledge base and Start Over."""
    for mode_id in ("strategy", "doc_review", "maturity"):
        _open(at, mode_id)
        assert not [b.key for b in at.sidebar.button if str(b.key).startswith("nav-")], mode_id
    labels = " ".join(b.label for b in at.sidebar.button)
    assert "Start Over" in labels
    assert not at.sidebar.info, "the full AI notice moved out of the sidebar into the page"


@pytest.mark.parametrize("mode_id", ["strategy", "doc_review", "maturity"])
def test_every_mode_screen_shows_the_full_ai_notice_and_icon(at, mode_id):
    """Article 50(1): the whole notice (not the short one) and the EU icon, in the
    main column of every screen, not only in a sidebar that can be closed."""
    _open(at, mode_id)
    blocks = _notice_blocks(at)
    assert len(blocks) == 1, blocks
    block = blocks[0]
    assert "<strong>You are interacting with an AI system.</strong>" in block
    assert "may log it and use it to train their models" in block
    assert "data:image/svg+xml;base64," in block


def test_landing_page_shows_the_full_notice_text(at):
    """The icon is in the landing hero (a component AppTest cannot see; the visual
    script checks it), so the full block below carries the text only."""
    blocks = _notice_blocks(at)
    assert len(blocks) == 1, blocks
    assert "may log it and use it to train their models" in blocks[0]


def test_agent_load_failure_screen_still_shows_the_ai_notice(tmp_path, monkeypatch):
    """Article 50(1) needs no agent: a missing key or a Pinecone outage must not
    leave the visitor on an error screen with no AI disclosure."""
    monkeypatch.chdir(REPO_ROOT)
    script = tmp_path / "app_agent_error.py"
    script.write_text(_SCRIPT.replace("(object(), None)", '(None, "Simulated agent load failure")'), encoding="utf-8")
    failed = AppTest.from_file(str(script), default_timeout=60).run()
    assert failed.error, "the error screen should render"
    blocks = _notice_blocks(failed)
    assert len(blocks) == 1 and "data:image/svg+xml;base64," in blocks[0], blocks


def _sidebar_home(at):
    return [b for b in at.sidebar.button if b.key == "sidebar-home"]


def test_landing_page_has_no_sidebar_home_button(at):
    assert not _sidebar_home(at)


@pytest.mark.parametrize("mode_id", ["strategy", "doc_review", "maturity"])
def test_sidebar_home_returns_to_the_landing_page(at, mode_id):
    _open(at, mode_id)
    (home,) = _sidebar_home(at)
    assert not home.disabled
    home.click().run()
    assert not at.exception
    assert at.session_state["current_step"] == "intro"
    assert not _sidebar_home(at)


def test_sidebar_home_keeps_unblurred_dialogue_text(at):
    _open(at, "strategy")
    at.text_input(key="input_project_name").input("Orbit")  # no .run(): the click's run carries it
    _sidebar_home(at)[0].click().run()
    assert at.session_state["answers"]["project_name"] == "Orbit"


def test_sidebar_home_locks_while_a_generation_runs(at):
    _open(at, "doc_review")
    at.session_state["review_narrative_pending"] = True
    at.session_state["run_count"] = 99  # renderer then shows the run-cap warning, no LLM call
    at.run()
    assert _sidebar_home(at)[0].disabled
