"""Tests for src/components.py -- Signal Ledger / Risk Ledger HTML builders
(Ledger section) and Landing hero + "What you get" (Landing section).

These build HTML strings only (no Streamlit runtime needed to test them --
st.markdown() is the caller's job, not this module's).
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from components import (  # noqa: E402
    build_landing_deliverables_html,
    build_landing_hero_html,
    risk_ledger_table_html,
    score_tier,
    signal_ledger_html,
)
from theme import DARK_TOKENS, LIGHT_TOKENS  # noqa: E402

SAMPLE_ROWS = [
    {"risk_id": "R01", "description": "Auth token expiry untested", "likelihood": "High",
     "impact": "High", "risk_level": "Critical", "priority": "1"},
    {"risk_id": "R02", "description": "No load test above 200 rps", "likelihood": "Medium",
     "impact": "Medium", "risk_level": "Medium", "priority": "2"},
]


def test_score_tier_boundaries():
    assert score_tier(100) == "pass"
    assert score_tier(80) == "pass"
    assert score_tier(79) == "hold"
    assert score_tier(50) == "hold"
    assert score_tier(49) == "fail"
    assert score_tier(0) == "fail"


def test_signal_ledger_html_contains_label_and_score():
    html = signal_ledger_html("Confidence", 72, sub="cited from 6 sources")
    assert "Confidence" in html
    assert "72" in html
    assert "cited from 6 sources" in html
    assert 'class="signal-ledger"' in html


def test_signal_ledger_html_uses_computed_tier_class():
    html = signal_ledger_html("Overall Score", 84)
    assert "sl-score pass" in html
    html = signal_ledger_html("Overall Score", 61)
    assert "sl-score hold" in html
    html = signal_ledger_html("Overall Score", 30)
    assert "sl-score fail" in html


def test_signal_ledger_html_accepts_explicit_tier_override():
    # e.g. effort confidence is a "how sure are we" score, not a "how good
    # is this" score -- callers may want to force the tier explicitly.
    html = signal_ledger_html("Confidence", 90, tier="hold")
    assert "sl-score hold" in html


def test_signal_ledger_html_escapes_label_and_sub_text():
    html = signal_ledger_html("<script>alert(1)</script>", 50, sub="<b>x</b>")
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_risk_ledger_table_html_renders_all_rows():
    html = risk_ledger_table_html(SAMPLE_ROWS)
    # 1 header <tr> (inside <thead>) + 1 per data row (2 rows here) = 3.
    assert html.count("<tr>") == 3
    assert "R01" in html and "R02" in html
    assert "Auth token expiry untested" in html


def test_risk_ledger_table_html_uses_severity_tier_classes():
    html = risk_ledger_table_html(SAMPLE_ROWS)
    assert 'class="sev fail"' in html   # Critical -> fail
    assert 'class="sev hold"' in html   # Medium -> hold


def test_risk_ledger_table_html_empty_rows_returns_empty_string():
    assert risk_ledger_table_html([]) == ""


def test_risk_ledger_table_html_escapes_description():
    rows = [{"risk_id": "R01", "description": "<img src=x onerror=alert(1)>",
              "likelihood": "Low", "impact": "Low", "risk_level": "Low", "priority": "1"}]
    html = risk_ledger_table_html(rows)
    assert "<img" not in html
    assert "&lt;img" in html


# ── Landing ─────────────────────────────────────────────────────────────


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


def test_build_landing_deliverables_html_uses_the_given_tokens_not_a_hardcoded_theme():
    light_html = build_landing_deliverables_html(LIGHT_TOKENS)
    dark_html = build_landing_deliverables_html(DARK_TOKENS)
    assert LIGHT_TOKENS["ink"] in light_html
    assert DARK_TOKENS["ink"] not in light_html
    assert DARK_TOKENS["ink"] in dark_html
    assert LIGHT_TOKENS["ink"] not in dark_html


def test_build_landing_deliverables_html_contains_all_four_deliverable_titles():
    html = build_landing_deliverables_html(LIGHT_TOKENS)
    for title in ["Risk Register", "Effort Estimation", "Test Strategy", "Test Plan"]:
        assert title in html


def test_build_landing_deliverables_html_contains_all_four_stat_labels():
    html = build_landing_deliverables_html(LIGHT_TOKENS)
    for label in ["Time to results", "Standards", "Deliverables", "Cost"]:
        assert label in html


def test_build_landing_deliverables_html_has_a_pom_readout_eyebrow_label():
    # Regression guard: this section was the landing screen's only
    # unlabeled content block after dropping the pre-existing "What you
    # get in ~2 minutes" markdown heading. Must reuse the .pom-readout
    # class build_landing_hero_html() already defines, not a new one.
    html = build_landing_deliverables_html(LIGHT_TOKENS)
    assert '<div class="pom-readout">&gt; what you get in ~2 minutes</div>' in html


def test_build_landing_deliverables_html_does_not_redefine_the_pom_card_in_keyframe():
    # Regression guard: must reuse the pom-card-in keyframe from
    # build_landing_hero_html() (concatenated into the same document) rather
    # than redefining it -- a silent duplicate would be easy to miss since
    # CSS allows redeclaring the same @keyframes name without error.
    html = build_landing_deliverables_html(LIGHT_TOKENS)
    assert "@keyframes pom-card-in" not in html


def test_build_landing_deliverables_html_delay_rules_are_scoped_under_pom_deliverables():
    # Regression guard: nth-child delay overrides must be scoped under
    # .pom-deliverables, never a bare ".pom-card:nth-child(...)" rule, which
    # would also match (and fight with) the "How it works" cards' own delay
    # rules defined in build_landing_hero_html().
    html = build_landing_deliverables_html(LIGHT_TOKENS)
    for line in html.splitlines():
        if ".pom-card:nth-child" in line:
            assert ".pom-deliverables" in line, \
                f"Found a bare (unscoped) .pom-card:nth-child rule: {line!r}"


def test_build_landing_deliverables_html_zeroes_animation_delay_for_reduced_motion():
    html = build_landing_deliverables_html(LIGHT_TOKENS)
    assert "@media (prefers-reduced-motion: reduce)" in html
    assert "animation-delay: 0s !important" in html
