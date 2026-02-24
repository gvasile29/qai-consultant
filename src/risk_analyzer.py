"""
QAI Consultant — Risk Analyzer Module
Automatically analyzes project context and generates a Risk Register
with Likelihood vs Impact matrix and concrete mitigations.
"""

import os
os.environ["ANONYMIZED_TELEMETRY"] = "False"
os.environ["CHROMA_TELEMETRY"] = "False"

from pathlib import Path
from datetime import datetime
from agent import QAIAgent
from dialogue import ProjectContext

# ── System Prompt ──────────────────────────────────────────────────────────────

RISK_SYSTEM_PROMPT = """You are QAI Consultant, a senior QA Architect and Risk Management expert.
You analyze software projects and identify testing risks based on:
- Project type, tech stack, and team constraints
- Known industry risks for specific domains
- Compliance and regulatory requirements
- Team size and experience relative to project complexity

Your risk analysis is:
- Specific to the project — never generic
- Honest about likelihood and impact
- Actionable — every risk has a concrete mitigation
- Prioritized — Critical risks are called out clearly
"""

# ── Risk Prompt Builder ────────────────────────────────────────────────────────

def build_risk_prompt(context: ProjectContext, knowledge_context: str) -> str:
    return f"""
Analyze the following project and generate a comprehensive Risk Register for QA testing.

PROJECT CONTEXT:
{context.to_summary()}

RELEVANT QA KNOWLEDGE BASE:
{knowledge_context}

Generate a Risk Register using EXACTLY this structure:

# Risk Register — {context.project_name}

## Executive Summary
2-3 sentences summarizing the overall risk profile of this project.
State clearly if the project is Low / Medium / High / Critical risk overall.

## Risk Matrix Overview

Provide a summary table:

| Risk ID | Risk Description | Likelihood | Impact | Risk Level | Priority |
|---|---|---|---|---|---|
| R01 | ... | High/Medium/Low | High/Medium/Low | Critical/High/Medium/Low | 1/2/3/... |

(List ALL identified risks sorted by priority)

## Detailed Risk Analysis

For each risk, provide:

### R01 — [Risk Title]
- **Category:** [Technical / Process / Compliance / Resource / External]
- **Description:** What is the risk and why does it exist for this project?
- **Likelihood:** High / Medium / Low — explain why
- **Impact:** High / Medium / Low — explain what happens if it materializes
- **Risk Level:** Critical / High / Medium / Low
- **Early Warning Signs:** What signals indicate this risk is materializing?
- **Mitigation Strategy:** Concrete, specific actions to reduce this risk
- **Contingency Plan:** What to do if the risk materializes despite mitigation

## Risk-Based Testing Priorities

Based on the risk analysis above, testing effort should be allocated as follows:

| Priority | Area to Test | Risk Level | Recommended Test Types |
|---|---|---|---|
| 1 | ... | Critical | ... |
| 2 | ... | High | ... |

## Recommendations for QA Strategy

Top 3-5 specific recommendations for this project based on the risk profile.

Be specific, practical, and tailored to this exact project context.
Reference relevant standards (ISO 26262, OWASP, ISTQB) where applicable.
"""


# ── Risk Analyzer ──────────────────────────────────────────────────────────────

class RiskAnalyzer:
    """Analyzes project context and generates a Risk Register."""

    def __init__(self, agent: QAIAgent):
        self.agent = agent

    def analyze(self, context: ProjectContext) -> tuple:
        """
        Analyze project risks and generate a Risk Register.
        Returns (risk_register_markdown, sources)
        """
        # Build RAG query focused on risks
        risk_query = self._build_risk_query(context)
        chunks = self.agent.retrieve_knowledge(risk_query, k=8)
        knowledge_context = self.agent.format_knowledge_context(chunks)

        # Generate risk register
        prompt = build_risk_prompt(context, knowledge_context)
        risk_register = self.agent.ask(prompt, system_prompt=RISK_SYSTEM_PROMPT)

        sources = list({
            f"[{c.metadata.get('category', 'N/A')}] {c.metadata.get('filename', 'N/A')}"
            for c in chunks
        })

        return risk_register, sources

    def _build_risk_query(self, context: ProjectContext) -> str:
        """Build a risk-focused RAG query from project context."""
        parts = [
            f"risk based testing {context.project_type}",
            f"testing risks {context.methodology}",
        ]
        if context.compliance_requirements and context.compliance_requirements.lower() not in ["no", "none", "n/a", ""]:
            parts.append(f"compliance risks {context.compliance_requirements}")
        if context.known_risks:
            parts.append(f"risk analysis {context.known_risks}")
        if context.tech_stack:
            parts.append(f"testing risks {context.tech_stack}")
        return " | ".join(parts)

    def save(self, risk_register: str, context: ProjectContext, output_dir: Path = None) -> Path:
        """Save the generated Risk Register to a markdown file."""
        if output_dir is None:
            output_dir = Path(__file__).resolve().parent.parent / "output"

        output_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"risk_register_{context.project_name.replace(' ', '_')}_{timestamp}.md"
        output_path = output_dir / filename

        full_content = f"""---
generated_by: QAI Consultant
date: {datetime.now().strftime("%Y-%m-%d %H:%M")}
project: {context.project_name}
document_type: Risk Register
---

{risk_register}
"""
        output_path.write_text(full_content, encoding="utf-8")
        return output_path


# ── Quick test ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    from dialogue import DialogueManager

    agent = QAIAgent()
    analyzer = RiskAnalyzer(agent)

    dialogue = DialogueManager()
    print("QAI Consultant — Risk Analyzer Test")
    print("=" * 50)

    while dialogue.has_next_question():
        question = dialogue.get_next_question()
        current, total = dialogue.get_progress()
        print(f"[{current}/{total}] {question['question']}")
        print(f"  Hint: {question['hint']}")
        answer = input("  Your answer: ")
        dialogue.submit_answer(answer)

    context = dialogue.get_context()
    print("\n" + "=" * 50)
    print("✅ Analyzing risks...\n")

    risk_register, sources = analyzer.analyze(context)
    output_path = analyzer.save(risk_register, context)

    print(risk_register)
    print("\n📚 Sources used:")
    for s in sources:
        print(f"  - {s}")
    print(f"\n💾 Risk Register saved to: {output_path}")
