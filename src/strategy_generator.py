"""
QAI Consultant — Strategy Generator
Uses the project context and RAG knowledge to generate a Test Strategy document.
"""

from pathlib import Path
from datetime import datetime
from agent import QAIAgent
from dialogue import ProjectContext
from risk_analyzer import RiskAnalyzer

# ── System Prompt ──────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are QAI Consultant, a senior QA Architect with 20+ years of experience.
You generate professional, actionable Test Strategy documents based on:
- The project context provided by the user
- Established QA methodologies (ISTQB, OWASP, IEEE 829, ISO/IEC 25010)
- Industry best practices and real-world experience

Your Test Strategy documents are:
- Practical and tailored to the specific project — never generic
- Based on risk — you prioritize what matters most
- Honest about constraints (team size, timeline, budget)
- Written in clear, professional English

Always reference the specific standards and methodologies that apply to the project.
Always flag risks that are specific to the project type and context.
"""


def build_strategy_prompt(context: ProjectContext, knowledge_context: str) -> str:
    """Build the full prompt for Test Strategy generation."""
    return f"""
Based on the following project context and QA knowledge base, generate a complete and professional Test Strategy document.

PROJECT CONTEXT:
{context.to_summary()}

RELEVANT QA KNOWLEDGE BASE:
{knowledge_context}

Generate a Test Strategy document using EXACTLY this structure:

# Test Strategy — {context.project_name}

## 1. Project Overview
Brief description of the project, its goals, and the testing scope.

## 2. Scope — What Will Be Tested
List the features, modules, and systems that are in scope for testing.

## 3. Scope — What Will NOT Be Tested
List what is explicitly excluded from testing and the reason why.

## 4. Risk Assessment
Identify and rate the top risks (High/Medium/Low) based on the project context.
For each risk: describe it, rate its likelihood and impact, and suggest mitigation.

## 5. Test Types Recommended
List the test types applicable to this project (functional, performance, security, etc.)
For each type: explain why it is needed and at what phase it should be performed.

## 6. Test Approach & Methodology
Describe the overall testing approach, referencing the team's methodology.
Include shift-left recommendations if applicable.

## 7. Entry & Exit Criteria
Define clear criteria for when testing starts and when it is considered complete.

## 8. Resources & Man Power Estimation
Based on team size and timeline, estimate QA effort distribution.
Be honest about gaps or resource constraints.

## 9. Tools & Environment
Recommend specific tools for each test type based on the tech stack.

## 10. Key Risks & Mitigations
Top 3-5 project-specific risks with concrete mitigation strategies.

## 11. References
List the QA standards and methodologies referenced in this strategy.

Be specific, practical, and tailored to this exact project. Avoid generic statements.
"""


class StrategyGenerator:
    """Generates Test Strategy documents using RAG + LLM."""

    def __init__(self, agent: QAIAgent):
        self.agent = agent

    def generate_all(self, context: ProjectContext) -> dict:
        """
        Generate both Test Strategy and Risk Register.
        Returns dict with keys: strategy, risk_register, sources, risk_sources
        """
        print("🔍 Analyzing project risks...")
        risk_analyzer = RiskAnalyzer(self.agent)
        risk_register, risk_sources = risk_analyzer.analyze(context)
        risk_path = risk_analyzer.save(risk_register, context)

        print("📋 Generating Test Strategy...")
        strategy, sources = self.generate(context)
        strategy_path = self.save(strategy, context)

        return {
            "strategy": strategy,
            "strategy_path": strategy_path,
            "sources": sources,
            "risk_register": risk_register,
            "risk_path": risk_path,
            "risk_sources": risk_sources,
        }

    def generate(self, context: ProjectContext) -> tuple:
        """
        Generate a Test Strategy document for the given project context.
        Returns (strategy_markdown, sources)
        """
        print("🔍 Retrieving relevant knowledge from knowledge base...")

        # Build a rich RAG query from project context
        rag_query = context.to_rag_query()
        chunks = self.agent.retrieve_knowledge(rag_query, k=8)
        knowledge_context = self.agent.format_knowledge_context(chunks)

        print(f"✅ Retrieved {len(chunks)} relevant knowledge chunks")
        print("🤖 Generating Test Strategy — this may take a moment...\n")

        # Build and send the prompt
        prompt = build_strategy_prompt(context, knowledge_context)
        strategy = self.agent.ask(prompt, system_prompt=SYSTEM_PROMPT)

        # Extract unique sources
        sources = list({
            f"[{c.metadata.get('category', 'N/A')}] {c.metadata.get('filename', 'N/A')}"
            for c in chunks
        })

        return strategy, sources

    def save(self, strategy: str, context: ProjectContext, output_dir: Path = None) -> Path:
        """Save the generated strategy to a markdown file."""
        if output_dir is None:
            output_dir = Path(__file__).resolve().parent.parent / "output"

        output_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"test_strategy_{context.project_name.replace(' ', '_')}_{timestamp}.md"
        output_path = output_dir / filename

        # Add metadata header
        full_content = f"""---
generated_by: QAI Consultant
date: {datetime.now().strftime("%Y-%m-%d %H:%M")}
project: {context.project_name}
---

{strategy}
"""
        output_path.write_text(full_content, encoding="utf-8")
        return output_path


# ── Quick test ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    from dialogue import DialogueManager

    # Load agent
    agent = QAIAgent()
    generator = StrategyGenerator(agent)

    # Run dialogue
    dialogue = DialogueManager()
    print("QAI Consultant — Strategy Generator Test")
    print("=" * 50)
    print("Answer the questions to generate a Test Strategy.\n")

    while dialogue.has_next_question():
        question = dialogue.get_next_question()
        current, total = dialogue.get_progress()
        print(f"[{current}/{total}] {question['question']}")
        print(f"  Hint: {question['hint']}")
        answer = input("  Your answer: ")
        dialogue.submit_answer(answer)

    context = dialogue.get_context()
    print("\n" + "=" * 50)
    print("✅ Context collected. Generating Test Strategy...\n")

    # Generate strategy
    strategy, sources = generator.generate(context)

    # Save to file
    output_path = generator.save(strategy, context)

    print(strategy)
    print("\n" + "=" * 50)
    print(f"\n📚 Sources used:")
    for s in sources:
        print(f"  - {s}")
    print(f"\n💾 Strategy saved to: {output_path}")
