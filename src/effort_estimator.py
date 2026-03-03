"""
QAI Consultant — Effort Estimator
Generates a QA Effort Estimation Report using a deterministic calculation
pipeline, with LLM used only for narrative sections (summary, assumptions,
recommendations).

Calculation pipeline:
  1. Parse timeline and team size from free-text dialogue answers
  2. Detect project type → baseline QA percentage (industry benchmarks)
  3. Apply complexity multipliers (compliance, automation, team size, integrations)
  4. PERT analysis across 9 QA activity areas
  5. Team capacity calculation (available person-days at 75% utilization)
  6. Risk buffer from Risk Register (critical/high/medium risk counts)
  7. Confidence score (0-100) from 4 factors: PERT spread, capacity gap,
     data quality, multiplier magnitude

Output: markdown report saved to output/effort_estimation_*.md
"""

import os
import re
os.environ["ANONYMIZED_TELEMETRY"] = "False"
os.environ["CHROMA_TELEMETRY"] = "False"

from pathlib import Path
from datetime import datetime
from logger import get_logger

logger = get_logger(__name__)
from dataclasses import dataclass, field
from typing import Optional
from agent import QAIAgent
from dialogue import ProjectContext

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


# ── Effort Estimator ───────────────────────────────────────────────────────────

class EffortEstimator:
    """Generates QA Effort Estimation Reports using deterministic logic + LLM narrative."""

    def __init__(self, agent: QAIAgent):
        self.agent = agent

    def estimate(self, context: ProjectContext, risk_register: str = "") -> tuple:
        """
        Generate an Effort Estimation Report.
        Returns (report_markdown, estimation_data)
        """
        data = EstimationData()

        self._detect_project_type(context, data)
        self._calculate_baseline(context, data)
        self._apply_multipliers(context, data)
        self._pert_breakdown(data)
        self._team_capacity(context, data)
        self._risk_buffer(risk_register, data)
        self._calculate_data_quality(context, data)
        self._finalize(data)

        report = self._generate_report(context, data)
        return report, data

    # ── Step 1: Detect project type ────────────────────────────────────────────

    def _detect_project_type(self, context: ProjectContext, data: EstimationData):
        pt = context.project_type.lower()
        meth = context.methodology.lower()

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

    # ── Step 2: Calculate baseline ─────────────────────────────────────────────

    def _calculate_baseline(self, context: ProjectContext, data: EstimationData):
        # Look up baseline percentage
        key = (data.project_type_detected, data.methodology_detected)
        if key not in BASELINE_QA_PERCENT:
            key = (data.project_type_detected, "")
        if key not in BASELINE_QA_PERCENT:
            key = ("default", "")

        data.baseline_qa_percent_min, data.baseline_qa_percent_max = BASELINE_QA_PERCENT[key]

        # Parse project duration
        data.project_duration_days = self._parse_duration(context.timeline)

        # Parse team sizes
        data.qa_team_size = self._parse_team_size(context.team_qa_size)
        dev_size = self._parse_team_size(context.team_dev_size)
        data.team_total_size = data.qa_team_size + dev_size

        # Total project effort estimate (dev + QA)
        # Assume developer works ~200 days/year at 75% utilization
        dev_days = dev_size * data.project_duration_days * 0.75

        # QA baseline = dev_days * (qa_pct / (1 - qa_pct))
        mid_pct = (data.baseline_qa_percent_min + data.baseline_qa_percent_max) / 2 / 100
        if mid_pct < 1:
            qa_multiplier_min = data.baseline_qa_percent_min / (100 - data.baseline_qa_percent_min)
            qa_multiplier_max = data.baseline_qa_percent_max / (100 - data.baseline_qa_percent_max)
        else:
            qa_multiplier_min = 0.2
            qa_multiplier_max = 0.3

        data.baseline_effort_min = round(dev_days * qa_multiplier_min, 1)
        data.baseline_effort_max = round(dev_days * qa_multiplier_max, 1)

    # ── Step 3: Apply multipliers ──────────────────────────────────────────────

    def _apply_multipliers(self, context: ProjectContext, data: EstimationData):
        compliance = context.compliance_requirements.lower()
        automation = context.existing_automation.lower()
        risks = context.known_risks.lower()
        stack = context.tech_stack.lower()

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

    # ── Step 4: PERT breakdown per activity ────────────────────────────────────

    def _pert_breakdown(self, data: EstimationData):
        mid_effort = (data.adjusted_effort_min + data.adjusted_effort_max) / 2

        # Skip automation setup if existing automation
        activities = {k: v for k, v in ACTIVITY_BREAKDOWN.items()
                      if k != "Automation Framework Setup" or data.total_multiplier > 0}

        # Normalize percentages to sum to 100
        total_o = total_m = total_p = 0

        for activity, (pct_lo, pct_hi) in activities.items():
            pct_mid = (pct_lo + pct_hi) / 2
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

    # ── Step 5: Team capacity ──────────────────────────────────────────────────

    def _team_capacity(self, context: ProjectContext, data: EstimationData):
        data.utilization_rate = 0.75
        data.available_person_days = round(
            data.qa_team_size * data.project_duration_days * data.utilization_rate, 1
        )
        data.capacity_gap = round(
            data.available_person_days - data.pert_total_expected, 1
        )

    # ── Step 6: Risk buffer ────────────────────────────────────────────────────

    def _risk_buffer(self, risk_register: str, data: EstimationData):
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

    # ── Step 6.5: Data quality score ──────────────────────────────────────────

    def _calculate_data_quality(self, context: ProjectContext, data: EstimationData):
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

    # ── Step 7: Finalize ───────────────────────────────────────────────────────

    def _finalize(self, data: EstimationData):
        data.final_effort_min = round(data.pert_total_optimistic + data.risk_buffer_days * 0.5, 1)
        data.final_effort_max = round(data.pert_total_pessimistic + data.risk_buffer_days, 1)
        data.confidence_level = self._calculate_confidence(data)

    def _calculate_confidence(self, data: EstimationData) -> str:
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

        # ── Factor 1: PERT spread ratio (40 pts) ──────────────────────────────
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

        # ── Factor 2: Capacity gap ratio (30 pts) ─────────────────────────────
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

        # ── Factor 3: Data quality (20 pts) ───────────────────────────────────
        # Uses pre-calculated data_quality_score (0-20) set during estimation
        score += min(20, max(0, data.data_quality_score))

        # ── Factor 4: Multiplier magnitude (10 pts) ───────────────────────────
        # total_multiplier is the sum of all % adjustments applied
        # 0% → 10 pts; 50% → 5 pts; ≥100% → 0 pts
        magnitude_score = max(0, 10 - int(data.total_multiplier / 10))
        score += magnitude_score

        # ── Map score to label ─────────────────────────────────────────────────
        data.confidence_score = score
        if score >= 70:
            return "High"
        elif score >= 40:
            return "Medium"
        else:
            return "Low"

    # ── Report Generation ──────────────────────────────────────────────────────

    def _generate_report(self, context: ProjectContext, data: EstimationData) -> str:
        """Build the markdown report from calculated data + LLM narrative."""

        # Build deterministic tables
        multiplier_table = self._build_multiplier_table(data)
        pert_table = self._build_pert_table(data)
        capacity_section = self._build_capacity_section(data)

        # Ask LLM for narrative sections only
        narrative_prompt = f"""
You are QAI Consultant, a senior QA Architect. Based on the following effort estimation data,
write concise professional narrative for these sections:

PROJECT: {context.project_name} ({context.project_type})
METHODOLOGY: {context.methodology}
QA TEAM: {context.team_qa_size} QA engineers
TIMELINE: {context.timeline}
COMPLIANCE: {context.compliance_requirements}
TOTAL MULTIPLIERS APPLIED: {data.total_multiplier}%
FINAL EFFORT RANGE: {data.final_effort_min}–{data.final_effort_max} person-days
CONFIDENCE: {data.confidence_level}
CAPACITY GAP: {"SURPLUS of " + str(data.capacity_gap) + " days" if data.capacity_gap >= 0 else "DEFICIT of " + str(abs(data.capacity_gap)) + " days"}

Write the following sections (keep each concise — 3-5 sentences max):
1. EXECUTIVE_SUMMARY: Overall effort profile and key drivers
2. ASSUMPTIONS: Key assumptions made in this estimate (4-6 bullet points)
3. RECOMMENDATIONS: Top 3-4 actionable recommendations for this specific project
"""
        narrative = self.agent.ask(narrative_prompt)
        exec_summary, assumptions, recommendations = self._parse_narrative(narrative)

        # Assemble final report
        report = f"""# Effort Estimation Report — {context.project_name}

## 1. Executive Summary

{exec_summary}

| Metric | Value |
|---|---|
| **Final Effort Range** | {data.final_effort_min} – {data.final_effort_max} person-days |
| **PERT Expected Effort** | {data.pert_total_expected} person-days |
| **Risk Buffer** | {data.risk_buffer_days} person-days |
| **Available Capacity** | {data.available_person_days} person-days |
| **Capacity Gap** | {"✅ Surplus: " + str(data.capacity_gap) + " days" if data.capacity_gap >= 0 else "⚠️ Deficit: " + str(abs(data.capacity_gap)) + " days"} |
| **Confidence Level** | {data.confidence_level} (score: {data.confidence_score}/100) |

---

## 2. Baseline Calculation

- **Project Type Detected:** {data.project_type_detected.title()}
- **Methodology Detected:** {data.methodology_detected.title() or "General"}
- **Baseline QA %:** {data.baseline_qa_percent_min}% – {data.baseline_qa_percent_max}% of total project effort
- **Project Duration:** ~{data.project_duration_days} working days
- **Team:** {data.qa_team_size} QA + {data.team_total_size - data.qa_team_size} developers
- **Baseline QA Effort:** {data.baseline_effort_min} – {data.baseline_effort_max} person-days

---

## 3. Complexity Adjustments

{multiplier_table}

**Total adjustment: +{data.total_multiplier}%**
**Adjusted effort: {data.adjusted_effort_min} – {data.adjusted_effort_max} person-days**

---

## 4. Activity Breakdown (PERT)

{pert_table}

**95% confidence range: {round(data.pert_total_expected - 2*data.pert_total_sd, 1)} – {round(data.pert_total_expected + 2*data.pert_total_sd, 1)} person-days**

---

## 5. Team Capacity Analysis

{capacity_section}

---

## 6. Risk Buffer

- **Risk buffer applied:** {data.risk_buffer_days} person-days
- **Based on:** Risk Register findings (critical/high/medium risks identified)
- **Final effort range:** {data.final_effort_min} – {data.final_effort_max} person-days

---

## 7. Assumptions & Constraints

{assumptions}

---

## 8. Recommendations

{recommendations}
"""
        return report

    def _build_multiplier_table(self, data: EstimationData) -> str:
        if not data.multipliers:
            return "_No complexity multipliers applied — standard baseline used._"
        rows = ["| Reason | Adjustment |", "|---|---|"]
        for reason, pct in data.multipliers:
            rows.append(f"| {reason} | +{pct}% |")
        return "\n".join(rows)

    def _build_pert_table(self, data: EstimationData) -> str:
        rows = [
            "| Activity | Optimistic | Most Likely | Pessimistic | PERT Expected | SD |",
            "|---|---|---|---|---|---|",
        ]
        for a in data.pert_activities:
            rows.append(
                f"| {a['activity']} | {a['optimistic']}d | {a['most_likely']}d | "
                f"{a['pessimistic']}d | **{a['expected']}d** | ±{a['sd']}d |"
            )
        rows.append(
            f"| **TOTAL** | **{data.pert_total_optimistic}d** | **{data.pert_total_most_likely}d** | "
            f"**{data.pert_total_pessimistic}d** | **{data.pert_total_expected}d** | **±{data.pert_total_sd}d** |"
        )
        return "\n".join(rows)

    def _build_capacity_section(self, data: EstimationData) -> str:
        gap_status = (
            f"✅ **Surplus:** {data.capacity_gap} person-days available above estimate"
            if data.capacity_gap >= 0
            else f"⚠️ **Deficit:** {abs(data.capacity_gap)} person-days short — action required"
        )
        return f"""- **QA Team Size:** {data.qa_team_size} engineers
- **Project Duration:** {data.project_duration_days} working days
- **Utilization Rate:** {int(data.utilization_rate * 100)}%
- **Available Capacity:** {data.available_person_days} person-days
- **PERT Expected Need:** {data.pert_total_expected} person-days
- {gap_status}"""

    def _parse_narrative(self, narrative: str) -> tuple:
        """Extract narrative sections from LLM response."""
        exec_summary = self._extract_section(narrative, "EXECUTIVE_SUMMARY") or \
            "QA effort estimate generated based on project context and industry benchmarks."
        assumptions = self._extract_section(narrative, "ASSUMPTIONS") or \
            "- Standard working days assumed (8h/day)\n- 75% utilization rate for QA engineers"
        recommendations = self._extract_section(narrative, "RECOMMENDATIONS") or \
            "- Prioritize testing based on identified risks\n- Invest in test automation early"
        return exec_summary, assumptions, recommendations

    def _extract_section(self, text: str, section: str) -> Optional[str]:
        pattern = rf"{section}[:\s]*(.*?)(?=\n[A-Z_]{{3,}}[:\s]|\Z)"
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return None

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _parse_duration(self, timeline: str) -> int:
        """Parse timeline string to working days."""
        tl = timeline.lower()
        if any(k in tl for k in ["year", "yr"]):
            match = re.search(r"(\d+\.?\d*)\s*(?:year|yr)", tl)
            years = float(match.group(1)) if match else 1
            return int(years * 230)
        if "month" in tl:
            match = re.search(r"(\d+)", tl)
            months = int(match.group(1)) if match else 6
            return months * 21
        if "week" in tl:
            match = re.search(r"(\d+)", tl)
            weeks = int(match.group(1)) if match else 4
            return weeks * 5
        # Try to extract a bare number (assume months)
        match = re.search(r"(\d+)", tl)
        if match:
            return int(match.group(1)) * 21
        return 130  # default: ~6 months

    def _parse_team_size(self, team_str: str) -> int:
        """Parse team size string to integer."""
        if not team_str:
            return 1
        ts = team_str.lower()
        # Handle "no dedicated QA" etc.
        if any(k in ts for k in ["no dedicated", "none", "developers test"]):
            return 0
        numbers = re.findall(r"\d+", ts)
        if numbers:
            return sum(int(n) for n in numbers)
        return 1

    def save(self, report: str, context: ProjectContext, output_dir: Path = None) -> Path:
        """Save the Effort Estimation Report to a markdown file."""
        if output_dir is None:
            output_dir = Path(__file__).resolve().parent.parent / "output"
        output_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"effort_estimation_{context.project_name.replace(' ', '_')}_{timestamp}.md"
        output_path = output_dir / filename

        full_content = f"""---
generated_by: QAI Consultant
date: {datetime.now().strftime("%Y-%m-%d %H:%M")}
project: {context.project_name}
document_type: Effort Estimation Report
---

{report}
"""
        output_path.write_text(full_content, encoding="utf-8")
        return output_path


# ── Quick test ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    from dialogue import DialogueManager

    agent = QAIAgent()
    estimator = EffortEstimator(agent)

    dialogue = DialogueManager()
    print("QAI Consultant — Effort Estimator Test")
    print("=" * 50)

    while dialogue.has_next_question():
        question = dialogue.get_next_question()
        current, total = dialogue.get_progress()
        print(f"[{current}/{total}] {question['question']}")
        print(f"  Hint: {question['hint']}")
        answer = input("  Your answer: ")
        dialogue.submit_answer(answer)

    context = dialogue.get_context()
    print("\n✅ Estimating effort...\n")

    report, data = estimator.estimate(context)
    output_path = estimator.save(report, context)

    print(report)
    print(f"\n💾 Report saved to: {output_path}")
    print(f"\n📊 Summary: {data.final_effort_min}–{data.final_effort_max} person-days")
    print(f"   Confidence: {data.confidence_level}")
    print(f"   Capacity gap: {'+' if data.capacity_gap >= 0 else ''}{data.capacity_gap} days")
