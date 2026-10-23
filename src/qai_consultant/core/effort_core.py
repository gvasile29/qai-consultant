"""
QAI Consultant — Deterministic Effort Estimation Core.

The PERT/multiplier/confidence calculation pipeline extracted out of
EffortEstimator, with zero agent/LLM dependency in its import graph. This is
what the MCP server's ``estimate_qa_effort`` tool calls directly (v3.0):
the client LLM writes its own narrative from these numbers, so the MCP path
never needs ``agent.py`` (which pulls Pinecone/Mistral/OpenAI/Streamlit).

``EffortEstimator`` (effort_estimator.py) delegates here for the numbers and
adds the LLM narrative on top for the Streamlit/CLI report; tests call these
functions directly.

Calculation pipeline (see compute_estimation()):
  1. Detect project type -> baseline QA % (industry benchmarks)
  2. Calculate baseline effort from team size, duration, baseline %
  3. Apply complexity multipliers (compliance, automation, team size, risk)
  4. PERT analysis across QA activity areas
  5. Team capacity (available person-days at 75% utilization)
  6. Risk buffer from Risk Register (critical/high/medium risk counts)
  7. Data quality score (dialogue completeness, 0-20)
  8. Finalize: final effort range + confidence score (0-100)
"""

import re
from dataclasses import dataclass, field
from typing import Optional

from qai_consultant.core.dialogue import ProjectContext
from qai_consultant.core.risk_ledger import parse_risk_matrix

LOW_DATA_QUALITY_MAX = 8  # data_quality_score (0-20) at or below this caps confidence at Medium

MAX_PLAUSIBLE_DURATION_DAYS = 1825  # ~5 working-years; a parsed timeline beyond this is
                                     # almost certainly a parsing error (e.g. a calendar
                                     # year misread as a month/week count), not a real project

# ── Baseline Benchmarks ────────────────────────────────────────────────────────

BASELINE_QA_PERCENT = {
    # (project_type_keyword, methodology_keyword): (min%, max%)
    ("embedded", "v-model"):        (30, 40),
    ("embedded", "agile"):          (35, 45),
    ("embedded", ""):               (30, 40),
    ("web", "agile"):               (15, 20),
    ("web", "waterfall"):           (25, 30),
    ("web", ""):                    (15, 20),
    ("mobile", "agile"):            (20, 25),
    ("mobile", ""):                 (20, 25),
    ("api", "agile"):               (15, 20),
    ("microservice", "agile"):      (15, 20),
    ("api", ""):                    (15, 20),
    ("desktop", "agile"):           (20, 25),
    ("desktop", ""):                (20, 25),
    ("data", "agile"):              (20, 30),
    ("ml", "agile"):                (20, 30),
    ("default", ""):                (20, 25),
}

# Activity breakdown as % of total QA effort
ACTIVITY_BREAKDOWN = {
    "Test Planning & Strategy":         (5,  10),
    "Test Design & Specification":      (15, 20),
    "Test Environment Setup":           (5,  10),
    "Automation Framework Setup":       (10, 20),   # only if no existing automation
    "Test Execution — Functional":      (25, 35),
    "Test Execution — Non-functional":  (10, 15),
    "Defect Management & Retesting":    (10, 15),
    "Regression Testing":               (10, 15),
    "Reporting & Documentation":        (5,   8),
}

# Risk buffer per risk level (days)
RISK_BUFFER = {
    "critical": 5,
    "high":     3,
    "medium":   1,
    "low":      0,
}

# ── Estimation Data ────────────────────────────────────────────────────────────

@dataclass
class EstimationData:
    """Holds all calculated estimation data."""
    # Baseline
    project_type_detected: str = ""
    methodology_detected: str = ""
    baseline_qa_percent_min: float = 0
    baseline_qa_percent_max: float = 0
    project_duration_days: int = 0
    team_total_size: int = 0
    baseline_effort_min: float = 0
    baseline_effort_max: float = 0

    # Multipliers
    multipliers: list = field(default_factory=list)  # list of (reason, pct_add)
    total_multiplier: float = 0

    # Adjusted effort
    adjusted_effort_min: float = 0
    adjusted_effort_max: float = 0

    # PERT per activity
    pert_activities: list = field(default_factory=list)  # list of dicts
    pert_total_optimistic: float = 0
    pert_total_most_likely: float = 0
    pert_total_pessimistic: float = 0
    pert_total_expected: float = 0
    pert_total_sd: float = 0

    # Team capacity
    qa_team_size: int = 0
    available_person_days: float = 0
    utilization_rate: float = 0.75
    capacity_gap: float = 0  # = available_person_days - pert_total_expected: positive = surplus, negative = deficit
    capacity_status: str = ""  # "surplus" | "deficit" | "balanced" (unambiguous companion of capacity_gap)
    capacity_note: str = ""    # one line explaining the sign of capacity_gap

    # Risk buffer
    risk_buffer_days: float = 0
    final_effort_min: float = 0
    final_effort_max: float = 0

    # Confidence
    confidence_level: str = "Medium"
    data_quality_score: int = 20   # 0-20; calculated from dialogue completeness
    confidence_score: int = 0      # raw score 0-100 (for debugging/display)
    data_quality_max: int = 20     # scale of data_quality_score (20 = every key answer specific)
    confidence_note: str = ""      # why confidence_level is what it is (caps / weakest factors)
    methodology_note: str = ""     # set only when the methodology does not change the numbers

    # Human-readable notes about inputs that were assumed, defaulted, ignored or\n    # look implausible. Surfaced as warnings in the MCP tool's JSON (asdict).
    warnings: list = field(default_factory=list)


def warn(data: EstimationData, message: str) -> None:
    """Append a warning to ``data.warnings`` (deduplicated, order preserved)."""
    if message not in data.warnings:
        data.warnings.append(message)


# ── Step 1: Detect project type ────────────────────────────────────────────────

def detect_project_type(context: ProjectContext, data: EstimationData) -> None:
    pt = (context.project_type or "").lower()
    meth = (context.methodology or "").lower()

    # Detect project type
    if any(k in pt for k in ["embedded", "firmware", "automotive"]):
        data.project_type_detected = "embedded"
    elif any(k in pt for k in ["mobile", "android"]) or re.search(r"\bios\b", pt):
        data.project_type_detected = "mobile"
    elif any(k in pt for k in ["microservice", "backend"]) or re.search(r"\b(?:apis?|rest|restful)\b", pt):
        data.project_type_detected = "api"
    elif any(k in pt for k in ["web", "browser", "frontend"]):
        data.project_type_detected = "web"
    elif any(k in pt for k in ["desktop"]):
        data.project_type_detected = "desktop"
    elif (
        any(k in pt for k in ["data", "machine learning", "llm", "genai", "generative", "chatbot", "artificial intelligence"])
        or re.search(r"\b(?:ai|ml|ai/ml)\b", pt)
    ):
        # AI/ML/LLM systems share the "data" benchmark band (20-30%).
        data.project_type_detected = "data"
    else:
        data.project_type_detected = "default"
        if pt.strip():
            warn(data, f"project_type '{context.project_type.strip()}' was not recognised; the default "
                       "20-25% QA baseline was used (recognised: embedded/automotive, mobile, API/backend, "
                       "web, desktop, data/AI/ML/LLM).")

    # Detect methodology
    if any(k in meth for k in ["v-model", "vmodel", "v model"]):
        data.methodology_detected = "v-model"
    elif any(k in meth for k in ["waterfall"]):
        data.methodology_detected = "waterfall"
    elif any(k in meth for k in ["agile", "scrum", "kanban", "safe"]):
        data.methodology_detected = "agile"
    else:
        data.methodology_detected = ""


# ── Step 2: Calculate baseline ─────────────────────────────────────────────────

def calculate_baseline(context: ProjectContext, data: EstimationData) -> None:
    # Look up baseline percentage
    key = (data.project_type_detected, data.methodology_detected)
    if key not in BASELINE_QA_PERCENT:
        key = (data.project_type_detected, "")
    if key not in BASELINE_QA_PERCENT:
        key = ("default", "")

    data.baseline_qa_percent_min, data.baseline_qa_percent_max = BASELINE_QA_PERCENT[key]

    meth_text = (context.methodology or "").strip()
    if meth_text and key[1] == "":
        if data.methodology_detected == "":
            data.methodology_note = (
                f"methodology '{meth_text}' was not recognised (recognised: V-model, waterfall, "
                "agile/scrum/kanban/SAFe); the methodology-neutral baseline was used.")
        else:
            data.methodology_note = (
                f"methodology '{meth_text}' ({data.methodology_detected}) does not change the numbers for "
                f"project type '{data.project_type_detected}': the benchmark has no methodology-specific band "
                "for it (only embedded and web projects differ by methodology). It is a label only.")
        warn(data, "methodology: " + data.methodology_note)

    # Parse project duration
    data.project_duration_days = parse_duration(context.timeline, data.warnings)

    # Parse team sizes
    data.qa_team_size = parse_team_size(context.team_qa_size, data.warnings, "team_qa_size")
    dev_size = parse_team_size(context.team_dev_size, data.warnings, "team_dev_size")
    data.team_total_size = data.qa_team_size + dev_size

    # Total project effort estimate (dev + QA)
    # Assume developer works ~200 days/year at 75% utilization
    dev_days = dev_size * data.project_duration_days * 0.75

    # QA baseline = dev_days * (qa_pct / (1 - qa_pct))
    mid_pct = (data.baseline_qa_percent_min + data.baseline_qa_percent_max) / 2 / 100
    if mid_pct < 1:
        pct_min = min(data.baseline_qa_percent_min, 99)
        pct_max = min(data.baseline_qa_percent_max, 99)
        qa_multiplier_min = pct_min / (100 - pct_min)
        qa_multiplier_max = pct_max / (100 - pct_max)
    else:
        qa_multiplier_min = 0.2
        qa_multiplier_max = 0.3

    data.baseline_effort_min = round(dev_days * qa_multiplier_min, 1)
    data.baseline_effort_max = round(dev_days * qa_multiplier_max, 1)


# ── Step 3: Apply multipliers ──────────────────────────────────────────────────

# (label, regex on lower-cased compliance text, % added). Whole-word where the
# token is short so e.g. "dora" does not match inside another word.
EXTRA_COMPLIANCE_RULES = [
    ("SOC 2", r"\bsoc[\s-]*2\b", 10),
    ("PSD2", r"\bpsd[\s-]*2\b", 12),
    ("ISO 27001", r"\b(?:iso[\s/-]*(?:iec[\s-]*)?)?27001\b", 10),
    ("EU AI Act", r"\b(?:eu\s+)?ai\s+act\b", 15),
    ("NIS2", r"\bnis[\s-]*2\b", 10),
    ("DORA", r"\bdora\b", 12),
]

# Patterns for the regimes handled inline in apply_multipliers(), used only to
# decide whether a compliance item was recognised.
_CORE_COMPLIANCE_RE = re.compile(
    r"asil|iso[\s-]*26262|spice|gdpr|\bpci\b|pci-dss|hipaa"
)
_NO_COMPLIANCE_RE = re.compile(
    r"^(?:none|n/?a|na|no|nothing|nil|not applicable|tbd|unknown|not sure|-|none yet|no compliance)\b"
)


def _warn_unrecognised_compliance(compliance_text: str, data: EstimationData) -> None:
    """Warn about compliance items that matched no known multiplier (they had no effect)."""
    unknown = []
    text = re.sub(r"\bn/a\b", "na", compliance_text, flags=re.IGNORECASE)
    for raw_item in re.split(r"[,;/\n+&]|\band\b", text, flags=re.IGNORECASE):
        raw_item = raw_item.strip(" .\t")
        item = raw_item.lower()
        if not item or _NO_COMPLIANCE_RE.match(item) or _CORE_COMPLIANCE_RE.search(item):
            continue
        if any(re.search(pattern, item) for _, pattern, _ in EXTRA_COMPLIANCE_RULES):
            continue
        unknown.append(raw_item)
    if unknown:
        warn(data, "Compliance item(s) not recognised and therefore had NO effect on the estimate: "
                   + ", ".join(unknown)
                   + ". Recognised: ISO 26262/ASIL, A-SPICE, GDPR, PCI-DSS, HIPAA, SOC 2, PSD2, "
                     "ISO 27001, EU AI Act, NIS2, DORA.")

def apply_multipliers(context: ProjectContext, data: EstimationData) -> None:
    compliance = (context.compliance_requirements or "").lower()
    automation = (context.existing_automation or "").lower()
    risks = (context.known_risks or "").lower()
    stack = (context.tech_stack or "").lower()

    total_add = 0.0

    # Compliance multipliers
    if any(k in compliance for k in ["asil d", "asil-d"]):
        data.multipliers.append(("ISO 26262 ASIL D requirement", 40))
        total_add += 40
    elif any(k in compliance for k in ["asil c", "asil-c"]):
        data.multipliers.append(("ISO 26262 ASIL C requirement", 30))
        total_add += 30
    elif any(k in compliance for k in ["asil b", "asil-b"]):
        data.multipliers.append(("ISO 26262 ASIL B requirement", 20))
        total_add += 20
    elif any(k in compliance for k in ["asil a", "asil-a", "iso 26262", "iso26262"]):
        data.multipliers.append(("ISO 26262 compliance", 15))
        total_add += 15

    if any(k in compliance for k in ["a-spice", "aspice", "spice"]):
        level_3 = any(k in compliance for k in ["level 3", "lvl 3", "l3"])
        add = 30 if level_3 else 20
        data.multipliers.append((f"A-SPICE compliance (Level {'3' if level_3 else '2'})", add))
        total_add += add

    if "gdpr" in compliance:
        data.multipliers.append(("GDPR compliance", 10))
        total_add += 10

    if any(k in compliance for k in ["pci", "pci-dss"]):
        data.multipliers.append(("PCI-DSS compliance", 15))
        total_add += 15

    if "hipaa" in compliance:
        data.multipliers.append(("HIPAA compliance", 15))
        total_add += 15

    # Additional regimes (benchmarks: audit-evidence and control-testing overhead
    # on top of normal functional QA; deliberately a little below PCI/HIPAA).
    for label, pattern, add in EXTRA_COMPLIANCE_RULES:
        if re.search(pattern, compliance):
            data.multipliers.append((f"{label} compliance", add))
            total_add += add

    _warn_unrecognised_compliance(context.compliance_requirements or "", data)

    # Automation multipliers
    # Whole-word match: a bare substring "no" fired on "CANoe" and charged +20%
    # "greenfield setup" to a project that lists CANoe test automation.
    no_automation = bool(re.search(r"\b(?:no|nothing|none|not yet|greenfield)\b", automation))
    if no_automation:
        data.multipliers.append(("No existing automation — greenfield setup needed", 20))
        total_add += 20
    elif any(k in automation for k in ["some", "partial", "unit"]):
        data.multipliers.append(("Partial automation — maintenance + extension needed", 10))
        total_add += 10

    # Team multipliers
    if data.qa_team_size <= 2:
        data.multipliers.append(("Small QA team (≤2 people) — context switching overhead", 10))
        total_add += 10

    # Technical complexity
    if any(k in risks for k in ["integration", "third-party", "external"]):
        data.multipliers.append(("External integrations identified as risk", 12))
        total_add += 12

    if any(k in risks for k in ["asil", "safety", "safety-critical"]):
        if not any(k in compliance for k in ["iso 26262", "asil"]):
            data.multipliers.append(("Safety-critical components identified", 20))
            total_add += 20

    if any(k in stack for k in ["legacy", "cobol", "mainframe"]):
        data.multipliers.append(("Legacy technology stack", 20))
        total_add += 20

    data.total_multiplier = total_add
    multiplier_factor = 1 + (total_add / 100)
    data.adjusted_effort_min = round(data.baseline_effort_min * multiplier_factor, 1)
    data.adjusted_effort_max = round(data.baseline_effort_max * multiplier_factor, 1)


# ── Step 4: PERT breakdown per activity ────────────────────────────────────────

def pert_breakdown(data: EstimationData) -> None:
    mid_effort = (data.adjusted_effort_min + data.adjusted_effort_max) / 2

    # Skip automation setup if existing automation
    activities = {k: v for k, v in ACTIVITY_BREAKDOWN.items()
                  if k != "Automation Framework Setup" or data.total_multiplier > 0}

    # Normalize raw mid-percentages so they sum to exactly 100
    raw_total = sum((lo + hi) / 2 for lo, hi in activities.values())
    norm_scale = 100.0 / raw_total if raw_total > 0 else 1.0

    total_o = total_m = total_p = total_e = 0.0

    for activity, (pct_lo, pct_hi) in activities.items():
        pct_mid = ((pct_lo + pct_hi) / 2) * norm_scale
        # Scale to actual effort
        m = round(mid_effort * pct_mid / 100, 1)
        o = round(m * 0.6, 1)   # optimistic = 60% of most likely
        p = round(m * 1.8, 1)   # pessimistic = 180% of most likely
        e = round((o + 4 * m + p) / 6, 1)
        sd = round((p - o) / 6, 1)

        data.pert_activities.append({
            "activity": activity,
            "optimistic": o,
            "most_likely": m,
            "pessimistic": p,
            "expected": e,
            "sd": sd,
            "pct": round(pct_mid, 0),
        })

        total_o += o
        total_m += m
        total_p += p
        total_e += e

    # Every total is the sum of the rounded per-activity values shown in the
    # report table, so the displayed TOTAL row always equals its column. The
    # expected total used to be recomputed as (O + 4M + P) / 6 from the
    # totals, which drifts from the sum of the rounded row values; capacity
    # gap, confidence and "% of capacity" all derive from this figure.
    data.pert_total_optimistic = round(total_o, 1)
    data.pert_total_most_likely = round(total_m, 1)
    data.pert_total_pessimistic = round(total_p, 1)
    data.pert_total_expected = round(total_e, 1)
    data.pert_total_sd = round((total_p - total_o) / 6, 1)


# ── Step 5: Team capacity ───────────────────────────────────────────────────────

def team_capacity(context: ProjectContext, data: EstimationData) -> None:
    data.utilization_rate = 0.75
    data.available_person_days = round(
        data.qa_team_size * data.project_duration_days * data.utilization_rate, 1
    )
    data.capacity_gap = round(
        data.available_person_days - data.pert_total_expected, 1
    )
    if data.capacity_gap > 0:
        data.capacity_status = "surplus"
    elif data.capacity_gap < 0:
        data.capacity_status = "deficit"
    else:
        data.capacity_status = "balanced"
    data.capacity_note = (
        "capacity_gap = available_person_days - pert_total_expected: POSITIVE means capacity exceeds the "
        f"expected effort (surplus), NEGATIVE means a shortfall (deficit). Here: {data.capacity_status}"
        + (f" of {abs(data.capacity_gap):g} person-days." if data.capacity_gap else ".")
    )


# ── Step 6: Risk buffer ─────────────────────────────────────────────────────────

def risk_buffer(risk_register: str, data: EstimationData) -> None:
    if not risk_register:
        data.risk_buffer_days = round(data.pert_total_expected * 0.15, 1)
        return

    # Count one entry per Risk Matrix row, keyed on its Risk Level cell only.
    # Counting keyword occurrences in the whole text also picked up prose
    # ("critical path") and the Likelihood/Impact columns, pushing almost
    # every register to the 35% cap regardless of its actual risks.
    rows = parse_risk_matrix(risk_register)
    if not rows:
        data.risk_buffer_days = round(data.pert_total_expected * 0.15, 1)
        return

    buffer = 0
    for row in rows:
        level = row["risk_level"].lower()
        for tier in ("critical", "high", "medium"):
            if tier in level:
                buffer += RISK_BUFFER[tier]
                break

    # Cap buffer at 35% of expected effort
    max_buffer = data.pert_total_expected * 0.35
    data.risk_buffer_days = round(min(buffer, max_buffer), 1)


# ── Step 6.5: Data quality score ────────────────────────────────────────────────

_VAGUE_ANSWER_RE = re.compile(
    r"\b(?:tbd|unknown|not sure|don'?t know|unclear|maybe|to be determined)\b",
    re.IGNORECASE,
)


def calculate_data_quality(context: ProjectContext, data: EstimationData) -> None:
    """
    Score dialogue completeness (0-20 pts).
    Vague or missing answers reduce confidence in the estimate.

    Scoring:
      - 5 key fields checked: timeline, team_qa_size, team_dev_size,
        compliance_requirements, existing_automation
      - Each field: 4 pts if specific, 2 pts if vague, 0 pts if empty
      - "none" / "n/a" state an absence precisely (no compliance, no
        automation) and count as specific; "unknown" / "not sure" are vague.
        Keywords match whole words — "na" in "functional" is not vague.
    """
    score = 0

    fields = [
        context.timeline,
        context.team_qa_size,
        context.team_dev_size,
        context.compliance_requirements,
        context.existing_automation,
    ]

    for field_val in fields:
        if not field_val or not field_val.strip():
            score += 0
        elif "?" in field_val or _VAGUE_ANSWER_RE.search(field_val):
            score += 2
        else:
            score += 4

    data.data_quality_score = score


# ── Step 7: Finalize ─────────────────────────────────────────────────────────────

def finalize(data: EstimationData) -> None:
    data.final_effort_min = round(data.pert_total_optimistic + data.risk_buffer_days * 0.5, 1)
    data.final_effort_max = round(data.pert_total_pessimistic + data.risk_buffer_days, 1)
    data.confidence_level = calculate_confidence(data)


def _confidence_components(data: EstimationData) -> tuple:
    """Return the four confidence factor scores (spread, gap, quality, magnitude)."""
    spread_pts = gap_pts = 0

    # ── Factor 1: PERT spread ratio (40 pts) ──────────────────────────────────
    # spread_ratio = (P - O) / E — lower is better (less uncertainty)
    if data.pert_total_expected > 0:
        spread_ratio = (data.pert_total_pessimistic - data.pert_total_optimistic) / data.pert_total_expected
        if spread_ratio < 1.0:
            spread_pts = 40
        elif spread_ratio < 2.0:
            spread_pts = int(40 - (spread_ratio - 1.0) * 20)   # 20-39
        elif spread_ratio < 3.0:
            spread_pts = int(20 - (spread_ratio - 2.0) * 15)   # 5-19
        else:
            spread_pts = 0

    # ── Factor 2: Capacity gap ratio (30 pts) ───────────────────────────────────
    # gap_ratio = capacity_gap / expected_effort
    # positive (surplus) → good; negative (deficit) → bad
    if data.pert_total_expected > 0:
        gap_ratio = data.capacity_gap / data.pert_total_expected
        if gap_ratio >= 0.3:
            gap_pts = 30    # comfortable surplus (≥30% buffer)
        elif gap_ratio >= 0.0:
            gap_pts = int(15 + gap_ratio / 0.3 * 15)   # 15-30
        elif gap_ratio >= -0.3:
            gap_pts = int(15 + gap_ratio / 0.3 * 15)   # 0-14  (mild deficit)
        else:
            gap_pts = 0     # severe deficit (>30% short)

    # ── Factor 3: Data quality (20 pts) ─────────────────────────────────────────
    quality_pts = min(20, max(0, data.data_quality_score))

    # ── Factor 4: Multiplier magnitude (10 pts) ─────────────────────────────────
    # 0% → 10 pts; 50% → 5 pts; ≥100% → 0 pts
    magnitude_pts = max(0, 10 - int(data.total_multiplier / 10))

    return spread_pts, gap_pts, quality_pts, magnitude_pts


def confidence_breakdown(data: EstimationData) -> list:
    """Per-factor confidence points as (label, points, max_points, detail) tuples.

    Deterministic and derived from the same helper calculate_confidence()
    sums, so the explanation shown in the UI can never disagree with the score.
    (The >5-year duration guard and the plausibility caps, when they fire, lower the total below\n    the factor sum; each cap also adds a capped at ... entry to `data.warnings`.)
    """
    spread_pts, gap_pts, quality_pts, magnitude_pts = _confidence_components(data)
    expected = data.pert_total_expected
    spread = (
        f"best-to-worst-case spread is {(data.pert_total_pessimistic - data.pert_total_optimistic) / expected:.1f}x "
        f"the expected effort (narrower is better)" if expected > 0 else "no expected effort to compare"
    )
    gap = (
        f"capacity is {data.capacity_gap / expected * 100:+.0f}% relative to expected effort "
        f"(surplus is better, deficit lowers it)" if expected > 0 else "no expected effort to compare"
    )
    return [
        ("PERT spread", spread_pts, 40, spread),
        ("Capacity gap", gap_pts, 30, gap),
        ("Data quality", quality_pts, 20, "how specific the dialogue answers were (timeline, team sizes, compliance, automation)"),
        ("Multiplier magnitude", magnitude_pts, 10, f"+{data.total_multiplier:g}% complexity adjustments applied (fewer is better)"),
    ]


def explain_effort_range(data: EstimationData) -> str:
    """One deterministic paragraph on what drives the final effort range and the
    capacity gap, built only from the numbers in ``data`` (no LLM)."""
    lo, hi = data.final_effort_min, data.final_effort_max
    ratio = f"{hi / lo:.1f}x" if lo > 0 else "n/a"
    half_buffer = round(data.risk_buffer_days * 0.5, 1)
    if data.capacity_gap >= 0:
        gap_text = f"a surplus of {data.capacity_gap:g}"
    else:
        gap_text = f"a deficit of {abs(data.capacity_gap):g}"
    return (
        f"The range runs {lo:g} to {hi:g} person-days (upper bound is {ratio} the lower). "
        f"The lower bound is the PERT optimistic total ({data.pert_total_optimistic:g}, each activity at 60% of its "
        f"most-likely estimate) plus half the risk buffer ({half_buffer:g}). "
        f"The upper bound is the PERT pessimistic total ({data.pert_total_pessimistic:g}, each activity at 180% of "
        f"its most-likely estimate) plus the full risk buffer ({data.risk_buffer_days:g}). "
        f"The most-likely total ({data.pert_total_most_likely:g}) comes from a baseline of "
        f"{data.baseline_effort_min:g}-{data.baseline_effort_max:g} person-days adjusted by +{data.total_multiplier:g}% "
        f"complexity multipliers. "
        f"The range is a planning band built from those fixed factors, not a statistical confidence interval. "
        f"Capacity gap = available capacity ({data.available_person_days:g}) minus PERT expected effort "
        f"({data.pert_total_expected:g}) = {gap_text} person-days."
    )


def capacity_utilization_pct(data: EstimationData) -> Optional[int]:
    """PERT expected effort as a whole-number % of available capacity (None if no capacity)."""
    if data.available_person_days <= 0:
        return None
    return round(data.pert_total_expected / data.available_person_days * 100)


def calculate_confidence(data: EstimationData) -> str:
    """
    Score-based confidence algorithm (0-100 points).

    Four factors:
      1. PERT spread ratio     — 0-40 pts  (how wide is O-P relative to E)
      2. Capacity gap ratio    — 0-30 pts  (surplus/deficit as % of expected)
      3. Data quality          — 0-20 pts  (stored in data.data_quality_score)
      4. Multiplier magnitude  — 0-10 pts  (total % adjustment applied)

    Final score → High (70-100), Medium (40-69), Low (0-39)
    """
    spread_pts, gap_pts, quality_pts, magnitude_pts = _confidence_components(data)
    score = spread_pts + gap_pts + quality_pts + magnitude_pts

    # ── Absolute magnitude guard ─────────────────────────────────────────────────
    # However well the four factors score, a physically-implausible duration
    # must never read "High" — this is a floor, not a fifth scored factor.
    if data.project_duration_days > MAX_PLAUSIBLE_DURATION_DAYS and score >= 70:
        score = 69

    # ── Plausibility caps ────────────────────────────────────────────────────────
    # The four factors are additive, so a strong spread + perfect data quality
    # can outvote a hopeless capacity gap. These caps are ceilings, not factors:
    #   * very vague answers (data quality <= 8/20) cannot read High
    #   * a deficit > 30% of expected effort cannot read High; > 50% reads Low
    #   * shortfall > 5x total capacity, or no QA capacity at all, reads Low
    #   * QA team > 3x the dev team is an implausible ratio: cannot read High
    expected = data.pert_total_expected
    cap = 100
    if data.data_quality_score <= LOW_DATA_QUALITY_MAX:
        cap = min(cap, 69)
        warn(data, f"Data quality is very low ({data.data_quality_score}/20: timeline, team sizes, compliance "
                   "or automation answers are vague or missing); confidence is capped at Medium.")
    if expected > 0:
        gap_ratio = data.capacity_gap / expected
        if gap_ratio < -0.5:
            cap = min(cap, 39)
            warn(data, f"Severe capacity shortfall: available capacity covers only "
                       f"{max(0.0, 1 + gap_ratio) * 100:.0f}% of expected effort "
                       f"({abs(data.capacity_gap):g} person-days short); confidence is capped at Low. "
                       "Check team size and timeline for input errors.")
        elif gap_ratio < -0.3:
            cap = min(cap, 69)
            warn(data, f"Capacity shortfall of {abs(data.capacity_gap):g} person-days exceeds 30% of expected "
                       "effort; confidence is capped at Medium.")
        if data.available_person_days > 0 and -data.capacity_gap > 5 * data.available_person_days:
            cap = min(cap, 39)
            warn(data, "Shortfall is more than 5x the available QA capacity; the team/duration inputs look "
                       "implausible. Confidence is capped at Low.")
        elif data.available_person_days <= 0 and data.project_duration_days > 0:
            cap = min(cap, 39)
            warn(data, "No QA capacity (QA team size or duration is zero) against non-zero expected effort; "
                       "confidence is capped at Low.")
    dev_size = data.team_total_size - data.qa_team_size
    if dev_size > 0 and data.qa_team_size > 3 * dev_size:
        cap = min(cap, 69)
        warn(data, f"QA team ({data.qa_team_size}) is more than 3x the dev team ({dev_size}); check for swapped "
                   "or mistyped team sizes. Confidence is capped at Medium.")
    uncapped = score
    score = min(score, cap)

    # Honest framing of what limited the level (deterministic; no new numbers).
    notes = [f"data quality {data.data_quality_score}/{data.data_quality_max} (20 = every key answer specific)"]
    if score < uncapped:
        notes.append(f"the factor score {uncapped} was capped to {score} by the plausibility rules in warnings")
    if cap == 100 and data.data_quality_score < data.data_quality_max:
        notes.append("some key answers were vague or missing, which lowers confidence")
    data.confidence_note = (
        "Confidence is a heuristic over input quality, PERT spread, capacity fit and complexity multipliers, "
        "not a statistical interval: " + "; ".join(notes) + ".")

    # ── Map score to label ───────────────────────────────────────────────────────
    data.confidence_score = score
    if score >= 70:
        return "High"
    elif score >= 40:
        return "Medium"
    else:
        return "Low"


# ── Helpers ──────────────────────────────────────────────────────────────────────

# ── Duration / team-size parsing ───────────────────────────────────────────────
# All timeline unit conversions live here (working days per unit).
WORKING_DAYS_PER_DAY = 1
WORKING_DAYS_PER_WEEK = 5
WORKING_DAYS_PER_MONTH = 21
WORKING_DAYS_PER_QUARTER = 63          # 3 months
WORKING_DAYS_PER_YEAR = 230
DEFAULT_SPRINT_WEEKS = 2               # a sprint is 2 weeks (10 working days) unless stated
CALENDAR_TO_WORKING_RATIO = 5 / 7      # "90 days" (calendar) -> ~64 working days
CALENDAR_DAYS_THRESHOLD = 10           # "N days" with N <= this is read as working days as written
DEFAULT_DURATION_DAYS = 130            # ~6 months; used (with a warning) when nothing parses
FEW_QUANTITY = 3                       # "a few" -> 3, "a couple" -> 2 (assumed, warned)

_NUMBER_WORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20,
    # Romanian (diacritics are stripped before matching)
    "doi": 2, "doua": 2, "trei": 3, "patru": 4, "cinci": 5, "sase": 6, "sapte": 7,
    "opt": 8, "noua": 9, "zece": 10,
}
_NUMBER_WORD_RE = re.compile(r"\b(" + "|".join(_NUMBER_WORDS) + r")\b")

_DIACRITICS = str.maketrans("ăâîșşțţ", "aaisstt")

_UNIT_PATTERNS = [  # order matters: more specific first
    ("workday", r"(?:working|business|work)[\s-]*days?|workdays?|zile\s+lucratoare"),
    ("sprint", r"sprints?|sprinturi"),
    ("quarter", r"quarters?|trimestr\w*"),
    ("year", r"years?|yrs?|ani|an"),
    ("month", r"months?|mos?|luni|luna"),
    ("week", r"weeks?|wks?|saptamani|saptamana"),
    ("day", r"days?|zile|zi"),
]
_UNIT_RE = "|".join(f"(?P<{name}>{pat})" for name, pat in _UNIT_PATTERNS)
_NUM = r"\d+(?:[.,]\d+)?"
_DURATION_RE = re.compile(
    rf"(?P<n1>{_NUM})(?:\s*(?:-|–|to|pana\s+la)\s*(?P<n2>{_NUM}))?\s*(?:de\s+)?(?:{_UNIT_RE})\b"
)
_SPRINT_LEN_RES = [
    re.compile(r"(\d+)[\s-]*(?:weeks?|wks?|saptamani)[\s-]+sprints?"),
    re.compile(r"sprints?\s+(?:of|de|lasting)\s+(\d+)\s*(?:weeks?|wks?|saptamani)"),
]


def _to_float(s: str) -> float:
    return float(s.replace(",", "."))


def _normalise_text(text: str) -> str:
    return text.lower().translate(_DIACRITICS)


def _add_warning(warnings: Optional[list], message: str) -> None:
    if warnings is not None and message not in warnings:
        warnings.append(message)


_VAGUE_QUANTITIES = [  # (regex, assumed value)
    (re.compile(r"\b(?:a\s+)?few\b"), FEW_QUANTITY),
    (re.compile(r"\bseveral\b"), FEW_QUANTITY),
    (re.compile(r"\b(?:a\s+)?couple(?:\s+of)?\b"), 2),
]


def _words_to_digits(text: str, warnings: Optional[list], label: str) -> str:
    """Replace number words ("three", "trei", "a year") with digits.

    Vague quantities ("a few", "several", "a couple") become a fixed assumed
    number and add a warning.
    """
    for rx, value in _VAGUE_QUANTITIES:
        m = rx.search(text)
        if m:
            _add_warning(warnings, f"{label}: '{m.group(0)}' is vague; assumed {value}.")
            text = rx.sub(str(value), text)
    text = _NUMBER_WORD_RE.sub(lambda m: str(_NUMBER_WORDS[m.group(1)]), text)
    return re.sub(r"\b(?:a|an|un|o)\s+(?=(?:year|month|week|quarter|sprint|day|an|luna|saptamana|trimestru|zi|sprint)s?\b)", "1 ", text)

def _midpoint_up(lo: float, hi: float) -> float:
    return float(-(-(lo + hi) // 2)) if float(lo).is_integer() and float(hi).is_integer() else (lo + hi) / 2


def parse_duration(timeline: str, warnings: Optional[list] = None) -> int:
    """Parse a timeline string to working days.

    Recognised units (English and Romanian): working/business days (as written),
    days ("N days" with N <= CALENDAR_DAYS_THRESHOLD is taken as working days,
    larger values are treated as calendar days x 5/7), weeks, months (21 wd),
    quarters (63 wd), years (230 wd) and sprints (DEFAULT_SPRINT_WEEKS weeks
    unless "N-week sprints" is given). Several parts are summed ("1 year 3
    months"); parenthesised restatements and "or" alternatives are ignored.
    A range ("3-4 months") uses its midpoint rounded up.

    Anything that cannot be parsed (e.g. "Dec 2026", "Q1 2027", "ASAP") falls
    back to DEFAULT_DURATION_DAYS and appends a warning naming the default;
    a bare number with no unit is read as months (legacy) with a warning.
    Bare 4+ digit numbers are calendar years and never counts. The result is
    clamped to MAX_PLAUSIBLE_DURATION_DAYS.

    ``warnings`` (optional list) receives human-readable notes.
    """
    if not timeline or not timeline.strip():
        _add_warning(warnings, f"timeline: empty; assumed the default {DEFAULT_DURATION_DAYS} working days (~6 months).")
        return DEFAULT_DURATION_DAYS
    original = timeline.strip()
    tl = _words_to_digits(_normalise_text(original), warnings, "timeline")
    tl = re.sub(r"(\d)\s*(?:-|–)\s*(?=\d)", r"\1-", tl)

    # Sprint length ("2-week sprints", "sprints of 3 weeks"): consume it so the
    # week count is not also read as a duration.
    sprint_weeks = DEFAULT_SPRINT_WEEKS
    for rx in _SPRINT_LEN_RES:
        m = rx.search(tl)
        if m:
            sprint_weeks = int(m.group(1))
            tl = rx.sub(" sprint", tl, count=1)
            break

    def _scan(text: str):
        return list(_DURATION_RE.finditer(text))

    matches = _scan(tl)
    if matches:
        # Drop "(...)" restatements and "or <alternative>" clauses when a main clause parses.
        stripped = re.sub(r"\([^)]*\)", " ", tl)
        stripped = re.split(r"\bor\b", stripped)[0]
        main = _scan(stripped)
        if main:
            matches = main

    if matches:
        total = 0.0
        for m in matches:
            n1 = _to_float(m.group("n1"))
            if m.group("n2"):
                n2 = _to_float(m.group("n2"))
                n = _midpoint_up(n1, n2)
                _add_warning(warnings, f"timeline: range '{m.group(0).strip()}' interpreted as its midpoint "
                                       f"({n:g}, rounded up).")
            else:
                n = n1
            unit = m.lastgroup
            if unit == "workday":
                total += n * WORKING_DAYS_PER_DAY
            elif unit == "day":
                if n <= CALENDAR_DAYS_THRESHOLD:
                    total += n * WORKING_DAYS_PER_DAY
                else:
                    total += n * CALENDAR_TO_WORKING_RATIO
            elif unit == "week":
                total += n * WORKING_DAYS_PER_WEEK
            elif unit == "month":
                total += n * WORKING_DAYS_PER_MONTH
            elif unit == "quarter":
                total += n * WORKING_DAYS_PER_QUARTER
            elif unit == "year":
                total += n * WORKING_DAYS_PER_YEAR
            elif unit == "sprint":
                total += n * sprint_weeks * WORKING_DAYS_PER_WEEK
        days = max(1, round(total))
        if days > MAX_PLAUSIBLE_DURATION_DAYS:
            _add_warning(warnings, f"timeline: '{original}' parsed to {days} working days, above the "
                                   f"{MAX_PLAUSIBLE_DURATION_DAYS}-day plausibility limit; clamped.")
        return min(days, MAX_PLAUSIBLE_DURATION_DAYS)

    # Bare 1-3 digit number with no unit: legacy "months" reading, flagged.
    bare = re.search(r"(?<![\w.])(\d{1,3})(?![\w])", tl)
    if bare:
        months = int(bare.group(1))
        _add_warning(warnings, f"timeline: '{original}' has no unit; the number {months} was read as months "
                               f"({months * WORKING_DAYS_PER_MONTH} working days). State a unit "
                               "(days/weeks/months/quarters/years/sprints).")
        return min(months * WORKING_DAYS_PER_MONTH, MAX_PLAUSIBLE_DURATION_DAYS)

    _add_warning(warnings, f"timeline: could not parse '{original}' (no duration such as '6 months'; calendar "
                           f"dates and quarters like 'Q1 2027' need a start date to convert). Used the default "
                           f"{DEFAULT_DURATION_DAYS} working days (~6 months).")
    return DEFAULT_DURATION_DAYS


_NO_TEAM_RE = re.compile(r"\b(?:no\s+dedicated|none|devs?\s+test|developers?\s+test|nobody|no\s+one)\b")


MAX_TEAM_SIZE = 100_000


def parse_team_size(team_str: str, warnings: Optional[list] = None, label: str = "team size") -> int:
    """Parse team size string to integer.

    * Number words are understood ("three", "eight", Romanian "trei", "opt").
    * A range ("2-3", "8 to 10") counts as its midpoint rounded up (3 and 9);
      a warning notes the interpretation.
    * Separate numbers are summed ("3 frontend + 2 backend" = 5), except that
      an "A, or B" clause restates the same team another way, so only the part
      before the first standalone "or" is summed.
    * "none" / "no dedicated" / "developers test" (whole words) mean 0.
    * Text with no number at all is read as 1, with a warning.
    """
    if not team_str or not team_str.strip():
        _add_warning(warnings, f"{label}: empty; assumed 1 person.")
        return 1
    ts = _normalise_text(team_str)
    if _NO_TEAM_RE.search(ts):
        return 0
    ts = _words_to_digits(ts, warnings, label)
    # "1,000" is a thousands separator (a comma followed by exactly three digits), not a decimal comma.
    grouped = re.sub(r"(?<![\d,.])\d{1,3}(?:,\d{3})+(?![\d,])", lambda m: m.group(0).replace(",", ""), ts)
    if grouped != ts:
        _add_warning(warnings, f"{label}: '{team_str.strip()}' read with a thousands separator.")
        ts = grouped
    first_alternative = re.split(r"\bor\b", ts)[0] if re.search(r"\d", re.split(r"\bor\b", ts)[0]) else ts

    total = 0.0
    found = False
    num = r"(?<!\d)\d+(?:[.,]\d+)?"  # anchored at the start of a digit run so long runs stay linear

    def _range(m):
        nonlocal total, found
        lo, hi = _to_float(m.group(1)), _to_float(m.group(2))
        if hi < lo:
            lo, hi = hi, lo
        mid = _midpoint_up(lo, hi)
        total += mid
        found = True
        _add_warning(warnings, f"{label}: range '{m.group(0).strip()}' interpreted as {mid:g} "
                               "(midpoint, rounded up).")
        return " "

    rest = re.sub(rf"({num})\s*(?:-|–|to)\s*({num})", _range, first_alternative)
    for n in re.findall(num, rest):
        total += _to_float(n)
        found = True
    if found:
        if total > MAX_TEAM_SIZE:  # also covers float overflow to inf on absurdly long digit runs
            _add_warning(warnings, f"{label}: '{team_str.strip()[:40]}' is implausibly large; capped at {MAX_TEAM_SIZE}.")
            total = float(MAX_TEAM_SIZE)
        whole = int(total + 0.5)  # round half up (never banker's rounding)
        if abs(total - whole) > 1e-9:
            _add_warning(warnings, f"{label}: '{team_str.strip()}' is not a whole headcount ({total:g}); "
                                   f"rounded half up to {whole}.")
        return whole
    _add_warning(warnings, f"{label}: no number found in '{team_str.strip()}'; assumed 1 person.")
    return 1


_NEGATIVE_RE = re.compile(r"(?<![\w.])[-\u2212]\s*\d|\b(?:minus|negative)\b")
_RANGE_STRIP_RE = re.compile(r"\d+(?:[.,]\d+)?\s*(?:-|\u2013|to)\s*\d+(?:[.,]\d+)?")


def _has_negative_number(text: str) -> bool:
    return bool(_NEGATIVE_RE.search(_RANGE_STRIP_RE.sub(" ", _normalise_text(text or ""))))


def _is_zero_duration(timeline: str) -> bool:
    """True if the timeline states a duration whose every number is zero ("0 months", "0")."""
    tl = _words_to_digits(_normalise_text(timeline or ""), None, "timeline")
    tl = re.sub(r"(\d)\s*(?:-|\u2013)\s*(?=\d)", r"\1-", tl)
    matches = list(_DURATION_RE.finditer(tl))
    if matches:
        nums = []
        for m in matches:
            nums.append(_to_float(m.group("n1")))
            if m.group("n2"):
                nums.append(_to_float(m.group("n2")))
        return all(n == 0 for n in nums)
    bare = re.search(r"(?<![\w.])(\d{1,3})(?![\w])", tl)
    return bare is not None and int(bare.group(1)) == 0


def validate_numeric_inputs(team_qa_size: str, team_dev_size: str, timeline: str) -> dict:
    """Return {field: message} for inputs that must be rejected rather than guessed:
    negative team sizes / durations and zero durations. Empty dict when fine."""
    errors: dict = {}
    for name, value in (("team_qa_size", team_qa_size), ("team_dev_size", team_dev_size)):
        if _has_negative_number(value):
            errors[name] = f"{name} cannot be negative (got '{(value or '').strip()}'); give a headcount of 0 or more."
    if _has_negative_number(timeline):
        errors["timeline"] = f"timeline cannot be negative (got '{(timeline or '').strip()}'); give a positive duration such as '6 months'."
    elif _is_zero_duration(timeline):
        errors["timeline"] = f"timeline must be greater than zero (got '{(timeline or '').strip()}'); give a duration such as '6 months'."
    return errors

# ── Orchestrator ───────────────────────────────────────────────────────────────

def compute_estimation(context: ProjectContext, risk_register: str = "") -> EstimationData:
    """Run the full deterministic pipeline (steps 1-8) and return the result.

    No agent, no LLM — this is the entire numeric core of the Effort
    Estimation Report, callable standalone (e.g. from the MCP server's
    estimate_qa_effort tool) without pulling in agent.py's Pinecone/Mistral/
    OpenAI/Streamlit dependencies.
    """
    data = EstimationData()
    detect_project_type(context, data)
    calculate_baseline(context, data)
    apply_multipliers(context, data)
    pert_breakdown(data)
    team_capacity(context, data)
    risk_buffer(risk_register, data)
    calculate_data_quality(context, data)
    finalize(data)
    return data


_PERSON_DAYS = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:(?:person|man|working)[- ]days?|PDs?|p/d)\b", re.IGNORECASE
)


def _known_person_day_figures(data: EstimationData) -> set:
    values = [
        data.pert_total_optimistic, data.pert_total_most_likely, data.pert_total_pessimistic,
        data.pert_total_expected, data.pert_total_sd, data.available_person_days,
        abs(data.capacity_gap), data.risk_buffer_days, data.final_effort_min,
        data.final_effort_max, data.baseline_effort_min, data.baseline_effort_max,
        data.adjusted_effort_min, data.adjusted_effort_max,
        data.pert_total_expected - 2 * data.pert_total_sd,
        data.pert_total_expected + 2 * data.pert_total_sd,
    ]
    for a in data.pert_activities:
        values += [v for v in a.values() if isinstance(v, (int, float))]
    known = set()
    for v in values:
        known.add(round(v, 1))
    return known


def drop_unverified_person_day_figures(text: str, data: EstimationData) -> str:
    """The LLM narrative must not restate effort totals (live runs showed 24 in
    prose vs 20.5 in the table). Drop every sentence that quotes a person-day
    figure not produced by the deterministic pipeline; lines left empty go away."""
    known = _known_person_day_figures(data)

    def _bad(sentence: str) -> bool:
        return any(round(float(m.group(1)), 1) not in known for m in _PERSON_DAYS.finditer(sentence))

    out_lines = []
    for line in text.split("\n"):
        if not _PERSON_DAYS.search(line):
            out_lines.append(line)
            continue
        kept = [s for s in re.split(r"(?<=[.!?])\s+", line) if not _bad(s)]
        if kept:
            out_lines.append(" ".join(kept))
    return "\n".join(out_lines)
