"""relabel_unknown_risk_ids: Strategy IDs missing from the Risk Register are renamed,
not deleted. The sample lines are the shapes ministral-14b produced in the first
multi-template smoke run (microservices and automotive Strategies)."""

from unittest.mock import MagicMock

from qai_consultant.core.dialogue import ProjectContext
from qai_consultant.generation import consistency as cons
from qai_consultant.generation.strategy_generator import StrategyGenerator

REGISTER = """## Risk Matrix Overview

| Risk ID | Description | Likelihood | Impact | Risk Level | Priority |
|---|---|---|---|---|---|
| R01 | Gateway failures | High | High | Critical | P1 |
| R02 | Wrong dispatch | Medium | High | High | P1 |
| R07 | Reporting drift | Low | Low | Low | P3 |
"""
LEDGER = cons.risk_ledger(REGISTER)


def relabel(text: str) -> str:
    return cons.relabel_unknown_risk_ids(text, LEDGER)


def test_known_ids_are_untouched():
    text = "R01 and R02 are covered; R07 is accepted."
    assert relabel(text) == text


def test_real_model_shapes_keep_their_structure():
    bold_table_line = "- **R08 (Additional)** | **Lack of Observability** | Medium | High | - Integrate **OpenTelemetry**"
    bold_bullet = "- **R08 (Observability)**: Deploy **OpenTelemetry** for distributed tracing."
    pipe_line = "- **R08** | **Incomplete MC/DC Coverage for ASIL C Components** (Low/Likelihood, High/Impact)"
    assert relabel(bold_table_line) == bold_table_line.replace("R08", "ADD-08")
    assert relabel(bold_bullet) == bold_bullet.replace("R08", "ADD-08")
    assert relabel(pipe_line) == pipe_line.replace("R08", "ADD-08")


def test_nothing_is_deleted_in_the_shapes_that_broke_removal():
    for text in ("Risks R01-R09 are covered", "R01 and R08", "See R08.", "### R08 Fallback", "- R09\n- R01",
                 "| R08 | Gurobi | High |", "R08: Gurobi fallback"):
        out = relabel(text)
        assert "R08" not in out and "R09" not in out
        assert len(out) == len(text) + out.count("ADD-") * 3  # "R" becomes "ADD-": +3 chars each
    assert relabel("**R08** is key") == "**ADD-08** is key"


def test_regulation_numbers_are_left_alone():
    for text in (
        "Homologation per UN R10 and ECE R13.", "UNECE R10 EMC", "ECE-R10", "UN-R10", "ISO 26262 R20",
        "CVSS R10", "IEC 61508 Part 2 R10", "Regulation (EU) 2019/2144 R10", "NIST SP 800-53 R5 R10",
    ):
        assert relabel(text) == text, text


def test_ordinary_prose_words_do_not_shield_an_invented_id():
    for word in ("There is no", "Rule", "Section 4 No.", "within No", "the annex and"):
        assert "ADD-08" in relabel(f"{word} R08 applies"), word


def test_standards_word_in_an_earlier_sentence_does_not_shield_the_id():
    assert relabel("Per ISO 26262. The extra R08 risk.") == "Per ISO 26262. The extra ADD-08 risk."


def test_links_urls_anchors_and_code_spans_are_left_alone():
    for text in ("http://x/R10/y", "`R10`", "see [guide](#R10)", "?id=R10", "[text](http://x/R10)"):
        assert relabel(text) == text, text
    assert relabel("[R10](http://x/R10)") == "[ADD-10](http://x/R10)"  # display text renamed, target kept
    assert relabel("`code` then R08") == "`code` then ADD-08"


def test_idempotent_and_noop_without_a_ledger():
    once = relabel("R08 and R09 are extra, R01 is real.")
    assert relabel(once) == once
    assert cons.relabel_unknown_risk_ids("R08 here", []) == "R08 here"
    assert cons.relabel_unknown_risk_ids("", LEDGER) == ""


def test_finalize_strategy_relabels_with_a_register_and_not_without():
    text = "Covers R01 and the extra R08."
    assert cons.finalize_strategy(text, None, REGISTER) == "Covers R01 and the extra ADD-08."
    assert cons.finalize_strategy(text, None, "") == text


def test_generate_relabels_unknown_ids_end_to_end():
    agent = MagicMock()
    agent.retrieve_knowledge.return_value = []
    agent.format_knowledge_context.return_value = ""
    agent.ask.return_value = "# Strategy\n\n- **R08 (Additional)** | Observability gap\n- R01 stays."
    ctx = ProjectContext(
        project_name="P", project_description="d", project_type="web", tech_stack="Python",
        team_qa_size="2", team_dev_size="6", timeline="9 months", methodology="Scrum",
        known_risks="none", existing_automation="none", compliance_requirements="none",
    )
    strategy, _ = StrategyGenerator(agent).generate(ctx, chunks=[], risk_register=REGISTER)
    assert "**ADD-08 (Additional)** | Observability gap" in strategy
    assert "R01 stays." in strategy and "R08" not in strategy
