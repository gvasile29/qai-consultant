"""
QAI Consultant — Dialogue Module
Manages the clarifying questions flow to understand the project context
before generating a Test Strategy.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ProjectContext:
    """Stores all information collected during the clarifying dialogue."""
    project_name: str = ""
    project_description: str = ""
    project_type: str = ""
    tech_stack: str = ""
    team_qa_size: str = ""
    team_dev_size: str = ""
    timeline: str = ""
    methodology: str = ""
    known_risks: str = ""
    existing_automation: str = ""
    compliance_requirements: str = ""

    def to_summary(self) -> str:
        """Returns a human-readable summary of the project context."""
        return f"""
PROJECT CONTEXT SUMMARY
========================
Project Name:          {self.project_name}
Description:           {self.project_description}
Type:                  {self.project_type}
Tech Stack:            {self.tech_stack}
QA Team Size:          {self.team_qa_size}
Dev Team Size:         {self.team_dev_size}
Timeline:              {self.timeline}
Methodology:           {self.methodology}
Known Risks:           {self.known_risks}
Existing Automation:   {self.existing_automation}
Compliance:            {self.compliance_requirements}
""".strip()

    def to_rag_query(self) -> str:
        """Builds a rich query string for RAG retrieval based on project context."""
        parts = [
            f"Test strategy for {self.project_type} application",
            f"methodology {self.methodology}",
        ]
        if self.known_risks:
            parts.append(f"risks: {self.known_risks}")
        if self.compliance_requirements and self.compliance_requirements.lower() not in ["no", "none", "n/a", ""]:
            parts.append(f"compliance: {self.compliance_requirements}")
        if self.existing_automation and self.existing_automation.lower() not in ["no", "none", ""]:
            parts.append(f"automation: {self.existing_automation}")
        return " | ".join(parts)


# ── Dialogue Questions ─────────────────────────────────────────────────────────

QUESTIONS = [
    {
        "key": "project_name",
        "question": "What is the name of your project?",
        "hint": "e.g., MyApp, E-commerce Platform, Banking API",
    },
    {
        "key": "project_description",
        "question": "Briefly describe what the product does. What problem does it solve and who are the users?",
        "hint": "e.g., A mobile app for tracking personal finances, used by individual consumers",
    },
    {
        "key": "project_type",
        "question": "What type of product are we testing?",
        "hint": "e.g., web app, mobile app (iOS/Android), REST API, microservices, embedded system, desktop app",
    },
    {
        "key": "tech_stack",
        "question": "What is the main technology stack?",
        "hint": "e.g., React + Node.js, Java Spring Boot, Python Django, Flutter, .NET",
    },
    {
        "key": "team_qa_size",
        "question": "How many people are on the QA team?",
        "hint": "e.g., 1, 2, or 'no dedicated QA — developers test their own code'",
    },
    {
        "key": "team_dev_size",
        "question": "How many developers are on the team?",
        "hint": "e.g., 3 frontend + 2 backend, or 5 full-stack developers",
    },
    {
        "key": "timeline",
        "question": "What is the project timeline or release deadline?",
        "hint": "e.g., 3 months, release in June 2026, ongoing product with monthly sprints",
    },
    {
        "key": "methodology",
        "question": "Does the team follow Agile, Waterfall, or another methodology?",
        "hint": "e.g., Scrum with 2-week sprints, Kanban, Waterfall, SAFe",
    },
    {
        "key": "known_risks",
        "question": "Are there any known high-risk areas or critical features?",
        "hint": "e.g., payment processing, user authentication, data migration, third-party integrations, performance under high load",
    },
    {
        "key": "existing_automation",
        "question": "Does the project have any existing automated tests?",
        "hint": "e.g., no automation yet, unit tests only, Selenium E2E suite, Postman API tests",
    },
    {
        "key": "compliance_requirements",
        "question": "Are there any compliance or regulatory requirements?",
        "hint": "e.g., GDPR, PCI-DSS, HIPAA, ISO 27001, none",
    },
]


class DialogueManager:
    """Manages the clarifying questions flow."""

    def __init__(self):
        self.context = ProjectContext()
        self.current_question_index = 0
        self.completed = False

    def has_next_question(self) -> bool:
        """Returns True if there are more questions to ask."""
        return self.current_question_index < len(QUESTIONS)

    def get_next_question(self) -> Optional[dict]:
        """Returns the next question or None if dialogue is complete."""
        if not self.has_next_question():
            self.completed = True
            return None
        return QUESTIONS[self.current_question_index]

    def submit_answer(self, answer: str):
        """Store the answer for the current question and advance."""
        if not self.has_next_question():
            return

        question = QUESTIONS[self.current_question_index]
        key = question["key"]
        setattr(self.context, key, answer.strip())
        self.current_question_index += 1

        if not self.has_next_question():
            self.completed = True

    def get_progress(self) -> tuple:
        """Returns (current, total) question numbers."""
        return self.current_question_index + 1, len(QUESTIONS)

    def get_context(self) -> ProjectContext:
        """Returns the collected project context."""
        return self.context

    def reset(self):
        """Reset the dialogue for a new session."""
        self.context = ProjectContext()
        self.current_question_index = 0
        self.completed = False


# ── Quick test ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    dialogue = DialogueManager()

    print("QAI Consultant — Dialogue Test")
    print("=" * 40)

    while dialogue.has_next_question():
        question = dialogue.get_next_question()
        current, total = dialogue.get_progress()

        print(f"\n[{current}/{total}] {question['question']}")
        print(f"  Hint: {question['hint']}")
        answer = input("  Your answer: ")
        dialogue.submit_answer(answer)

    print("\n" + "=" * 40)
    print(dialogue.get_context().to_summary())
    print("\nRAG Query:")
    print(dialogue.get_context().to_rag_query())
