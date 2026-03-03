"""
QAI Consultant — Dialogue Module
Manages the clarifying questions flow to understand the project context
before generating a Test Strategy. Includes input validation for all fields.
"""

import re
from dataclasses import dataclass
from typing import Optional
from logger import get_logger

logger = get_logger(__name__)

# ── Validation Config ──────────────────────────────────────────────────────────

MIN_ANSWER_LENGTH = 2          # minimum characters for most fields
MIN_DESCRIPTION_LENGTH = 10    # minimum for free-text description fields
MAX_ANSWER_LENGTH = 500        # maximum characters for any field
MAX_PROJECT_NAME_LENGTH = 50   # used in filenames

# Characters invalid in filenames (stripped from project_name)
INVALID_FILENAME_CHARS = r'[/\\:*?"<>|]'

# Characters considered potentially dangerous (stripped from all inputs)
DANGEROUS_CHARS = r'[<>{}|\\]'

# Fields that accept short answers (e.g. "1", "no")
SHORT_ANSWER_FIELDS = {"team_qa_size", "team_dev_size", "existing_automation", "compliance_requirements"}

# Fields with longer minimum length
LONG_ANSWER_FIELDS = {"project_description", "known_risks"}


# ── Validation Result ──────────────────────────────────────────────────────────

@dataclass
class ValidationResult:
    """Result of input validation — valid flag + optional error message."""
    valid: bool
    error: str = ""
    cleaned: str = ""


# ── Input Validator ────────────────────────────────────────────────────────────

class InputValidator:
    """
    Validates and sanitizes user answers from the dialogue.
    Each field has specific rules based on its purpose.
    """

    def validate(self, key: str, answer: str) -> ValidationResult:
        """
        Validate and sanitize an answer for a given question key.

        Args:
            key: The question key (e.g., 'project_name', 'team_qa_size').
            answer: The raw user input string.

        Returns:
            ValidationResult with valid flag, error message, and cleaned value.
        """
        # Strip leading/trailing whitespace
        cleaned = answer.strip()

        # Check empty
        if not cleaned:
            return ValidationResult(valid=False, error="Please provide an answer to continue.")

        # Strip dangerous characters
        original = cleaned
        cleaned = re.sub(DANGEROUS_CHARS, "", cleaned)
        if cleaned != original:
            stripped = set(original) - set(cleaned)
            logger.warning(f"Stripped dangerous chars from field '{key}': {stripped}")

        # Check length after stripping
        if not cleaned:
            return ValidationResult(valid=False, error="Please provide a valid answer.")

        if len(cleaned) > MAX_ANSWER_LENGTH:
            return ValidationResult(
                valid=False,
                error=f"Answer is too long (max {MAX_ANSWER_LENGTH} characters). Please be more concise."
            )

        # Field-specific validation
        if key == "project_name":
            return self._validate_project_name(cleaned)
        elif key in LONG_ANSWER_FIELDS:
            return self._validate_long_answer(key, cleaned)
        elif key in SHORT_ANSWER_FIELDS:
            return self._validate_short_answer(key, cleaned)
        else:
            return self._validate_default(key, cleaned)

    def _validate_project_name(self, value: str) -> ValidationResult:
        """Project name is used in filenames — strip invalid chars, enforce length."""
        cleaned = re.sub(INVALID_FILENAME_CHARS, "", value).strip()
        cleaned = re.sub(r"\s+", "_", cleaned)  # spaces → underscores

        if not cleaned:
            return ValidationResult(
                valid=False,
                error="Project name contains only invalid characters. Please use letters and numbers."
            )
        if len(cleaned) < MIN_ANSWER_LENGTH:
            return ValidationResult(
                valid=False,
                error="Project name is too short. Please use at least 2 characters."
            )
        if len(cleaned) > MAX_PROJECT_NAME_LENGTH:
            cleaned = cleaned[:MAX_PROJECT_NAME_LENGTH]
            logger.info(f"Project name truncated to {MAX_PROJECT_NAME_LENGTH} chars")

        return ValidationResult(valid=True, cleaned=cleaned)

    def _validate_long_answer(self, key: str, value: str) -> ValidationResult:
        """Description-style fields need more detail."""
        if len(value) < MIN_DESCRIPTION_LENGTH:
            return ValidationResult(
                valid=False,
                error=f"Answer seems too short — please be more specific (at least {MIN_DESCRIPTION_LENGTH} characters)."
            )
        return ValidationResult(valid=True, cleaned=value)

    def _validate_short_answer(self, key: str, value: str) -> ValidationResult:
        """Fields that accept short answers like '1', 'no', 'none'."""
        if len(value) < 1:
            return ValidationResult(valid=False, error="Please provide an answer.")

        # Hint for team size fields expecting a number
        if key in {"team_qa_size", "team_dev_size"}:
            # Accept numeric or descriptive (e.g. "2 QA engineers", "no dedicated QA")
            words = ["zero", "one", "two", "three", "four", "five", "six",
                     "seven", "eight", "nine", "ten"]
            has_digit = any(c.isdigit() for c in value)
            has_word_number = any(w in value.lower() for w in words)
            has_no_qa = any(k in value.lower() for k in ["no ", "none", "n/a", "developers test"])
            if not (has_digit or has_word_number or has_no_qa):
                return ValidationResult(
                    valid=False,
                    error="Please specify a number (e.g., '3') or describe the setup (e.g., 'no dedicated QA')."
                )

        return ValidationResult(valid=True, cleaned=value)

    def _validate_default(self, key: str, value: str) -> ValidationResult:
        """Default validation for most fields."""
        if len(value) < MIN_ANSWER_LENGTH:
            return ValidationResult(
                valid=False,
                error="Answer seems too short — please be more specific."
            )
        return ValidationResult(valid=True, cleaned=value)


# ── Project Context ────────────────────────────────────────────────────────────

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


# ── Dialogue Manager ───────────────────────────────────────────────────────────

class DialogueManager:
    """
    Manages the clarifying questions flow for project context collection.
    Validates all user input before storing answers.
    """

    def __init__(self):
        self.context = ProjectContext()
        self.current_question_index = 0
        self.completed = False
        self._validator = InputValidator()

    def has_next_question(self) -> bool:
        """Returns True if there are more questions to ask."""
        return self.current_question_index < len(QUESTIONS)

    def get_next_question(self) -> Optional[dict]:
        """Returns the next question dict or None if dialogue is complete."""
        if not self.has_next_question():
            self.completed = True
            return None
        return QUESTIONS[self.current_question_index]

    def validate_answer(self, answer: str) -> ValidationResult:
        """
        Validate an answer for the current question without advancing.
        Use this to check input before calling submit_answer().

        Args:
            answer: The raw user input.

        Returns:
            ValidationResult with valid flag and error message if invalid.
        """
        if not self.has_next_question():
            return ValidationResult(valid=True, cleaned=answer)
        key = QUESTIONS[self.current_question_index]["key"]
        return self._validator.validate(key, answer)

    def submit_answer(self, answer: str) -> ValidationResult:
        """
        Validate, store the answer for the current question, and advance.

        Args:
            answer: The raw user input.

        Returns:
            ValidationResult — check .valid before proceeding.
        """
        if not self.has_next_question():
            return ValidationResult(valid=True, cleaned=answer)

        question = QUESTIONS[self.current_question_index]
        key = question["key"]

        result = self._validator.validate(key, answer)
        if not result.valid:
            logger.debug(f"Validation failed for '{key}': {result.error}")
            return result

        setattr(self.context, key, result.cleaned)
        logger.debug(f"Answer stored for '{key}': {result.cleaned[:50]}")
        self.current_question_index += 1

        if not self.has_next_question():
            self.completed = True

        return result

    def get_progress(self) -> tuple:
        """Returns (current, total) question numbers (1-based)."""
        return self.current_question_index + 1, len(QUESTIONS)

    def get_context(self) -> ProjectContext:
        """Returns the collected ProjectContext."""
        return self.context

    def reset(self):
        """Reset the dialogue for a new session."""
        self.context = ProjectContext()
        self.current_question_index = 0
        self.completed = False
        logger.debug("DialogueManager reset")


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

        while True:
            answer = input("  Your answer: ")
            result = dialogue.submit_answer(answer)
            if result.valid:
                break
            print(f"  ⚠️  {result.error}")

    print("\n" + "=" * 40)
    print(dialogue.get_context().to_summary())
    print("\nRAG Query:")
    print(dialogue.get_context().to_rag_query())
