"""
QAI Consultant -- Executive Readout (deterministic, no LLM call).

A one-screen "so what?" shown above the four output tabs (external audit,
2026-09-23, docs/audits/): overall risk, QA effort range, team capacity,
confidence, and the top-priority risks to address first. Built only from
the parsed Risk Matrix (risk_ledger.parse_risk_matrix()) and the
deterministic EstimationData (effort_core) -- it never invents actions or
numbers the underlying documents don't already contain.

Dependency-free, never raises -- same tier as risk_ledger.py.
"""
import re
from dataclasses import dataclass, field
from typing import Optional

_LEVEL_ORDER = ["critical", "high", "medium", "low"]


@dataclass
class ExecutiveReadout:
    overall_risk: str = ""            # "Critical" | "High" | "Medium" | "Low" | ""
    risk_breakdown: str = ""          # e.g. "1 Critical · 2 High · 1 Medium"
    effort_range: str = ""            # e.g. "42–51 person-days"
    capacity: str = ""                # e.g. "36 person-days available — 9 short of expected effort"
    capacity_deficit: bool = False
    confidence: str = ""              # e.g. "Medium (59/100)"
    address_first: list = field(default_factory=list)  # [(risk_id, description), ...]


def _level_key(risk_level: str) -> Optional[str]:
    level = (risk_level or "").lower()
    for key in _LEVEL_ORDER:
        if key in level:
            return key
    return None


def _priority_sort_key(row: dict):
    match = re.search(r"\d+", row.get("priority", "") or "")
    return int(match.group()) if match else 10_000


def _fmt_days(value: float) -> str:
    return f"{value:g}"


def build_readout(risk_rows: list, effort_data) -> Optional[ExecutiveReadout]:
    """Returns None when there is nothing to summarize (no parsed risks and
    no effort data), so the caller can skip rendering entirely."""
    if not risk_rows and effort_data is None:
        return None

    readout = ExecutiveReadout()

    if risk_rows:
        counts = {key: 0 for key in _LEVEL_ORDER}
        for row in risk_rows:
            key = _level_key(row.get("risk_level", ""))
            if key:
                counts[key] += 1
        present = [key for key in _LEVEL_ORDER if counts[key]]
        if present:
            readout.overall_risk = present[0].title()
            readout.risk_breakdown = " · ".join(f"{counts[k]} {k.title()}" for k in present)
        top = sorted(risk_rows, key=_priority_sort_key)[:3]
        readout.address_first = [(r.get("risk_id", ""), r.get("description", "")) for r in top]

    if effort_data is not None:
        readout.effort_range = (
            f"{_fmt_days(effort_data.final_effort_min)}–{_fmt_days(effort_data.final_effort_max)} person-days"
        )
        available = _fmt_days(round(effort_data.available_person_days, 1))
        gap = round(effort_data.capacity_gap, 1)
        if gap < 0:
            readout.capacity = f"{available} person-days available — {_fmt_days(-gap)} short of expected effort"
            readout.capacity_deficit = True
        else:
            readout.capacity = f"{available} person-days available — {_fmt_days(gap)} above expected effort"
        readout.confidence = f"{effort_data.confidence_level} ({effort_data.confidence_score}/100)"

    return readout
