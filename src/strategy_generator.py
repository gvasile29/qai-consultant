"""
QAI Consultant — Strategy Generator
Generates professional Test Strategy documents using RAG + LLM.

Orchestrates the full generation pipeline:
  1. Risk Register (RiskAnalyzer)
  2. Effort Estimation Report (EffortEstimator)
  3. Test Strategy (LLM + RAG)

Output files are saved as timestamped markdown files in output/.
"""

import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from datetime import datetime
from agent import QAIAgent, RAG_K_GENERATION
from dialogue import ProjectContext
from risk_analyzer import RiskAnalyzer
from test_plan_generator import TestPlanGenerator
from effort_estimator import EffortEstimator
from logger import get_logger

logger = get_logger(__name__)

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
    """
    Generates Test Strategy documents using RAG-augmented LLM generation.

    Retrieves relevant QA knowledge from Pinecone (k=RAG_K_GENERATION chunks),
    builds a structured prompt, and generates a markdown Test Strategy
    grounded in ISTQB, IEEE 829, OWASP, and ISO/IEC 25010 methodologies.
    """

    def __init__(self, agent: QAIAgent):
        """
        Args:
            agent: Initialized QAIAgent with Pinecone and LLM connections.
        """
        self.agent = agent

    def generate_all(self, context: ProjectContext) -> dict:
        """
        Run the full generation pipeline: Risk Register → Effort Estimation → Test Strategy.

        Args:
            context: Collected ProjectContext from DialogueManager.

        Returns:
            Dict with keys: strategy, strategy_path, sources, risk_register,
            risk_path, risk_sources, effort_report, effort_path, effort_data.
        """
        logger.info(f"Starting full generation pipeline for '{context.project_name}'")
        risk_analyzer = RiskAnalyzer(self.agent)

        # Parallel RAG prefetch — both are read-only Pinecone queries, thread-safe
        logger.info("Prefetching knowledge base context (parallel)...")
        test_plan_generator = TestPlanGenerator(self.agent)
        with ThreadPoolExecutor(max_workers=3) as executor:
            f_risk = executor.submit(
                self.agent.retrieve_knowledge,
                risk_analyzer._build_risk_query(context),
                RAG_K_GENERATION,
            )
            f_strategy = executor.submit(
                self.agent.retrieve_knowledge,
                context.to_rag_query(),
                RAG_K_GENERATION,
            )
            f_test_plan = executor.submit(
                self.agent.retrieve_knowledge,
                test_plan_generator._build_test_plan_query(context),
                RAG_K_GENERATION,
            )
            try:
                risk_chunks = f_risk.result()
            except Exception as exc:
                logger.warning("Risk RAG prefetch failed: %s", exc)
                risk_chunks = []
            try:
                strategy_chunks = f_strategy.result()
            except Exception as exc:
                logger.warning("Strategy RAG prefetch failed: %s", exc)
                strategy_chunks = []
            try:
                test_plan_chunks = f_test_plan.result()
            except Exception as exc:
                logger.warning("Test Plan RAG prefetch failed: %s", exc)
                test_plan_chunks = []
        logger.info(f"RAG prefetch done: {len(risk_chunks)} risk chunks, {len(strategy_chunks)} strategy chunks")

        logger.info("Step 1/4 — Analyzing project risks...")
        try:
            risk_register, risk_sources = risk_analyzer.analyze(context, chunks=risk_chunks)
            risk_path = risk_analyzer.save(risk_register, context)
            logger.info(f"Risk Register saved: {risk_path.name}")
        except Exception as exc:
            logger.error("Risk Register generation failed: %s", exc)
            risk_register, risk_sources, risk_path = "", [], None

        logger.info("Step 2/4 — Generating Effort Estimation...")
        try:
            estimator = EffortEstimator(self.agent)
            effort_report, effort_data = estimator.estimate(context, risk_register)
            effort_path = estimator.save(effort_report, context)
            logger.info(f"Effort Report saved: {effort_path.name}")
        except Exception as exc:
            logger.error("Effort Estimation failed: %s", exc)
            effort_report, effort_data, effort_path = "", {}, None

        logger.info("Step 3/4 — Generating Test Strategy...")
        try:
            strategy, sources = self.generate(context, chunks=strategy_chunks)
            strategy_path = self.save(strategy, context)
            logger.info(f"Test Strategy saved: {strategy_path.name}")
        except Exception as exc:
            logger.error("Test Strategy generation failed: %s", exc)
            strategy, sources, strategy_path = "", [], None

        logger.info("Step 4/4 — Generating Test Plan...")
        try:
            test_plan, test_plan_sources = test_plan_generator.generate(context, risk_register, chunks=test_plan_chunks)
            test_plan_path = test_plan_generator.save(test_plan, context)
            logger.info(f"Test Plan saved: {test_plan_path.name}")
        except Exception as exc:
            logger.error("Test Plan generation failed: %s", exc)
            test_plan, test_plan_sources, test_plan_path = "", [], None

        return {
            "strategy": strategy,
            "strategy_path": strategy_path,
            "sources": sources,
            "risk_register": risk_register,
            "risk_path": risk_path,
            "risk_sources": risk_sources,
            "effort_report": effort_report,
            "effort_path": effort_path,
            "effort_data": effort_data,
            "test_plan": test_plan,
            "test_plan_path": test_plan_path,
            "test_plan_sources": test_plan_sources,
        }

    def generate(self, context: ProjectContext, chunks: list = None) -> tuple:
        """
        Generate a Test Strategy document for the given project context.

        Retrieves relevant chunks from Pinecone (k=RAG_K_GENERATION) using
        the project's RAG query, builds a structured prompt, and generates
        via LLM (Mistral API).

        Args:
            context: Collected ProjectContext from DialogueManager.
            chunks: Optional pre-fetched knowledge chunks. If None, retrieves
                    from Pinecone. Pass pre-fetched chunks to enable parallel
                    RAG retrieval in generate_all().

        Returns:
            Tuple of (strategy_markdown: str, sources: list[str]).
        """
        if chunks is None:
            logger.info(f"Retrieving knowledge for '{context.project_name}'...")
            rag_query = context.to_rag_query()
            chunks = self.agent.retrieve_knowledge(rag_query, k=RAG_K_GENERATION)
        knowledge_context = self.agent.format_knowledge_context(chunks)
        logger.info(f"Retrieved {len(chunks)} knowledge chunks")

        prompt = build_strategy_prompt(context, knowledge_context)
        logger.info("Generating Test Strategy via LLM...")
        strategy = self.agent.ask(prompt, system_prompt=SYSTEM_PROMPT)
        strategy = strategy or ""
        if not strategy.strip():
            raise ValueError(f"LLM returned empty Test Strategy for '{context.project_name}'")
        logger.info(f"Test Strategy generated ({len(strategy)} chars)")

        sources = list({
            f"[{(c.metadata or {}).get('category', 'N/A')}] {(c.metadata or {}).get('filename', 'N/A')}"
            for c in chunks
        })

        return strategy, sources

    def save(self, strategy: str, context: ProjectContext, output_dir: Path = None) -> Path:
        """
        Save the generated strategy to a timestamped markdown file.

        Args:
            strategy: The generated markdown strategy string.
            context: ProjectContext used to name the file.
            output_dir: Output directory. Defaults to output/ in project root.

        Returns:
            Path to the saved file.
        """
        if output_dir is None:
            output_dir = Path(__file__).resolve().parent.parent / "output"

        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = re.sub(r'[^\w\-.]', '_', context.project_name.replace(' ', '_'))
        filename = f"test_strategy_{safe_name}_{timestamp}.md"
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
    print("\n📚 Sources used:")
    for s in sources:
        print(f"  - {s}")
    print(f"\n💾 Strategy saved to: {output_path}")
