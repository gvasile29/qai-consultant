# Risk-Based Testing — Methodology Guide

Source: Compiled from ISTQB Advanced Level syllabus, public industry best practices, and risk-based testing frameworks.

---

## Overview

Risk-Based Testing (RBT) is a testing approach that prioritizes testing activities based on the risk of failure and the impact of that failure. Instead of testing everything equally, RBT focuses effort where it matters most.

**Core Philosophy:** Not everything can be tested. Focus testing effort on the areas with the highest risk to maximize quality within time and budget constraints.

---

## What is Risk in Software Testing?

**Risk = Likelihood of Failure × Impact of Failure**

- **Likelihood** — how probable is it that this feature will fail?
- **Impact** — if it fails, how bad is it for the business or end user?

---

## Types of Risk

### Product Risk (Quality Risk)
Risks related to the software itself:
- Missing or incorrect functionality
- Performance issues under load
- Security vulnerabilities
- Data integrity problems
- Usability issues

### Project Risk
Risks related to the project management:
- Unrealistic timelines
- Insufficient resources or skills
- Unclear requirements
- Third-party dependencies
- Environment availability

---

## Risk Identification Techniques

### 1. Expert Interviews
Talk to developers, business analysts, architects, and end users. Ask:
- "What keeps you up at night about this release?"
- "What has broken before in similar projects?"
- "What are the most complex areas?"

### 2. Historical Data Analysis
Review past defects, incidents, and production issues:
- Which modules have the most defects historically?
- Which features caused the most customer complaints?
- Which areas are most frequently changed?

### 3. Requirements Analysis
Identify risky requirements:
- Vague or ambiguous requirements → high likelihood of misunderstanding
- New functionality with no existing baseline → high likelihood of defects
- Integrations with external systems → high impact if broken

### 4. Architecture Review
Work with architects to identify:
- Single points of failure
- Complex integration points
- New technologies or frameworks being used
- Areas with high technical debt

### 5. Brainstorming / Risk Workshops
Structured sessions with the whole team to identify and rate risks collaboratively.

---

## Risk Assessment — Likelihood vs Impact Matrix

```
         │ LOW IMPACT │ MEDIUM IMPACT │ HIGH IMPACT
─────────┼────────────┼───────────────┼────────────
HIGH     │  MEDIUM    │     HIGH      │  CRITICAL
LIKELIHOOD│           │               │
─────────┼────────────┼───────────────┼────────────
MEDIUM   │    LOW     │    MEDIUM     │    HIGH
LIKELIHOOD│           │               │
─────────┼────────────┼───────────────┼────────────
LOW      │  MINIMAL   │      LOW      │   MEDIUM
LIKELIHOOD│           │               │
```

### Risk Levels and Testing Response

| Risk Level | Testing Approach |
|---|---|
| Critical | Extensive testing, multiple techniques, mandatory before release |
| High | Thorough testing, automated + exploratory, priority in sprint |
| Medium | Standard testing, focus on happy path + key edge cases |
| Low | Lightweight testing, smoke tests, sanity checks |
| Minimal | Minimal or no dedicated testing |

---

## Risk-Based Test Prioritization

### Step 1 — List All Features/Areas
Create a complete inventory of what needs to be tested.

### Step 2 — Score Each Area
Rate each feature on:
- **Likelihood of failure** (1-5 scale)
- **Business impact if it fails** (1-5 scale)
- **Risk score** = Likelihood × Impact

### Step 3 — Rank by Risk Score
Sort features from highest to lowest risk score.

### Step 4 — Allocate Testing Effort
- High risk areas → more test cases, more techniques, more time
- Low risk areas → fewer test cases, lighter approach

### Step 5 — Review and Update
Risk changes as development progresses. Reassess:
- After major code changes
- After defects are found in unexpected areas
- When requirements change

---

## Risk-Based Testing in Practice

### Example Risk Register

| Feature | Likelihood (1-5) | Impact (1-5) | Risk Score | Priority |
|---|---|---|---|---|
| Payment Processing | 3 | 5 | 15 | Critical |
| User Authentication | 4 | 4 | 16 | Critical |
| Search Functionality | 3 | 3 | 9 | Medium |
| Profile Picture Upload | 2 | 2 | 4 | Low |
| Dark Mode Toggle | 1 | 1 | 1 | Minimal |

---

## Residual Risk

After testing, some risk always remains. Residual risk is the risk that:
- Not all defects were found
- Some areas were not tested
- Production environment differs from test environment

**QA responsibility:** Communicate residual risk clearly to stakeholders before release. Never imply that testing = zero risk.

---

## Risk-Based Testing and Test Coverage

RBT redefines coverage — instead of aiming for 100% code coverage, aim for:
- 100% coverage of critical risk areas
- High coverage of high risk areas
- Representative coverage of medium risk areas
- Minimal coverage of low risk areas

---

## Common Mistakes in Risk-Based Testing

1. **Risk identified once and never updated** — risk is dynamic, must be reassessed
2. **Only considering technical risk** — business impact is equally important
3. **Risk assessment done by QA alone** — should involve the whole team
4. **Ignoring residual risk communication** — stakeholders must understand what was NOT tested
5. **Confusing risk with complexity** — complex ≠ risky, simple ≠ safe

---

## QAI Consultant Application

When generating a Test Strategy, QAI Consultant should:
1. Ask about known risk areas in the project
2. Generate a Risk Register template pre-populated with common risks for the project type
3. Recommend likelihood and impact scoring criteria
4. Map risk levels to test effort and techniques
5. Include a residual risk communication section in the Test Strategy
6. Recommend risk reassessment checkpoints throughout the project
