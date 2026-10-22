"""Cross-document consistency helpers (generation/consistency.py) and their
wiring into the Strategy / Test Plan prompts and generate_all()."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from qai_consultant.core.dialogue import ProjectContext
from qai_consultant.generation import consistency as cons
from qai_consultant.generation import strategy_generator as sg_module
from qai_consultant.generation.strategy_generator import StrategyGenerator, build_strategy_prompt

CTX = ProjectContext(
    project_name="BESS", project_description="100 MW battery, automatic trading",
    project_type="energy trading", tech_stack="Python, Gurobi", team_qa_size="2",
    team_dev_size="6", timeline="9 months", methodology="Scrum", known_risks="none",
    existing_automation="none", compliance_requirements="French/EU energy rules + GDPR",
)

EFFORT = SimpleNamespace(
    pert_total_expected=332.7, final_effort_min=290.0, final_effort_max=410.5,
    available_person_days=283.5, capacity_gap=-49.2, qa_team_size=2, project_duration_days=189,
)

RISK_REGISTER = """# Risk Register

## Risk Matrix Overview

| Risk ID | Description | Likelihood | Impact | Risk Level | Priority |
|---|---|---|---|---|---|
| R01 | Market Data & Gateway Integration Failures | High | High | Critical | P1 |
| R02 | Optimiser (Gurobi) wrong dispatch | Medium | High | High | P1 |
| R03 | GDPR non-compliance | Low | Medium | Low | P3 |
"""


# ── Finding 3a: effort numbers ────────────────────────────────────────────────

def test_effort_facts_extracts_all_fields():
    facts = cons.effort_facts(EFFORT)
    assert facts["pert_total_expected"] == 332.7
    assert facts["capacity_gap"] == -49.2
    assert facts["qa_team_size"] == 2


def test_effort_facts_none_for_empty_or_dict():
    assert cons.effort_facts(None) is None
    assert cons.effort_facts({}) is None
    assert cons.effort_facts({"total_days": 5}) is None


def test_strategy_prompt_contains_effort_numbers_verbatim():
    prompt = build_strategy_prompt(CTX, "kb", effort=cons.effort_facts(EFFORT))
    assert "332.7" in prompt and "283.5" in prompt and "49.2" in prompt
    assert "290" in prompt and "410.5" in prompt
    assert "do not invent" in prompt.lower()


def test_strategy_prompt_without_effort_has_no_effort_block():
    assert "AUTHORITATIVE QA EFFORT" not in build_strategy_prompt(CTX, "kb")


STRATEGY_BAD_TOTAL = """## 7. Entry & Exit Criteria
x

## 8. Resources & Man Power Estimation

| Activity | Person-days |
|---|---|
| Test design | 60 |
| **Total** | **200 person-days** |

Total QA effort: 200 person-days for 2 QA engineers.

## 9. Tools & Environment
Total of 12 tools
"""


def test_enforce_effort_totals_rewrites_conflicting_totals_only_in_section_8():
    out = cons.enforce_effort_totals(STRATEGY_BAD_TOTAL, cons.effort_facts(EFFORT))
    assert "200 person-days" not in out
    assert out.count("332.7 person-days") >= 2
    assert "| Test design | 60 |" in out
    assert "Total of 12 tools" in out  # other sections untouched


def test_enforce_effort_totals_idempotent_and_noop_without_facts():
    facts = cons.effort_facts(EFFORT)
    once = cons.enforce_effort_totals(STRATEGY_BAD_TOTAL, facts)
    assert cons.enforce_effort_totals(once, facts) == once
    assert cons.enforce_effort_totals(STRATEGY_BAD_TOTAL, None) == STRATEGY_BAD_TOTAL


def test_enforce_effort_totals_keeps_allowed_numbers():
    text = "## 8. Resources\nTotal capacity: 283.5 person-days\nTotal need: 332.7 person-days\n"
    assert cons.enforce_effort_totals(text, cons.effort_facts(EFFORT)) == text


def test_generate_applies_effort_and_prompt(monkeypatch):
    agent = MagicMock()
    agent.format_knowledge_context.return_value = "kb"
    agent.ask.return_value = STRATEGY_BAD_TOTAL
    strategy, _ = StrategyGenerator(agent).generate(CTX, chunks=[], effort_data=EFFORT)
    assert "332.7" in agent.ask.call_args[0][0]
    assert "200 person-days" not in strategy


def test_generate_all_wires_effort_data(monkeypatch, tmp_path):
    captured = {}

    def fake_generate(self, ctx, chunks=None, effort_data=None, risk_register=None):
        captured["effort"] = effort_data
        return "strategy", []

    monkeypatch.setattr(sg_module.RiskAnalyzer, "analyze", lambda self, c, chunks=None, results_summary=None: (RISK_REGISTER, []))
    monkeypatch.setattr(sg_module.RiskAnalyzer, "save", lambda self, t, c: tmp_path / "r.md")
    monkeypatch.setattr(sg_module.EffortEstimator, "estimate", lambda self, c, r: ("effort", EFFORT))
    monkeypatch.setattr(sg_module.EffortEstimator, "save", lambda self, t, c: tmp_path / "e.md")
    monkeypatch.setattr(sg_module.StrategyGenerator, "generate", fake_generate)
    monkeypatch.setattr(sg_module.StrategyGenerator, "save", lambda self, t, c: tmp_path / "s.md")
    monkeypatch.setattr(sg_module.TestPlanGenerator, "generate", lambda self, c, r, chunks=None, **kw: ("plan", []))
    monkeypatch.setattr(sg_module.TestPlanGenerator, "save", lambda self, t, c: tmp_path / "p.md")
    agent = MagicMock()
    agent.retrieve_knowledge.return_value = []
    StrategyGenerator(agent).generate_all(CTX)
    assert captured["effort"] is EFFORT


# ── Finding 3b: risk ledger in the Strategy ───────────────────────────────────

def test_ledger_prompt_block_lists_ids_and_levels_verbatim():
    ledger = cons.risk_ledger(RISK_REGISTER)
    block = cons.ledger_prompt_block(ledger)
    assert "R01 | Market Data & Gateway Integration Failures | High | High | Critical | P1" in block
    assert "R03" in block
    assert "verbatim" in block.lower() and "re-rate" in block.lower()


def test_ledger_empty_degrades_gracefully():
    assert cons.risk_ledger("") == []
    assert cons.risk_ledger("no table here") == []
    assert cons.ledger_prompt_block([]) == ""


def test_strategy_prompt_includes_ledger_and_omits_when_empty():
    ledger = cons.risk_ledger(RISK_REGISTER)
    assert "RISK LEDGER" in build_strategy_prompt(CTX, "kb", ledger=ledger)
    assert "RISK LEDGER" not in build_strategy_prompt(CTX, "kb", ledger=[])


def test_generate_parses_risk_register_into_prompt():
    agent = MagicMock()
    agent.format_knowledge_context.return_value = "kb"
    agent.ask.return_value = "# Strategy"
    StrategyGenerator(agent).generate(CTX, chunks=[], risk_register=RISK_REGISTER)
    prompt = agent.ask.call_args[0][0]
    assert "R01 | Market Data & Gateway Integration Failures | High | High | Critical" in prompt


def test_generate_all_wires_risk_register(monkeypatch, tmp_path):
    captured = {}

    def fake_generate(self, ctx, chunks=None, effort_data=None, risk_register=None):
        captured["risk"] = risk_register
        return "strategy", []

    monkeypatch.setattr(sg_module.RiskAnalyzer, "analyze", lambda self, c, chunks=None, results_summary=None: (RISK_REGISTER, []))
    monkeypatch.setattr(sg_module.RiskAnalyzer, "save", lambda self, t, c: tmp_path / "r.md")
    monkeypatch.setattr(sg_module.EffortEstimator, "estimate", lambda self, c, r: ("effort", {}))
    monkeypatch.setattr(sg_module.EffortEstimator, "save", lambda self, t, c: tmp_path / "e.md")
    monkeypatch.setattr(sg_module.StrategyGenerator, "generate", fake_generate)
    monkeypatch.setattr(sg_module.StrategyGenerator, "save", lambda self, t, c: tmp_path / "s.md")
    monkeypatch.setattr(sg_module.TestPlanGenerator, "generate", lambda self, c, r, chunks=None, **kw: ("plan", []))
    monkeypatch.setattr(sg_module.TestPlanGenerator, "save", lambda self, t, c: tmp_path / "p.md")
    agent = MagicMock()
    agent.retrieve_knowledge.return_value = []
    StrategyGenerator(agent).generate_all(CTX)
    assert captured["risk"] == RISK_REGISTER


# ── Finding 3c: scope consistency ─────────────────────────────────────────────

STRATEGY_WITH_SCOPE = """# Test Strategy: BESS

## 2. Scope: What Will Be Tested
- Trading engine
- Gateway adapters

## 3. Scope: What Will NOT Be Tested
- UI testing (backend-only)
- Exploratory testing not feasible

## 4. Risk Assessment
irrelevant
"""


def test_scope_rules_text_forbids_contradiction_and_unstated_ui():
    rules = cons.SCOPE_RULES.lower()
    assert "out of scope" in rules and "must not" in rules
    assert "ui not specified in the intake" in rules


def test_strategy_prompt_has_scope_rules():
    assert cons.SCOPE_RULES.strip().splitlines()[0] in build_strategy_prompt(CTX, "kb")


def test_extract_scope_decisions_returns_only_scope_sections():
    out = cons.extract_scope_decisions(STRATEGY_WITH_SCOPE)
    assert "UI testing (backend-only)" in out and "Trading engine" in out
    assert "irrelevant" not in out
    assert cons.extract_scope_decisions("") == ""
    assert cons.extract_scope_decisions("# no scope sections") == ""
    assert len(cons.extract_scope_decisions("## 2. Scope: x\n" + "a" * 5000)) <= 1600


def _plan_prompt(**kw):
    from qai_consultant.generation.test_plan_generator import build_test_plan_prompt
    return build_test_plan_prompt(CTX, RISK_REGISTER, "kb", **kw)


def test_test_plan_prompt_has_scope_rules_and_strategy_scope():
    p = _plan_prompt(strategy_scope="- UI testing (backend-only)")
    assert cons.SCOPE_RULES.strip().splitlines()[0] in p
    assert "STRATEGY SCOPE DECISIONS" in p and "UI testing (backend-only)" in p
    assert "STRATEGY SCOPE DECISIONS" not in _plan_prompt()


def test_test_plan_generate_accepts_strategy_scope():
    from qai_consultant.generation.test_plan_generator import TestPlanGenerator
    agent = MagicMock()
    agent.format_knowledge_context.return_value = "kb"
    agent.ask.return_value = "# Plan"
    TestPlanGenerator(agent).generate(CTX, RISK_REGISTER, chunks=[], strategy_scope="- no UI")
    assert "- no UI" in agent.ask.call_args[0][0]


def test_generate_all_passes_strategy_scope_to_test_plan(monkeypatch, tmp_path):
    captured = {}

    def fake_plan(self, ctx, risk, chunks=None, strategy_scope=None):
        captured["scope"] = strategy_scope
        return "plan", []

    monkeypatch.setattr(sg_module.RiskAnalyzer, "analyze", lambda self, c, chunks=None, results_summary=None: ("rr", []))
    monkeypatch.setattr(sg_module.RiskAnalyzer, "save", lambda self, t, c: tmp_path / "r.md")
    monkeypatch.setattr(sg_module.EffortEstimator, "estimate", lambda self, c, r: ("effort", {}))
    monkeypatch.setattr(sg_module.EffortEstimator, "save", lambda self, t, c: tmp_path / "e.md")
    monkeypatch.setattr(sg_module.StrategyGenerator, "generate", lambda self, c, chunks=None, **kw: (STRATEGY_WITH_SCOPE, []))
    monkeypatch.setattr(sg_module.StrategyGenerator, "save", lambda self, t, c: tmp_path / "s.md")
    monkeypatch.setattr(sg_module.TestPlanGenerator, "generate", fake_plan)
    monkeypatch.setattr(sg_module.TestPlanGenerator, "save", lambda self, t, c: tmp_path / "p.md")
    agent = MagicMock()
    agent.retrieve_knowledge.return_value = []
    StrategyGenerator(agent).generate_all(CTX)
    assert "UI testing (backend-only)" in captured["scope"]


# ── Finding 7a: Test Plan risk-ID mapping ─────────────────────────────────────

def test_plan_prompt_has_ledger_table_and_critical_exit_rule():
    p = _plan_prompt()
    assert "RISK LEDGER" in p
    assert "R02 | Optimiser (Gurobi) wrong dispatch | Medium | High | High | P1" in p
    low = p.lower()
    assert "every risk with level critical" in low and "exit criteria" in low
    assert "match" in low and "exactly" in low


def test_plan_prompt_without_ledger_has_no_ledger_block():
    from qai_consultant.generation.test_plan_generator import build_test_plan_prompt
    assert "RISK LEDGER" not in build_test_plan_prompt(CTX, "no table", "kb")


def test_remove_unknown_risk_ids_flags_only_unknown():
    ledger = cons.risk_ledger(RISK_REGISTER)
    text = "| Perf (R01) | R09 |\nGDPR R03, R07 and R02\nUnmapped (R10) here"
    out = cons.remove_unknown_risk_ids(text, ledger)
    assert "R01" in out and "R02" in out and "R03" in out
    assert "R07" not in out and "R09" not in out and "R10" not in out
    assert "()" not in out and ", and" not in out
    assert cons.remove_unknown_risk_ids(out, ledger) == out  # idempotent


def test_remove_unknown_risk_ids_noop_without_ledger():
    assert cons.remove_unknown_risk_ids("R09 stays", []) == "R09 stays"


def test_test_plan_generate_removes_unknown_ids():
    from qai_consultant.generation.test_plan_generator import TestPlanGenerator
    agent = MagicMock()
    agent.format_knowledge_context.return_value = "kb"
    agent.ask.return_value = "Feature X covers R01 and R99"
    plan, _ = TestPlanGenerator(agent).generate(CTX, RISK_REGISTER, chunks=[])
    assert "R01" in plan and "R99" not in plan


# ── Finding 7b: padding references ────────────────────────────────────────────

REFS = """## 10. Key Risks
Use boundary analysis [Source 1] and OWASP checks [Source 3].

## 11. References
- ISTQB Foundation Syllabus [Source 1]
- OWASP Testing Guide (Implicit)
- IEEE 829 Standard (Implicit)
- OWASP ASVS [Source 3]
- ISO 25010 [Source 7]
"""


def test_drop_padding_references_exact_lines():
    out = cons.drop_padding_references(REFS)
    assert "(Implicit)" not in out
    assert "OWASP Testing Guide" not in out and "IEEE 829 Standard" not in out
    assert "ISTQB Foundation Syllabus [Source 1]" in out
    assert "OWASP ASVS [Source 3]" in out
    assert "ISO 25010 [Source 7]" not in out  # [Source 7] never cited in the body
    assert "Use boundary analysis [Source 1]" in out


def test_drop_padding_references_idempotent_and_conservative():
    once = cons.drop_padding_references(REFS)
    assert cons.drop_padding_references(once) == once
    no_cites = "## 1. Intro\ntext\n\n## 2. References\n- ISO 25010 [Source 7]\n- Foo (Implicit)\n"
    out = cons.drop_padding_references(no_cites)
    assert "ISO 25010 [Source 7]" in out and "Foo" not in out  # no body citations -> keep sourced lines
    assert cons.drop_padding_references("") == ""
    assert cons.drop_padding_references("no references here") == "no references here"


def test_strategy_prompt_restricts_references_to_cited_sources():
    p = build_strategy_prompt(CTX, "kb").lower()
    assert "references" in p and "actually cited" in p


def test_strategy_generate_drops_implicit_references():
    agent = MagicMock()
    agent.format_knowledge_context.return_value = "kb"
    agent.ask.return_value = REFS
    strategy, _ = StrategyGenerator(agent).generate(CTX, chunks=[])
    assert "(Implicit)" not in strategy


# ── Shared by app.py / cli.py: the Streamlit and CLI paths build their own prompts ──

def test_strategy_prompt_kwargs_degrade_when_inputs_unusable():
    from qai_consultant.generation.consistency import strategy_prompt_kwargs

    assert strategy_prompt_kwargs(None, "") == {}
    assert strategy_prompt_kwargs({}, "no table here") == {}


def test_finalize_helpers_are_idempotent_on_plain_text():
    from qai_consultant.generation.consistency import finalize_strategy, finalize_test_plan

    assert finalize_strategy("# S\n\ntext", None) == "# S\n\ntext"
    assert finalize_test_plan("# P\n\ntext", "") == "# P\n\ntext"


def test_streamlit_and_cli_paths_use_the_consistency_helpers():
    """generate_all() was fixed first and the UI/CLI paths, which build their own
    prompts, were missed (live BESS re-run). Keep all three wired."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[3] / "src"
    for rel in ("app.py", "qai_consultant/cli.py"):
        src = (root / rel).read_text(encoding="utf-8")
        for needle in ("strategy_prompt_kwargs(", "finalize_strategy(", "extract_scope_decisions(", "finalize_test_plan("):
            assert needle in src, f"{rel} no longer calls {needle}"
