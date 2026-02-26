"""
Tests for src/effort_estimator.py — v0.6 Confidence Level Algorithm.

Four-factor score-based algorithm (0-100 pts):

  Factor 1: PERT spread ratio     0-40 pts  spread=(P-O)/E
            < 1.0 → 40, 1.0-2.0 → 20-39 (linear), 2.0-3.0 → 5-19 (linear), ≥ 3.0 → 0

  Factor 2: Capacity gap ratio    0-30 pts  gap_ratio=capacity_gap/expected
            ≥ 0.3 → 30, 0.0-0.3 → 15-30 (linear), -0.3-0.0 → 0-14 (linear), < -0.3 → 0

  Factor 3: Data quality          0-20 pts  from dialogue completeness
            each of 5 fields: 4 pts if specific, 2 pts if vague, 0 pts if empty

  Factor 4: Multiplier magnitude  0-10 pts  10 - int(total_multiplier / 10)
            0% → 10, 50% → 5, ≥ 100% → 0

  Final: score ≥ 70 → "High"  |  40-69 → "Medium"  |  < 40 → "Low"

Covers (24 static tests):
1.  PERT spread < 1.0 → +40 pts
2.  PERT spread = 1.5 → +30 pts
3.  PERT spread = 2.5 → +12 pts
4.  PERT spread ≥ 3.0 → +0 pts
5.  gap_ratio ≥ 0.3 → +30 pts
6.  gap_ratio = 0.15 → +22 pts
7.  gap_ratio = -0.15 → +7 pts
8.  gap_ratio = -0.3 → +0 pts
9.  Data quality: all 5 specific → +20 pts
10. Data quality: 3 specific + 2 vague ("TBD", "unknown") → +16 pts
11. Data quality: all fields empty → +0 pts
12. Multiplier 0% → +10 pts
13. Multiplier 50% → +5 pts
14. Multiplier ≥ 100% → +0 pts
15. score = 100 → "High"
16. score = 70 (boundary) → "High"
17. score = 40 (boundary) → "Medium"
18. score = 39 (boundary) → "Low"
19. score = 0 → "Low"
20. BMW ECU scenario (82% multiplier, severe capacity deficit, vague fields) → "Low", score < 40
21. Simple web app (no compliance, comfortable surplus, all specific) → "High", score ≥ 70
22. data_quality_score stored in EstimationData after _calculate_data_quality()
23. confidence_score stored in EstimationData after _calculate_confidence()
24. Report markdown contains "score: X/100" alongside confidence label
"""

import sys
import os
os.environ["ANONYMIZED_TELEMETRY"] = "False"
os.environ["CHROMA_TELEMETRY"] = "False"

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from dialogue import ProjectContext
from effort_estimator import EffortEstimator, EstimationData


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_dummy_estimator() -> EffortEstimator:
    """EffortEstimator with a no-op agent for deterministic-only tests."""
    class _DummyAgent:
        def ask(self, prompt, system_prompt=""):
            return (
                "EXECUTIVE_SUMMARY: Test estimate generated.\n"
                "ASSUMPTIONS: - Standard working days assumed.\n"
                "RECOMMENDATIONS: - Prioritize risk-based testing.\n"
            )
    return EffortEstimator(_DummyAgent())


def make_confidence_data(
    o: float,       # pert_total_optimistic
    e: float,       # pert_total_expected
    p: float,       # pert_total_pessimistic
    gap: float,     # capacity_gap
    quality: int,   # data_quality_score (0-20)
    mult: float,    # total_multiplier (%)
) -> EstimationData:
    """Construct a minimal EstimationData for directly testing _calculate_confidence()."""
    data = EstimationData()
    data.pert_total_optimistic = o
    data.pert_total_expected = e
    data.pert_total_pessimistic = p
    data.capacity_gap = gap
    data.data_quality_score = quality
    data.total_multiplier = mult
    return data


def make_context(**overrides) -> ProjectContext:
    """Minimal ProjectContext with sensible defaults, overrideable by kwargs."""
    defaults = {
        "project_name": "Test Project",
        "project_description": "A simple test project",
        "project_type": "web application",
        "tech_stack": "React + Node.js",
        "team_qa_size": "3 engineers",
        "team_dev_size": "5 developers",
        "timeline": "6 months",
        "methodology": "Agile",
        "known_risks": "minimal identified risks",
        "existing_automation": "Full CI/CD with Selenium and JUnit",
        "compliance_requirements": "GDPR",
    }
    defaults.update(overrides)
    return ProjectContext(**defaults)


# ── ISOLATION CONSTANTS ───────────────────────────────────────────────────────
# To isolate a single factor, set the other three to zero:
#
#   Factor 1 = 0 → spread ≥ 3.0: O=50, E=100, P=350 → spread = 3.0
#   Factor 2 = 0 → gap_ratio ≤ -0.3: gap=-100 (with E=100) → gap_ratio = -1.0
#   Factor 3 = 0 → quality = 0
#   Factor 4 = 0 → mult = 100
#
# Used in all factor isolation tests below.
_ZERO_SPREAD = dict(o=50, e=100, p=350)     # spread=3.0 → Factor 1 = 0
_ZERO_GAP    = dict(gap=-100)               # gap_ratio=-1.0 → Factor 2 = 0  (with e=100)


# ── FACTOR 1: PERT Spread Ratio (0-40 pts) ────────────────────────────────────

def test_spread_below_1_gives_40pts():
    """spread_ratio < 1.0 → +40 pts from Factor 1."""
    # O=90, E=100, P=100 → spread = (100-90)/100 = 0.1 < 1.0 → Factor 1 = 40
    # Isolation: gap=-100 (Factor 2=0), quality=0 (Factor 3=0), mult=100 (Factor 4=0)
    data = make_confidence_data(o=90, e=100, p=100, gap=-100, quality=0, mult=100)
    est = make_dummy_estimator()
    est._calculate_confidence(data)
    assert data.confidence_score == 40, \
        f"spread=0.1 → expected 40 pts from Factor 1 only, got {data.confidence_score}"
    print("  PASS: spread_ratio=0.1 (<1.0) → Factor 1 = +40 pts  (score={})".format(data.confidence_score))


def test_spread_1_5_gives_30pts():
    """spread_ratio = 1.5 → +30 pts from Factor 1.

    Formula: int(40 - (1.5 - 1.0) * 20) = int(40 - 10) = 30
    """
    # O=50, E=100, P=200 → spread = 150/100 = 1.5 → int(40 - 0.5*20) = 30
    data = make_confidence_data(o=50, e=100, p=200, gap=-100, quality=0, mult=100)
    est = make_dummy_estimator()
    est._calculate_confidence(data)
    assert data.confidence_score == 30, \
        f"spread=1.5 → expected 30 pts from Factor 1 only, got {data.confidence_score}"
    print("  PASS: spread_ratio=1.5 → Factor 1 = +30 pts  (score={})".format(data.confidence_score))


def test_spread_2_5_gives_12pts():
    """spread_ratio = 2.5 → +12 pts from Factor 1.

    Formula: int(20 - (2.5 - 2.0) * 15) = int(20 - 7.5) = 12
    """
    # O=50, E=100, P=300 → spread = 250/100 = 2.5 → int(20 - 0.5*15) = 12
    data = make_confidence_data(o=50, e=100, p=300, gap=-100, quality=0, mult=100)
    est = make_dummy_estimator()
    est._calculate_confidence(data)
    assert data.confidence_score == 12, \
        f"spread=2.5 → expected 12 pts from Factor 1 only, got {data.confidence_score}"
    print("  PASS: spread_ratio=2.5 → Factor 1 = +12 pts  (score={})".format(data.confidence_score))


def test_spread_3_or_more_gives_0pts():
    """spread_ratio ≥ 3.0 → +0 pts from Factor 1."""
    # O=50, E=100, P=350 → spread = 300/100 = 3.0 → 0 pts
    data = make_confidence_data(o=50, e=100, p=350, gap=-100, quality=0, mult=100)
    est = make_dummy_estimator()
    est._calculate_confidence(data)
    assert data.confidence_score == 0, \
        f"spread=3.0 → expected 0 pts from Factor 1 only, got {data.confidence_score}"
    print("  PASS: spread_ratio=3.0 (≥3.0) → Factor 1 = +0 pts  (score={})".format(data.confidence_score))


# ── FACTOR 2: Capacity Gap Ratio (0-30 pts) ───────────────────────────────────

def test_gap_ratio_large_surplus_gives_30pts():
    """gap_ratio ≥ 0.3 (comfortable surplus) → +30 pts from Factor 2."""
    # spread=3.0 (Factor 1=0), gap=30 → gap_ratio=0.3 → +30 pts, quality=0, mult=100
    data = make_confidence_data(o=50, e=100, p=350, gap=30, quality=0, mult=100)
    est = make_dummy_estimator()
    est._calculate_confidence(data)
    assert data.confidence_score == 30, \
        f"gap_ratio=0.3 → expected 30 pts from Factor 2 only, got {data.confidence_score}"
    print("  PASS: gap_ratio=0.3 (≥0.3) → Factor 2 = +30 pts  (score={})".format(data.confidence_score))


def test_gap_ratio_0_15_gives_22pts():
    """gap_ratio = 0.15 (mild surplus) → +22 pts from Factor 2.

    Formula: int(15 + 0.15/0.3 * 15) = int(15 + 7.5) = 22
    """
    # spread=3.0 (Factor 1=0), gap=15 → gap_ratio=0.15 → 22 pts, quality=0, mult=100
    data = make_confidence_data(o=50, e=100, p=350, gap=15, quality=0, mult=100)
    est = make_dummy_estimator()
    est._calculate_confidence(data)
    assert data.confidence_score == 22, \
        f"gap_ratio=0.15 → expected 22 pts from Factor 2 only, got {data.confidence_score}"
    print("  PASS: gap_ratio=0.15 → Factor 2 = +22 pts  (score={})".format(data.confidence_score))


def test_gap_ratio_minus_0_15_gives_7pts():
    """gap_ratio = -0.15 (mild deficit) → +7 pts from Factor 2.

    Formula: int(15 + (-0.15)/0.3 * 15) = int(15 - 7.5) = 7
    """
    # spread=3.0 (Factor 1=0), gap=-15 → gap_ratio=-0.15 → 7 pts, quality=0, mult=100
    data = make_confidence_data(o=50, e=100, p=350, gap=-15, quality=0, mult=100)
    est = make_dummy_estimator()
    est._calculate_confidence(data)
    assert data.confidence_score == 7, \
        f"gap_ratio=-0.15 → expected 7 pts from Factor 2 only, got {data.confidence_score}"
    print("  PASS: gap_ratio=-0.15 → Factor 2 = +7 pts  (score={})".format(data.confidence_score))


def test_gap_ratio_at_minus_0_3_gives_0pts():
    """gap_ratio = -0.3 (at-deficit boundary) → +0 pts from Factor 2.

    Formula: int(15 + (-0.3)/0.3 * 15) = int(15 - 15) = 0
    Note: gap_ratio = exactly -0.3 falls in the ≥ -0.3 branch, still gives 0 pts.
    """
    # spread=3.0 (Factor 1=0), gap=-30 → gap_ratio=-0.3 → 0 pts, quality=0, mult=100
    data = make_confidence_data(o=50, e=100, p=350, gap=-30, quality=0, mult=100)
    est = make_dummy_estimator()
    est._calculate_confidence(data)
    assert data.confidence_score == 0, \
        f"gap_ratio=-0.3 → expected 0 pts from Factor 2 only, got {data.confidence_score}"
    print("  PASS: gap_ratio=-0.3 (severe deficit boundary) → Factor 2 = +0 pts  (score={})".format(data.confidence_score))


# ── FACTOR 3: Data Quality Score (0-20 pts) ───────────────────────────────────

def test_data_quality_all_specific_gives_20pts():
    """All 5 fields specific → data_quality_score = 20 (5 × 4 pts)."""
    ctx = make_context(
        timeline="6 months",
        team_qa_size="3 engineers",
        team_dev_size="5 developers",
        compliance_requirements="GDPR",
        existing_automation="Full CI/CD with Selenium and JUnit",
    )
    est = make_dummy_estimator()
    data = EstimationData()
    est._calculate_data_quality(ctx, data)
    assert data.data_quality_score == 20, \
        f"All specific fields → expected data_quality_score=20, got {data.data_quality_score}"
    print(f"  PASS: 5 specific fields → data_quality_score = {data.data_quality_score} (5 × 4 pts)")


def test_data_quality_3_specific_2_vague_gives_16pts():
    """3 specific + 2 vague ('TBD', 'unknown') → data_quality_score = 16 (3×4 + 2×2)."""
    ctx = make_context(
        timeline="TBD",            # vague → 2 pts
        team_qa_size="unknown",    # vague → 2 pts
        team_dev_size="5 developers",          # specific → 4 pts
        compliance_requirements="GDPR",        # specific → 4 pts
        existing_automation="Full CI/CD with Selenium and JUnit",  # specific → 4 pts
    )
    est = make_dummy_estimator()
    data = EstimationData()
    est._calculate_data_quality(ctx, data)
    assert data.data_quality_score == 16, \
        f"3 specific + 2 vague → expected data_quality_score=16, got {data.data_quality_score}"
    print(f"  PASS: 3 specific + 2 vague (TBD/unknown) → data_quality_score = {data.data_quality_score} (3×4 + 2×2)")


def test_data_quality_all_empty_gives_0pts():
    """All 5 fields empty → data_quality_score = 0."""
    ctx = make_context(
        timeline="",
        team_qa_size="",
        team_dev_size="",
        compliance_requirements="",
        existing_automation="",
    )
    est = make_dummy_estimator()
    data = EstimationData()
    est._calculate_data_quality(ctx, data)
    assert data.data_quality_score == 0, \
        f"All empty fields → expected data_quality_score=0, got {data.data_quality_score}"
    print(f"  PASS: All empty fields → data_quality_score = {data.data_quality_score}")


# ── FACTOR 4: Multiplier Magnitude (0-10 pts) ─────────────────────────────────

def test_multiplier_0pct_gives_10pts():
    """total_multiplier = 0% → +10 pts from Factor 4.

    Formula: max(0, 10 - int(0 / 10)) = max(0, 10 - 0) = 10
    """
    # spread=3.0, gap=-100 (both zero), quality=0 → isolate Factor 4
    data = make_confidence_data(o=50, e=100, p=350, gap=-100, quality=0, mult=0)
    est = make_dummy_estimator()
    est._calculate_confidence(data)
    assert data.confidence_score == 10, \
        f"mult=0% → expected 10 pts from Factor 4 only, got {data.confidence_score}"
    print("  PASS: total_multiplier=0% → Factor 4 = +10 pts  (score={})".format(data.confidence_score))


def test_multiplier_50pct_gives_5pts():
    """total_multiplier = 50% → +5 pts from Factor 4.

    Formula: max(0, 10 - int(50 / 10)) = max(0, 10 - 5) = 5
    """
    data = make_confidence_data(o=50, e=100, p=350, gap=-100, quality=0, mult=50)
    est = make_dummy_estimator()
    est._calculate_confidence(data)
    assert data.confidence_score == 5, \
        f"mult=50% → expected 5 pts from Factor 4 only, got {data.confidence_score}"
    print("  PASS: total_multiplier=50% → Factor 4 = +5 pts  (score={})".format(data.confidence_score))


def test_multiplier_100pct_gives_0pts():
    """total_multiplier ≥ 100% → +0 pts from Factor 4.

    Formula: max(0, 10 - int(100 / 10)) = max(0, 10 - 10) = 0
    """
    data = make_confidence_data(o=50, e=100, p=350, gap=-100, quality=0, mult=100)
    est = make_dummy_estimator()
    est._calculate_confidence(data)
    assert data.confidence_score == 0, \
        f"mult=100% → expected 0 pts from Factor 4 only, got {data.confidence_score}"
    print("  PASS: total_multiplier=100% → Factor 4 = +0 pts  (score={})".format(data.confidence_score))


# ── SCORE → LABEL MAPPING ─────────────────────────────────────────────────────

def test_score_100_is_high():
    """Maximum possible score (100) → 'High' confidence."""
    # spread<1.0 (→40) + gap_ratio≥0.3 (→30) + quality=20 + mult=0% (→10) = 100
    data = make_confidence_data(o=90, e=100, p=100, gap=50, quality=20, mult=0)
    est = make_dummy_estimator()
    label = est._calculate_confidence(data)
    assert label == "High", f"score=100 → expected 'High', got '{label}'"
    assert data.confidence_score == 100, \
        f"Expected confidence_score=100, got {data.confidence_score}"
    print(f"  PASS: score=100 → '{label}'")


def test_score_70_is_high():
    """Score = 70 (boundary) → 'High' confidence.

    Breakdown: spread<1.0 (→40) + gap_ratio=0 (→15) + quality=10 + mult=50% (→5) = 70
    """
    # O=90, E=100, P=100 → spread=0.1 → 40; gap=0 → gap_ratio=0 → int(15+0)=15
    # quality=10; mult=50 → max(0,10-5)=5
    data = make_confidence_data(o=90, e=100, p=100, gap=0, quality=10, mult=50)
    est = make_dummy_estimator()
    label = est._calculate_confidence(data)
    assert label == "High", f"score=70 → expected 'High', got '{label}'"
    assert data.confidence_score == 70, \
        f"Expected confidence_score=70, got {data.confidence_score}"
    print(f"  PASS: score=70 (boundary) → '{label}'  (40+15+10+5={data.confidence_score})")


def test_score_40_is_medium():
    """Score = 40 (boundary) → 'Medium' confidence.

    Breakdown: spread=1.5 (→30) + gap_ratio=-0.15 (→7) + quality=2 + mult=90% (→1) = 40
    """
    # O=50, E=100, P=200 → spread=1.5 → 30
    # gap=-15 → gap_ratio=-0.15 → int(15-7.5)=7
    # quality=2; mult=90 → max(0,10-9)=1
    data = make_confidence_data(o=50, e=100, p=200, gap=-15, quality=2, mult=90)
    est = make_dummy_estimator()
    label = est._calculate_confidence(data)
    assert label == "Medium", f"score=40 → expected 'Medium', got '{label}'"
    assert data.confidence_score == 40, \
        f"Expected confidence_score=40, got {data.confidence_score}"
    print(f"  PASS: score=40 (boundary) → '{label}'  (30+7+2+1={data.confidence_score})")


def test_score_39_is_low():
    """Score = 39 (below Medium boundary) → 'Low' confidence.

    Breakdown: spread=1.5 (→30) + gap_ratio=-0.15 (→7) + quality=2 + mult=100% (→0) = 39
    """
    # Same as score=40 except mult=100 → Factor 4 = 0 (saves 1 pt)
    data = make_confidence_data(o=50, e=100, p=200, gap=-15, quality=2, mult=100)
    est = make_dummy_estimator()
    label = est._calculate_confidence(data)
    assert label == "Low", f"score=39 → expected 'Low', got '{label}'"
    assert data.confidence_score == 39, \
        f"Expected confidence_score=39, got {data.confidence_score}"
    print(f"  PASS: score=39 (boundary) → '{label}'  (30+7+2+0={data.confidence_score})")


def test_score_0_is_low():
    """Minimum possible score (0) → 'Low' confidence."""
    # spread=3.0 (→0) + gap_ratio=-1.0 (→0) + quality=0 + mult=100% (→0) = 0
    data = make_confidence_data(o=50, e=100, p=350, gap=-100, quality=0, mult=100)
    est = make_dummy_estimator()
    label = est._calculate_confidence(data)
    assert label == "Low", f"score=0 → expected 'Low', got '{label}'"
    assert data.confidence_score == 0, \
        f"Expected confidence_score=0, got {data.confidence_score}"
    print(f"  PASS: score=0 → '{label}'")


# ── SCENARIO TESTS ────────────────────────────────────────────────────────────

def test_bmw_ecu_scenario_is_low():
    """BMW ECU: 82% multiplier + severe capacity deficit + vague fields → 'Low', score < 40.

    Scenario represents automotive embedded project with:
    - High technical complexity: 82% total multiplier (ASIL B + A-SPICE L2 + no-auto + small team + integrations)
    - Severe capacity deficit: only 2 QA for a large project (gap_ratio ≈ -0.56)
    - Vague inputs: timeline and automation status not yet confirmed
    - Moderate PERT spread (uncertainty from complexity)

    Expected score breakdown:
      Factor 1: spread=1.625 → int(40 - 0.625*20) = int(27.5) = 27 pts
      Factor 2: gap_ratio=-0.5625 (<-0.3 severe deficit) → 0 pts
      Factor 3: data_quality_score=4 (vague fields) → 4 pts
      Factor 4: mult=82% → max(0, 10-8) = 2 pts
      Total = 33 → "Low"
    """
    data = make_confidence_data(
        o=600,       # pert_optimistic
        e=1600,      # pert_expected
        p=3200,      # pert_pessimistic → spread=(3200-600)/1600=1.625 → 27 pts
        gap=-900,    # severe deficit → gap_ratio=-900/1600≈-0.56 → 0 pts
        quality=4,   # vague timeline + automation fields → 4 pts
        mult=82,     # ASIL B(20)+A-SPICE(20)+no-auto(20)+small-team(10)+integrations(12) → 2 pts
    )
    est = make_dummy_estimator()
    label = est._calculate_confidence(data)

    assert label == "Low", \
        f"BMW ECU scenario → expected 'Low', got '{label}' (score={data.confidence_score})"
    assert data.confidence_score < 40, \
        f"BMW ECU score should be < 40, got {data.confidence_score}"
    print(f"  PASS: BMW ECU scenario → '{label}' (score: {data.confidence_score}/100)")
    print(f"        spread→27pts + deficit→0pts + quality→4pts + mult→2pts = {data.confidence_score}")


def test_simple_webapp_scenario_is_high():
    """Simple web app: no compliance, comfortable surplus, all specific → 'High', score ≥ 70.

    Scenario represents a straightforward web project with:
    - Tight PERT estimate (well-understood scope)
    - Comfortable team capacity surplus
    - All project fields clearly defined
    - No compliance or legacy complexity

    Expected score breakdown:
      Factor 1: spread=0.667 (<1.0 tight estimate) → 40 pts
      Factor 2: gap_ratio=0.4 (≥0.3 comfortable surplus) → 30 pts
      Factor 3: data_quality_score=20 (all specific) → 20 pts
      Factor 4: mult=0% → max(0, 10-0) = 10 pts
      Total = 100 → "High"
    """
    data = make_confidence_data(
        o=100,      # optimistic
        e=150,      # expected  → spread=(200-100)/150 ≈ 0.667 < 1.0 → 40 pts
        p=200,      # pessimistic
        gap=60,     # surplus → gap_ratio=60/150=0.4 ≥ 0.3 → 30 pts
        quality=20, # all 5 fields specific → 20 pts
        mult=0,     # no compliance/complexity → 10 pts
    )
    est = make_dummy_estimator()
    label = est._calculate_confidence(data)

    assert label == "High", \
        f"Simple web app → expected 'High', got '{label}' (score={data.confidence_score})"
    assert data.confidence_score >= 70, \
        f"Simple web app score should be ≥ 70, got {data.confidence_score}"
    print(f"  PASS: Simple web app scenario → '{label}' (score: {data.confidence_score}/100)")
    print(f"        spread→40pts + surplus→30pts + quality→20pts + mult→10pts = {data.confidence_score}")


# ── DATA STORAGE TESTS ────────────────────────────────────────────────────────

def test_data_quality_score_stored_in_estimation_data():
    """_calculate_data_quality() stores result in data.data_quality_score (int, 0-20)."""
    ctx = make_context(
        timeline="6 months",
        team_qa_size="3 engineers",
        team_dev_size="5 developers",
        compliance_requirements="GDPR",
        existing_automation="Full CI/CD",
    )
    est = make_dummy_estimator()
    data = EstimationData()

    # Verify default value
    assert isinstance(data.data_quality_score, int), \
        "data.data_quality_score should be an int"

    est._calculate_data_quality(ctx, data)

    assert isinstance(data.data_quality_score, int), \
        "data.data_quality_score should be an int after calculation"
    assert 0 <= data.data_quality_score <= 20, \
        f"data_quality_score must be in [0, 20], got {data.data_quality_score}"
    assert data.data_quality_score == 20, \
        f"All specific fields → expected 20, got {data.data_quality_score}"
    print(f"  PASS: data_quality_score stored in EstimationData = {data.data_quality_score} (int, 0-20)")


def test_confidence_score_stored_in_estimation_data():
    """_calculate_confidence() stores raw score in data.confidence_score (int, 0-100)."""
    # Use a known configuration: should produce exactly score=100
    data = make_confidence_data(o=90, e=100, p=100, gap=50, quality=20, mult=0)
    est = make_dummy_estimator()

    # Before calling: default value
    assert isinstance(data.confidence_score, int), \
        "data.confidence_score should be initialized as int"

    label = est._calculate_confidence(data)

    assert isinstance(data.confidence_score, int), \
        "data.confidence_score should be an int after calculation"
    assert 0 <= data.confidence_score <= 100, \
        f"confidence_score must be in [0, 100], got {data.confidence_score}"
    assert data.confidence_score == 100, \
        f"Expected confidence_score=100 for maximum scenario, got {data.confidence_score}"
    assert label == "High", \
        f"Expected 'High' for score=100, got '{label}'"
    print(f"  PASS: confidence_score stored in EstimationData = {data.confidence_score} (int, 0-100)")
    print(f"        Label: '{label}'")


# ── REPORT FORMAT TEST ────────────────────────────────────────────────────────

def test_report_shows_confidence_score_per_100():
    """Report markdown contains 'score: X/100' alongside the confidence level label."""
    ctx = make_context()
    est = make_dummy_estimator()
    report, data = est.estimate(ctx)

    # Confidence level label must be in the report
    assert data.confidence_level in report, \
        f"Confidence level '{data.confidence_level}' not found in report"

    # Score in "X/100" format must appear
    score_str = f"score: {data.confidence_score}/100"
    assert score_str in report, \
        f"Expected '{score_str}' in report confidence row, not found.\n" \
        f"Relevant report section:\n" + \
        "\n".join(l for l in report.splitlines() if "Confidence" in l or "score:" in l)

    print(f"  PASS: Report contains '{score_str}' in confidence row")
    print(f"        Confidence level: {data.confidence_level}  |  Score: {data.confidence_score}/100")


# ── Runner ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":

    tests = [
        # Factor 1: PERT spread ratio
        ("PERT spread_ratio < 1.0 → +40 pts",
            test_spread_below_1_gives_40pts),
        ("PERT spread_ratio = 1.5 → +30 pts",
            test_spread_1_5_gives_30pts),
        ("PERT spread_ratio = 2.5 → +12 pts",
            test_spread_2_5_gives_12pts),
        ("PERT spread_ratio ≥ 3.0 → +0 pts",
            test_spread_3_or_more_gives_0pts),
        # Factor 2: Capacity gap ratio
        ("gap_ratio ≥ 0.3 (surplus) → +30 pts",
            test_gap_ratio_large_surplus_gives_30pts),
        ("gap_ratio = 0.15 → +22 pts",
            test_gap_ratio_0_15_gives_22pts),
        ("gap_ratio = -0.15 (mild deficit) → +7 pts",
            test_gap_ratio_minus_0_15_gives_7pts),
        ("gap_ratio = -0.3 (at-deficit boundary) → +0 pts",
            test_gap_ratio_at_minus_0_3_gives_0pts),
        # Factor 3: Data quality
        ("Data quality: 5 specific fields → +20 pts",
            test_data_quality_all_specific_gives_20pts),
        ("Data quality: 3 specific + 2 vague ('TBD','unknown') → +16 pts",
            test_data_quality_3_specific_2_vague_gives_16pts),
        ("Data quality: all fields empty → +0 pts",
            test_data_quality_all_empty_gives_0pts),
        # Factor 4: Multiplier magnitude
        ("Multiplier 0% → +10 pts",
            test_multiplier_0pct_gives_10pts),
        ("Multiplier 50% → +5 pts",
            test_multiplier_50pct_gives_5pts),
        ("Multiplier ≥ 100% → +0 pts",
            test_multiplier_100pct_gives_0pts),
        # Score → label mapping
        ("score = 100 → 'High'",
            test_score_100_is_high),
        ("score = 70 (boundary) → 'High'",
            test_score_70_is_high),
        ("score = 40 (boundary) → 'Medium'",
            test_score_40_is_medium),
        ("score = 39 (boundary) → 'Low'",
            test_score_39_is_low),
        ("score = 0 → 'Low'",
            test_score_0_is_low),
        # Scenario tests
        ("BMW ECU (82% mult, deficit, vague fields) → 'Low', score < 40",
            test_bmw_ecu_scenario_is_low),
        ("Simple web app (no compliance, surplus, all specific) → 'High', score ≥ 70",
            test_simple_webapp_scenario_is_high),
        # Data storage
        ("data_quality_score stored in EstimationData (int, 0-20)",
            test_data_quality_score_stored_in_estimation_data),
        ("confidence_score stored in EstimationData (int, 0-100)",
            test_confidence_score_stored_in_estimation_data),
        # Report format
        ("Report contains 'score: X/100' in confidence row",
            test_report_shows_confidence_score_per_100),
    ]

    passed = failed = 0

    print("=" * 68)
    print("  QAI Consultant — Confidence Level Algorithm v0.6 Tests")
    print("=" * 68)

    for name, fn in tests:
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

    print(f"\n{'=' * 68}")
    print(f"  Results: {passed} passed, {failed} failed")
    print(f"{'=' * 68}")

    import sys as _sys
    _sys.exit(0 if failed == 0 else 1)
