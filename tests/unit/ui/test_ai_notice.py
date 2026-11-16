"""build_ai_notice_html(): the in-page EU AI Act Article 50(1) disclosure block."""
import re

from qai_consultant.compliance.ai_disclosure import AI_INTERACTION_NOTICE
from qai_consultant.ui.components import build_ai_notice_html
from qai_consultant.ui.theme import DARK_TOKENS, LIGHT_TOKENS

ICON = '<img alt="EU AI Act: fully AI-generated content" width="120" src="data:image/svg+xml;base64,AAAA">'


def test_block_carries_the_full_notice_and_the_icon():
    html = build_ai_notice_html(DARK_TOKENS, AI_INTERACTION_NOTICE, ICON)
    assert 'role="note"' in html
    assert ICON in html
    assert "You are interacting with an AI system." in html
    assert "may log it and use it to train their models" in html  # the part the short notice leaves out
    assert "confidential or personal data" in html


def test_bold_markup_becomes_strong_and_no_asterisks_remain():
    html = build_ai_notice_html(LIGHT_TOKENS, AI_INTERACTION_NOTICE, ICON)
    assert "<strong>You are interacting with an AI system.</strong>" in html
    assert "**" not in html


def test_block_is_never_hidden_at_any_width():
    """It used to be display:none from 1024px up, which left a collapsed
    sidebar as the only place the notice lived. Article 50(1) needs it on
    every screen, at every width."""
    html = build_ai_notice_html(DARK_TOKENS, AI_INTERACTION_NOTICE, ICON)
    assert "display: none" not in html and "display:none" not in html
    assert not re.search(r"@media", html)


def test_notice_text_is_html_escaped():
    html = build_ai_notice_html(DARK_TOKENS, "<script>alert(1)</script> **bold**", ICON)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "<strong>bold</strong>" in html


def test_empty_icon_omits_the_icon_container():
    """The landing page shows the icon in its hero, so its full notice has none."""
    html = build_ai_notice_html(DARK_TOKENS, AI_INTERACTION_NOTICE, "")
    assert '<div class="ai-notice-icon">' not in html
    assert "You are interacting with an AI system." in html
