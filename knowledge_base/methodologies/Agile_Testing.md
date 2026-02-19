# Agile Testing — Methodology Guide

Source: Compiled from public knowledge — Lisa Crispin & Janet Gregory "Agile Testing" concepts, Agile Testing Manifesto, and industry best practices.

---

## Overview

Agile Testing is a software testing practice that follows the principles of agile software development. Unlike traditional testing which happens at the end of development, agile testing is continuous and collaborative — everyone on the team is responsible for quality.

**Core Philosophy:** Testing is not a phase. It is a continuous activity integrated into every sprint.

---

## Agile Testing Manifesto Principles

1. **Testing is everyone's responsibility** — not just the QA team
2. **Continuous testing** — test early, test often, test automatically
3. **Customer collaboration** — involve business stakeholders in defining acceptance criteria
4. **Responding to change** — adapt test strategies as requirements evolve
5. **Working software over comprehensive documentation** — lightweight test artifacts

---

## The Agile Testing Quadrants (Lisa Crispin & Janet Gregory)

The quadrants model helps teams understand what types of testing to do and when.

```
                    BUSINESS FACING
                          |
    Q2                    |                    Q3
 Story Tests              |           Exploratory Testing
 Prototypes               |           Scenarios
 Simulations              |           Usability Testing
 -------------------------|-------------------------
 SUPPORTS THE TEAM        |         CRITIQUE PRODUCT
 -------------------------|-------------------------
    Q1                    |                    Q4
 Unit Tests               |           Performance Testing
 Component Tests          |           Security Testing
 Integration Tests        |           Load Testing
                          |
                    TECHNOLOGY FACING
```

### Quadrant 1 — Technology Facing, Support Team
- Unit tests, component tests, integration tests
- Automated, run continuously in CI/CD
- Written by developers, supported by QA

### Quadrant 2 — Business Facing, Support Team
- Functional tests, story tests, acceptance criteria
- Define "done" for user stories
- Written collaboratively (BDD style preferred)

### Quadrant 3 — Business Facing, Critique Product
- Exploratory testing, usability testing, UAT
- Human intelligence and creativity required
- Cannot be fully automated

### Quadrant 4 — Technology Facing, Critique Product
- Performance, load, stress, security testing
- Specialized tools required
- Often run outside of sprint or in dedicated sprints

---

## Shift-Left Testing

**Definition:** Moving testing activities earlier in the development lifecycle.

### Traditional vs Shift-Left

| Traditional | Shift-Left |
|---|---|
| Test after development | Test during development |
| QA finds bugs | Everyone prevents bugs |
| Requirements → Dev → Test | Requirements → Test + Dev simultaneously |
| Late defect detection (expensive) | Early defect detection (cheap) |

### How to Implement Shift-Left

1. **Three Amigos Sessions** — BA, Developer, and QA review each story before development starts
2. **Acceptance Criteria First** — define test conditions before writing code
3. **Developer Unit Testing** — developers write and own unit tests
4. **Static Analysis** — automated code quality checks in CI pipeline
5. **Early NFR Definition** — performance and security requirements defined upfront

---

## Agile Testing in Sprints

### Sprint Planning
- QA participates in planning
- Stories must have clear acceptance criteria before entering sprint
- Test effort is estimated alongside development effort
- Definition of Ready includes testability check

### During Sprint
- Testing happens in parallel with development
- QA tests completed stories immediately — no waiting for "testing phase"
- Defects found in sprint are fixed in sprint
- Automated regression suite grows with each sprint

### Sprint Review / Demo
- QA verifies acceptance criteria are met
- Live demo serves as final acceptance check

### Sprint Retrospective
- QA contributes quality metrics (defect count, escaped defects, coverage)
- Team discusses process improvements for quality

---

## Definition of Done (DoD) — QA Perspective

A story is "Done" when:
- [ ] All acceptance criteria are met and verified
- [ ] Unit tests written and passing
- [ ] Integration tests passing
- [ ] New automated regression tests added
- [ ] Exploratory testing completed
- [ ] No open critical or high defects
- [ ] Code reviewed and merged
- [ ] Documentation updated if needed

---

## Agile Test Planning

Unlike traditional test plans, agile test planning is lightweight and iterative.

### Release Test Strategy
- High-level approach for the entire release
- Updated each sprint if needed
- Covers: scope, environments, automation approach, risk areas

### Sprint Test Plan (Lightweight)
- What stories are being tested this sprint
- What test types are needed
- Any special considerations or dependencies

---

## Key Metrics in Agile Testing

| Metric | What It Measures |
|---|---|
| Defect Escape Rate | Bugs found in production vs total bugs found |
| Automated Test Coverage | % of functionality covered by automated tests |
| Test Execution Time | How long the full regression suite takes |
| Defects per Sprint | Volume of defects found per sprint |
| Defect Age | How long defects stay open |
| Sprint Velocity Impact | How much testing bottlenecks development |

---

## Common Agile Testing Anti-Patterns

1. **Testing Phase at End of Sprint** — QA waiting for dev to "finish" before testing starts
2. **QA as Gatekeeper** — QA is the only one responsible for quality
3. **Automation as Afterthought** — automating only at the end of the project
4. **Missing Acceptance Criteria** — stories enter sprint without clear testability
5. **Ignoring Non-Functional Requirements** — only functional testing in sprints, NFRs deferred forever
6. **No Regression Strategy** — every sprint breaks something from before

---

## Agile Testing Roles

### QA Engineer in Agile
- Collaborates from story creation to deployment
- Writes and maintains automated tests
- Performs exploratory testing
- Acts as quality advocate for the team
- Coaches developers on testability

### Whole Team Approach
- Developers write unit and integration tests
- Product Owner defines clear acceptance criteria
- Scrum Master removes testing impediments
- Everyone is responsible for quality

---

## QAI Consultant Application

When a project uses Agile methodology, QAI Consultant should:
1. Recommend the Agile Testing Quadrants framework for test type selection
2. Include Shift-Left practices in the Test Strategy
3. Define a lightweight Sprint Test approach instead of heavy formal plans
4. Recommend Definition of Done criteria that include QA checks
5. Suggest key agile testing metrics for the project
6. Flag common anti-patterns relevant to the project context
