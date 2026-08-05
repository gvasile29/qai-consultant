"""
QAI Consultant -- Signal Ledger / Risk Ledger HTML builders.

Builds the HTML strings for the Calibration Bench's signature reusable
device (a heat-tier score/severity readout) and the Risk Register table.
Callers pass the result to st.markdown(html, unsafe_allow_html=True) --
this module has no Streamlit dependency itself, so it's directly
unit-testable (see tests/test_ledger_components.py).

All user-supplied text (labels, descriptions) is HTML-escaped -- this
renders LLM-generated and user-uploaded content, so unescaped interpolation
would be a stored-XSS path via unsafe_allow_html=True.
"""
import html as _html

from risk_ledger import severity_tier


def score_tier(score: int) -> str:
    """Map a 0-100 score to a Signal Ledger tier. >=80 pass, 50-79 hold,
    <50 fail -- the same thresholds used app-wide (see this plan's Global
    Constraints)."""
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
