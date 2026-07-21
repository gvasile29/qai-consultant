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

import re

from pathlib import Path
from datetime import datetime
from logger import get_logger

logger = get_logger(__name__)
from typing import Optional
from agent import MISTRAL_MODEL, QAIAgent
from ai_disclosure import build_front_matter, with_ai_footer
from dialogue import ProjectContext

import effort_core
from effort_core import (
    ACTIVITY_BREAKDOWN,
    BASELINE_QA_PERCENT,
    MAX_PLAUSIBLE_DURATION_DAYS,
    RISK_BUFFER,
    EstimationData,
    compute_estimation,
)

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
        data = compute_estimation(context, risk_register)
        report = self._generate_report(context, data)
        return report, data

    # ── Deterministic pipeline — thin delegating wrappers ──────────────────────
    # The actual logic lives in effort_core.py (no agent/LLM dependency, so it's
    # importable from the MCP server path). Kept here as instance methods, rather
    # than removed, purely for backward compatibility: existing tests call these
    # directly (e.g. est._detect_project_type(context, data)).

    def _detect_project_type(self, context: ProjectContext, data: EstimationData):
        return effort_core.detect_project_type(context, data)

    def _calculate_baseline(self, context: ProjectContext, data: EstimationData):
        return effort_core.calculate_baseline(context, data)

    def _apply_multipliers(self, context: ProjectContext, data: EstimationData):
        return effort_core.apply_multipliers(context, data)

    def _pert_breakdown(self, data: EstimationData):
        return effort_core.pert_breakdown(data)

    def _team_capacity(self, context: ProjectContext, data: EstimationData):
        return effort_core.team_capacity(context, data)

    def _risk_buffer(self, risk_register: str, data: EstimationData):
        return effort_core.risk_buffer(risk_register, data)

    def _calculate_data_quality(self, context: ProjectContext, data: EstimationData):
        return effort_core.calculate_data_quality(context, data)

    def _finalize(self, data: EstimationData):
        return effort_core.finalize(data)

    def _calculate_confidence(self, data: EstimationData) -> str:
        return effort_core.calculate_confidence(data)

    # ── Report Generation ──────────────────────────────────────────────────────

    def _generate_report(self, context: ProjectContext, data: EstimationData) -> str:
        """Build the markdown report from calculated data + LLM narrative."""

        # Build deterministic tables
        multiplier_table = self._build_multiplier_table(data)
        pert_table = self._build_pert_table(data)
        capacity_section = self._build_capacity_section(data)

        # Ask LLM for narrative sections only
        additional_ctx_line = (
            f"ADDITIONAL CONTEXT FROM THE USER: {context.additional_context}\n"
            if context.additional_context else ""
        )
        narrative_prompt = f"""
You are QAI Consultant, a senior QA Architect. Based on the following effort estimation data,
write concise professional narrative for these sections:

PROJECT: {context.project_name} ({context.project_type})
METHODOLOGY: {context.methodology}
QA TEAM: {context.team_qa_size} QA engineers
TIMELINE: {context.timeline}
COMPLIANCE: {context.compliance_requirements}
{additional_ctx_line}TOTAL MULTIPLIERS APPLIED: {data.total_multiplier}%
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

    _NARRATIVE_SECTION_NAMES = ("EXECUTIVE_SUMMARY", "ASSUMPTIONS", "RECOMMENDATIONS")

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
        """Pull one requested section out of the LLM's narrative response.

        The LLM reliably renders each section as its own markdown heading —
        bold, numbered, sometimes with a space instead of the underscore we
        asked for (e.g. "### **2. ASSUMPTIONS**" for "ASSUMPTIONS",
        "EXECUTIVE SUMMARY" for "EXECUTIVE_SUMMARY") rather than the plain
        "LABEL:" this used to assume. A stop condition tied to that exact
        format never matches the (also-decorated) next section, so the
        current section silently swallows every section after it — visible
        as a whole section duplicated verbatim under two headings. Stopping
        at the next *known* section name — regardless of what markdown
        decorates it — fixes that.
        """
        if not text:
            return None
        name = section.replace("_", "[_ ]")
        other_names = "|".join(
            s.replace("_", "[_ ]") for s in self._NARRATIVE_SECTION_NAMES if s != section
        )
        pattern = rf"{name}\**[:\s]*(.*?)(?=[#*\d.\s-]*(?:{other_names})|\Z)"
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return None

    # ── Helpers — thin delegating wrappers (logic in effort_core.py) ───────────

    def _parse_duration(self, timeline: str) -> int:
        return effort_core.parse_duration(timeline)

    def _parse_team_size(self, team_str: str) -> int:
        return effort_core.parse_team_size(team_str)

    def save(self, report: str, context: ProjectContext, output_dir: Optional[Path] = None) -> Path:
        """Save the Effort Estimation Report to a markdown file."""
        if output_dir is None:
            output_dir = Path(__file__).resolve().parent.parent / "output"
        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = re.sub(r'[^\w\-.]', '_', context.project_name.replace(' ', '_'))
        filename = f"effort_estimation_{safe_name}_{timestamp}.md"
        output_path = output_dir / filename

        front_matter = build_front_matter("Effort Estimation Report", context.project_name, MISTRAL_MODEL)
        full_content = f"""{front_matter}

{with_ai_footer(report)}
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
        assert question is not None
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
