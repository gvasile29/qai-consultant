"""Tests for src/qai_consultant/ui/landing.py -- the landing page component.

build_mission_landing_html() is pure, so these run without a Streamlit
runtime. What a visitor does with the page (buttons, carousel, scrolling) is
checked in a browser by scripts/verify_landing_visual.py: AppTest cannot
click inside a st.components.v2 component.
"""
import ast
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from qai_consultant.compliance.ai_disclosure import AI_INTERACTION_NOTICE_SHORT
from qai_consultant.ui import landing
from qai_consultant.ui.components import APP_MODES, GENERATION_TIME_ESTIMATE_LONG
from qai_consultant.ui.landing import (
    COMPONENT_KEY,
    build_landing_frame_css,
    build_mission_landing_html,
    landing_target,
)

SERVER_PY = Path(__file__).resolve().parents[3] / "src" / "qai_consultant" / "mcp" / "server.py"
from qai_consultant.ui.theme import DARK_TOKENS, LIGHT_TOKENS

MODE_IDS = [mode_id for mode_id, _idx, _label in APP_MODES]
THEMES = [(DARK_TOKENS, True), (LIGHT_TOKENS, False)]


def _html(dark=True, version="3.9.3"):
    return build_mission_landing_html(DARK_TOKENS if dark else LIGHT_TOKENS, dark=dark, version=version)


@pytest.mark.parametrize("mode_id", MODE_IDS)
def test_landing_target_lets_every_mode_through(mode_id):
    assert landing_target(mode_id) == mode_id


@pytest.mark.parametrize("value", [None, "", "intro", "strategy ", "../dialogue", "results", 3, [], {}, ["strategy"]])
def test_landing_target_drops_anything_else(value):
    # The value comes from the browser; _go_to() would otherwise set
    # current_step to it and main() would dispatch to no screen at all.
    assert landing_target(value) is None


@pytest.mark.parametrize("tokens, dark", THEMES)
def test_every_data_go_value_is_a_known_mode_and_every_mode_has_a_button(tokens, dark):
    html = build_mission_landing_html(tokens, dark=dark, version="3.9.3")
    targets = re.findall(r'data-go="([^"]*)"', html)
    assert set(targets) == set(MODE_IDS)
    # nav link + mission row each, plus the hero's primary CTA for strategy
    assert targets.count("strategy") == 3
    assert targets.count("doc_review") == 2 and targets.count("maturity") == 2


def test_hero_copy_is_the_approved_headline_and_time_claim():
    html = _html()
    assert "<h1>Clear your release for launch.</h1>" in html
    assert "grounded in ISTQB, OWASP and ISO" in html
    assert f"get four documents in {GENERATION_TIME_ESTIMATE_LONG}." in html


def test_carousel_has_one_card_per_document_and_labelled_arrows():
    html = _html()
    for title in ("Risk Register", "Effort Estimation", "Test Strategy", "Test Plan"):
        assert f"<h3>{title}</h3>" in html
    assert html.count('class="ql-card"') == 4
    assert 'aria-label="Previous document"' in html and 'aria-label="Next document"' in html
    assert "01 / 04" in html


def test_every_control_is_a_real_button_or_link():
    # Keyboard users reach buttons and links with Tab; a clickable div is skipped.
    html = _html()
    assert not re.search(r"<(div|span|section|article)[^>]*\sdata-(go|scroll|dir)=", html)
    assert all(tag.startswith('<button type="button"') for tag in re.findall(r"<button[^>]*>", html))


def test_see_example_output_scrolls_to_the_native_details_section():
    html = _html()
    assert 'data-scroll=".st-key-landing-details"' in html
    assert 'data-scroll="#ql-ground"' in html and 'id="ql-ground"' in html


@pytest.mark.parametrize("tokens, dark", THEMES)
def test_uses_the_given_theme_tokens(tokens, dark):
    html = build_mission_landing_html(tokens, dark=dark, version="3.9.3")
    other = LIGHT_TOKENS if dark else DARK_TOKENS
    assert f"background: {tokens['page']}" in html
    assert tokens["accent"] in html
    assert other["accent"] not in html


@pytest.mark.parametrize("dark, pixel", [(True, "#2DD4BF"), (False, "#14B8A6")])
def test_logo_defect_pixel_keeps_its_brand_color(dark, pixel):
    html = _html(dark=dark)
    logo = html[html.index('aria-label="QAI Consultant logo"'):]
    logo = logo[:logo.index("</svg>")]
    assert f'<rect x="60" y="60" width="12" height="12" rx="3" fill="{pixel}"/>' in logo


def test_reduced_motion_turns_animations_off():
    html = _html()
    block = html[html.index("@media (prefers-reduced-motion: reduce)"):]
    assert "animation: none !important" in block and "transition: none !important" in block


def test_version_is_escaped():
    assert "v&lt;b&gt;1&lt;/b&gt;" in _html(version="<b>1</b>")


def test_hero_carries_the_short_ai_notice_before_the_first_screen_ends():
    # Article 50(1): the sidebar with the full notice starts closed on a
    # phone, so the short form sits in the hero, right after the buttons.
    html = _html()
    hero = html[html.index('<section class="ql-hero"'):html.index("</section>")]
    assert AI_INTERACTION_NOTICE_SHORT in hero
    assert hero.index(AI_INTERACTION_NOTICE_SHORT) > hero.index('class="ql-cta" data-go="strategy"')


def _registered_mcp_tools() -> set[str]:
    # Read the server by AST: importing it would pull the MCP SDK into a UI test.
    tree = ast.parse(SERVER_PY.read_text(encoding="utf-8"))
    return {
        node.name for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
        and any(isinstance(d, ast.Call) and getattr(d.func, "attr", "") == "tool" for d in node.decorator_list)
    }


def test_mcp_tool_list_matches_the_server():
    assert set(landing._MCP_TOOLS) == _registered_mcp_tools()
    assert len(landing._MCP_TOOLS) == len(set(landing._MCP_TOOLS))


def test_mcp_block_shows_a_real_setup_command_and_the_telemetry_default():
    html = _html()
    assert "claude mcp add qai-consultant -- uvx qai-consultant-mcp" in html
    assert "telemetry is on by default" in html and "QAI_TELEMETRY=0" in html
    assert landing.MCP_GUIDE_URL in html


@pytest.mark.parametrize("sent, expected", [("doc_review", "doc_review"), ("maturity", "maturity"), ("nope", None), (None, None)])
def test_render_mission_landing_returns_only_a_known_mode(monkeypatch, sent, expected):
    calls = {}

    def fake_component(**kwargs):
        calls.update(kwargs)
        return SimpleNamespace(go=sent)

    monkeypatch.setattr(landing, "_component", lambda: fake_component)
    assert landing.render_mission_landing(LIGHT_TOKENS, dark=False, version="1") == expected
    assert calls["key"] == COMPONENT_KEY and "on_go_change" in calls


def test_no_em_dash_in_visible_copy():
    for tokens, dark in THEMES:
        assert "—" not in build_mission_landing_html(tokens, dark=dark, version="3.9.3")


def test_frame_css_only_applies_while_the_landing_component_is_on_the_page():
    css = build_landing_frame_css(DARK_TOKENS)
    assert f':has(.st-key-{COMPONENT_KEY})' in css
    assert ".st-key-landing-more" in css


def test_button_reset_cannot_override_the_cta_label_color():
    # A plain ".ql button { color: inherit }" outranks ".ql-cta { color: page }"
    # and put an ink label on the accent fill (seen in the browser, both themes).
    html = _html()
    assert ":where(.ql button) { font: inherit; color: inherit; }" in html
    assert not re.search(r"^\.ql button\s*\{", html, re.M)
    cta = re.search(r"^\.ql-cta \{[^}]*\}", html, re.M).group(0)
    assert f"color: {DARK_TOKENS['page']}" in cta and f"background: {DARK_TOKENS['accent']}" in cta

