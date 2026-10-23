"""The estimate_qa_effort MCP tool returns clean validation errors for bad numerics."""
from qai_consultant.mcp import server

ARGS = dict(
    project_name="Proj", project_description="A web shop for tests", project_type="web",
    tech_stack="python", team_qa_size="2", team_dev_size="4", timeline="6 months",
    methodology="agile", known_risks="payment gateway outages", existing_automation="some unit tests",
    compliance_requirements="none applicable",
)


def _call(**over):
    return server.estimate_qa_effort(**{**ARGS, **over})


def test_negative_and_zero_inputs_are_validation_errors():
    for field, value in [("team_qa_size", "-3"), ("team_dev_size", "-5"),
                         ("timeline", "-2 months"), ("timeline", "0 months")]:
        r = _call(**{field: value})
        assert r["error"] == "validation" and field in r["fields"], (field, value, r)


def test_decimal_headcount_and_new_fields():
    r = _call(team_qa_size="2.5")
    assert r["qa_team_size"] == 3 and r["team_total_size"] == 7
    assert any("2.5" in w for w in r["warnings"])
    assert r["capacity_status"] in ("surplus", "deficit", "balanced")
    assert r["capacity_note"] and r["confidence_note"]
