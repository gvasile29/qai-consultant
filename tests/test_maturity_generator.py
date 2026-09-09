"""
Tests for src/maturity_generator.py — narrative prompt building, report
markdown assembly, and save() conventions for the QA Maturity Assessment
(v3.5). No LLM call is made here — only the pure prompt/markdown builders
and the file-save path. Mirrors tests/test_review_generator.py's structure.
"""

import shutil
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from maturity_core import MaturityFinding, MaturityResult  # noqa: E402
from maturity_generator import (  # noqa: E402
    MATURITY_SYSTEM_PROMPT,
    build_maturity_prompt,
    build_maturity_report_markdown,
    save_maturity_report,
)

_SAMPLE_RESULT = MaturityResult(
    status="ok",
    indicative_tmmi_level=2,
    tmmi_dimension_scores={"test_policy_and_strategy": 100, "peer_reviews": 0},
    ai_act_relevant=True,
    ai_act_dimension_scores={"risk_management": 0, "human_oversight": 100},
    findings=[
        MaturityFinding(
            framework="tmmi", dimension="peer_reviews", level=3, severity="minor",
            message="No evidence found for 'review_type'.", evidence="review_type",
            citation_queries=["TMMi Peer Reviews process area"],
        ),
        MaturityFinding(
            framework="eu_ai_act", dimension="risk_management", level=None, severity="critical",
            message="No evidence found for risk management (Article 9 risk management system).",
            evidence="risk_management",
            citation_queries=["EU AI Act Article 9 risk management system"],
        ),
    ],
    disclaimer="This is an informal indicative signal, not a certified TMMi appraisal.",
    stats={"char_count": 1000, "word_count": 150, "ai_act_relevant": True},
)

_NO_FINDINGS_RESULT = MaturityResult(
    status="ok",
    indicative_tmmi_level=3,
    tmmi_dimension_scores={"test_policy_and_strategy": 100},
    ai_act_relevant=False,
    ai_act_dimension_scores={},
    findings=[],
    disclaimer="This is an informal indicative signal, not a certified TMMi appraisal.",
    stats={"char_count": 2000, "word_count": 300, "ai_act_relevant": False},
)


# ── build_maturity_prompt ────────────────────────────────────────────────────

def test_build_maturity_prompt_includes_indicative_level():
    prompt = build_maturity_prompt(_SAMPLE_RESULT, "some knowledge context")
    assert "2" in prompt


def test_build_maturity_prompt_includes_findings():
    prompt = build_maturity_prompt(_SAMPLE_RESULT, "")
    assert "[CRITICAL]" in prompt
    assert "risk management" in prompt.lower()


def test_build_maturity_prompt_no_findings_says_so():
    prompt = build_maturity_prompt(_NO_FINDINGS_RESULT, "")
    assert "no findings" in prompt.lower()


def test_build_maturity_prompt_includes_knowledge_context():
    prompt = build_maturity_prompt(_SAMPLE_RESULT, "UNIQUE_KB_MARKER_XYZ")
    assert "UNIQUE_KB_MARKER_XYZ" in prompt


def test_build_maturity_prompt_instructs_not_to_rescore():
    prompt = build_maturity_prompt(_SAMPLE_RESULT, "")
    assert "do not invent" in prompt.lower() or "do not re-score" in prompt.lower()


def test_maturity_system_prompt_forbids_rescoring():
    assert "never invent" in MATURITY_SYSTEM_PROMPT.lower() or "never change" in MATURITY_SYSTEM_PROMPT.lower()


# ── build_maturity_report_markdown ───────────────────────────────────────────

def test_build_maturity_report_markdown_includes_level_and_disclaimer():
    md = build_maturity_report_markdown(_SAMPLE_RESULT, "")
    assert "Indicative TMMi Level" in md
    assert _SAMPLE_RESULT.disclaimer in md


def test_build_maturity_report_markdown_includes_ai_act_section_when_relevant():
    md = build_maturity_report_markdown(_SAMPLE_RESULT, "")
    assert "EU AI Act" in md
    assert "risk_management".replace("_", " ") in md.lower()


def test_build_maturity_report_markdown_omits_ai_act_section_when_not_relevant():
    md = build_maturity_report_markdown(_NO_FINDINGS_RESULT, "")
    assert "EU AI Act Readiness" not in md


def test_build_maturity_report_markdown_appends_narrative_when_given():
    md = build_maturity_report_markdown(_SAMPLE_RESULT, "# QA Maturity Assessment\n\nNarrative body text.")
    assert "Narrative body text." in md
    assert md.rstrip().endswith("Narrative body text.")


def test_build_maturity_report_markdown_is_deterministic():
    md1 = build_maturity_report_markdown(_SAMPLE_RESULT, "narrative")
    md2 = build_maturity_report_markdown(_SAMPLE_RESULT, "narrative")
    assert md1 == md2


# ── save_maturity_report ──────────────────────────────────────────────────────

def test_save_maturity_report_writes_file_with_front_matter_and_footer():
    tmp_dir = Path(tempfile.mkdtemp())
    try:
        path = save_maturity_report("# QA Maturity Assessment\n\nBody.", "My Project", output_dir=tmp_dir)
        assert path.exists()
        content = path.read_text(encoding="utf-8")
        assert content.startswith("---\n")
        assert "ai_generated: true" in content
        assert "AI-generated content" in content
        assert "Body." in content
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_save_maturity_report_sanitizes_filename():
    tmp_dir = Path(tempfile.mkdtemp())
    try:
        path = save_maturity_report("body", "My:Weird/Project*Name?", output_dir=tmp_dir)
        assert path.exists()
        for bad_char in [':', '/', '*', '?']:
            assert bad_char not in path.name
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_save_maturity_report_filename_starts_with_maturity_assessment_prefix():
    tmp_dir = Path(tempfile.mkdtemp())
    try:
        path = save_maturity_report("body", "Acme", output_dir=tmp_dir)
        assert path.name.startswith("maturity_assessment_Acme_")
        assert path.name.endswith(".md")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_save_maturity_report_handles_empty_label():
    tmp_dir = Path(tempfile.mkdtemp())
    try:
        path = save_maturity_report("body", "", output_dir=tmp_dir)
        assert path.exists()
        assert "Assessment" in path.name
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
