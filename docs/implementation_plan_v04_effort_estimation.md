# QAI Consultant — v0.4 Effort Estimation Implementation Plan

## Overview

v0.4 adds a third auto-generated document: **Effort Estimation Report**.
It is generated automatically alongside the Test Strategy and Risk Register,
using project context + risk profile to produce a detailed breakdown of QA effort.

---

## Estimation Methodology

QAI Consultant uses a **hybrid approach** combining multiple industry techniques:

### 1. Baseline Benchmark (Industry Standards)
Starting point based on project type and methodology:

| Project Type | Methodology | QA % of Total Effort |
|---|---|---|
| Web Application | Agile | 15–20% |
| Web Application | Waterfall | 25–30% |
| Mobile App | Agile | 20–25% |
| REST API / Microservices | Agile | 15–20% |
| Embedded System | V-model | 30–40% |
| Embedded System (ASIL A/B) | V-model + Agile | 35–45% |
| Embedded System (ASIL C/D) | V-model | 45–60% |
| Desktop Application | Agile | 20–25% |

### 2. Complexity Multipliers
Applied on top of the baseline based on project-specific factors:

| Factor | Condition | Multiplier |
|---|---|---|
| Compliance | ISO 26262 ASIL C/D | +30–40% |
| Compliance | ISO 26262 ASIL A/B | +15–20% |
| Compliance | GDPR / PCI-DSS / HIPAA | +10–15% |
| Compliance | A-SPICE Level 2/3 | +20–30% |
| Automation | No automation, greenfield | +20% (automation setup) |
| Automation | Existing suite to maintain | +10% (maintenance) |
| Team | Small QA team (1–2 people) | +10% (context switching) |
| Integrations | 3+ external integrations | +10–15% |
| Risk | High/Critical risks identified | +10–20% per critical risk |

### 3. Three-Point Estimation (PERT)
For each activity area, estimate 3 scenarios:
- **Optimistic (O):** Best case, no blockers
- **Most Likely (M):** Realistic estimate
- **Pessimistic (P):** Worst case, with delays and rework

**PERT Formula:** `E = (O + 4M + P) / 6`
**Standard Deviation:** `SD = (P - O) / 6`

### 4. Activity Breakdown
Effort is split across these QA activities:

| Activity | Typical % of QA Effort |
|---|---|
| Test Planning & Strategy | 5–10% |
| Test Design & Specification | 15–20% |
| Test Environment Setup | 5–10% |
| Automation Framework Setup | 10–20% (if greenfield) |
| Test Execution — Functional | 25–35% |
| Test Execution — Non-functional | 10–15% |
| Defect Management & Retesting | 10–15% |
| Regression Testing | 10–15% |
| Reporting & Documentation | 5–8% |

---

## Output Document Structure

```markdown
# Effort Estimation Report — [Project Name]

## 1. Estimation Summary
  - Total QA effort range (person-days)
  - Confidence level (Low / Medium / High)
  - Methodology used
  - Key assumptions

## 2. Baseline Calculation
  - Project type + methodology → baseline benchmark
  - Total project duration estimate
  - Baseline QA effort (person-days)

## 3. Complexity Adjustments
  - Table of applied multipliers with justification
  - Adjusted QA effort after multipliers

## 4. Activity Breakdown (PERT)
  - Table: Activity | O | M | P | PERT Estimate | % of Total
  - Visual: effort distribution per activity

## 5. Team Capacity Analysis
  - Available QA person-days based on team size + timeline
  - Gap analysis: estimated need vs available capacity
  - Recommendation: is the team sufficient?

## 6. Risk Buffer
  - Additional effort buffer based on Risk Register findings
  - Per critical/high risk: recommended buffer days

## 7. Automation ROI
  - If greenfield: estimated setup cost vs long-term savings
  - Break-even point (sprints/releases)

## 8. Assumptions & Constraints
  - List of assumptions made during estimation
  - Constraints that could invalidate the estimate

## 9. Recommendations
  - Prioritization if capacity is insufficient
  - Suggested phasing of QA activities
```

---

## New File: `src/effort_estimator.py`

```python
class EffortEstimator:
    def estimate(context: ProjectContext, risk_register: str) -> tuple
    def _calculate_baseline(context) -> dict
    def _apply_multipliers(context, baseline) -> dict
    def _pert_breakdown(adjusted_effort, context) -> dict
    def _team_capacity(context) -> dict
    def _risk_buffer(risk_register) -> dict
    def save(report, context, output_dir) -> Path
```

**Key design decision:** The effort estimator uses **deterministic logic** (rules + formulas) for the baseline and multipliers, then uses the **LLM only for narrative generation** — not for the numbers. This ensures consistent, reproducible estimates.

---

## Integration Points

### strategy_generator.py
`generate_all()` will call `EffortEstimator.estimate()` and include the report in its return dict.

### cli.py
Third panel added after Risk Register and Test Strategy:
```
⚠️  Risk Register
📋 Test Strategy
📊 Effort Estimation Report   ← NEW
```

### app.py
Third tab added:
```
⚠️ Risk Register | 📋 Test Strategy | 📊 Effort Estimation   ← NEW
```

---

## Knowledge Base Additions Needed

Add estimation-specific knowledge to improve LLM narrative quality:

- `knowledge_base/expert_knowledge/PROMPT_Effort_Estimation.md` ← already exists!
- Add real estimation data from LinkedIn polls (when available)
- Add `knowledge_base/methodologies/Effort_Estimation_Techniques.md` ← CREATE

---

## Definition of Done for v0.4

- [ ] `effort_estimator.py` implemented with deterministic baseline + multipliers
- [ ] PERT calculation implemented for all activity areas
- [ ] Team capacity gap analysis implemented
- [ ] Risk buffer calculated from Risk Register
- [ ] `generate_all()` updated to include effort estimation
- [ ] CLI updated with third output panel
- [ ] Streamlit updated with third tab
- [ ] `Effort_Estimation_Techniques.md` added to knowledge base
- [ ] CLAUDE.md updated
- [ ] Tests written and passing
