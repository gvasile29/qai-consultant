"""
QAI Consultant -- reusable Streamlit HTML/CSS components.

Consolidates four previously separate modules (ledger_components.py,
landing_hero.py, interactive_flow_style.py, output_screen_style.py) that
were split by which "Power-On Sequence" redesign PR touched them, not by
functional boundary -- see
docs/superpowers/plans/2026-09-17-architecture-cleanup.md. All functions
are pure (a token dict plus plain arguments -> an HTML string); callers
render the result via st.markdown(html, unsafe_allow_html=True). No
Streamlit dependency in this module itself, so every function here is
directly unit-testable without a Streamlit runtime -- see
tests/test_components.py.

All user-supplied text (labels, descriptions, project-context field
values) is HTML-escaped via html.escape() before interpolation -- this
renders LLM-generated and user-uploaded content, so unescaped
interpolation would be a stored-XSS path via unsafe_allow_html=True.

theme.py is NOT modified by anything here and stays a separate file (it
owns tokens + base CSS, including the shared .ledger-card base rule);
functions below only ever add scoped CSS additions (e.g.
.ledger-card:hover) that compose safely with theme.py's rules regardless
of <style> tag load order.
"""
import html as _html

from risk_ledger import severity_tier


# ── Ledger: score/severity HTML (Signal Ledger, Risk Ledger table) ─────────

def score_tier(score: int) -> str:
    """Map a 0-100 score to a Signal Ledger tier. >=80 pass, 50-79 hold,
    <50 fail -- the same thresholds used app-wide."""
    if score >= 80:
        return "pass"
    if score >= 50:
        return "hold"
    return "fail"


def signal_ledger_html(label: str, score: int, sub: str = "", tier: str | None = None) -> str:
    """A compact score readout: an uppercase mono label, a large tabular
    score, an optional sub-line, and a 10-segment meter. `tier` overrides
    the auto-computed pass/hold/fail class when the caller's score isn't a
    "higher is better toward 100" quality score (e.g. it's fine to leave
    unset for Review/Results scores, and explicit for anything where the
    caller has better domain judgment than the generic 80/50 split)."""
    resolved_tier = tier or score_tier(score)
    filled = max(0, min(10, round(score / 10)))
    meter = "".join(
        f'<i class="on {resolved_tier}"></i>' if i < filled else "<i></i>"
        for i in range(10)
    )
    sub_html = f'<div class="sl-sub">{_html.escape(sub)}</div>' if sub else ""
    return (
        '<div class="signal-ledger">'
        f'<div class="sl-label">{_html.escape(label)}</div>'
        f'<div class="sl-score {resolved_tier}">{score}</div>'
        f"{sub_html}"
        f'<div class="sl-meter">{meter}</div>'
        "</div>"
    )


def risk_ledger_table_html(rows: list) -> str:
    """Render parsed Risk Matrix rows (risk_ledger.parse_risk_matrix()'s
    output shape) as a <table class="risk-ledger">. Empty input returns ""
    so callers can `if html: st.markdown(html, ...)` without a blank
    table appearing."""
    if not rows:
        return ""

    body_rows = []
    for row in rows:
        tier = severity_tier(row.get("risk_level", ""))
        body_rows.append(
            "<tr>"
            f'<td class="rid">{_html.escape(row.get("risk_id", ""))}</td>'
            f'<td><span class="sev {tier}">{_html.escape(row.get("risk_level", ""))}</span></td>'
            f'<td>{_html.escape(row.get("description", ""))}</td>'
            f'<td>{_html.escape(row.get("likelihood", ""))}</td>'
            f'<td>{_html.escape(row.get("impact", ""))}</td>'
            f'<td class="rid">{_html.escape(row.get("priority", ""))}</td>'
            "</tr>"
        )

    return (
        '<table class="risk-ledger">'
        "<thead><tr>"
        "<th>ID</th><th>Severity</th><th>Risk</th>"
        "<th>Likelihood</th><th>Impact</th><th>Priority</th>"
        "</tr></thead>"
        f"<tbody>{''.join(body_rows)}</tbody>"
        "</table>"
    )
