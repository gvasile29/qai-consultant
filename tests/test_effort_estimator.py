"""
Tests for src/effort_estimator.py — v0.4 Effort Estimation module.

Covers:
1.  Duration parsing: "2 years" -> 460 working days, "18 months" -> 378 days
2.  Team size parsing: "2" -> 2, "6" -> 6
3.  Project type detection: embedded + V-model methodology
4.  Baseline QA %: embedded + V-model -> (30, 40)%
5.  Multiplier: ISO 26262 ASIL B -> +20%
6.  Multiplier: A-SPICE level 2 -> +20%
7.  Multiplier: No existing automation -> +20%
8.  Multiplier: Small QA team (<=2) -> +10%
9.  Multiplier: External/third-party integrations risk -> +12%
10. Total multiplier sum for BMW ECU profile -> +82%
11. PERT formula: E = (O + 4*M + P) / 6
12. PERT produces 9 activities when automation multiplier applies
13. Confidence level = "Low" for >= 5 multipliers
14. Streamlit app.py has 3 tabs (Risk Register, Effort Estimation, Test Strategy)
15. Effort Estimation tab has correct download button label
16. init_session_state() initializes effort_report and effort_path keys
17. "Generate Another Strategy" clears effort_report and effort_path
18. Sidebar "Start Over" clears effort_report and effort_path
19. CLI shows 3 panels (Risk Register, Effort Estimation, Test Strategy)
20. LLM smoke: full report with BMW ECU context, all 8 sections present, file saved
"""

import sys
import os
os.environ["ANONYMIZED_TELEMETRY"] = "False"
os.environ["CHROMA_TELEMETRY"] = "False"

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
APP_PY = SRC_DIR / "app.py"
CLI_PY = SRC_DIR / "cli.py"
sys.path.insert(0, str(SRC_DIR))

from dialogue import ProjectContext
from effort_estimator import EffortEstimator, EstimationData, BASELINE_QA_PERCENT


# ── BMW ECU sample context (triggers all 5 key multipliers) ─────────────────

BMW_EFFORT_CONTEXT = ProjectContext(
    project_name="BMW Embedded ECU",
    project_description=(
        "Safety-critical embedded control unit for BMW electric vehicles, "
        "controlling powertrain, battery management, and CAN bus communications"
    ),
    project_type="automotive embedded system",
    tech_stack="C++ with AUTOSAR Classic, QNX RTOS",
    team_qa_size="2",               # <= 2 -> small team +10%
    team_dev_size="6",
    timeline="2 years",             # 2 * 230 = 460 working days
    methodology="V-model",          # -> v-model baseline (30-40%)
    known_risks=(
        "third-party CAN bus integration risks, "
        "hardware timing failures under load"
    ),                              # third-party -> +12%
    existing_automation="No existing automation",  # -> +20%
    compliance_requirements="ISO 26262 ASIL B, A-SPICE level 2",
    # ASIL B -> +20%, A-SPICE L2 -> +20%
)

# Expected multipliers for BMW_EFFORT_CONTEXT
EXPECTED_MULTIPLIERS = [
    ("ISO 26262 ASIL B requirement", 20),
    ("A-SPICE compliance (Level 2)", 20),
    ("No existing automation — greenfield setup needed", 20),
    ("Small QA team (<=2 people) — context switching overhead", 10),
    ("External integrations identified as risk", 12),
]
EXPECTED_TOTAL_MULTIPLIER = 82  # 20 + 20 + 20 + 10 + 12

# Required sections in the Effort Estimation Report
REQUIRED_REPORT_SECTIONS = [
    "## 1. Executive Summary",
    "## 2. Baseline Calculation",
    "## 3. Complexity Adjustments",
    "## 4. Activity Breakdown (PERT)",
    "## 5. Team Capacity Analysis",
    "## 6. Risk Buffer",
    "## 7. Assumptions & Constraints",
    "## 8. Recommendations",
]


# ── Helpers ──────────────────────────────────────────────────────────────────

def read_app_source() -> str:
    return APP_PY.read_text(encoding="utf-8")


def read_cli_source() -> str:
    return CLI_PY.read_text(encoding="utf-8")


def extract_function(source: str, fn_name: str) -> str:
    """Return the source lines of a top-level function."""
    pattern = rf'\ndef {fn_name}\('
    start = re.search(pattern, source)
    if not start:
        raise ValueError(f"Function '{fn_name}' not found")
    rest = source[start.start():]
    next_def = re.search(r'\ndef \w', rest[4:])
    if next_def:
        return rest[:next_def.start() + 4]
    return rest


def make_dummy_estimator():
    """Create an EffortEstimator with a no-op agent for deterministic-only tests."""

    class _DummyAgent:
        def ask(self, prompt, system_prompt=""):
            return (
                "EXECUTIVE_SUMMARY: Test estimate generated.\n"
                "ASSUMPTIONS: - Standard working days.\n"
                "RECOMMENDATIONS: - Prioritize risk-based testing.\n"
            )

    return EffortEstimator(_DummyAgent())


# ── Non-LLM Structural Tests ─────────────────────────────────────────────────

def test_parse_duration_2years():
    """'2 years' parses to 460 working days (2 * 230)."""
    est = make_dummy_estimator()
    days = est._parse_duration("2 years")
    assert days == 460, f"Expected 460, got {days}"
    print("  PASS: '2 years' -> 460 working days")


def test_parse_duration_18months():
    """'18 months' parses to 378 working days (18 * 21).
    NOTE: strings containing 'year' (e.g. 'model year') trigger the year
    branch; use a clean month-only string to test the month path.
    """
    est = make_dummy_estimator()
    days = est._parse_duration("18 months")
    assert days == 378, f"Expected 378, got {days}"
    print("  PASS: '18 months' -> 378 working days")


def test_parse_duration_6weeks():
    """'6 weeks' parses to 30 working days (6 * 5)."""
    est = make_dummy_estimator()
    days = est._parse_duration("6 weeks")
    assert days == 30, f"Expected 30, got {days}"
    print("  PASS: '6 weeks' -> 30 working days")


def test_parse_team_size_2():
    """'2' parses to 2."""
    est = make_dummy_estimator()
    size = est._parse_team_size("2")
    assert size == 2, f"Expected 2, got {size}"
    print("  PASS: '2' -> team size 2")


def test_parse_team_size_range():
    """'5 developers' parses to 5."""
    est = make_dummy_estimator()
    size = est._parse_team_size("5 developers")
    assert size == 5, f"Expected 5, got {size}"
    print("  PASS: '5 developers' -> team size 5")


def test_detect_project_type_embedded():
    """'automotive embedded system' detects as 'embedded'."""
    est = make_dummy_estimator()
    data = EstimationData()
    est._detect_project_type(BMW_EFFORT_CONTEXT, data)
    assert data.project_type_detected == "embedded", \
        f"Expected 'embedded', got '{data.project_type_detected}'"
    print(f"  PASS: 'automotive embedded system' -> project_type_detected = 'embedded'")


def test_detect_methodology_vmodel():
    """'V-model' detects as 'v-model'."""
    est = make_dummy_estimator()
    data = EstimationData()
    est._detect_project_type(BMW_EFFORT_CONTEXT, data)
    assert data.methodology_detected == "v-model", \
        f"Expected 'v-model', got '{data.methodology_detected}'"
    print(f"  PASS: 'V-model' -> methodology_detected = 'v-model'")


def test_baseline_embedded_vmodel():
    """embedded + v-model baseline QA % is (30, 40)."""
    assert ("embedded", "v-model") in BASELINE_QA_PERCENT, \
        "('embedded', 'v-model') key missing from BASELINE_QA_PERCENT"
    lo, hi = BASELINE_QA_PERCENT[("embedded", "v-model")]
    assert (lo, hi) == (30, 40), f"Expected (30, 40), got ({lo}, {hi})"
    print(f"  PASS: embedded + v-model baseline QA % = {lo}% - {hi}%")


def test_multiplier_iso26262_asil_b():
    """ISO 26262 ASIL B compliance adds +20% multiplier."""
    est = make_dummy_estimator()
    data = EstimationData()
    est._detect_project_type(BMW_EFFORT_CONTEXT, data)
    est._calculate_baseline(BMW_EFFORT_CONTEXT, data)
    est._apply_multipliers(BMW_EFFORT_CONTEXT, data)

    asil_b = [r for r, p in data.multipliers if "asil b" in r.lower()]
    assert asil_b, "ISO 26262 ASIL B multiplier not applied"
    reason, pct = next((r, p) for r, p in data.multipliers if "asil b" in r.lower())
    assert pct == 20, f"ISO 26262 ASIL B should be +20%, got +{pct}%"
    print(f"  PASS: ISO 26262 ASIL B -> +20% (reason: '{reason}')")


def test_multiplier_aspice_level2():
    """A-SPICE level 2 compliance adds +20% multiplier."""
    est = make_dummy_estimator()
    data = EstimationData()
    est._detect_project_type(BMW_EFFORT_CONTEXT, data)
    est._calculate_baseline(BMW_EFFORT_CONTEXT, data)
    est._apply_multipliers(BMW_EFFORT_CONTEXT, data)

    aspice = [(r, p) for r, p in data.multipliers if "a-spice" in r.lower()]
    assert aspice, "A-SPICE multiplier not applied"
    reason, pct = aspice[0]
    assert pct == 20, f"A-SPICE Level 2 should be +20%, got +{pct}%"
    assert "2" in reason, f"Expected Level 2 in reason, got: '{reason}'"
    print(f"  PASS: A-SPICE Level 2 -> +20% (reason: '{reason}')")


def test_multiplier_no_automation():
    """'No existing automation' adds +20% multiplier."""
    est = make_dummy_estimator()
    data = EstimationData()
    est._detect_project_type(BMW_EFFORT_CONTEXT, data)
    est._calculate_baseline(BMW_EFFORT_CONTEXT, data)
    est._apply_multipliers(BMW_EFFORT_CONTEXT, data)

    no_auto = [(r, p) for r, p in data.multipliers if "automation" in r.lower() and "greenfield" in r.lower()]
    assert no_auto, "No-automation multiplier not applied"
    reason, pct = no_auto[0]
    assert pct == 20, f"No automation should be +20%, got +{pct}%"
    print(f"  PASS: No existing automation -> +20% (reason: '{reason}')")


def test_multiplier_small_qa_team():
    """QA team size <=2 adds +10% multiplier."""
    est = make_dummy_estimator()
    data = EstimationData()
    est._detect_project_type(BMW_EFFORT_CONTEXT, data)
    est._calculate_baseline(BMW_EFFORT_CONTEXT, data)
    est._apply_multipliers(BMW_EFFORT_CONTEXT, data)

    small_team = [(r, p) for r, p in data.multipliers if "small qa team" in r.lower()]
    assert small_team, "Small QA team multiplier not applied"
    reason, pct = small_team[0]
    assert pct == 10, f"Small QA team should be +10%, got +{pct}%"
    print(f"  PASS: Small QA team (<=2) -> +10% (reason: '{reason}')")


def test_multiplier_external_integrations():
    """'third-party' risk adds +12% external integrations multiplier."""
    est = make_dummy_estimator()
    data = EstimationData()
    est._detect_project_type(BMW_EFFORT_CONTEXT, data)
    est._calculate_baseline(BMW_EFFORT_CONTEXT, data)
    est._apply_multipliers(BMW_EFFORT_CONTEXT, data)

    integrations = [(r, p) for r, p in data.multipliers if "integration" in r.lower()]
    assert integrations, "External integrations multiplier not applied"
    reason, pct = integrations[0]
    assert pct == 12, f"External integrations should be +12%, got +{pct}%"
    print(f"  PASS: Third-party integrations risk -> +12% (reason: '{reason}')")


def test_total_multiplier_82pct():
    """BMW ECU context total multiplier = 82% (20+20+20+10+12)."""
    est = make_dummy_estimator()
    data = EstimationData()
    est._detect_project_type(BMW_EFFORT_CONTEXT, data)
    est._calculate_baseline(BMW_EFFORT_CONTEXT, data)
    est._apply_multipliers(BMW_EFFORT_CONTEXT, data)

    assert data.total_multiplier == EXPECTED_TOTAL_MULTIPLIER, \
        f"Expected total multiplier {EXPECTED_TOTAL_MULTIPLIER}%, got {data.total_multiplier}%"
    assert len(data.multipliers) == 5, \
        f"Expected 5 multipliers, got {len(data.multipliers)}: {data.multipliers}"
    print(f"  PASS: Total multiplier = +{data.total_multiplier}% ({len(data.multipliers)} factors)")
    for reason, pct in data.multipliers:
        print(f"        + {pct}%: {reason}")


def test_pert_formula():
    """PERT formula: E = (O + 4*M + P) / 6 verified for each activity."""
    est = make_dummy_estimator()
    data = EstimationData()
    est._detect_project_type(BMW_EFFORT_CONTEXT, data)
    est._calculate_baseline(BMW_EFFORT_CONTEXT, data)
    est._apply_multipliers(BMW_EFFORT_CONTEXT, data)
    est._pert_breakdown(data)

    failures = []
    for act in data.pert_activities:
        o, m, p = act["optimistic"], act["most_likely"], act["pessimistic"]
        expected = round((o + 4 * m + p) / 6, 1)
        if abs(expected - act["expected"]) > 0.2:  # allow small rounding diff
            failures.append(f"{act['activity']}: E={act['expected']} but (O+4M+P)/6={expected}")

    assert not failures, "PERT formula mismatch:\n" + "\n".join(failures)
    print(f"  PASS: PERT formula E=(O+4M+P)/6 verified for all {len(data.pert_activities)} activities")


def test_pert_nine_activities():
    """When total_multiplier > 0, PERT produces 9 activities (Automation Framework Setup included)."""
    est = make_dummy_estimator()
    data = EstimationData()
    est._detect_project_type(BMW_EFFORT_CONTEXT, data)
    est._calculate_baseline(BMW_EFFORT_CONTEXT, data)
    est._apply_multipliers(BMW_EFFORT_CONTEXT, data)
    est._pert_breakdown(data)

    assert data.total_multiplier > 0, "Precondition: total_multiplier must be > 0"
    assert len(data.pert_activities) == 9, \
        f"Expected 9 PERT activities, got {len(data.pert_activities)}"
    names = [a["activity"] for a in data.pert_activities]
    assert "Automation Framework Setup" in names, \
        "Automation Framework Setup missing from PERT when total_multiplier > 0"
    print(f"  PASS: 9 PERT activities (Automation Framework Setup included)")
    for a in data.pert_activities:
        print(f"        {a['activity']}: {a['optimistic']}d / {a['most_likely']}d / {a['pessimistic']}d -> E={a['expected']}d")


def test_confidence_level_medium():
    """BMW ECU with v0.6 score-based algorithm -> confidence = 'Medium'.

    v0.6 replaces count-based logic with a four-factor score (0-100):
      Factor 1 (PERT spread ≈ 1.125): ~37 pts
      Factor 2 (capacity gap_ratio ≈ -0.74 — severe deficit): 0 pts
      Factor 3 (data quality — all fields specific): 20 pts
      Factor 4 (82% multiplier): 2 pts
      Total ≈ 59 → "Medium"
    """
    est = make_dummy_estimator()
    data = EstimationData()
    est._detect_project_type(BMW_EFFORT_CONTEXT, data)
    est._calculate_baseline(BMW_EFFORT_CONTEXT, data)
    est._apply_multipliers(BMW_EFFORT_CONTEXT, data)
    est._pert_breakdown(data)
    est._team_capacity(BMW_EFFORT_CONTEXT, data)
    est._risk_buffer("", data)
    est._calculate_data_quality(BMW_EFFORT_CONTEXT, data)
    est._finalize(data)

    assert len(data.multipliers) >= 5, \
        f"Precondition: need >= 5 multipliers, got {len(data.multipliers)}"
    assert data.confidence_level == "Medium", \
        f"Expected 'Medium' confidence (v0.6 score-based), got '{data.confidence_level}' (score={data.confidence_score})"
    assert 40 <= data.confidence_score < 70, \
        f"Expected score in [40, 69], got {data.confidence_score}"
    print(f"  PASS: {len(data.multipliers)} multipliers -> confidence = '{data.confidence_level}' (score={data.confidence_score}/100)")


# ── Streamlit app.py structural tests ────────────────────────────────────────

def test_three_tabs_in_app():
    """render_strategy() defines 3 tabs with Risk Register, Effort Estimation, Test Strategy."""
    source = read_app_source()
    fn = extract_function(source, "render_strategy")

    assert 'st.tabs(' in fn, "st.tabs() not found in render_strategy"
    assert '"⚠️ Risk Register"' in fn or "'⚠️ Risk Register'" in fn, \
        "Tab '⚠️ Risk Register' not found"
    assert '"📊 Effort Estimation"' in fn or "'📊 Effort Estimation'" in fn, \
        "Tab '📊 Effort Estimation' not found"
    assert '"📋 Test Strategy"' in fn or "'📋 Test Strategy'" in fn, \
        "Tab '📋 Test Strategy' not found"
    print("  PASS: 3 tabs defined: 'Risk Register', 'Effort Estimation', 'Test Strategy'")


def test_effort_tab_download_button():
    """Tab 2 (Effort Estimation) has a download button with the correct label."""
    source = read_app_source()
    fn = extract_function(source, "render_strategy")

    assert '"⬇️ Download Effort Estimation (.md)"' in fn, \
        "Effort Estimation download button label not found"
    assert 'effort_estimation_' in fn, \
        "effort_estimation_ filename prefix not found"
    print("  PASS: Effort Estimation tab has download button '⬇️ Download Effort Estimation (.md)'")


def test_effort_keys_in_init_session_state():
    """init_session_state() initializes effort_report and effort_path."""
    source = read_app_source()
    fn = extract_function(source, "init_session_state")

    assert '"effort_report"' in fn, "effort_report not initialized in init_session_state"
    assert '"effort_path"' in fn, "effort_path not initialized in init_session_state"

    assert 'effort_report"] = None' in fn or 'effort_report = None' in fn, \
        "effort_report should default to None"
    assert 'effort_path"] = None' in fn or 'effort_path = None' in fn, \
        "effort_path should default to None"
    print("  PASS: init_session_state() initializes effort_report=None, effort_path=None")


def test_generate_another_clears_effort_keys():
    """'Generate Another Strategy' cleanup list includes effort_report and effort_path."""
    source = read_app_source()
    fn = extract_function(source, "render_strategy")

    for key in ["effort_report", "effort_path"]:
        assert f'"{key}"' in fn, \
            f"Key '{key}' missing from 'Generate Another Strategy' cleanup list"
    print("  PASS: 'Generate Another Strategy' clears effort_report and effort_path")


def test_start_over_clears_effort_keys():
    """Sidebar 'Start Over' cleanup list includes effort_report and effort_path."""
    source = read_app_source()
    fn = extract_function(source, "render_sidebar")

    for key in ["effort_report", "effort_path"]:
        assert f'"{key}"' in fn, \
            f"Sidebar 'Start Over' is missing key: '{key}'"
    print("  PASS: Sidebar 'Start Over' clears effort_report and effort_path")


def test_effort_estimator_imported_in_app():
    """EffortEstimator is imported at module level in app.py."""
    source = read_app_source()
    top_imports = source.split("def ")[0]
    assert "from effort_estimator import EffortEstimator" in top_imports, \
        "EffortEstimator should be imported at module level"
    print("  PASS: EffortEstimator imported at module level in app.py")


# ── CLI structural tests ──────────────────────────────────────────────────────

def test_cli_shows_three_panels():
    """cli.py _run_main_loop() displays 3 panels: Risk Register, Effort Estimation, Test Strategy.

    In v0.5, display logic moved from main() to _run_main_loop() so the watcher
    can be passed in as a parameter. Check _run_main_loop() for the 3 panels.
    """
    source = read_cli_source()
    fn = extract_function(source, "_run_main_loop")

    assert "Risk Register" in fn, "Risk Register panel not found in cli.py _run_main_loop()"
    assert "Effort Estimation" in fn, "Effort Estimation panel not found in cli.py _run_main_loop()"
    assert "Generated Test Strategy" in fn or "Test Strategy" in fn, \
        "Test Strategy panel not found in cli.py _run_main_loop()"
    print("  PASS: CLI _run_main_loop() shows 3 panels: Risk Register, Effort Estimation, Test Strategy")


def test_cli_generate_strategy_returns_effort_keys():
    """generate_strategy() in cli.py returns effort_report and effort_path keys."""
    source = read_cli_source()
    fn = extract_function(source, "generate_strategy")

    assert '"effort_report"' in fn or "'effort_report'" in fn, \
        "generate_strategy() does not include 'effort_report' in its return dict"
    assert '"effort_path"' in fn or "'effort_path'" in fn, \
        "generate_strategy() does not include 'effort_path' in its return dict"
    print("  PASS: generate_strategy() returns effort_report and effort_path")


# ── LLM smoke test ───────────────────────────────────────────────────────────

def test_full_estimate_bmw(agent):
    """
    Smoke test: EffortEstimator generates a valid report with all 8 sections
    for the BMW ECU context, saves file with frontmatter.
    """
    estimator = EffortEstimator(agent)

    print("  Calling EffortEstimator.estimate() with BMW ECU context...")
    report, data = estimator.estimate(BMW_EFFORT_CONTEXT)

    # All 8 sections present
    for section in REQUIRED_REPORT_SECTIONS:
        assert section in report, f"Missing section in report: '{section}'"
    print(f"  PASS: All {len(REQUIRED_REPORT_SECTIONS)} required sections present")

    # Deterministic values verified in report (total_multiplier is float e.g. 82.0)
    multiplier_str = f"+{data.total_multiplier}%"
    assert multiplier_str in report, \
        f"Total multiplier '{multiplier_str}' not found in report"
    assert str(data.final_effort_min) in report, \
        f"Final effort min '{data.final_effort_min}' not found in report"
    assert str(data.final_effort_max) in report, \
        f"Final effort max '{data.final_effort_max}' not found in report"
    print(f"  PASS: Deterministic values in report:")
    print(f"        Multiplier total: +{data.total_multiplier}%")
    print(f"        Final effort: {data.final_effort_min} - {data.final_effort_max} person-days")
    print(f"        Confidence: {data.confidence_level}")
    print(f"        Capacity gap: {'+' if data.capacity_gap >= 0 else ''}{data.capacity_gap} days")

    # data fields are populated
    assert data.project_type_detected == "embedded", \
        f"Expected 'embedded', got '{data.project_type_detected}'"
    assert data.methodology_detected == "v-model", \
        f"Expected 'v-model', got '{data.methodology_detected}'"
    assert data.total_multiplier == EXPECTED_TOTAL_MULTIPLIER, \
        f"Expected +82%, got +{data.total_multiplier}%"
    assert data.confidence_level == "Medium", \
        f"Expected 'Medium' (v0.6 score-based), got '{data.confidence_level}' (score={data.confidence_score})"
    assert len(data.pert_activities) == 9, \
        f"Expected 9 PERT activities, got {len(data.pert_activities)}"
    print(f"  PASS: EstimationData fields verified")

    # Save and verify file
    output_path = estimator.save(report, BMW_EFFORT_CONTEXT)
    assert output_path.exists(), f"Output file not created: {output_path}"
    assert "effort_estimation_BMW_Embedded_ECU" in output_path.name, \
        f"Unexpected filename: {output_path.name}"

    content = output_path.read_text(encoding="utf-8")
    assert "document_type: Effort Estimation Report" in content, \
        "Missing 'document_type: Effort Estimation Report' frontmatter"
    assert "generated_by: QAI Consultant" in content, \
        "Missing 'generated_by: QAI Consultant' frontmatter"
    assert f"project: {BMW_EFFORT_CONTEXT.project_name}" in content, \
        f"Missing project name in frontmatter"
    print(f"  PASS: File saved: {output_path.name}")
    print(f"        Frontmatter: document_type: Effort Estimation Report")


# ── Runner ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    static_tests = [
        ("_parse_duration: '2 years' -> 460 days",
            test_parse_duration_2years),
        ("_parse_duration: '18 months' -> 378 days",
            test_parse_duration_18months),
        ("_parse_duration: '6 weeks' -> 30 days",
            test_parse_duration_6weeks),
        ("_parse_team_size: '2' -> 2",
            test_parse_team_size_2),
        ("_parse_team_size: '5 developers' -> 5",
            test_parse_team_size_range),
        ("project type 'automotive embedded system' -> 'embedded'",
            test_detect_project_type_embedded),
        ("methodology 'V-model' -> 'v-model'",
            test_detect_methodology_vmodel),
        ("baseline: embedded + v-model -> (30, 40)%",
            test_baseline_embedded_vmodel),
        ("multiplier: ISO 26262 ASIL B -> +20%",
            test_multiplier_iso26262_asil_b),
        ("multiplier: A-SPICE level 2 -> +20%",
            test_multiplier_aspice_level2),
        ("multiplier: No existing automation -> +20%",
            test_multiplier_no_automation),
        ("multiplier: Small QA team (<=2) -> +10%",
            test_multiplier_small_qa_team),
        ("multiplier: third-party integrations risk -> +12%",
            test_multiplier_external_integrations),
        ("total multiplier for BMW ECU = +82%",
            test_total_multiplier_82pct),
        ("PERT formula E=(O+4M+P)/6 for all activities",
            test_pert_formula),
        ("9 PERT activities when total_multiplier > 0",
            test_pert_nine_activities),
        ("confidence = 'Medium' for BMW ECU (v0.6 score-based algorithm)",
            test_confidence_level_medium),
        ("app.py has 3 tabs: Risk Register, Effort Estimation, Test Strategy",
            test_three_tabs_in_app),
        ("Effort Estimation tab has download button",
            test_effort_tab_download_button),
        ("init_session_state() initializes effort_report and effort_path",
            test_effort_keys_in_init_session_state),
        ("'Generate Another Strategy' clears effort_report and effort_path",
            test_generate_another_clears_effort_keys),
        ("Sidebar 'Start Over' clears effort_report and effort_path",
            test_start_over_clears_effort_keys),
        ("EffortEstimator imported at module level in app.py",
            test_effort_estimator_imported_in_app),
        ("CLI _run_main_loop() shows 3 panels: Risk Register, Effort Estimation, Test Strategy",
            test_cli_shows_three_panels),
        ("generate_strategy() returns effort_report and effort_path",
            test_cli_generate_strategy_returns_effort_keys),
    ]

    passed = failed = 0

    print("=" * 68)
    print("  QAI Consultant — Effort Estimator v0.4 Tests")
    print("=" * 68)

    for name, fn in static_tests:
        print(f"\n[TEST] {name}")
        try:
            fn()
            passed += 1
        except AssertionError as e:
            print(f"  FAIL: {e}")
            failed += 1
        except Exception as e:
            import traceback
            print(f"  ERROR: {type(e).__name__}: {e}")
            traceback.print_exc()
            failed += 1

    # LLM smoke test
    print(f"\n{'=' * 68}")
    print("  Loading agent + running LLM smoke test (requires Ollama)...")
    print(f"{'=' * 68}")

    try:
        from agent import QAIAgent
        agent = QAIAgent()
        print(f"\n[TEST] Full estimate: BMW ECU context, all sections, file saved")
        test_full_estimate_bmw(agent)
        passed += 1
    except AssertionError as e:
        print(f"  FAIL: {e}")
        failed += 1
    except Exception as e:
        import traceback
        print(f"  ERROR: {type(e).__name__}: {e}")
        traceback.print_exc()
        failed += 1

    print(f"\n{'=' * 68}")
    print(f"  Results: {passed} passed, {failed} failed")
    print(f"{'=' * 68}")

    import sys as _sys
    _sys.exit(0 if failed == 0 else 1)
