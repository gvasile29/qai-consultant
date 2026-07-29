"""
Tests for machine-readable AI-generated marking (EU AI Act Article 50(2), v3.0
step 9): YAML front matter (ai_generated: true, generator name/version, model)
in every generated document's Markdown save, and equivalent PDF metadata
(/Author, /Subject, /Keywords) in PDF exports.

Covers ai_disclosure.build_front_matter()/pdf_meta_html() directly, plus each
of the 4 document generators' save() paths (Risk Register, Effort Estimation,
Test Strategy, Test Plan) — all structural, no live LLM calls needed since
save() only writes what it's given.
"""

import io
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pypdf

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from ai_disclosure import build_front_matter, pdf_meta_html
from agent import MISTRAL_MODEL
from dialogue import ProjectContext
from effort_estimator import EffortEstimator
from pdf_export import markdown_to_pdf
from risk_analyzer import RiskAnalyzer
from strategy_generator import StrategyGenerator
from test_plan_generator import TestPlanGenerator
from version import __version__

SAMPLE_CONTEXT = ProjectContext(
    project_name="MarkingTestProject",
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


# ── build_front_matter() / pdf_meta_html() directly ─────────────────────────────

def test_build_front_matter_contains_required_fields():
    fm = build_front_matter("Risk Register", "Acme Project", MISTRAL_MODEL)
    assert fm.startswith("---\n")
    assert fm.rstrip().endswith("---")
    assert "ai_generated: true" in fm
    assert f"generator_version: {__version__}" in fm
    assert f"model: {MISTRAL_MODEL}" in fm
    assert "document_type: Risk Register" in fm
    assert "project: Acme Project" in fm
    assert "generated_by: QAI Consultant" in fm


def test_build_front_matter_extra_fields():
    fm = build_front_matter("Test Plan", "Acme", MISTRAL_MODEL, extra={"standard": "IEEE 829"})
    assert "standard: IEEE 829" in fm
    # extra fields land before the closing delimiter, not after
    assert fm.rstrip().endswith("---")
    assert fm.index("standard: IEEE 829") < fm.rindex("---")


def test_pdf_meta_html_contains_expected_tags():
    html = pdf_meta_html(MISTRAL_MODEL)
    assert 'name="author"' in html
    assert 'name="subject"' in html
    assert 'name="keywords"' in html
    assert __version__ in html
    assert MISTRAL_MODEL in html
    assert "Article 50(2)" in html


def test_ai_disclosure_module_has_no_third_party_or_agent_imports():
    """ai_disclosure.py must stay importable from any code path, including the
    keyless MCP server path — it must not import agent.py (Pinecone/Mistral/
    OpenAI) or any third-party package. Checked via actual import statements
    (AST), not a substring scan, since the module's own docstring discusses
    agent.py in prose (explaining why it's NOT imported)."""
    import ast
    source = (SRC_DIR / "ai_disclosure.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    allowed = {"datetime", "version", "__future__", "base64", "pathlib"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".")[0] in allowed, f"Unexpected import: {alias.name}"
        elif isinstance(node, ast.ImportFrom):
            assert node.module and node.module.split(".")[0] in allowed, f"Unexpected import from: {node.module}"


# ── Markdown front matter present in every generator's save() path ─────────────

def test_risk_register_save_has_ai_generated_marking(tmp_path):
    analyzer = RiskAnalyzer(agent=None)
    output_path = analyzer.save("# Risk Register body", SAMPLE_CONTEXT, output_dir=tmp_path)
    content = output_path.read_text(encoding="utf-8")
    assert "ai_generated: true" in content
    assert f"generator_version: {__version__}" in content
    assert f"model: {MISTRAL_MODEL}" in content
    assert "AI-generated content" in content  # human-visible footer still present too


def test_effort_estimation_save_has_ai_generated_marking(tmp_path):
    estimator = EffortEstimator(agent=None)
    output_path = estimator.save("# Effort Estimation body", SAMPLE_CONTEXT, output_dir=tmp_path)
    content = output_path.read_text(encoding="utf-8")
    assert "ai_generated: true" in content
    assert f"generator_version: {__version__}" in content
    assert f"model: {MISTRAL_MODEL}" in content


def test_test_strategy_save_has_ai_generated_marking(tmp_path):
    generator = StrategyGenerator(MagicMock())
    output_path = generator.save("# Test Strategy body", SAMPLE_CONTEXT, output_dir=tmp_path)
    content = output_path.read_text(encoding="utf-8")
    assert "ai_generated: true" in content
    assert f"generator_version: {__version__}" in content
    assert f"model: {MISTRAL_MODEL}" in content
    assert "document_type: Test Strategy" in content  # was missing entirely before step 9


def test_test_plan_save_has_ai_generated_marking(tmp_path):
    generator = TestPlanGenerator(MagicMock())
    output_path = generator.save("# Test Plan body", SAMPLE_CONTEXT, output_dir=tmp_path)
    content = output_path.read_text(encoding="utf-8")
    assert "ai_generated: true" in content
    assert f"generator_version: {__version__}" in content
    assert f"model: {MISTRAL_MODEL}" in content
    assert "standard: IEEE 829" in content


def test_marking_survives_special_characters_in_project_name(tmp_path):
    """Filename sanitization (space/invalid-char stripping) must not affect the
    front matter's `project:` field, which keeps the original display name."""
    context = ProjectContext(
        project_name="Acme: Project Hub (β) — Tëam/Sync™ #1",
        project_description="desc", project_type="web app", tech_stack="Django",
        team_qa_size="1", team_dev_size="2", timeline="4 weeks", methodology="Scrum",
        known_risks="None", existing_automation="None", compliance_requirements="none",
    )
    analyzer = RiskAnalyzer(agent=None)
    output_path = analyzer.save("# Risk Register body", context, output_dir=tmp_path)
    assert output_path.exists()
    content = output_path.read_text(encoding="utf-8")
    assert "ai_generated: true" in content
    assert "project: Acme: Project Hub" in content  # original display name preserved


# ── PDF metadata survives conversion ────────────────────────────────────────────

def test_pdf_export_carries_ai_generated_metadata():
    meta_html = pdf_meta_html(MISTRAL_MODEL)
    pdf_bytes = markdown_to_pdf("# Sample Document\n\nSome body text.", "Risk Register", meta_html)
    assert pdf_bytes is not None

    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    metadata = reader.metadata
    assert metadata is not None
    assert __version__ in (metadata.author or "")
    assert "AI-generated" in (metadata.subject or "")
    assert "ai-generated" in (metadata.get("/Keywords") or "").lower()
    assert MISTRAL_MODEL in (metadata.get("/Keywords") or "")


def test_pdf_export_without_extra_meta_html_still_works():
    """extra_meta_html defaults to "" — existing callers that don't pass it
    (if any remain) must not break."""
    pdf_bytes = markdown_to_pdf("# Sample Document\n\nSome body text.", "Risk Register")
    assert pdf_bytes is not None
