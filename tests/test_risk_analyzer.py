"""
Tests for src/risk_analyzer.py — RiskAnalyzer module.

Strategy: build ProjectContext directly (no interactive dialogue),
call RiskAnalyzer.analyze() + .save(), then verify:
  1. All required Risk Register sections are present
  2. Risk IDs (R01, R02, ...) appear in Detailed Risk Analysis
  3. The risk matrix table header is present
  4. File is saved in output/ with the correct name pattern and frontmatter
  5. _build_risk_query includes compliance and known-risk terms
"""

import sys
import os
os.environ["ANONYMIZED_TELEMETRY"] = "False"
os.environ["CHROMA_TELEMETRY"] = "False"

import re
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from dialogue import ProjectContext
from agent import QAIAgent
from risk_analyzer import RiskAnalyzer, build_risk_prompt

# ── BMW Infotainment sample context ──────────────────────────────────────────

BMW_CONTEXT = ProjectContext(
    project_name="BMW Infotainment",
    project_description=(
        "An in-vehicle infotainment system for BMW vehicles controlling "
        "navigation, media, phone connectivity, and climate control, used by drivers"
    ),
    project_type="embedded system",
    tech_stack="C++ with QNX RTOS, HMI layer in HTML5/JavaScript",
    team_qa_size="3",
    team_dev_size="8",
    timeline="18 months, target 2027 model year",
    methodology="Agile with 6-week iterations",
    known_risks=(
        "Safety-critical UI lockouts while driving, "
        "over-the-air update failures, "
        "third-party app sandbox escapes"
    ),
    existing_automation="Unit tests with GoogleTest, some Hardware-in-Loop tests",
    compliance_requirements="ISO 26262 ASIL B, A-SPICE level 2",
)

# ── Required sections (from build_risk_prompt template) ──────────────────────

REQUIRED_SECTIONS = [
    "Executive Summary",
    "Risk Matrix Overview",
    "Detailed Risk Analysis",
    "Risk-Based Testing Priorities",
    "Recommendations",
]

# ── Helpers ───────────────────────────────────────────────────────────────────

def load_agent():
    print("  Loading QAIAgent (ChromaDB + embeddings)...")
    return QAIAgent()


# ── Fixtures (pytest mode only; the __main__ runner below wires these by hand) ──

@pytest.fixture(scope="module")
def agent():
    """Real QAIAgent for the LLM smoke tests; SKIP (not ERROR) without live API keys."""
    try:
        return load_agent()
    except Exception as exc:
        pytest.skip(f"live agent unavailable ({type(exc).__name__}: {exc}) — requires API keys")


@pytest.fixture(scope="module")
def _generated_risk_register(agent):
    """One real analyze() call, shared by risk_register/sources so downstream tests
    don't each pay for a separate LLM+RAG round trip."""
    return RiskAnalyzer(agent).analyze(BMW_CONTEXT)


@pytest.fixture(scope="module")
def risk_register(_generated_risk_register):
    return _generated_risk_register[0]


@pytest.fixture(scope="module")
def sources(_generated_risk_register):
    return _generated_risk_register[1]


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_build_risk_prompt_structure():
    """build_risk_prompt() includes all required section headings and project name."""
    prompt = build_risk_prompt(BMW_CONTEXT, knowledge_context="[no knowledge]")

    assert "BMW Infotainment" in prompt, "Project name missing from prompt"
    for section in REQUIRED_SECTIONS:
        assert section in prompt, f"Required section '{section}' missing from prompt template"

    print("  PASS: All required sections present in risk prompt template")


def test_build_risk_query_includes_compliance_and_risks():
    """_build_risk_query() incorporates compliance and known-risk terms."""
    analyzer = RiskAnalyzer(agent=None)  # agent not used for query building
    query = analyzer._build_risk_query(BMW_CONTEXT)

    assert "embedded system" in query.lower(), "project_type missing from query"
    assert "iso 26262" in query.lower() or "a-spice" in query.lower(), \
        "compliance requirements missing from query"
    assert "safety" in query.lower() or "lockout" in query.lower() or "ota" in query.lower() \
        or "sandbox" in query.lower() or "over-the-air" in query.lower(), \
        "known_risks missing from query"

    print(f"  PASS: RAG query = {query}")


def test_risk_register_sections(risk_register: str):
    """analyze() returns markdown with all required sections."""
    missing = [s for s in REQUIRED_SECTIONS if s not in risk_register]
    assert not missing, f"Missing sections in Risk Register: {missing}"

    print("  PASS: All required sections present in generated Risk Register")
    for section in REQUIRED_SECTIONS:
        print(f"    + {section}")


def test_risk_ids_present(risk_register: str):
    """Detailed Risk Analysis contains at least R01 and R02."""
    assert "R01" in risk_register, "R01 missing from Detailed Risk Analysis"
    assert "R02" in risk_register, "R02 missing from Detailed Risk Analysis"

    risk_ids = re.findall(r'\bR\d{2}\b', risk_register)
    unique_ids = sorted(set(risk_ids))
    assert len(unique_ids) >= 2, f"Expected at least 2 risk IDs, found: {unique_ids}"

    print(f"  PASS: Risk IDs found: {', '.join(unique_ids)}")


def test_risk_matrix_table(risk_register: str):
    """Risk Matrix Overview contains a markdown table with required columns."""
    assert "Risk ID" in risk_register, "Table header 'Risk ID' missing"
    assert "Likelihood" in risk_register, "Table column 'Likelihood' missing"
    assert "Impact" in risk_register, "Table column 'Impact' missing"
    assert "Risk Level" in risk_register, "Table column 'Risk Level' missing"

    # Verify at least one table row with a risk ID (tolerate markdown bold: | **R01** |)
    assert re.search(r'\|\s*\*{0,2}R\d{2}\*{0,2}\s*\|', risk_register), \
        "No table row with risk ID found in Risk Matrix"

    print("  PASS: Risk matrix table present with correct columns and data rows")


def test_save_creates_file_with_frontmatter(agent, risk_register: str):
    """save() creates a file in output/ with the correct name and YAML frontmatter."""
    analyzer = RiskAnalyzer(agent)
    output_path = analyzer.save(risk_register, BMW_CONTEXT)

    assert output_path.exists(), f"Output file not found: {output_path}"
    assert output_path.name.startswith("risk_register_BMW_Infotainment_"), \
        f"Unexpected filename: {output_path.name}"
    assert output_path.suffix == ".md", "Expected .md file"

    content = output_path.read_text(encoding="utf-8")
    assert "generated_by: QAI Consultant" in content, "Missing frontmatter: generated_by"
    assert "document_type: Risk Register" in content, "Missing frontmatter: document_type"
    assert "project: BMW Infotainment" in content, "Missing frontmatter: project"
    assert risk_register in content, "Risk register body missing from saved file"

    print(f"  PASS: File saved: {output_path.relative_to(REPO_ROOT)}")
    print(f"        Frontmatter: {content[:160].strip()}")


def test_save_includes_ai_generated_footer(tmp_path):
    """save() appends the visible AI-generated footer to the saved file body (v2.5.2)."""
    analyzer = RiskAnalyzer(agent=None)
    body = "# Risk Register — Sample\n\nSome generated body text."
    output_path = analyzer.save(body, BMW_CONTEXT, output_dir=tmp_path)

    content = output_path.read_text(encoding="utf-8")
    assert "AI-generated" in content, "AI-generated footer missing from saved Risk Register"
    assert content.index(body) < content.index("AI-generated"), \
        "Footer must come after the document body"

    print("  PASS: save() includes visible AI-generated footer")


def test_sources_non_empty(sources: list):
    """analyze() returns at least one knowledge source."""
    assert sources, "Expected at least one source, got empty list"
    print(f"  PASS: {len(sources)} knowledge source(s) used:")
    for s in sources:
        print(f"    - {s}")


# ── Runner ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tests_no_llm = [
        ("build_risk_prompt() has all required sections",  test_build_risk_prompt_structure),
        ("_build_risk_query() includes compliance + risks", test_build_risk_query_includes_compliance_and_risks),
    ]

    print("=" * 65)
    print("  QAI Consultant — Risk Analyzer Tests")
    print("=" * 65)

    passed = failed = 0

    # ── Tests that don't need the LLM ────────────────────────────────────────
    for name, fn in tests_no_llm:
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

    # ── Tests that need the LLM (Ollama + Mistral) ────────────────────────────
    print(f"\n{'=' * 65}")
    print("  Loading agent + running LLM tests (requires Ollama)...")
    print(f"{'=' * 65}")

    try:
        agent = load_agent()
    except Exception as e:
        print(f"\n  ERROR loading agent: {e}")
        print("  Skipping LLM-dependent tests.")
        print(f"\n{'=' * 65}")
        print(f"  Results: {passed} passed, {failed} failed (LLM tests skipped)")
        print(f"{'=' * 65}")
        sys.exit(1 if failed else 0)

    # Generate risk register once; feed to subsequent tests
    risk_register = sources = None

    print("  Calling RiskAnalyzer.analyze() with BMW context...")
    try:
        risk_register, sources = RiskAnalyzer(agent).analyze(BMW_CONTEXT)
    except Exception as e:
        import traceback
        print(f"\n  ERROR generating Risk Register: {e}")
        traceback.print_exc()
        failed += 1

    if risk_register:
        print("\n[TEST] analyze() returns all required sections")
        try:
            test_risk_register_sections(risk_register)
            passed += 1
        except AssertionError as e:
            print(f"  FAIL: {e}")
            failed += 1
        except Exception as e:
            import traceback
            print(f"  ERROR: {type(e).__name__}: {e}")
            traceback.print_exc()
            failed += 1

    if risk_register:
        for name, fn, args in [
            ("Detailed Risk Analysis has R01, R02, ... IDs",     test_risk_ids_present,      (risk_register,)),
            ("Risk Matrix table present with correct columns",    test_risk_matrix_table,     (risk_register,)),
            ("sources list is non-empty",                         test_sources_non_empty,     (sources,)),
            ("save() creates file in output/ with frontmatter",   test_save_creates_file_with_frontmatter, (agent, risk_register)),
        ]:
            print(f"\n[TEST] {name}")
            try:
                fn(*args)
                passed += 1
            except AssertionError as e:
                print(f"  FAIL: {e}")
                failed += 1
            except Exception as e:
                import traceback
                print(f"  ERROR: {type(e).__name__}: {e}")
                traceback.print_exc()
                failed += 1

    print(f"\n{'=' * 65}")
    print(f"  Results: {passed} passed, {failed} failed")
    print(f"{'=' * 65}")

    sys.exit(0 if failed == 0 else 1)
