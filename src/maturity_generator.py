"""
QAI Consultant — QA Maturity Assessment: narrative + save.

Wraps the deterministic src/maturity_core.py rubric with an LLM-written
narrative and the same save()/Article 50(2) marking conventions as the
other generator modules (review_generator.py, risk_analyzer.py). Streamlit/
CLI only — the MCP server never generates text (see mcp_server.py's
docstring and MCP_PLAN.md section 1); this module is not in the MCP
server's import graph.
"""

import re
from pathlib import Path
from datetime import datetime
from typing import Optional

from agent import MISTRAL_MODEL
from ai_disclosure import build_front_matter, with_ai_footer
from maturity_core import MaturityResult
from logger import get_logger

logger = get_logger(__name__)

MATURITY_SYSTEM_PROMPT = """You are QAI Consultant, a senior QA Architect performing a QA process
maturity assessment. A deterministic rubric has already scored the process — you never invent,
change, or contradict the given indicative TMMi level, dimension scores, or findings. Your job is
to explain why they matter (grounded in the TMMi/CMMI/EU AI Act knowledge base provided) and give
the team concrete, prioritized next steps toward the next maturity level.
"""


def build_maturity_prompt(result: MaturityResult, knowledge_context: str) -> str:
    """Build the narrative-generation prompt from an already-computed
    MaturityResult — the LLM explains and prioritizes, it does not re-score."""
    tmmi_text = "\n".join(
        f"- {dim.replace('_', ' ').title()}: {score}/100"
        for dim, score in result.tmmi_dimension_scores.items()
    )
    ai_act_text = "\n".join(
        f"- {dim.replace('_', ' ').title()}: {score}/100"
        for dim, score in result.ai_act_dimension_scores.items()
    ) if result.ai_act_relevant else "Not applicable — no AI/ML system signal detected in the input."

    findings_text = "\n".join(
        f"- [{f.severity.upper()}] ({f.framework}/{f.dimension}) {f.message} (evidence: {f.evidence})"
        for f in result.findings
    ) or "- No findings — every mechanical check passed."

    return f"""
A deterministic rubric has already assessed a QA process description against a TMMi-based process
maturity model{"and EU AI Act Articles 9-15 readiness" if result.ai_act_relevant else ""}. Write a
narrative QA Maturity Assessment report explaining these already-computed results to the team and
prioritizing what to address first toward the next maturity level. Do not invent a different level,
score, or additional findings — use exactly what is given below.

INDICATIVE TMMI LEVEL: {result.indicative_tmmi_level}
DISCLAIMER (include this verbatim in your Summary): {result.disclaimer}

TMMI PROCESS AREA SCORES:
{tmmi_text}

EU AI ACT ARTICLE 9-15 READINESS SCORES:
{ai_act_text}

FINDINGS (deterministic, already computed):
{findings_text}

RELEVANT QA KNOWLEDGE BASE:
{knowledge_context}

Generate the narrative using EXACTLY this structure:

# QA Maturity Assessment

## Summary
2-3 sentences on the indicative maturity level and the single most important next step. Include the
disclaimer above verbatim.

## What's Working Well
Bullet points on the process areas that scored well.

## Priority Gaps
For each Critical and Major finding: explain why it matters (reference the standards in the
knowledge base where relevant) and give a concrete, actionable next step.

## Minor Improvements
Briefly list the Minor findings with suggested next steps.

## References
List the standards/methodologies referenced above.

Be specific — reference the actual dimension/article names and evidence given above rather than
generic advice.
"""


def build_maturity_report_markdown(result: MaturityResult, narrative: str = "") -> str:
    """Deterministic score/findings section + the optional LLM narrative —
    used for both the in-app display and the saved file."""
    lines = [
        "# QA Maturity Assessment",
        "",
        f"**Indicative TMMi Level:** {result.indicative_tmmi_level}",
        "",
        f"> {result.disclaimer}",
        "",
        "## TMMi Process Area Scores",
        "",
        "| Process Area | Score |",
        "|---|---|",
    ]
    for dim, score in result.tmmi_dimension_scores.items():
        lines.append(f"| {dim.replace('_', ' ').title()} | {score}/100 |")

    if result.ai_act_relevant:
        lines.append("")
        lines.append("## EU AI Act Readiness (Articles 9-15)")
        lines.append("")
        lines.append(f"> {result.ai_act_note}")
        lines.append("")
        lines.append("| Article Area | Score |")
        lines.append("|---|---|")
        for dim, score in result.ai_act_dimension_scores.items():
            lines.append(f"| {dim.replace('_', ' ').title()} | {score}/100 |")

    lines.append("")
    lines.append("## Findings")
    lines.append("")
    if not result.findings:
        lines.append("No findings — every mechanical check in the rubric passed.")
    else:
        for finding in result.findings:
            lines.append(
                f"- **[{finding.severity.upper()}]** ({finding.framework}/{finding.dimension}) "
                f"{finding.message} — _evidence: {finding.evidence}_"
            )
    if narrative:
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append(narrative)
    return "\n".join(lines)


def save_maturity_report(markdown_text: str, source_label: str, output_dir: Optional[Path] = None) -> Path:
    """Save a QA maturity assessment report with the same filename-
    sanitization and Article 50(2) front-matter/footer convention as the
    other generators."""
    if output_dir is None:
        output_dir = Path(__file__).resolve().parent.parent / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = re.sub(r'[^\w\-.]', '_', (source_label or "Assessment").replace(' ', '_')) or "Assessment"
    filename = f"maturity_assessment_{safe_name}_{timestamp}.md"
    output_path = output_dir / filename

    front_matter = build_front_matter("QA Maturity Assessment", source_label or "Assessment", MISTRAL_MODEL)
    full_content = f"""{front_matter}

{with_ai_footer(markdown_text)}
"""
    output_path.write_text(full_content, encoding="utf-8")
    return output_path
