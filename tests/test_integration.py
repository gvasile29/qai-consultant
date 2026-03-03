"""
Tests for end-to-end pipeline — DialogueManager → StrategyGenerator (v1.0).

All tests use mocks for Ollama and ChromaDB — no real services required.

Covers:
1.  Full dialogue: DialogueManager → 11 answers submitted → get_context() returns
    a fully populated ProjectContext with correct field values
2.  StrategyGenerator.generate() called with valid context → returns (str, list) tuple
3.  StrategyGenerator.save() creates a file in output/ with correct filename pattern
    (contains project_name and timestamp)
4.  generate_all() returns dict with ALL required keys:
    strategy, strategy_path, sources, risk_register, risk_path, risk_sources,
    effort_report, effort_path, effort_data
5.  Filenames from save() and generate_all() contain the project_name and timestamp
"""

import sys
import os
import re
import tempfile
os.environ["ANONYMIZED_TELEMETRY"] = "False"
os.environ["CHROMA_TELEMETRY"] = "False"

from pathlib import Path
from unittest.mock import patch, MagicMock

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR   = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from dialogue import DialogueManager, ProjectContext
from strategy_generator import StrategyGenerator


# ── Mock helpers ──────────────────────────────────────────────────────────────

class MockDocument:
    """Lightweight stand-in for langchain Document objects."""
    def __init__(self, content="QA knowledge context.", category="Standard", filename="istqb.md"):
        self.page_content = content
        self.metadata = {"category": category, "filename": filename}


class MockAgent:
    """
    Mock QAIAgent that satisfies all method signatures used by StrategyGenerator,
    RiskAnalyzer, and EffortEstimator — without connecting to Ollama or ChromaDB.
    """

    def retrieve_knowledge(self, query: str, k: int = 5) -> list:
        return [
            MockDocument("Risk-based testing strategies per ISTQB.", "Standard", "istqb.pdf"),
            MockDocument("OWASP WSTG security testing checklist.", "Standard", "WSTG.md"),
        ]

    def format_knowledge_context(self, chunks: list) -> str:
        return "\n\n---\n\n".join(
            f"[Source — {c.metadata['category']}: {c.metadata['filename']}]\n{c.page_content}"
            for c in chunks
        )

    def ask(self, prompt: str, system_prompt: str = None) -> str:
        """Return structured text that satisfies all three generators."""
        return (
            "EXECUTIVE_SUMMARY: Integration test estimate generated.\n"
            "ASSUMPTIONS: - Standard working days assumed.\n"
            "RECOMMENDATIONS: - Apply risk-based testing first.\n"
            "\n"
            "# Risk Register — Test Project\n\n"
            "## Executive Summary\n"
            "Low overall risk. Standard web project.\n\n"
            "## Risk Matrix Overview\n\n"
            "| Risk ID | Risk Description | Likelihood | Impact | Risk Level | Priority |\n"
            "|---|---|---|---|---|---|\n"
            "| R01 | Authentication bypass | Low | High | Medium | 1 |\n\n"
            "# Test Strategy — Test Project\n\n"
            "## 1. Project Overview\n"
            "A web application for task management.\n\n"
            "## 2. Scope — What Will Be Tested\n"
            "Authentication, CRUD operations, API endpoints.\n"
        )


# ── 11 dialogue answers covering all QUESTIONS keys ───────────────────────────

ALL_ANSWERS = [
    "IntegrationTestProject",                    # project_name
    "A task management web application for teams",  # project_description (>= 10 chars)
    "web application",                           # project_type
    "React + Node.js + PostgreSQL",             # tech_stack
    "2",                                        # team_qa_size
    "5 full-stack developers",                  # team_dev_size
    "6 months",                                 # timeline
    "Agile with 2-week sprints",               # methodology
    "authentication and payment processing",    # known_risks (>= 10 chars)
    "CI/CD with Jest and Cypress",              # existing_automation
    "GDPR",                                     # compliance_requirements
]

EXPECTED_PROJECT_NAME = "IntegrationTestProject"

GENERATE_ALL_REQUIRED_KEYS = {
    "strategy", "strategy_path", "sources",
    "risk_register", "risk_path", "risk_sources",
    "effort_report", "effort_path", "effort_data",
}

TIMESTAMP_PATTERN = re.compile(r"\d{8}_\d{6}")   # e.g. 20260227_143512


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_full_dialogue_produces_valid_project_context():
    """Submitting all 11 answers produces a fully populated ProjectContext.

    Verifies that:
    - Each submitted answer is accepted (valid=True)
    - get_context() returns a ProjectContext instance
    - project_name field is stored with correct cleaned value
    - dialogue.completed is True after last answer
    """
    dm = DialogueManager()

    for i, answer in enumerate(ALL_ANSWERS):
        assert dm.has_next_question(), f"Expected question {i + 1} to exist"
        result = dm.submit_answer(answer)
        assert result.valid, \
            f"Answer {i + 1} ('{answer}') rejected: {result.error}"

    assert not dm.has_next_question(), "Expected dialogue to be complete after 11 answers"
    assert dm.completed, "Expected dialogue.completed = True"

    context = dm.get_context()
    assert isinstance(context, ProjectContext), \
        f"Expected ProjectContext, got {type(context)}"
    assert context.project_name == EXPECTED_PROJECT_NAME, \
        f"Expected project_name='{EXPECTED_PROJECT_NAME}', got '{context.project_name}'"
    assert context.project_description != "", "project_description should not be empty"
    assert context.tech_stack != "", "tech_stack should not be empty"

    print("  PASS: All 11 answers accepted → ProjectContext populated")
    print(f"        project_name='{context.project_name}', tech_stack='{context.tech_stack}'")


def test_strategy_generator_returns_str_list_tuple():
    """StrategyGenerator.generate() returns a (str, list) tuple.

    - First element: the Test Strategy as a non-empty string
    - Second element: list of source strings (can be empty if mock returns no chunks)
    """
    dm = DialogueManager()
    for answer in ALL_ANSWERS:
        dm.submit_answer(answer)
    context = dm.get_context()

    generator = StrategyGenerator(MockAgent())
    result = generator.generate(context)

    assert isinstance(result, tuple), \
        f"Expected tuple, got {type(result)}"
    assert len(result) == 2, \
        f"Expected 2-element tuple (strategy, sources), got {len(result)} elements"

    strategy, sources = result
    assert isinstance(strategy, str), \
        f"Expected strategy to be str, got {type(strategy)}"
    assert len(strategy) > 0, \
        "Strategy string should not be empty"
    assert isinstance(sources, list), \
        f"Expected sources to be list, got {type(sources)}"

    print(f"  PASS: generate() → (str[{len(strategy)} chars], list[{len(sources)} sources])")


def test_strategy_generator_save_creates_correct_filename():
    """StrategyGenerator.save() creates a file whose name contains project_name and timestamp.

    Uses a temporary directory to avoid polluting output/.
    """
    dm = DialogueManager()
    for answer in ALL_ANSWERS:
        dm.submit_answer(answer)
    context = dm.get_context()

    generator = StrategyGenerator(MockAgent())
    strategy, _ = generator.generate(context)

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = generator.save(strategy, context, output_dir=Path(tmpdir))

        assert output_path.exists(), \
            f"Expected saved file to exist at {output_path}"
        assert EXPECTED_PROJECT_NAME in output_path.name, \
            f"Expected project name '{EXPECTED_PROJECT_NAME}' in filename '{output_path.name}'"
        assert TIMESTAMP_PATTERN.search(output_path.name), \
            f"Expected YYYYMMDD_HHMMSS timestamp in filename '{output_path.name}'"
        assert output_path.name.startswith("test_strategy_"), \
            f"Expected filename to start with 'test_strategy_', got '{output_path.name}'"

    print(f"  PASS: save() → '{output_path.name}'")
    print("        project_name present: True | timestamp present: True")


def test_generate_all_returns_all_required_keys():
    """generate_all() returns a dict with all 9 required keys.

    Required keys: strategy, strategy_path, sources, risk_register, risk_path,
    risk_sources, effort_report, effort_path, effort_data.
    """
    dm = DialogueManager()
    for answer in ALL_ANSWERS:
        dm.submit_answer(answer)
    context = dm.get_context()

    generator = StrategyGenerator(MockAgent())
    result = generator.generate_all(context)

    assert isinstance(result, dict), \
        f"Expected dict, got {type(result)}"

    missing = GENERATE_ALL_REQUIRED_KEYS - result.keys()
    assert not missing, \
        f"generate_all() is missing required keys: {missing}"

    # Type-check the key values
    assert isinstance(result["strategy"], str) and result["strategy"], \
        "strategy should be a non-empty string"
    assert isinstance(result["risk_register"], str) and result["risk_register"], \
        "risk_register should be a non-empty string"
    assert isinstance(result["effort_report"], str) and result["effort_report"], \
        "effort_report should be a non-empty string"
    assert isinstance(result["sources"], list), \
        "sources should be a list"
    assert isinstance(result["risk_sources"], list), \
        "risk_sources should be a list"
    assert isinstance(result["strategy_path"], Path), \
        f"strategy_path should be a Path, got {type(result['strategy_path'])}"
    assert isinstance(result["risk_path"], Path), \
        f"risk_path should be a Path, got {type(result['risk_path'])}"
    assert isinstance(result["effort_path"], Path), \
        f"effort_path should be a Path, got {type(result['effort_path'])}"

    print(f"  PASS: generate_all() returned all {len(GENERATE_ALL_REQUIRED_KEYS)} required keys")
    for key in sorted(GENERATE_ALL_REQUIRED_KEYS):
        val = result[key]
        type_str = type(val).__name__
        print(f"        {key}: {type_str}")


def test_generated_filenames_contain_project_name_and_timestamp():
    """All files saved by generate_all() include project_name and a timestamp.

    Verifies: strategy_path, risk_path, and effort_path filenames.
    """
    dm = DialogueManager()
    for answer in ALL_ANSWERS:
        dm.submit_answer(answer)
    context = dm.get_context()

    generator = StrategyGenerator(MockAgent())
    result = generator.generate_all(context)

    for key in ("strategy_path", "risk_path", "effort_path"):
        path = result[key]
        assert isinstance(path, Path), f"{key} should be a Path"
        assert path.exists(), f"Expected {key} file to exist: {path}"
        assert EXPECTED_PROJECT_NAME in path.name, \
            f"Expected '{EXPECTED_PROJECT_NAME}' in {key} filename '{path.name}'"
        assert TIMESTAMP_PATTERN.search(path.name), \
            f"Expected YYYYMMDD_HHMMSS timestamp in {key} filename '{path.name}'"
        print(f"  PASS: {key} → '{path.name}'")


# ── Runner ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [
        ("DialogueManager: 11 answers → fully populated ProjectContext",
            test_full_dialogue_produces_valid_project_context),
        ("StrategyGenerator.generate() → returns (str, list) tuple",
            test_strategy_generator_returns_str_list_tuple),
        ("StrategyGenerator.save() → file with project_name + timestamp",
            test_strategy_generator_save_creates_correct_filename),
        ("generate_all() → dict with all 9 required keys",
            test_generate_all_returns_all_required_keys),
        ("All save() filenames contain project_name and timestamp",
            test_generated_filenames_contain_project_name_and_timestamp),
    ]

    passed = failed = 0

    print("=" * 68)
    print("  QAI Consultant — Integration Pipeline v1.0 Tests")
    print("=" * 68)

    for name, fn in tests:
        print(f"\n[TEST] {name}")
        try:
            fn()
            passed += 1
        except AssertionError as e:
            print(f"  FAIL: {e}")
            failed += 1
        except Exception as e:
            import traceback
            print(f"  ERROR: {type(e).__name__}: {e}")
            traceback.print_exc()
            failed += 1

    print(f"\n{'=' * 68}")
    print(f"  Results: {passed} passed, {failed} failed")
    print(f"{'=' * 68}")

    import sys as _sys
    _sys.exit(0 if failed == 0 else 1)
