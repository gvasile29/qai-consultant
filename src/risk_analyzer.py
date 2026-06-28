"""
QAI Consultant — Risk Analyzer
Analyzes project context and generates a structured Risk Register
with Likelihood × Impact matrix and concrete mitigations.

Output is a markdown document saved to output/risk_register_*.md.
The Risk Register is also passed to EffortEstimator to calculate risk buffers.
"""

import os
import re
from pathlib import Path
from datetime import datetime
from agent import QAIAgent, RAG_K_GENERATION
from dialogue import ProjectContext
from logger import get_logger

logger = get_logger(__name__)

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
    """
    Analyzes project context and generates a structured Risk Register.

    Uses RAG to retrieve risk-relevant knowledge (OWASP, ISO 26262, etc.)
    then generates a markdown Risk Register via LLM (Mistral API) with:
    - Risk matrix (Likelihood × Impact)
    - Mitigation strategies per risk
    - Risk-based testing priorities
    """

    def __init__(self, agent: QAIAgent):
        """
        Args:
            agent: Initialized QAIAgent with Pinecone and LLM connections.
        """
        self.agent = agent

    def analyze(self, context: ProjectContext, chunks: list = None) -> tuple:
        """
        Analyze project risks using RAG + LLM and generate a Risk Register.

        Args:
            context: Collected ProjectContext from DialogueManager.
            chunks: Optional pre-fetched knowledge chunks. If None, retrieves
                    from Pinecone using the risk-focused query. Pass pre-fetched
                    chunks to enable parallel RAG retrieval in the pipeline.

        Returns:
            Tuple of (risk_register_markdown: str, sources: list[str]).
        """
        logger.info(f"Analyzing risks for '{context.project_name}'...")
        if chunks is None:
            risk_query = self._build_risk_query(context)
            chunks = self.agent.retrieve_knowledge(risk_query, k=RAG_K_GENERATION)
        knowledge_context = self.agent.format_knowledge_context(chunks)
        logger.info(f"Retrieved {len(chunks)} risk-relevant chunks")

        prompt = build_risk_prompt(context, knowledge_context)
        risk_register = self.agent.ask(prompt, system_prompt=RISK_SYSTEM_PROMPT)
        risk_register = risk_register or ""
        logger.info(f"Risk Register generated ({len(risk_register)} chars)")

        sources = list({
            f"[{(c.metadata or {}).get('category', 'N/A')}] {(c.metadata or {}).get('filename', 'N/A')}"
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

        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = re.sub(r'[^\w\-.]', '_', context.project_name.replace(' ', '_'))
        filename = f"risk_register_{safe_name}_{timestamp}.md"
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
