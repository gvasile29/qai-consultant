"""The Effort narrative must not contradict the deterministic tables (BESS live run)."""

from unittest.mock import MagicMock

from qai_consultant.core.dialogue import ProjectContext
from qai_consultant.generation.effort_estimator import (
    EffortEstimator,
    sanitize_narrative_claims,
)
from qai_consultant.core.effort_core import compute_estimation

BESS = ProjectContext(
    project_name="BESS Trading",
    project_description="100 MW battery storage in France with automatic trading and Gurobi optimisation",
    project_type="backend API trading platform",
    tech_stack="Python, Gurobi",
    team_qa_size="2",
    team_dev_size="6",
    timeline="9 months",
    methodology="Scrum",
    known_risks="external market integrations, safety-critical dispatch",
    existing_automation="No automation",
    compliance_requirements="French and EU energy market regulations, GDPR",
)

BAD_NARRATIVE = """EXECUTIVE_SUMMARY: The +72% uplift is due to regulatory complexity (French/EU energy market rules, GDPR) and the system's dual backend/optimization engine scope. The team is small.
ASSUMPTIONS:
- Compliance adds ~50%+ effort for test design, traceability, and audit trails.
- Scrum sprints assume ~80% velocity.
- Testing starts in the first sprint.
RECOMMENDATIONS:
- Automate regression early.
"""


def _report(narrative=BAD_NARRATIVE):
    agent = MagicMock()
    agent.ask.return_value = narrative
    est = EffortEstimator(agent)
    report, data = est.estimate(BESS)
    return report, data, agent


def test_bad_claims_removed_and_tables_kept():
    report, data, _ = _report()
    assert "~50%" not in report
    assert "80% velocity" not in report
    assert "French/EU" not in report
    assert "regulatory complexity" not in report
    assert "Automate regression early" in report
    assert "Testing starts in the first sprint" in report
    # deterministic content intact
    assert "| GDPR" in report or "GDPR" in report
    for n in ("332.7", "283.5", "49.2"):
        assert n in report
    assert "+72" in report


def test_prompt_lists_multipliers_and_warnings_and_rules():
    _, data, agent = _report()
    prompt = agent.ask.call_args[0][0]
    for reason, pct in data.multipliers:
        assert f"{reason}: +{pct}%" in prompt
    assert "NO effect" in prompt
    assert "EU energy market regulations" in prompt
    assert "only" in prompt.lower() and "velocity" in prompt.lower()


def test_prompt_carries_project_context_block_so_guards_know_the_intake():
    from qai_consultant.compliance import output_guards as g

    _, _, agent = _report()
    prompt = agent.ask.call_args[0][0]
    ctx = g.project_context_of(prompt)
    assert "existing automation" in ctx and "multipliers applied" not in ctx
    claim = "No existing automation requires a greenfield setup."
    assert g.sanitize_llm_markdown(claim, source_text=prompt) == claim


def test_second_range_is_labelled_statistical_approximation():
    report, _, _ = _report()
    assert "95% confidence range" not in report
    assert "statistical approximation" in report.lower()
    assert "planning band" in report.lower()


def test_sanitizer_idempotent_and_keeps_valid_percentages():
    data = compute_estimation(BESS, "")
    text = "GDPR contributes +10% to the uplift. Velocity is 80% of nominal. Utilization is fine."
    once = sanitize_narrative_claims(text, data)
    assert "+10%" in once
    assert "80%" not in once
    assert sanitize_narrative_claims(once, data) == once


def test_unrecognised_item_negation_is_kept():
    data = compute_estimation(BESS, "")
    text = "French and EU energy market regulations had no effect on the numbers."
    assert sanitize_narrative_claims(text, data) == text


def test_all_dropped_falls_back_to_neutral():
    data = compute_estimation(BESS, "")
    out = sanitize_narrative_claims("Velocity is 80%.", data)
    assert out.strip() != ""
    assert "80%" not in out
