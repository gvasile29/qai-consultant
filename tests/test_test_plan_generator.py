"""
Tests for src/test_plan_generator.py — structural tests (no LLM required).

Covers:
1. Module imports and class structure
2. System prompt and prompt builder
3. RAG query construction
4. File save naming convention
5. generate() accepts pre-fetched chunks
"""

import sys
import os
os.environ["ANONYMIZED_TELEMETRY"] = "False"
os.environ["CHROMA_TELEMETRY"] = "False"

from pathlib import Path
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parent.parent
APP_SRC = REPO_ROOT / "src"
sys.path.insert(0, str(APP_SRC))


def test_module_imports():
    """TestPlanGenerator, build_test_plan_prompt, TEST_PLAN_SYSTEM_PROMPT importable."""
    from test_plan_generator import TestPlanGenerator, build_test_plan_prompt, TEST_PLAN_SYSTEM_PROMPT
    assert TestPlanGenerator is not None
    assert callable(build_test_plan_prompt)
    assert isinstance(TEST_PLAN_SYSTEM_PROMPT, str) and len(TEST_PLAN_SYSTEM_PROMPT) > 50
    print("  PASS: module imports correctly")


def test_system_prompt_content():
    """TEST_PLAN_SYSTEM_PROMPT references IEEE 829 and tactical planning."""
    from test_plan_generator import TEST_PLAN_SYSTEM_PROMPT
    assert "IEEE 829" in TEST_PLAN_SYSTEM_PROMPT
    assert "WHO" in TEST_PLAN_SYSTEM_PROMPT or "tactical" in TEST_PLAN_SYSTEM_PROMPT.lower() or "WHAT" in TEST_PLAN_SYSTEM_PROMPT
    print("  PASS: system prompt references IEEE 829 and tactical scope")


def test_build_test_plan_prompt_contains_project_name():
    """build_test_plan_prompt includes project name in output."""
    from test_plan_generator import build_test_plan_prompt
    from dialogue import ProjectContext

    context = ProjectContext(
        project_name="TestApp",
        project_description="A test app",
        project_type="web app",
        tech_stack="Python Flask",
        team_qa_size="2",
        team_dev_size="4",
        timeline="8 weeks",
        methodology="Scrum",
        known_risks="None",
        existing_automation="None",
        compliance_requirements="none",
    )
    prompt = build_test_plan_prompt(context, "# Risk Register\n- R01: test risk", "test knowledge")
    assert "TestApp" in prompt
    assert "IEEE 829" in prompt
    assert "Entry" in prompt and "Exit" in prompt
    print("  PASS: build_test_plan_prompt contains project name and key sections")


def test_build_test_plan_query_non_empty():
    """_build_test_plan_query returns a non-empty string."""
    from test_plan_generator import TestPlanGenerator
    from dialogue import ProjectContext

    mock_agent = MagicMock()
    generator = TestPlanGenerator(mock_agent)

    context = ProjectContext(
        project_name="TestApp",
        project_description="A test app",
        project_type="mobile app",
        tech_stack="React Native",
        team_qa_size="1",
        team_dev_size="3",
        timeline="6 weeks",
        methodology="Kanban",
        known_risks="None",
        existing_automation="None",
        compliance_requirements="GDPR",
    )
    query = generator._build_test_plan_query(context)
    assert isinstance(query, str) and len(query) > 20
    assert "mobile app" in query
    assert "GDPR" in query
    print(f"  PASS: _build_test_plan_query returned: {query[:80]}...")


def test_generate_uses_provided_chunks():
    """generate() uses pre-fetched chunks and does not call retrieve_knowledge."""
    from test_plan_generator import TestPlanGenerator
    from dialogue import ProjectContext

    mock_agent = MagicMock()
    mock_agent.format_knowledge_context.return_value = "test knowledge context"
    mock_agent.ask.return_value = "# Test Plan\n\n## 1. Introduction\nTest plan content."

    mock_chunk = MagicMock()
    mock_chunk.metadata = {"category": "Standard", "filename": "IEEE_829.md"}

    generator = TestPlanGenerator(mock_agent)
    context = ProjectContext(
        project_name="TestProject",
        project_description="desc",
        project_type="web app",
        tech_stack="Django",
        team_qa_size="2",
        team_dev_size="4",
        timeline="10 weeks",
        methodology="Scrum",
        known_risks="None",
        existing_automation="None",
        compliance_requirements="none",
    )

    result, sources = generator.generate(context, "# Risk Register", chunks=[mock_chunk])

    mock_agent.retrieve_knowledge.assert_not_called()
    mock_agent.format_knowledge_context.assert_called_once_with([mock_chunk])
    assert "Test Plan" in result
    assert len(sources) == 1
    print("  PASS: generate() uses provided chunks without calling retrieve_knowledge")


def test_save_creates_file_with_correct_name(tmp_path):
    """save() creates a file named test_plan_<ProjectName>_<timestamp>.md."""
    from test_plan_generator import TestPlanGenerator

    mock_agent = MagicMock()
    generator = TestPlanGenerator(mock_agent)

    from dialogue import ProjectContext
    context = ProjectContext(
        project_name="MyProject",
        project_description="desc",
        project_type="web app",
        tech_stack="Django",
        team_qa_size="1",
        team_dev_size="2",
        timeline="4 weeks",
        methodology="Scrum",
        known_risks="None",
        existing_automation="None",
        compliance_requirements="none",
    )

    output_path = generator.save("# Test Plan\n\nContent here.", context, output_dir=tmp_path)
    assert output_path.exists()
    assert output_path.name.startswith("test_plan_MyProject_")
    assert output_path.suffix == ".md"
    content = output_path.read_text(encoding="utf-8")
    assert "document_type: Test Plan" in content
    assert "standard: IEEE 829" in content
    print(f"  PASS: save() created {output_path.name}")


def test_class_has_required_methods():
    """TestPlanGenerator exposes generate(), save(), _build_test_plan_query()."""
    from test_plan_generator import TestPlanGenerator
    assert hasattr(TestPlanGenerator, "generate")
    assert hasattr(TestPlanGenerator, "save")
    assert hasattr(TestPlanGenerator, "_build_test_plan_query")
    print("  PASS: TestPlanGenerator has all required methods")


if __name__ == "__main__":
    tests = [
        test_module_imports,
        test_system_prompt_content,
        test_build_test_plan_prompt_contains_project_name,
        test_build_test_plan_query_non_empty,
        test_generate_uses_provided_chunks,
        test_class_has_required_methods,
    ]
    passed = failed = 0
    print("=" * 60)
    print("  QAI Consultant — TestPlanGenerator Tests")
    print("=" * 60)
    for fn in tests:
        print(f"\n[TEST] {fn.__name__}")
        try:
            if "tmp_path" in fn.__code__.co_varnames:
                import tempfile
                with tempfile.TemporaryDirectory() as d:
                    fn(Path(d))
            else:
                fn()
            passed += 1
        except Exception as e:
            import traceback
            print(f"  FAIL: {e}")
            traceback.print_exc()
            failed += 1
    print(f"\n{'=' * 60}")
    print(f"  Results: {passed} passed, {failed} failed")
    print(f"{'=' * 60}")
