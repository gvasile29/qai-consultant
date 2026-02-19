# Exploratory Testing — Methodology Guide

Source: Compiled from James Bach, Michael Bolton, and Elisabeth Hendrickson public writings and industry best practices.

---

## Overview

Exploratory Testing is a simultaneous learning, test design, and test execution approach. The tester actively controls the design of the tests as those tests are performed, using information gained while testing to design new and better tests.

**Core Philosophy:** Testing is an intellectual activity. Skilled testers learn about the system while testing it and use that knowledge to find more and better bugs.

**Key Distinction:** Exploratory testing is NOT unstructured random clicking. It is disciplined, skilled, and purposeful — just not scripted in advance.

---

## Exploratory Testing vs Scripted Testing

| Aspect | Scripted Testing | Exploratory Testing |
|---|---|---|
| Test design | Before execution | During execution |
| Learning | Assumed upfront | Continuous |
| Creativity | Limited by script | Encouraged |
| Documentation | Detailed steps | Charter and notes |
| Best for | Regression, compliance | New features, edge cases |
| Skill required | Lower | Higher |

---

## Session-Based Test Management (SBTM)

SBTM is the most widely adopted framework for structuring exploratory testing.

### Core Elements

**Session** — an uninterrupted block of testing time (typically 60-120 minutes)

**Charter** — a mission statement for the session that defines:
- What to explore (feature, area, scenario)
- What to look for (specific risks, question to answer)

**Debrief** — a short meeting after the session to review findings

### Charter Format
```
Explore [TARGET]
With [RESOURCES / TOOLS]
To discover [INFORMATION]
```

### Charter Examples

```
Explore the payment checkout flow
With different payment methods (credit card, PayPal, invalid cards)
To discover edge cases and error handling issues
```

```
Explore the user authentication system
With focus on session management and token expiration
To discover security and reliability issues
```

```
Explore the application under slow network conditions
With Chrome DevTools network throttling
To discover performance and timeout handling issues
```

---

## Session Structure

### Before the Session
- Define charter (mission)
- Set time box (60-90 minutes recommended)
- Prepare environment and test data
- Note any specific risks or questions to investigate

### During the Session
- Follow the charter but deviate if interesting findings emerge
- Take notes continuously (what you did, what you found, questions)
- Document bugs immediately
- Track time spent on: testing, bug investigation, setup

### After the Session
- Complete session notes
- File bug reports
- Debrief with team (5-15 minutes)
- Identify follow-up charters if needed

---

## Session Notes Template

```
Charter: [mission statement]
Tester: [name]
Date/Time: [date and time]
Duration: [actual time spent]

Areas Covered:
- [what was explored]

Bugs Found:
- [bug ID and brief description]

Questions / Follow-ups:
- [open questions, areas to explore further]

Observations:
- [anything interesting that wasn't a bug]

Time Split:
- Testing: X%
- Bug investigation: X%
- Setup/other: X%
```

---

## Test Heuristics for Exploratory Testing

Heuristics are mental models that guide exploratory testers toward finding bugs.

### SFDPOT (San Francisco Depot) — James Bach
- **S**tructure — what is the system made of?
- **F**unction — what does it do?
- **D**ata — what data does it process?
- **P**latform — what environment does it run on?
- **O**perations — how will it be used?
- **T**ime — how does time affect it?

### CRUD
Test all data operations:
- **C**reate — can data be created correctly?
- **R**ead — can data be read and displayed correctly?
- **U**pdate — can data be modified correctly?
- **D**elete — can data be deleted correctly?

### Boundary Values
- Minimum and maximum values
- Just below minimum, just above maximum
- Zero, null, empty
- Very large values

### Error Guessing
Based on experience, guess where bugs are likely:
- Input fields without validation
- State transitions
- Concurrent operations
- Third-party integrations
- Recently changed code

---

## Personas in Exploratory Testing

Testing as different types of users reveals different bugs:

- **New User** — what happens when someone uses the feature for the first time?
- **Power User** — what happens with complex, advanced usage?
- **Malicious User** — what happens when someone tries to break the system?
- **Distracted User** — what happens with incomplete or interrupted actions?
- **Non-Technical User** — what happens when someone doesn't follow expected flows?

---

## When to Use Exploratory Testing

**Best suited for:**
- New or recently changed features
- Areas with high complexity or high risk
- When requirements are unclear or incomplete
- Complement to automated regression testing
- Finding usability issues
- Security and edge case discovery
- Post-release sanity checks in production

**Less suitable for:**
- Compliance testing requiring documented evidence
- High-volume regression testing
- Performance and load testing

---

## Metrics for Exploratory Testing

| Metric | How to Measure |
|---|---|
| Sessions completed | Count of completed test sessions |
| Bugs per session | Total bugs / total sessions |
| Charter coverage | % of planned charters executed |
| Defect severity distribution | % critical, high, medium, low |
| Debrief findings | Key risks identified per debrief |

---

## Common Mistakes in Exploratory Testing

1. **No charter** — testing without a mission leads to shallow coverage
2. **Sessions too long** — over 2 hours leads to fatigue and reduced effectiveness
3. **No notes during session** — findings get lost
4. **Skipping debrief** — insights are not captured or shared
5. **Only one tester per area** — different testers find different bugs
6. **Treating it as "informal"** — exploratory testing requires skill and discipline

---

## QAI Consultant Application

When including Exploratory Testing in a Test Strategy, QAI Consultant should:
1. Recommend session-based test management for structure
2. Generate starter charters for high-risk areas identified in the project
3. Recommend session duration and frequency
4. Suggest relevant heuristics for the project type
5. Include exploratory testing in effort estimation
6. Define what documentation is expected from sessions
