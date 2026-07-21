"""
QAI Consultant — Deterministic Effort Estimation Core.

The PERT/multiplier/confidence calculation pipeline extracted out of
EffortEstimator, with zero agent/LLM dependency in its import graph. This is
what the MCP server's ``estimate_qa_effort`` tool calls directly (v3.0):
the client LLM writes its own narrative from these numbers, so the MCP path
never needs ``agent.py`` (which pulls Pinecone/Mistral/OpenAI/Streamlit).

``EffortEstimator`` (effort_estimator.py) delegates here for the numbers and
adds the LLM narrative on top for the Streamlit/CLI report. Its private
``_foo`` methods are thin wrappers kept for backward compatibility with
existing tests that call them directly — the actual logic lives here.

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

from dialogue import ProjectContext

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
    capacity_gap: float = 0  # positive = surplus, negative = deficit

    # Risk buffer
    risk_buffer_days: float = 0
    final_effort_min: float = 0
    final_effort_max: float = 0

    # Confidence
    confidence_level: str = "Medium"
    data_quality_score: int = 20   # 0-20; calculated from dialogue completeness
    confidence_score: int = 0      # raw score 0-100 (for debugging/display)


# ── Step 1: Detect project type ────────────────────────────────────────────────

def detect_project_type(context: ProjectContext, data: EstimationData) -> None:
    pt = (context.project_type or "").lower()
    meth = (context.methodology or "").lower()

    # Detect project type
    if any(k in pt for k in ["embedded", "firmware", "automotive"]):
        data.project_type_detected = "embedded"
    elif any(k in pt for k in ["mobile", "ios", "android"]):
        data.project_type_detected = "mobile"
    elif any(k in pt for k in ["api", "microservice", "backend", "rest"]):
        data.project_type_detected = "api"
    elif any(k in pt for k in ["web", "browser", "frontend"]):
        data.project_type_detected = "web"
    elif any(k in pt for k in ["desktop"]):
        data.project_type_detected = "desktop"
    elif any(k in pt for k in ["data", "ml", "machine learning", "ai"]):
        data.project_type_detected = "data"
    else:
        data.project_type_detected = "default"

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

    # Parse project duration
    data.project_duration_days = parse_duration(context.timeline)

    # Parse team sizes
    data.qa_team_size = parse_team_size(context.team_qa_size)
    dev_size = parse_team_size(context.team_dev_size)
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

    # Automation multipliers
    no_automation = any(k in automation for k in ["no", "nothing", "none", "not yet", "greenfield"])
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

    total_o = total_m = total_p = 0.0

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

    data.pert_total_optimistic = round(total_o, 1)
    data.pert_total_most_likely = round(total_m, 1)
    data.pert_total_pessimistic = round(total_p, 1)
    data.pert_total_expected = round((total_o + 4 * total_m + total_p) / 6, 1)
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


# ── Step 6: Risk buffer ─────────────────────────────────────────────────────────

def risk_buffer(risk_register: str, data: EstimationData) -> None:
    if not risk_register:
        data.risk_buffer_days = round(data.pert_total_expected * 0.15, 1)
        return

    rr_lower = risk_register.lower()
    buffer = 0

    # Count risk levels mentioned in the risk register
    critical_count = rr_lower.count("critical")
    high_count = rr_lower.count("| high") + rr_lower.count("risk level: high")
    medium_count = rr_lower.count("| medium") + rr_lower.count("risk level: medium")

    buffer += critical_count * RISK_BUFFER["critical"]
    buffer += high_count * RISK_BUFFER["high"]
    buffer += medium_count * RISK_BUFFER["medium"]

    # Cap buffer at 35% of expected effort
    max_buffer = data.pert_total_expected * 0.35
    data.risk_buffer_days = round(min(buffer, max_buffer), 1)


# ── Step 6.5: Data quality score ────────────────────────────────────────────────

def calculate_data_quality(context: ProjectContext, data: EstimationData) -> None:
    """
    Score dialogue completeness (0-20 pts).
    Vague or missing answers reduce confidence in the estimate.

    Scoring:
      - 5 key fields checked: timeline, team_qa_size, team_dev_size,
        compliance_requirements, existing_automation
      - Each field: 4 pts if specific, 2 pts if vague, 0 pts if empty/unknown
    """
    VAGUE_KEYWORDS = {"tbd", "unknown", "not sure", "don't know", "n/a",
                      "na", "none", "?", "unclear", "maybe", "to be determined"}
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
        elif any(vague in field_val.lower() for vague in VAGUE_KEYWORDS):
            score += 2
        else:
            score += 4

    data.data_quality_score = score


# ── Step 7: Finalize ─────────────────────────────────────────────────────────────

def finalize(data: EstimationData) -> None:
    data.final_effort_min = round(data.pert_total_optimistic + data.risk_buffer_days * 0.5, 1)
    data.final_effort_max = round(data.pert_total_pessimistic + data.risk_buffer_days, 1)
    data.confidence_level = calculate_confidence(data)


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
    score = 0

    # ── Factor 1: PERT spread ratio (40 pts) ──────────────────────────────────
    # spread_ratio = (P - O) / E — lower is better (less uncertainty)
    if data.pert_total_expected > 0:
        spread_ratio = (data.pert_total_pessimistic - data.pert_total_optimistic) / data.pert_total_expected
        # spread_ratio < 1.0 → very tight → 40 pts
        # spread_ratio 1.0-2.0 → moderate → 20-39 pts
        # spread_ratio 2.0-3.0 → wide → 5-19 pts
        # spread_ratio > 3.0 → very wide → 0 pts
        if spread_ratio < 1.0:
            score += 40
        elif spread_ratio < 2.0:
            score += int(40 - (spread_ratio - 1.0) * 20)   # 20-39
        elif spread_ratio < 3.0:
            score += int(20 - (spread_ratio - 2.0) * 15)   # 5-19
        else:
            score += 0

    # ── Factor 2: Capacity gap ratio (30 pts) ───────────────────────────────────
    # gap_ratio = capacity_gap / expected_effort
    # positive (surplus) → good; negative (deficit) → bad
    if data.pert_total_expected > 0:
        gap_ratio = data.capacity_gap / data.pert_total_expected
        if gap_ratio >= 0.3:
            score += 30    # comfortable surplus (≥30% buffer)
        elif gap_ratio >= 0.0:
            score += int(15 + gap_ratio / 0.3 * 15)   # 15-30
        elif gap_ratio >= -0.3:
            score += int(15 + gap_ratio / 0.3 * 15)   # 0-14  (mild deficit)
        else:
            score += 0     # severe deficit (>30% short)

    # ── Factor 3: Data quality (20 pts) ─────────────────────────────────────────
    # Uses pre-calculated data_quality_score (0-20) set during estimation
    score += min(20, max(0, data.data_quality_score))

    # ── Factor 4: Multiplier magnitude (10 pts) ─────────────────────────────────
    # total_multiplier is the sum of all % adjustments applied
    # 0% → 10 pts; 50% → 5 pts; ≥100% → 0 pts
    magnitude_score = max(0, 10 - int(data.total_multiplier / 10))
    score += magnitude_score

    # ── Absolute magnitude guard ─────────────────────────────────────────────────
    # However well the four factors score, a physically-implausible duration
    # must never read "High" — this is a floor, not a fifth scored factor.
    if data.project_duration_days > MAX_PLAUSIBLE_DURATION_DAYS and score >= 70:
        score = 69

    # ── Map score to label ───────────────────────────────────────────────────────
    data.confidence_score = score
    if score >= 70:
        return "High"
    elif score >= 40:
        return "Medium"
    else:
        return "Low"


# ── Helpers ──────────────────────────────────────────────────────────────────────

def parse_duration(timeline: str) -> int:
    """Parse timeline string to working days.

    A bare 4+ digit number (e.g. "2026") is a calendar year mentioned
    alongside a target date, never a month/week count — excluded via
    `\\b(\\d{1,3})\\b` so "release in June 2026" doesn't parse as 2026
    months. The final result is clamped to MAX_PLAUSIBLE_DURATION_DAYS
    as a safety net against any other mis-parse.
    """
    if not timeline:
        return 130
    tl = timeline.lower()
    if any(k in tl for k in ["year", "yr"]):
        match = re.search(r"(\d+\.?\d*)\s*(?:year|yr)", tl)
        years = float(match.group(1)) if match else 1
        days = int(years * 230)
    else:
        num_pattern = r"\b(\d{1,3})\b"  # 1-3 digits only; excludes 4-digit years
        if "month" in tl:
            match = re.search(num_pattern, tl)
            months = int(match.group(1)) if match else 6
            days = months * 21
        elif "week" in tl:
            match = re.search(num_pattern, tl)
            weeks = int(match.group(1)) if match else 4
            days = weeks * 5
        else:
            match = re.search(num_pattern, tl)
            days = int(match.group(1)) * 21 if match else 130  # default: ~6 months
    return min(days, MAX_PLAUSIBLE_DURATION_DAYS)


def parse_team_size(team_str: str) -> int:
    """Parse team size string to integer.

    An "A, or B" clause restates the same team two ways (a headcount
    alternative, e.g. "3 frontend + 2 backend, or 5 full-stack") rather
    than describing additional people — only the numbers before the
    first standalone "or" are summed, so a restatement isn't double-counted.
    """
    if not team_str:
        return 1
    ts = team_str.lower()
    # Handle "no dedicated QA" etc.
    if any(k in ts for k in ["no dedicated", "none", "developers test"]):
        return 0
    first_alternative = re.split(r"\bor\b", ts)[0]
    numbers = re.findall(r"\d+", first_alternative)
    if numbers:
        return sum(int(n) for n in numbers)
    return 1


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
