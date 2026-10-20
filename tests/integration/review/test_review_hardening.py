"""
Regression tests for the end-to-end MCP test findings against review_core:
F5 (QA-relevance gate), F6 (test-case rubric), F20 (detection confidence),
F7 (language warning), F19 (input size cap). Also covers text_checks.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from review_core import MAX_REVIEW_CHARS, review_document  # noqa: E402
from text_checks import detect_language, looks_like_qa_document  # noqa: E402

PASTA = (
    "Classic Pasta Carbonara. Ingredients: 400g spaghetti, 150g guanciale, 4 egg yolks, "
    "100g pecorino romano, black pepper and salt. Method: Boil the water, salt it generously, "
    "and cook the spaghetti until al dente. Meanwhile, fry the guanciale until crisp and the fat "
    "has rendered. Whisk the yolks with the cheese and plenty of pepper. Toss the hot pasta with "
    "the guanciale, remove from the heat, and stir in the egg mixture with a splash of pasta "
    "water until creamy. Serve immediately."
)

USER_STORIES = (
    "As a registered user I want to reset my password so that I can regain access to my account.\n"
    "Acceptance criteria: the user receives an email with a reset link which expires after 24 hours.\n"
    "As an administrator I want to deactivate accounts so that former employees lose access to the system.\n"
    "As a customer I want to view my order history so that I can track what I purchased last year."
)

TC_TABLE = """# Login test cases

| ID | Title | Preconditions | Steps | Expected result |
|----|-------|---------------|-------|-----------------|
| TC-001 | Valid login | User exists | 1. Open login 2. Enter valid credentials 3. Submit | User lands on dashboard within 2 seconds |
| TC-002 | Invalid password | User exists | 1. Enter wrong password 2. Submit | Error message "Invalid credentials" is shown |
| TC-003 | Account lockout | User exists | 1. Enter wrong password 5 times | Account is locked for 15 minutes and a lockout email is sent |
| TC-004 | Password length boundary | None | 1. Enter a password of exactly 8 characters 2. Enter 7 characters | 8 characters accepted; 7 characters rejected with message |
| TC-005 | Empty fields | None | 1. Submit with empty fields | Both fields show a required-field error |
"""

TC_HEADINGS = """# Test Cases
## TC-001 Valid login
Precondition: user exists.
Steps:
1. Open the login page
2. Enter valid credentials
3. Click Submit
Expected result: user is redirected to the dashboard.
## TC-002 Lockout after 5 failed attempts
Steps:
1. Enter a wrong password five times
Expected result: the account is locked for 15 minutes.
## TC-003 Boundary password length
Steps:
1. Enter 8 characters
Expected result: accepted; a 7 character password is rejected.
"""

ROMANIAN_PLAN = (
    "Plan de testare pentru aplicatia de comert electronic. Scopul acestui document este de a "
    "descrie abordarea de testare pentru modulul de plata. Echipa de testare va executa testele "
    "functionale si testele de performanta in mediul de staging, iar defectele vor fi raportate "
    "in sistemul de urmarire. Criteriile de intrare sunt ca toate cerintele sa fie implementate, "
    "iar criteriile de iesire sunt ca toate testele critice sa treaca cu succes. Riscurile "
    "principale sunt legate de integrarea cu procesatorul de plati si de volumul mare de "
    "tranzactii in perioada sarbatorilor."
)


# ── F5: QA-relevance gate ────────────────────────────────────────────────────

def test_pasta_recipe_is_not_a_qa_document():
    r = review_document(PASTA)
    assert r.status == "not_a_qa_document"
    assert r.doc_type == "not_a_qa_document"
    assert r.overall_score == 0
    assert r.dimension_scores == {}
    assert r.findings == []
    assert "reason" in r.stats


def test_user_stories_are_not_a_qa_document():
    r = review_document(USER_STORIES)
    assert r.status == "not_a_qa_document"


def test_recipe_rejected_even_with_explicit_doc_type():
    assert review_document(PASTA, doc_type="test_plan").status == "not_a_qa_document"


def test_real_qa_document_status_ok():
    assert review_document(TC_TABLE).status == "ok"


def test_looks_like_qa_document_needs_core_term():
    ok, hits = looks_like_qa_document("The risk and scope of the requirement and acceptance coverage.")
    assert ok is False and "risk" in hits


# ── F6: test-case rubric ─────────────────────────────────────────────────────

def test_test_case_table_autodetected_and_scored_with_case_rubric():
    r = review_document(TC_TABLE)
    assert r.doc_type == "test_cases"
    assert r.detection_confidence == "high"
    assert r.overall_score >= 70
    assert set(r.dimension_scores) == {
        "structure_completeness", "measurability", "traceability", "test_design_coverage"}


def test_test_case_list_has_no_plan_only_findings():
    for doc in (TC_TABLE, TC_HEADINGS):
        r = review_document(doc)
        msgs = " ".join(f.message for f in r.findings)
        assert "objectives" not in msgs.lower()
        assert "in-scope" not in msgs.lower()
        assert "Missing expected section" not in msgs
        assert not any(f.dimension in ("objectives_scope_clarity", "entry_exit_criteria", "risk_coverage")
                       for f in r.findings)


def test_test_case_headings_form_recognised():
    r = review_document(TC_HEADINGS)
    assert r.doc_type == "test_cases"
    assert r.dimension_scores["structure_completeness"] == 100
    assert r.dimension_scores["measurability"] == 100


def test_test_case_ids_are_not_mistaken_for_requirement_links():
    r = review_document(TC_TABLE)
    assert r.dimension_scores["traceability"] == 0
    assert any(f.dimension == "traceability" for f in r.findings)


def test_test_case_requirement_ids_give_full_traceability():
    r = review_document(TC_TABLE + "\nAll cases trace to REQ-101 and REQ-102.\n")
    assert r.dimension_scores["traceability"] == 100


def test_vague_expected_results_in_table_are_flagged():
    table = (
        "| ID | Steps | Expected result |\n|---|---|---|\n"
        "| TC-001 | 1. Login 2. Logout | works correctly |\n"
        "| TC-002 | 1. Pay | as expected |\n"
        "| TC-003 | 1. Refund | works as intended |\n"
        "Precondition: a registered user exists in the test environment of the QA team.\n"
    )
    r = review_document(table, doc_type="test_cases")
    assert r.dimension_scores["measurability"] == 0


def test_test_case_list_without_negative_or_boundary_is_flagged():
    text = (
        "# Test cases\nTC-001 Precondition: user exists. Steps: 1. Open page 2. Click save. "
        "Expected result: record is saved and listed.\n"
        "TC-002 Steps: 1. Open page 2. Click export. Expected result: file is downloaded.\n"
        "TC-003 Steps: 1. Open page 2. Click print. Expected result: print dialog opens.\n"
    )
    r = review_document(text)
    assert r.doc_type == "test_cases"
    msgs = [f.message for f in r.findings if f.dimension == "test_design_coverage"]
    assert any("negative" in m for m in msgs)


# ── F20: detection confidence ────────────────────────────────────────────────

def test_low_confidence_detection_is_reported_and_noted():
    text = ("Notes about testing the application, its defect reports and the release. " * 6)
    r = review_document(text)
    assert r.status == "ok"
    assert r.detection_confidence == "low"
    assert r.detected_type == "test_plan"
    assert "LOW" in r.detection_note
    assert "votes" in r.detection_signals


def test_explicit_doc_type_reports_explicit_confidence():
    r = review_document(TC_TABLE, doc_type="test_cases")
    assert r.detection_confidence == "explicit"
    assert r.detected_type is None
    assert r.detection_note == ""


def test_strong_plan_detects_with_high_confidence():
    plan = (REPO_ROOT / "evals" / "fixtures" / "review" / "strong_test_plan.md").read_text(encoding="utf-8")
    r = review_document(plan)
    assert r.doc_type == "test_plan"
    assert r.detection_confidence == "high"


# ── F7: language warning ─────────────────────────────────────────────────────

def test_romanian_plan_carries_language_warning():
    r = review_document(ROMANIAN_PLAN)
    assert r.language == "ro"
    assert r.score_reliable is False
    assert "NOT reliable" in r.language_warning


def test_english_documents_have_no_language_warning():
    for doc in (TC_TABLE, TC_HEADINGS):
        r = review_document(doc)
        assert r.language_warning == ""
        assert r.score_reliable is True


def test_detect_language_short_text_is_unknown_not_a_false_positive():
    d = detect_language("TC-001 login ok")
    assert d["language"] == "unknown" and d["reliable"] is True


def test_detect_language_flags_other_european_language():
    german = ("Der Testplan beschreibt den Umfang und die Strategie für das Testen der Anwendung. "
              "Die Tests werden von dem Team in der Staging Umgebung ausgeführt und die Fehler "
              "werden in einem System erfasst, das von allen Beteiligten genutzt wird.")
    assert detect_language(german)["reliable"] is False


# ── F19: size cap ────────────────────────────────────────────────────────────

def test_oversized_input_returns_structured_status_not_a_truncated_score():
    r = review_document("test plan scope risk " * (MAX_REVIEW_CHARS // 10))
    assert r.status == "input_too_large"
    assert r.doc_type == "input_too_large"
    assert r.overall_score == 0
    assert r.stats["max_chars"] == MAX_REVIEW_CHARS


def test_input_at_the_cap_is_still_reviewed():
    base = TC_TABLE
    text = base + "x " * ((MAX_REVIEW_CHARS - len(base)) // 2 - 1)
    assert len(text) <= MAX_REVIEW_CHARS
    assert review_document(text).status == "ok"
