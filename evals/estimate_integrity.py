"""Estimate-integrity gate: deterministic checks over QAI Consultant's real shipped
functions (``InputValidator``, ``EffortEstimator``) — nothing re-implemented. Issues
surface as failing checks, not prose; a green table means inputs round-trip honestly.
Keyless and instant (no LLM, no keys), so it drops straight into CI.

    python -m evals.estimate_integrity          # exits non-zero if any check fails

Golden cases live in ``golden.jsonl``; the fabricated-version check reads
``captured_test_plan.md``.
"""

from __future__ import annotations

import json
import re
import sys
import types
from dataclasses import dataclass
from pathlib import Path

from . import thresholds as T

_DIR = Path(__file__).resolve().parent
_SRC_DIR = _DIR.parent / "src"


# ── Import the real shipped code (stub only the heavy LLM client) ────────────────

def _load_target():
    """Import the app's real modules. ``effort_estimator`` imports the heavyweight
    ``agent`` module (langchain/pinecone/openai) only to call ``agent.ask`` for the
    narrative; the deterministic pipeline never touches it, so we stub it."""
    if str(_SRC_DIR) not in sys.path:
        sys.path.insert(0, str(_SRC_DIR))

    # ALWAYS install the stub (don't gate on "agent" not in sys.modules): the keyless
    # gate must not reach the real Pinecone/LLM client even if a prior import cached it.
    stub = types.ModuleType("agent")

    class QAIAgent:  # minimal stand-in; deterministic steps never call it
        def ask(self, *_args, **_kwargs):
            return ""

    stub.QAIAgent = QAIAgent
    sys.modules["agent"] = stub

    from dialogue import InputValidator, ProjectContext  # noqa: PLC0415
    from effort_estimator import EffortEstimator  # noqa: PLC0415

    return InputValidator, ProjectContext, EffortEstimator


# ── Result types ──────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Finding:
    """One concrete defect: what was tried, what was expected, what came back."""

    case: str
    expected: str
    actual: str


@dataclass(frozen=True)
class CheckOutcome:
    name: str
    findings: tuple[Finding, ...]

    @property
    def passed(self) -> bool:
        return not self.findings


def _golden() -> list[dict]:
    """Parse golden.jsonl once; skip blank and malformed lines rather than letting one
    bad appended line crash every check."""
    cases = []
    for line in (_DIR / "golden.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and "kind" in obj:
            cases.append(obj)
    return cases


# ── Checks ───────────────────────────────────────────────────────────────────────

def check_duration_bounds(est) -> tuple[Finding, ...]:
    """Every parsed timeline must land in a plausible range. A 4-digit year must
    not be read as a duration."""
    out: list[Finding] = []
    for case in (c for c in _golden() if c.get("kind") == "duration" and {"id", "input"} <= c.keys()):
        days = est._parse_duration(case["input"])
        if not (T.DURATION_MIN_DAYS <= days <= T.DURATION_MAX_DAYS):
            out.append(Finding(
                case=f'{case["id"]}: "{case["input"]}"',
                expected=f"{T.DURATION_MIN_DAYS}–{T.DURATION_MAX_DAYS} working days",
                actual=f"{days} working days (~{days / 230:.0f} years)",
            ))
    return tuple(out)


def check_team_restatement_invariance(est) -> tuple[Finding, ...]:
    """Headcount must be invariant to restatement: 'A + B, or C' describes the same
    team two ways and must not sum to A+B+C."""
    out: list[Finding] = []
    for case in (c for c in _golden()
                 if c.get("kind") == "team_invariance" and {"id", "base", "restated"} <= c.keys()):
        base = est._parse_team_size(case["base"])
        restated = est._parse_team_size(case["restated"])
        if abs(restated - base) > T.TEAM_RESTATEMENT_DELTA_MAX:
            out.append(Finding(
                case=f'{case["id"]}: "{case["restated"]}"',
                expected=f"{base} people (same as the base phrasing)",
                actual=f"{restated} people",
            ))
    return tuple(out)


_OS_RESERVED = set('/\\:*?"<>|')


def check_name_display_fidelity(iv) -> tuple[Finding, ...]:
    """The stored/displayed project name must preserve spaces and visible
    characters; only OS-reserved filename chars may be dropped. Collapsing spaces
    to underscores or truncating is a display defect."""
    out: list[Finding] = []
    for case in (c for c in _golden() if c.get("kind") == "name" and {"id", "input"} <= c.keys()):
        raw = case["input"]
        cleaned = iv.validate("project_name", raw).cleaned
        expected = "".join(ch for ch in raw if ch not in _OS_RESERVED).strip()
        if T.NAME_MUST_PRESERVE_SPACES and (" " in expected) and (" " not in cleaned):
            out.append(Finding(
                case=f'{case["id"]}: "{raw}"',
                expected=f'spaces preserved, e.g. "{expected}"',
                actual=f'"{cleaned}"',
            ))
    return tuple(out)


def check_confidence_magnitude_sanity(ProjectContext, EffortEstimator) -> tuple[Finding, ...]:
    """A physically-impossible estimate must not read 'High' confidence. Runs the
    real shipped ``estimate()`` pipeline (LLM narrative stubbed) on a realistic
    context — no re-listing of the private steps, so it can't drift from the app."""
    ctx = ProjectContext(
        project_name="Acme Project Hub API",
        project_type="REST API microservices",
        tech_stack="FastAPI, Postgres",
        team_qa_size="2 QA engineers",
        team_dev_size="4 developers",
        timeline="Ongoing product on monthly sprints; next major release September 2026",
        methodology="Scrum with 2-week sprints",
        known_risks="access control, data integrity, file storage, third-party integrations",
        existing_automation="unit tests only",
        compliance_requirements="GDPR",
    )
    from agent import QAIAgent  # noqa: PLC0415 — the stub installed by _load_target()
    _, data = EffortEstimator(QAIAgent()).estimate(ctx)

    impossible = data.project_duration_days > T.CONFIDENCE_HIGH_FORBIDDEN_ABOVE_DAYS
    if impossible and data.confidence_level == "High":
        return (Finding(
            case=f'timeline "{ctx.timeline}"',
            expected='confidence must NOT be "High" for an impossible magnitude',
            actual=(f'"High" (score {data.confidence_score}/100) on '
                    f'{data.pert_total_expected:.0f} person-days / '
                    f'{data.project_duration_days} working-day duration'),
        ),)
    return ()


# A "version" is v-prefixed (v1.2, v15.4) or 3-part X.Y.Z — NOT a bare two-part decimal,
# so real figures (PERT "22.5", "99.9%", heading "4.2") aren't flagged as fabricated.
_VERSION = re.compile(r"\b(?:v\d+\.\d+(?:\.\d+)?|\d+\.\d+\.\d+)\b")
# The 11 user answers for the captured run — must describe the same project as
# captured_test_plan.md (the version-check pair), independent of the confidence check.
_RUN_INPUTS = (
    "Acme Project Hub "
    "A team task and project management tool for small teams. Users create projects, "
    "assign tasks, track progress, and share files. "
    "Web app + REST API "
    "React frontend, Python FastAPI backend, Postgres "
    "2 QA engineers; developers also test their own code "
    "4 developers "
    "Ongoing product on monthly sprints; next major release September 2026 "
    "Scrum with 2-week sprints "
    "Access control, data integrity, file storage, third-party integrations, notification delivery "
    "Unit tests only "
    "GDPR"
)


def check_no_fabricated_versions() -> tuple[Finding, ...]:
    """No version string may appear in a generated deliverable that the user never
    supplied. Runs on a captured artifact, no API key."""
    artifact = (_DIR / "captured_test_plan.md").read_text(encoding="utf-8")
    source_versions = set(_VERSION.findall(_RUN_INPUTS))
    out: list[Finding] = []
    for m in _VERSION.finditer(artifact):
        tok = m.group(0)
        if tok not in source_versions:
            out.append(Finding(
                case=f'version "{tok}" in Test Plan',
                expected="every version traceable to a user answer",
                actual="not present in any of the 11 inputs (fabricated)",
            ))
    if len(out) <= T.FABRICATED_FACTS_MAX:
        return ()
    return tuple(out)


# ── Runner ───────────────────────────────────────────────────────────────────────

def run_all() -> list[CheckOutcome]:
    # _load_target() overwrites sys.modules["agent"] with a stub; restore the prior
    # module afterwards so evals can share a process (e.g. a pytest session) without
    # leaving the real `agent` shadowed by the stub.
    prev_agent = sys.modules.get("agent")
    iv_cls, ctx_cls, est_cls = _load_target()
    iv = iv_cls()
    est = est_cls.__new__(est_cls)  # pure-method calls; no agent needed
    try:
        return [
            CheckOutcome("duration_bounds", check_duration_bounds(est)),
            CheckOutcome("team_restatement_invariance", check_team_restatement_invariance(est)),
            CheckOutcome("name_display_fidelity", check_name_display_fidelity(iv)),
            CheckOutcome("confidence_magnitude_sanity", check_confidence_magnitude_sanity(ctx_cls, est_cls)),
            CheckOutcome("no_fabricated_versions", check_no_fabricated_versions()),
        ]
    finally:
        if prev_agent is not None:
            sys.modules["agent"] = prev_agent
        else:
            sys.modules.pop("agent", None)


def format_table(outcomes: list[CheckOutcome]) -> str:
    lines = ["", f"{'Check':<32} Result   Defects", f"{'-' * 32} -------  -------"]
    for o in outcomes:
        lines.append(f"{o.name:<32} {'pass' if o.passed else 'FAIL':<8} {len(o.findings)}")
    lines.append("")
    for o in outcomes:
        for f in o.findings:
            lines.append(f"  [{o.name}] {f.case}")
            lines.append(f"      expected: {f.expected}")
            lines.append(f"      actual:   {f.actual}")
    return "\n".join(lines)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # findings contain non-ASCII; don't crash on cp1252/ascii
    outcomes = run_all()
    print(format_table(outcomes))
    ok = all(o.passed for o in outcomes)
    total_defects = sum(len(o.findings) for o in outcomes)
    print(f"\nRelease gate: {'PASS' if ok else 'FAIL'} ({total_defects} defect(s) across "
          f"{sum(1 for o in outcomes if not o.passed)} check(s))")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
