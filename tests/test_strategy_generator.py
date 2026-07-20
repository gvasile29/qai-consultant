"""
Tests for src/strategy_generator.py — StrategyGenerator.save() (structural, no LLM required).

Covers:
1. save() creates a file named test_strategy_<ProjectName>_<timestamp>.md with frontmatter
2. save() appends the visible AI-generated footer to the saved body (v2.5.2)
"""

import sys
import os
os.environ["ANONYMIZED_TELEMETRY"] = "False"
os.environ["CHROMA_TELEMETRY"] = "False"

from pathlib import Path
from unittest.mock import MagicMock

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from dialogue import ProjectContext
import strategy_generator as sg_module
from strategy_generator import StrategyGenerator

SAMPLE_CONTEXT = ProjectContext(
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


def test_save_creates_file_with_correct_name(tmp_path):
    """save() creates a file named test_strategy_<ProjectName>_<timestamp>.md."""
    generator = StrategyGenerator(MagicMock())
    output_path = generator.save("# Test Strategy\n\nContent here.", SAMPLE_CONTEXT, output_dir=tmp_path)

    assert output_path.exists()
    assert output_path.name.startswith("test_strategy_MyProject_")
    assert output_path.suffix == ".md"
    content = output_path.read_text(encoding="utf-8")
    assert "generated_by: QAI Consultant" in content
    print(f"  PASS: save() created {output_path.name}")


def test_save_includes_ai_generated_footer(tmp_path):
    """save() appends the visible AI-generated footer to the saved body (v2.5.2)."""
    generator = StrategyGenerator(MagicMock())
    body = "# Test Strategy — Sample\n\nSome generated body text."
    output_path = generator.save(body, SAMPLE_CONTEXT, output_dir=tmp_path)

    content = output_path.read_text(encoding="utf-8")
    assert "AI-generated" in content, "AI-generated footer missing from saved Test Strategy"
    assert content.index(body) < content.index("AI-generated"), \
        "Footer must come after the document body"
    print("  PASS: save() includes visible AI-generated footer")


def test_generate_all_passes_results_summary_to_risk_analyzer(monkeypatch, tmp_path):
    """generate_all(results_summary=...) passes it straight through to
    RiskAnalyzer.analyze() (v3.1 F2 requirement) — every other stage is
    stubbed out so this exercises only the passthrough, not a real pipeline."""
    captured = {}

    def fake_analyze(self, context, chunks=None, results_summary=None):
        captured["results_summary"] = results_summary
        return "# Risk Register\n\nBody.", ["[Standard] foo.md"]

    monkeypatch.setattr(sg_module.RiskAnalyzer, "analyze", fake_analyze)
    monkeypatch.setattr(sg_module.RiskAnalyzer, "save", lambda self, text, ctx: tmp_path / "risk.md")
    monkeypatch.setattr(sg_module.EffortEstimator, "estimate", lambda self, ctx, risk: ("effort", {}))
    monkeypatch.setattr(sg_module.EffortEstimator, "save", lambda self, text, ctx: tmp_path / "effort.md")
    monkeypatch.setattr(sg_module.StrategyGenerator, "generate", lambda self, ctx, chunks=None: ("strategy", []))
    monkeypatch.setattr(sg_module.StrategyGenerator, "save", lambda self, text, ctx: tmp_path / "strategy.md")
    monkeypatch.setattr(sg_module.TestPlanGenerator, "generate", lambda self, ctx, risk, chunks=None: ("plan", []))
    monkeypatch.setattr(sg_module.TestPlanGenerator, "save", lambda self, text, ctx: tmp_path / "plan.md")

    agent = MagicMock()
    agent.retrieve_knowledge.return_value = []
    generator = StrategyGenerator(agent)

    summary = "Runs: 1, distinct tests: 2, executions: 2, overall pass rate: 100.0%"
    generator.generate_all(SAMPLE_CONTEXT, results_summary=summary)

    assert captured["results_summary"] == summary
    print("  PASS: generate_all() passes results_summary through to RiskAnalyzer.analyze()")


def test_generate_all_results_summary_defaults_to_none():
    """Absence of results_summary must not change generate_all()'s call to
    RiskAnalyzer.analyze() — the parameter is purely additive."""
    import inspect
    sig = inspect.signature(StrategyGenerator.generate_all)
    assert sig.parameters["results_summary"].default is None
    print("  PASS: generate_all()'s results_summary parameter defaults to None")
