"""Tests for src/landing_hero.py -- the "Power-On Sequence" landing hero
(Phase 1 of the 2026-08-06 redesign, see
docs/superpowers/specs/2026-08-06-landing-power-on-redesign-design.md)."""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from theme import LIGHT_TOKENS, DARK_TOKENS  # noqa: E402
from landing_hero import build_landing_hero_html  # noqa: E402


def test_build_landing_hero_html_uses_the_given_tokens_not_a_hardcoded_theme():
    light_html = build_landing_hero_html(LIGHT_TOKENS)
    dark_html = build_landing_hero_html(DARK_TOKENS)
    assert LIGHT_TOKENS["ink"] in light_html
    assert DARK_TOKENS["ink"] not in light_html
    assert DARK_TOKENS["ink"] in dark_html
    assert LIGHT_TOKENS["ink"] not in dark_html


def test_build_landing_hero_html_defines_all_keyframes():
    html = build_landing_hero_html(LIGHT_TOKENS)
    for name in [
        "pom-reveal", "pom-fill-risk", "pom-fill-effort",
        "pom-fill-strategy", "pom-tick", "pom-card-in",
    ]:
        assert f"@keyframes {name}" in html


def test_build_landing_hero_html_does_not_reuse_ledger_card_class():
    # Regression guard for the design-spec correction: .ledger-card belongs
    # to the Phase-2 dialogue screen and has no :hover rule to inherit --
    # this phase must define its own class, never touch .ledger-card.
    html = build_landing_hero_html(LIGHT_TOKENS)
    assert "ledger-card" not in html
    assert ".pom-card:hover" in html


def test_build_landing_hero_html_contains_the_standards_row():
    html = build_landing_hero_html(LIGHT_TOKENS)
    for standard in ["ISTQB", "OWASP", "IEEE 829", "ISO 25010"]:
        assert standard in html


def test_build_landing_hero_html_contains_how_it_works_copy():
    html = build_landing_hero_html(LIGHT_TOKENS)
    assert "Answer a few questions" in html
    assert "AI analyzes" in html
    assert "Download your strategy" in html


def test_build_landing_hero_html_zeroes_animation_delays_for_reduced_motion():
    # theme.py's global prefers-reduced-motion rule only zeroes
    # animation-duration/transition-duration -- it never touches
    # animation-delay, so delayed "pom-" elements (staggered standards
    # badges, cards) would sit at their opacity:0 "from" state for the
    # full original delay before snapping in. This module defines its own
    # scoped prefers-reduced-motion block to zero those delays -- don't
    # let it be deleted as "redundant" with theme.py's rule, they cover
    # different CSS properties.
    html = build_landing_hero_html(LIGHT_TOKENS)
    assert "@media (prefers-reduced-motion: reduce)" in html
    assert "animation-delay: 0s !important" in html


def test_build_landing_hero_html_relies_on_theme_global_rule_for_duration():
    # This module still relies on theme.py's existing global
    # prefers-reduced-motion rule (build_css()) to zero out
    # animation-duration/transition-duration -- confirm that global rule
    # still exists so this reliance stays valid.
    from theme import build_css
    assert "prefers-reduced-motion" in build_css(LIGHT_TOKENS)
