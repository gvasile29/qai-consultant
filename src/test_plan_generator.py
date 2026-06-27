"""
QAI Consultant — Test Plan Generator
Generates IEEE 829-aligned Test Plan documents using RAG + LLM.

Output is a markdown document saved to output/test_plan_*.md.
Receives the Risk Register to inform test priorities and resource allocation.
"""

from pathlib import Path
from datetime import datetime
from agent import QAIAgent, RAG_K_GENERATION
from dialogue import ProjectContext
from logger import get_logger

logger = get_logger(__name__)

# ── System Prompt ──────────────────────────────────────────────────────────────

TEST_PLAN_SYSTEM_PROMPT = """You are QAI Consultant, a senior QA Architect and Test Manager.
You generate detailed, actionable Test Plans aligned with IEEE 829 and adapted for AI-era teams.
Your Test Plans are:
- Tactical and specific — WHO/WHAT/WHEN/HOW, not high-level strategy
- Risk-informed — test items and priorities derived from the Risk Register
- AI-aware — addresses AI tools used by the team and their QA implications
- Practical — measurable entry/exit criteria, concrete schedule, clear responsibilities
"""


# ── Test Plan Prompt Builder ───────────────────────────────────────────────────

def build_test_plan_prompt(context: ProjectContext, risk_register: str, knowledge_context: str) -> str:
    risk_summary = risk_register[:2000] + "..." if len(risk_register) > 2000 else risk_register
    return f"""
Based on the following project context, Risk Register, and QA knowledge base, generate a complete Test Plan aligned with IEEE 829.

PROJECT CONTEXT:
{context.to_summary()}

RISK REGISTER (use this to inform test priorities and resource allocation):
{risk_summary}

RELEVANT QA KNOWLEDGE BASE:
{knowledge_context}

Generate a Test Plan using EXACTLY this structure:

# Test Plan — {context.project_name}

## 1. Introduction
Brief description of the project under test and the purpose of this test plan.
State how this Test Plan relates to the Test Strategy.

## 2. Test Items
List the specific software components, modules, and features that will be tested.
Include version information where applicable.

## 3. Features to be Tested
Detailed list of features/functions in scope, with rationale derived from the Risk Register.
Prioritize based on risk level (Critical → High → Medium → Low).

## 4. Features NOT to be Tested
Explicit list of features excluded from testing, with justification for each exclusion.

## 5. Test Approach
For each applicable test level (Unit, Integration, System, Acceptance, Performance, Security):
- Specific techniques to be used
- Tools recommended (based on tech stack: {context.tech_stack})
- Automation vs. manual split
- AI tool usage (if any) and human review gates

## 6. Entry and Exit Criteria

### Entry Criteria (when testing can start)
Measurable conditions (e.g., "Build passes CI", "Test environment deployed", "Test data seeded").

### Exit Criteria (when testing is complete)
Measurable conditions (e.g., "0 open Critical defects", ">90% test cases executed", "All OWASP Top 10 checks passed").

### Suspension and Resumption Criteria
Conditions to pause testing and conditions to resume.

## 7. Test Deliverables
List all test artifacts to be produced: test cases, test data, test reports, defect reports, test summary report.

## 8. Testing Schedule

| Phase | Activities | Duration | Owner |
|---|---|---|---|
| Test Planning | Test plan finalisation, environment setup | ... | QA Lead |
| Test Design | Test case design, test data preparation | ... | QA Engineers |
| Test Execution | Functional + integration testing | ... | QA Engineers |
| Security Testing | OWASP checks, penetration testing | ... | QA Lead |
| Performance Testing | Load and stress testing | ... | QA Engineers |
| Regression & UAT | Regression suite, user acceptance | ... | QA + Dev |

Base this on timeline: {context.timeline}, QA team: {context.team_qa_size}, Dev team: {context.team_dev_size}.

## 9. Environmental Needs
- Hardware, software, and network requirements
- Test data requirements and data masking needs
- Access, permissions, and third-party dependencies

## 10. Responsibilities

| Role | Responsibilities |
|---|---|
| QA Lead | Test plan ownership, risk sign-off, metrics reporting |
| QA Engineers | Test case design, execution, defect logging |
| Dev Team | Unit tests, bug fixes within SLA, environment support |
| Product Owner | UAT participation, acceptance sign-off |

## 11. AI Tool Usage and Oversight
Document AI tools in the team's QA workflow:
- AI tools used (test case generation, automation, code review)
- Human review gates for AI-generated artifacts
- Validation criteria for AI-generated test cases
- Risks from AI tool usage and mitigations

## 12. Risks and Contingencies
Top 3-5 test execution risks (QA process risks, not project risks):

| Risk | Probability | Impact | Contingency |
|---|---|---|---|
| ... | ... | ... | ... |

Be specific to this project. Reference the Risk Register for test priority decisions.
"""


# ── Test Plan Generator ────────────────────────────────────────────────────────

class TestPlanGenerator:
    """
    Generates IEEE 829-aligned Test Plan documents.

    Receives the Risk Register to align test priorities with identified risks.
    Uses RAG to retrieve IEEE 829, test planning, and AI testing methodology chunks.
    """

    def __init__(self, agent: QAIAgent):
        """
        Args:
            agent: Initialized QAIAgent with Pinecone and LLM connections.
        """
        self.agent = agent

    def generate(self, context: ProjectContext, risk_register: str, chunks: list = None) -> tuple:
        """
        Generate a Test Plan using RAG + LLM.

        Args:
            context: Collected ProjectContext from DialogueManager.
            risk_register: Generated Risk Register markdown (informs test priorities).
            chunks: Optional pre-fetched knowledge chunks.

        Returns:
            Tuple of (test_plan_markdown: str, sources: list[str]).
        """
        logger.info(f"Generating Test Plan for '{context.project_name}'...")
        if chunks is None:
            query = self._build_test_plan_query(context)
            chunks = self.agent.retrieve_knowledge(query, k=RAG_K_GENERATION)
        knowledge_context = self.agent.format_knowledge_context(chunks)
        logger.info(f"Retrieved {len(chunks)} test plan chunks")

        prompt = build_test_plan_prompt(context, risk_register, knowledge_context)
        test_plan = self.agent.ask(prompt, system_prompt=TEST_PLAN_SYSTEM_PROMPT)
        logger.info(f"Test Plan generated ({len(test_plan)} chars)")

        sources = list({
            f"[{c.metadata.get('category', 'N/A')}] {c.metadata.get('filename', 'N/A')}"
            for c in chunks
        })
        return test_plan, sources

    def _build_test_plan_query(self, context: ProjectContext) -> str:
        """Build a test-plan-focused RAG query from project context."""
        parts = [
            f"test plan IEEE 829 {context.project_type}",
            f"test plan structure entry exit criteria {context.methodology}",
            "AI assisted test planning human oversight",
        ]
        if context.compliance_requirements and context.compliance_requirements.lower() not in ["no", "none", "n/a", ""]:
            parts.append(f"test plan compliance {context.compliance_requirements}")
        if context.tech_stack:
            parts.append(f"test plan tools {context.tech_stack}")
        return " | ".join(parts)

    def save(self, test_plan: str, context: ProjectContext, output_dir: Path = None) -> Path:
        """Save the generated Test Plan to a timestamped markdown file."""
        if output_dir is None:
            output_dir = Path(__file__).resolve().parent.parent / "output"
        output_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"test_plan_{context.project_name.replace(' ', '_')}_{timestamp}.md"
        output_path = output_dir / filename
        full_content = f"""---
generated_by: QAI Consultant
date: {datetime.now().strftime("%Y-%m-%d %H:%M")}
project: {context.project_name}
document_type: Test Plan
standard: IEEE 829
---

{test_plan}
"""
        output_path.write_text(full_content, encoding="utf-8")
        return output_path
