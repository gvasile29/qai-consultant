"""
Tests for src/effort_core.py — the deterministic effort-estimation core.

effort_core.py was extracted out of EffortEstimator (v3.0 step 2) so the
MCP server's estimate_qa_effort tool can call compute_estimation() directly
without pulling in agent.py's Pinecone/Mistral/OpenAI/Streamlit-adjacent
dependencies. Covers:

1. Import-graph isolation: importing effort_core must never load agent,
   pinecone, mistralai, openai, or streamlit — the property this whole
   refactor exists for. (Before this refactor, evals/estimate_integrity.py
   had to install a fake sys.modules["agent"] stub just to import
   effort_estimator.py; effort_core.py needs no such trick.)
2. Golden-input parity: parse_duration()/parse_team_size() against the
   same cases evals/golden.jsonl uses for the release-gate checks.
3. EffortEstimator.estimate() delegates to compute_estimation() without
   diverging — the two must produce identical EstimationData for the same
   inputs.
"""

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

import effort_core
from dialogue import ProjectContext
from effort_core import EstimationData, compute_estimation


# ── 1. Import-graph isolation ───────────────────────────────────────────────────

def test_importing_effort_core_pulls_in_no_agent_or_llm_modules():
    """Run in a fresh subprocess (not this test process, which may already have
    agent.py imported by other test modules) so sys.modules starts clean."""
    script = (
        "import sys; sys.path.insert(0, r'" + str(SRC_DIR) + "'); "
        "import effort_core; "
        "forbidden = ['agent', 'pinecone', 'mistralai', 'openai', 'streamlit']; "
        "leaked = [m for m in forbidden if m in sys.modules]; "
        "print(','.join(leaked))"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, f"subprocess failed: {result.stderr}"
    leaked = result.stdout.strip()
    assert leaked == "", (
        f"Importing effort_core pulled in forbidden module(s): {leaked}. "
        "effort_core.py must stay importable without agent.py/Pinecone/LLM/"
        "Streamlit for the MCP server path to work without those dependencies."
    )


def test_effort_core_module_does_not_import_agent_by_name():
    """Static check on effort_core.py's own source (defense in depth alongside
    the subprocess check above, which also catches indirect/transitive leaks)."""
    source = (SRC_DIR / "effort_core.py").read_text(encoding="utf-8")
    for forbidden in ("import agent", "from agent"):
        assert forbidden not in source, (
            f"effort_core.py contains '{forbidden}' — it must have zero agent.py "
            "dependency so the MCP server path never pulls in Pinecone/LLM/Streamlit."
        )


# ── 2. Golden-input parity (evals/golden.jsonl) ─────────────────────────────────

def _golden_cases() -> list[dict]:
    golden_path = REPO_ROOT / "evals" / "golden.jsonl"
    cases = []
    for line in golden_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            cases.append(json.loads(line))
    return cases


def test_golden_duration_cases_stay_within_plausible_bounds():
    cases = [c for c in _golden_cases() if c["kind"] == "duration"]
    assert cases, "No duration cases found in evals/golden.jsonl"
    for case in cases:
        days = effort_core.parse_duration(case["input"])
        assert 1 <= days <= effort_core.MAX_PLAUSIBLE_DURATION_DAYS, (
            f"{case['id']}: parse_duration({case['input']!r}) = {days}, "
            f"outside [1, {effort_core.MAX_PLAUSIBLE_DURATION_DAYS}]"
        )


def test_golden_team_restatement_cases_are_invariant():
    """An 'A, or B' restatement of the same team must not double-count —
    the exact regression this golden case guards against."""
    cases = [c for c in _golden_cases() if c["kind"] == "team_invariance"]
    assert cases, "No team_invariance cases found in evals/golden.jsonl"
    for case in cases:
        base = effort_core.parse_team_size(case["base"])
        restated = effort_core.parse_team_size(case["restated"])
        assert base == restated, (
            f"{case['id']}: parse_team_size({case['base']!r})={base} != "
            f"parse_team_size({case['restated']!r})={restated}"
        )


# ── 3. EffortEstimator.estimate() delegates without diverging ──────────────────

_SAMPLE_CONTEXT = ProjectContext(
    project_name="Sample Fintech API",
    project_description="Payment processing API for a fintech startup",
    project_type="api",
    tech_stack="Python, FastAPI, PostgreSQL",
    team_qa_size="3",
    team_dev_size="8",
    timeline="6 months",
    methodology="agile",
    known_risks="third-party payment gateway integration",
    existing_automation="some unit tests",
    compliance_requirements="PCI-DSS",
)


def test_compute_estimation_has_no_agent_field_dependency():
    """compute_estimation() takes only (context, risk_register) — no agent
    object anywhere in its signature or call chain."""
    data = compute_estimation(_SAMPLE_CONTEXT)
    assert isinstance(data, EstimationData)
    assert data.project_type_detected == "api"
    assert data.confidence_level in ("Low", "Medium", "High")


def test_effort_estimator_estimate_matches_compute_estimation_directly():
    """EffortEstimator.estimate()'s returned EstimationData must be identical
    (field-for-field) to calling compute_estimation() directly — proves the
    'extract-and-delegate, not reimplementation' rule actually holds."""
    sys.path.insert(0, str(SRC_DIR))
    from effort_estimator import EffortEstimator

    class _DummyAgent:
        def ask(self, *_args, **_kwargs):
            return "EXECUTIVE_SUMMARY: test\nASSUMPTIONS: test\nRECOMMENDATIONS: test"

    direct = compute_estimation(_SAMPLE_CONTEXT, risk_register="")
    _, via_estimator = EffortEstimator(_DummyAgent()).estimate(_SAMPLE_CONTEXT, risk_register="")

    assert direct == via_estimator, (
        "EffortEstimator.estimate()'s EstimationData diverged from a direct "
        "compute_estimation() call with the same inputs."
    )


def test_effort_estimator_estimate_matches_compute_estimation_with_risk_register():
    sys.path.insert(0, str(SRC_DIR))
    from effort_estimator import EffortEstimator

    class _DummyAgent:
        def ask(self, *_args, **_kwargs):
            return "EXECUTIVE_SUMMARY: test\nASSUMPTIONS: test\nRECOMMENDATIONS: test"

    risk_register = "| R01 | Critical | Payment gateway outage |\n| R02 | High | Data breach |"
    direct = compute_estimation(_SAMPLE_CONTEXT, risk_register=risk_register)
    _, via_estimator = EffortEstimator(_DummyAgent()).estimate(_SAMPLE_CONTEXT, risk_register=risk_register)

    assert direct == via_estimator
