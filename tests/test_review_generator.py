"""
Tests for src/review_generator.py — narrative prompt building, report
markdown assembly, and save() conventions for the QA Document Quality
Review (F1, v3.1). No LLM call is made here — only the pure prompt/markdown
builders and the file-save path.
"""

import shutil
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from review_core import ReviewFinding, ReviewResult  # noqa: E402
from review_generator import (  # noqa: E402
    REVIEW_SYSTEM_PROMPT,
    build_review_prompt,
    build_review_report_markdown,
    save_review_report,
)

_SAMPLE_RESULT = ReviewResult(
    doc_type="test_plan",
    overall_score=72,
    dimension_scores={"structure_completeness": 80, "risk_coverage": 60},
    findings=[
        ReviewFinding(
            dimension="risk_coverage", severity="major",
            message="Risks are not rated by severity.", evidence="severity markers",
            citation_queries=["risk likelihood impact matrix"],
        ),
        ReviewFinding(
            dimension="structure_completeness", severity="minor",
            message="Missing expected section: approvals.", evidence="approvals",
            citation_queries=["IEEE 829 approvals"],
        ),
    ],
    stats={"char_count": 1000, "word_count": 150, "heading_count": 5, "auto_detected": False},
)

_EMPTY_FINDINGS_RESULT = ReviewResult(
    doc_type="test_strategy",
    overall_score=95,
    dimension_scores={"structure_completeness": 100},
    findings=[],
    stats={"char_count": 2000, "word_count": 300, "heading_count": 8, "auto_detected": True},
)


# ── build_review_prompt ─────────────────────────────────────────────────────────

def test_build_review_prompt_includes_overall_score():
    prompt = build_review_prompt(_SAMPLE_RESULT, "some knowledge context")
    assert "72/100" in prompt


def test_build_review_prompt_includes_dimension_scores():
    prompt = build_review_prompt(_SAMPLE_RESULT, "")
    assert "Structure Completeness: 80/100" in prompt
    assert "Risk Coverage: 60/100" in prompt


def test_build_review_prompt_includes_findings():
    prompt = build_review_prompt(_SAMPLE_RESULT, "")
    assert "[MAJOR]" in prompt
    assert "Risks are not rated by severity." in prompt
    assert "[MINOR]" in prompt


def test_build_review_prompt_no_findings_says_so():
    prompt = build_review_prompt(_EMPTY_FINDINGS_RESULT, "")
    assert "No findings — every mechanical check passed." in prompt


def test_build_review_prompt_includes_knowledge_context():
    prompt = build_review_prompt(_SAMPLE_RESULT, "UNIQUE_KB_MARKER_XYZ")
    assert "UNIQUE_KB_MARKER_XYZ" in prompt


def test_build_review_prompt_instructs_not_to_rescore():
    prompt = build_review_prompt(_SAMPLE_RESULT, "")
    assert "Do NOT invent a different score" in prompt


def test_review_system_prompt_forbids_rescoring():
    assert "never invent, change, or contradict" in REVIEW_SYSTEM_PROMPT.lower() \
        or "never invent" in REVIEW_SYSTEM_PROMPT


# ── build_review_report_markdown ────────────────────────────────────────────────

def test_build_review_report_markdown_includes_score_and_findings():
    md = build_review_report_markdown(_SAMPLE_RESULT, "")
    assert "**Overall score:** 72/100" in md
    assert "MAJOR" in md
    assert "MINOR" in md


def test_build_review_report_markdown_no_findings_says_so():
    md = build_review_report_markdown(_EMPTY_FINDINGS_RESULT, "")
    assert "every mechanical check in the rubric passed" in md


def test_build_review_report_markdown_appends_narrative_when_given():
    md = build_review_report_markdown(_SAMPLE_RESULT, "# QA Document Quality Review\n\nNarrative body text.")
    assert "Narrative body text." in md
    assert md.rstrip().endswith("Narrative body text.")


def test_build_review_report_markdown_omits_narrative_section_when_empty():
    md = build_review_report_markdown(_SAMPLE_RESULT, "")
    assert "---" not in md.split("## Findings")[-1]


def test_build_review_report_markdown_is_deterministic():
    md1 = build_review_report_markdown(_SAMPLE_RESULT, "narrative")
    md2 = build_review_report_markdown(_SAMPLE_RESULT, "narrative")
    assert md1 == md2


# ── save_review_report ───────────────────────────────────────────────────────────

def test_save_review_report_writes_file_with_front_matter_and_footer():
    tmp_dir = Path(tempfile.mkdtemp())
    try:
        path = save_review_report("# QA Document Quality Review\n\nBody.", "My Project", output_dir=tmp_dir)
        assert path.exists()
        content = path.read_text(encoding="utf-8")
        assert content.startswith("---\n")
        assert "ai_generated: true" in content
        assert "AI-generated content" in content
        assert "Body." in content
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_save_review_report_sanitizes_filename():
    tmp_dir = Path(tempfile.mkdtemp())
    try:
        path = save_review_report("body", "My:Weird/Project*Name?", output_dir=tmp_dir)
        assert path.exists()
        for bad_char in [':', '/', '*', '?']:
            assert bad_char not in path.name
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_save_review_report_filename_starts_with_quality_review_prefix():
    tmp_dir = Path(tempfile.mkdtemp())
    try:
        path = save_review_report("body", "Acme", output_dir=tmp_dir)
        assert path.name.startswith("quality_review_Acme_")
        assert path.name.endswith(".md")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_save_review_report_creates_output_dir_if_missing():
    tmp_dir = Path(tempfile.mkdtemp()) / "nested" / "output"
    try:
        assert not tmp_dir.exists()
        path = save_review_report("body", "Acme", output_dir=tmp_dir)
        assert tmp_dir.exists()
        assert path.exists()
    finally:
        shutil.rmtree(tmp_dir.parent.parent, ignore_errors=True)


def test_save_review_report_handles_empty_label():
    tmp_dir = Path(tempfile.mkdtemp())
    try:
        path = save_review_report("body", "", output_dir=tmp_dir)
        assert path.exists()
        assert "Document" in path.name
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
