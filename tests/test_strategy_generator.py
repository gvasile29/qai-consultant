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


def _stub_all_stages(monkeypatch, tmp_path):
    """Wire every one of the 4 generate_all() stages to a cheap, successful
    stub. Individual tests below override one stage with a raising stub to
    exercise that stage's except-branch in isolation."""
    monkeypatch.setattr(sg_module.RiskAnalyzer, "analyze",
                         lambda self, context, chunks=None, results_summary=None: ("# Risk Register", ["[Standard] risk.md"]))
    monkeypatch.setattr(sg_module.RiskAnalyzer, "save", lambda self, text, ctx: tmp_path / "risk.md")
    monkeypatch.setattr(sg_module.EffortEstimator, "estimate", lambda self, ctx, risk: ("# Effort Report", {"total_days": 5}))
    monkeypatch.setattr(sg_module.EffortEstimator, "save", lambda self, text, ctx: tmp_path / "effort.md")
    monkeypatch.setattr(sg_module.StrategyGenerator, "generate", lambda self, ctx, chunks=None: ("# Test Strategy", ["[Standard] strategy.md"]))
    monkeypatch.setattr(sg_module.StrategyGenerator, "save", lambda self, text, ctx: tmp_path / "strategy.md")
    monkeypatch.setattr(sg_module.TestPlanGenerator, "generate", lambda self, ctx, risk, chunks=None: ("# Test Plan", ["[Standard] plan.md"]))
    monkeypatch.setattr(sg_module.TestPlanGenerator, "save", lambda self, text, ctx: tmp_path / "plan.md")


def test_generate_all_risk_failure_still_populates_other_steps(monkeypatch, tmp_path):
    """A Risk Register failure (step 1/4) must not prevent Effort, Strategy,
    or Test Plan from running — CLAUDE.md's 'Per-step isolation' gotcha."""
    _stub_all_stages(monkeypatch, tmp_path)
    monkeypatch.setattr(sg_module.RiskAnalyzer, "analyze",
                         lambda self, context, chunks=None, results_summary=None: (_ for _ in ()).throw(RuntimeError("boom")))

    agent = MagicMock()
    agent.retrieve_knowledge.return_value = []
    result = StrategyGenerator(agent).generate_all(SAMPLE_CONTEXT)

    assert result["risk_register"] == ""
    assert result["risk_sources"] == []
    assert result["risk_path"] is None
    assert result["effort_report"] == "# Effort Report"
    assert result["strategy"] == "# Test Strategy"
    assert result["test_plan"] == "# Test Plan"
    print("  PASS: Risk Register failure isolated, Effort/Strategy/Test Plan still populated")


def test_generate_all_effort_failure_still_populates_other_steps(monkeypatch, tmp_path):
    """An Effort Estimation failure (step 2/4) must not prevent Strategy or
    Test Plan from running, and must not discard the already-generated
    Risk Register."""
    _stub_all_stages(monkeypatch, tmp_path)
    monkeypatch.setattr(sg_module.EffortEstimator, "estimate",
                         lambda self, ctx, risk: (_ for _ in ()).throw(RuntimeError("boom")))

    agent = MagicMock()
    agent.retrieve_knowledge.return_value = []
    result = StrategyGenerator(agent).generate_all(SAMPLE_CONTEXT)

    assert result["risk_register"] == "# Risk Register"
    assert result["effort_report"] == ""
    assert result["effort_data"] == {}
    assert result["effort_path"] is None
    assert result["strategy"] == "# Test Strategy"
    assert result["test_plan"] == "# Test Plan"
    print("  PASS: Effort Estimation failure isolated, Risk/Strategy/Test Plan still populated")


def test_generate_all_strategy_failure_still_populates_other_steps(monkeypatch, tmp_path):
    """A Test Strategy failure (step 3/4) must not prevent Test Plan from
    running, and must not discard Risk Register or Effort results."""
    _stub_all_stages(monkeypatch, tmp_path)
    monkeypatch.setattr(sg_module.StrategyGenerator, "generate",
                         lambda self, ctx, chunks=None: (_ for _ in ()).throw(ValueError("LLM returned empty Test Strategy")))

    agent = MagicMock()
    agent.retrieve_knowledge.return_value = []
    result = StrategyGenerator(agent).generate_all(SAMPLE_CONTEXT)

    assert result["risk_register"] == "# Risk Register"
    assert result["effort_report"] == "# Effort Report"
    assert result["strategy"] == ""
    assert result["sources"] == []
    assert result["strategy_path"] is None
    assert result["test_plan"] == "# Test Plan"
    print("  PASS: Test Strategy failure isolated, Risk/Effort/Test Plan still populated")


def test_generate_all_test_plan_failure_still_populates_other_steps(monkeypatch, tmp_path):
    """A Test Plan failure (step 4/4, the last stage) must not discard the
    results already produced by Risk Register, Effort, or Strategy."""
    _stub_all_stages(monkeypatch, tmp_path)
    monkeypatch.setattr(sg_module.TestPlanGenerator, "generate",
                         lambda self, ctx, risk, chunks=None: (_ for _ in ()).throw(RuntimeError("boom")))

    agent = MagicMock()
    agent.retrieve_knowledge.return_value = []
    result = StrategyGenerator(agent).generate_all(SAMPLE_CONTEXT)

    assert result["risk_register"] == "# Risk Register"
    assert result["effort_report"] == "# Effort Report"
    assert result["strategy"] == "# Test Strategy"
    assert result["test_plan"] == ""
    assert result["test_plan_sources"] == []
    assert result["test_plan_path"] is None
    print("  PASS: Test Plan failure isolated, Risk/Effort/Strategy still populated")


def test_generate_all_rag_prefetch_failure_falls_back_to_empty_chunks(monkeypatch, tmp_path):
    """A Pinecone/RAG prefetch timeout on any of the 3 futures must fall back
    to an empty chunk list rather than aborting the whole pipeline —
    CLAUDE.md's 'RAG futures' gotcha."""
    _stub_all_stages(monkeypatch, tmp_path)

    agent = MagicMock()
    agent.retrieve_knowledge.side_effect = RuntimeError("Pinecone timeout")
    result = StrategyGenerator(agent).generate_all(SAMPLE_CONTEXT)

    # All 4 stages still ran and produced their stubbed output despite every
    # RAG future raising.
    assert result["risk_register"] == "# Risk Register"
    assert result["effort_report"] == "# Effort Report"
    assert result["strategy"] == "# Test Strategy"
    assert result["test_plan"] == "# Test Plan"
    print("  PASS: RAG prefetch failure on all 3 futures falls back to [] without aborting the pipeline")
