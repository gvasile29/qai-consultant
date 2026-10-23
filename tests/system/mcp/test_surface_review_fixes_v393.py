"""Regression tests for the surface-review findings on the 3.9.3 PR: a crash on huge team sizes, three
quadratic regex/scan hot paths, the not_a_qa_description response shape, the chunker size cap and header-only
filter, the thousands-separator reading and run-id collisions."""
import json
import time

import pytest

from qai_consultant.core import effort_core
from qai_consultant.mcp import local_index as li
from qai_consultant.mcp import server

TIME_BUDGET_SECONDS = 3.0


def _as_dict(result):
    return result if isinstance(result, dict) else json.loads(result)


def _estimate(**overrides):
    args = dict(
        project_name="Huge", project_description="A backend service that trades batteries", project_type="API/backend",
        tech_stack="Python", team_qa_size="2", team_dev_size="6", timeline="9 months",
        methodology="Scrum", known_risks="optimization model correctness", existing_automation="none", compliance_requirements="none",
    )
    args.update(overrides)
    return _as_dict(server.estimate_qa_effort(**args))


def test_huge_digit_run_team_size_is_capped_not_a_crash():
    result = _estimate(team_qa_size="1" * 400)
    assert "error" not in result or result["error"] != "internal"
    assert any("implausibly large" in w for w in result.get("warnings", []))


def test_team_size_thousands_separator_is_read_as_thousands():
    warnings: list = []
    assert effort_core.parse_team_size("1,000", warnings) == 1000
    assert any("thousands separator" in w for w in warnings)
    assert effort_core.parse_team_size("12,500") == 12500
    assert effort_core.parse_team_size("2,5") == 3  # still a decimal comma


def test_review_numeric_criteria_regex_is_linear_on_a_long_digit_run():
    start = time.monotonic()
    server.review_qa_document("test plan " + "1" * 40000)
    assert time.monotonic() - start < TIME_BUDGET_SECONDS


def test_maturity_ai_gate_is_linear_on_thousands_of_negated_mentions():
    start = time.monotonic()
    server.assess_qa_maturity("We test software. " + "no ai " * 40000)
    assert time.monotonic() - start < TIME_BUDGET_SECONDS


def test_non_body_line_check_does_not_backtrack_on_whitespace():
    start = time.monotonic()
    assert li._body_chars(" " * 50000 + "x") == 1
    assert time.monotonic() - start < 1.0


def test_numeric_criteria_still_count_as_measurable_evidence():
    plan = "# Test Plan\nExit criteria: 95% pass rate and p95 < 500 ms for the checkout API under load."
    result = _as_dict(server.review_qa_document(plan, doc_type="test_plan"))
    measurability = next(d for d in result["dimensions"] if d["name"] == "measurability") \
        if "dimensions" in result else None
    if measurability is not None:
        assert measurability["score"] >= 60


def test_not_a_qa_description_has_the_same_keys_as_a_scored_result():
    scored = _as_dict(server.assess_qa_maturity(
        "We test manually before each release, there is no documentation, no test plan and nobody owns quality. "
        "Bugs are found by customers after shipping to production and fixed ad hoc by whoever has time, and "
        "nothing is written down about what was tested or what was found, so every release is a gamble."
    ))
    refused = _as_dict(server.assess_qa_maturity(
        "Mix flour and water, add salt, let the dough rest overnight, then bake at 230 degrees until golden "
        "brown and the crust crackles when you tap it. Serve warm with butter and a little honey, and keep any "
        "leftovers wrapped in a clean cloth so the loaf stays soft for the next morning."
    ))
    assert scored["status"] == "ok" and refused["status"] == "not_a_qa_description"
    assert set(scored) <= set(refused)
    assert refused["score_reliable"] is False


def test_chunks_never_exceed_chunk_size_including_overlap():
    para = ("Sentence about testing practice that goes on for a while. " * 14).strip()  # ~800 chars
    text = "\n\n".join(f"{para} {i}" for i in range(12))
    chunks = li._simple_chunk_splits(text, li.CHUNK_SIZE, li.CHUNK_OVERLAP)
    assert chunks and max(len(c) for c in chunks) <= li.CHUNK_SIZE


def test_real_kb_chunks_stay_within_chunk_size():
    kb = li.Path(li.__file__).resolve().parents[3] / "knowledge_base"
    longest = 0
    for path in kb.rglob("*.md"):
        for chunk in li._simple_chunk_splits(path.read_text(encoding="utf-8"), li.CHUNK_SIZE, li.CHUNK_OVERLAP):
            longest = max(longest, len(chunk))
    assert longest <= li.CHUNK_SIZE


def test_header_only_raw_chunk_is_dropped_but_its_heading_stays_with_the_next_chunk():
    para = ("Body text that describes how the team plans and runs testing every sprint. " * 11).strip()  # ~800
    para = para[:790]
    text = para + "\n\n## Only A Heading\n\n" + para[::-1].replace(" ", "_")[:790] + "\n\n" + para
    chunks = li._simple_chunk_splits(text, li.CHUNK_SIZE, li.CHUNK_OVERLAP)
    assert all(li._body_chars(c) >= li.MIN_BODY_CHARS for c in chunks)
    assert any("Only A Heading" in c for c in chunks)


def test_duplicate_run_id_suffix_never_collides_with_a_caller_supplied_id():
    xml = '<testsuite name="s"><testcase classname="c" name="t"/></testsuite>'
    entries = [{"run_id": "a", "xml": xml}, {"run_id": "a", "xml": xml}, {"run_id": "a#2", "xml": xml}]
    records, warnings = server._records_from_run_entries(entries)
    run_ids = {r.run_id for r in records}
    assert len(run_ids) == 3, run_ids
    assert any("Duplicate run_id" in w for w in warnings)
