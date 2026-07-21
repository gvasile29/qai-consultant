"""
QAI Consultant — QA Document Quality Review: narrative + save.

Wraps the deterministic src/review_core.py rubric with an LLM-written
narrative and the same save()/Article 50(2) marking conventions as the
other generator modules (risk_analyzer.py, strategy_generator.py).
Streamlit/CLI only — the MCP server never generates text (see
mcp_server.py's docstring and MCP_PLAN.md section 1); this module is not
in the MCP server's import graph.
"""

import re
from pathlib import Path
from datetime import datetime
from typing import Optional

from agent import MISTRAL_MODEL
from ai_disclosure import build_front_matter, with_ai_footer
from review_core import ReviewResult
from logger import get_logger

logger = get_logger(__name__)

REVIEW_SYSTEM_PROMPT = """You are QAI Consultant, a senior QA Architect performing a QA document quality review.
A deterministic rubric has already scored the document — you never invent, change,
or contradict the given overall score, dimension scores, or findings. Your job is to
explain why they matter (grounded in the ISTQB/IEEE/ISO knowledge base provided) and
give the document's author concrete, prioritized, actionable fixes.
"""


def build_review_prompt(result: ReviewResult, knowledge_context: str) -> str:
    """Build the narrative-generation prompt from an already-computed
    ReviewResult — the LLM explains and prioritizes, it does not re-score."""
    dimension_text = "\n".join(
        f"- {dim.replace('_', ' ').title()}: {score}/100"
        for dim, score in result.dimension_scores.items()
    )
    findings_text = "\n".join(
        f"- [{f.severity.upper()}] ({f.dimension}) {f.message} (evidence: {f.evidence})"
        for f in result.findings
    ) or "- No findings — every mechanical check passed."

    return f"""
A deterministic rubric has already reviewed an existing QA document (detected type:
{result.doc_type}). Write a narrative Quality Review report explaining these
already-computed results to the document's author and prioritizing what to fix first.
Do NOT invent a different score or additional findings — use exactly what is given below.

OVERALL SCORE: {result.overall_score}/100

DIMENSION SCORES:
{dimension_text}

FINDINGS (deterministic, already computed):
{findings_text}

RELEVANT QA KNOWLEDGE BASE:
{knowledge_context}

Generate the narrative review using EXACTLY this structure:

# QA Document Quality Review

## Summary
2-3 sentences on overall quality and the single most important fix.

## What's Working Well
Bullet points on the dimensions/sections that scored well.

## Priority Fixes
For each Critical and Major finding: explain why it matters (reference the standards
in the knowledge base where relevant) and give a concrete, actionable fix.

## Minor Improvements
Briefly list the Minor findings with suggested fixes.

## References
List the standards/methodologies referenced above.

Be specific — reference the actual dimension names and evidence given above rather
than generic advice.
"""


def build_review_report_markdown(result: ReviewResult, narrative: str = "") -> str:
    """Deterministic score/findings section + the optional LLM narrative —
    used for both the in-app display and the saved file."""
    lines = [
        "# QA Document Quality Review",
        "",
        f"**Detected document type:** {result.doc_type}",
        f"**Overall score:** {result.overall_score}/100",
        "",
        "## Dimension Scores",
        "",
        "| Dimension | Score |",
        "|---|---|",
    ]
    for dim, score in result.dimension_scores.items():
        lines.append(f"| {dim.replace('_', ' ').title()} | {score}/100 |")
    lines.append("")
    lines.append("## Findings")
    lines.append("")
    if not result.findings:
        lines.append("No findings — every mechanical check in the rubric passed.")
    else:
        for finding in result.findings:
            lines.append(
                f"- **[{finding.severity.upper()}]** ({finding.dimension}) "
                f"{finding.message} — _evidence: {finding.evidence}_"
            )
    if narrative:
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append(narrative)
    return "\n".join(lines)


def save_review_report(markdown_text: str, source_label: str, output_dir: Optional[Path] = None) -> Path:
    """Save a quality review report with the same filename-sanitization and
    Article 50(2) front-matter/footer convention as the other generators."""
    if output_dir is None:
        output_dir = Path(__file__).resolve().parent.parent / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = re.sub(r'[^\w\-.]', '_', (source_label or "Document").replace(' ', '_')) or "Document"
    filename = f"quality_review_{safe_name}_{timestamp}.md"
    output_path = output_dir / filename

    front_matter = build_front_matter("QA Document Quality Review", source_label or "Document", MISTRAL_MODEL)
    full_content = f"""{front_matter}

{with_ai_footer(markdown_text)}
"""
    output_path.write_text(full_content, encoding="utf-8")
    return output_path
