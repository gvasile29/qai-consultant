"""
QAI Consultant -- deterministic Risk Matrix table parser.

risk_analyzer.py's RISK_SYSTEM_PROMPT forces the LLM to emit a "Risk Matrix
Overview" section as a markdown pipe-table with an EXACT, fixed column set
(see build_risk_prompt() in risk_analyzer.py). This module parses that
table back into structured rows so app.py can render it with the Signal
Ledger's heat-swatch treatment instead of raw markdown.

Dependency-free, no LLM call, never raises -- same tier as results_core.py
and review_core.py.
"""
import re

_TABLE_HEADER_RE = re.compile(r"^\|\s*Risk ID\s*\|", re.IGNORECASE | re.MULTILINE)

_SEVERITY_TIERS = {
    "low": "pass",
    "medium": "hold",
    "high": "fail",
    "critical": "fail",
}


def severity_tier(risk_level: str) -> str:
    """Map a Risk Level string (Low/Medium/High/Critical) to a Signal
    Ledger tier (pass/hold/fail). Unrecognized or empty input defaults to
    "hold" rather than raising -- a wrong-but-visible middle tier is safer
    than crashing the whole Risk Register render over one bad LLM token."""
    return _SEVERITY_TIERS.get((risk_level or "").strip().lower(), "hold")


def parse_risk_matrix(markdown_text: str) -> list:
    """Extract the "Risk Matrix Overview" pipe-table into a list of dicts
    with keys: risk_id, description, likelihood, impact, risk_level,
    priority. Returns [] if no matching table is found or the input is
    malformed -- never raises."""
    if not markdown_text:
        return []

    match = _TABLE_HEADER_RE.search(markdown_text)
    if not match:
        return []

    lines = markdown_text[match.start():].splitlines()
    rows = []
    for line in lines[2:]:  # skip the header row and the |---|---| separator
        stripped = line.strip()
        if not stripped.startswith("|"):
            break  # table ended
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if len(cells) != 6:
            continue  # ragged row -- skip rather than guess
        risk_id, description, likelihood, impact, risk_level, priority = cells
        if not risk_id or set(risk_id) == {"-"}:
            continue  # stray separator-like row
        rows.append({
            "risk_id": risk_id,
            "description": description,
            "likelihood": likelihood,
            "impact": impact,
            "risk_level": risk_level,
            "priority": priority,
        })
    return rows
