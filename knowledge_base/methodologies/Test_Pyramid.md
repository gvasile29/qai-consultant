# Test Pyramid — Methodology Guide

Source: Compiled from Mike Cohn, Martin Fowler, and Google Engineering public writings and industry best practices.

---

## Overview

The Test Pyramid is a framework for thinking about the right balance of different types of automated tests. It guides teams on where to invest testing effort to maximize coverage while minimizing cost and execution time.

**Core Philosophy:** Have many small, fast, isolated tests at the bottom and fewer, slower, broader tests at the top.

---

## The Classic Test Pyramid (Mike Cohn)

```
           /\
          /  \
         / UI \          ← Few, slow, expensive
        /______\
       /        \
      / Service  \       ← Some, moderate speed
     /____________\
    /              \
   /   Unit Tests   \    ← Many, fast, cheap
  /__________________ \
```

### Layer 1 — Unit Tests (Base)
- Test individual functions, methods, or classes in isolation
- Written and maintained by developers
- Run in milliseconds
- No external dependencies (databases, APIs, file system)
- Should make up ~70% of your test suite

### Layer 2 — Service / Integration Tests (Middle)
- Test interactions between components, services, APIs
- Verify that modules work together correctly
- Slower than unit tests but faster than UI tests
- Should make up ~20% of your test suite

### Layer 3 — UI / End-to-End Tests (Top)
- Test the full application from the user's perspective
- Simulate real user actions through the UI
- Slowest and most expensive to write and maintain
- Most prone to flakiness
- Should make up ~10% of your test suite

---

## The Modern Test Trophy (Kent C. Dodds)

An evolution of the pyramid that emphasizes integration testing:

```
        /\
       /e2e\              ← Few
      /______\
     /        \
    /Integration\         ← Most
   /______________\
  /                \
 /    Unit Tests    \     ← Some
/____________________\
        ||||
     Static Analysis      ← Always
```

The Trophy argues that integration tests provide the best ROI — they test real behavior without the brittleness of full E2E tests.

---

## Google's Testing Approach (70/20/10 Rule)

Google publicly recommends:
- **70%** Unit Tests
- **20%** Integration Tests
- **10%** End-to-End Tests

This ratio maximizes:
- Speed of feedback
- Reliability of test suite
- Maintainability over time

---

## Test Characteristics by Layer

| Characteristic | Unit | Integration | E2E |
|---|---|---|---|
| Speed | Milliseconds | Seconds | Minutes |
| Cost to write | Low | Medium | High |
| Cost to maintain | Low | Medium | High |
| Flakiness | Very Low | Low-Medium | High |
| Confidence | Low (isolated) | Medium | High (real flow) |
| Feedback speed | Immediate | Fast | Slow |
| Who writes | Developer | Dev + QA | QA |

---

## The Ice Cream Cone Anti-Pattern

The inverse of the pyramid — most tests at the UI level:

```
  /________________________\
 /        Manual Tests      \   ← Many (expensive!)
/____________________________\
           /\
          /  \
         / UI \              ← Many (slow, brittle)
        /______\
       /        \
      / Service  \           ← Few
     /____________\
    /              \
   /   Unit Tests   \        ← Very few
  /__________________ \
```

**Problems with the Ice Cream Cone:**
- Slow feedback cycles
- Expensive to maintain
- High flakiness
- Cannot scale
- Developers don't know about failures quickly

---

## Applying the Test Pyramid in Practice

### Step 1 — Audit Your Current State
- How many tests do you have at each layer?
- What is your current ratio?
- Where do most failures occur?

### Step 2 — Identify Gaps
- Too many E2E tests and too few unit tests → refactor toward pyramid shape
- Missing integration layer → add API/service tests
- No static analysis → add linters and code quality tools

### Step 3 — Define Standards per Layer

**Unit Test Standards:**
- Coverage target (e.g., 80% line coverage)
- Must run in under 100ms each
- No external dependencies (mock everything)

**Integration Test Standards:**
- Cover all API contracts
- Cover all database interactions
- Run in CI on every PR

**E2E Test Standards:**
- Cover only critical user journeys
- Run on merge to main / before release
- Maximum acceptable flakiness rate defined

---

## Test Pyramid per Project Type

| Project Type | Unit | Integration | E2E |
|---|---|---|---|
| REST API / Microservice | 60% | 35% | 5% |
| Web Application | 50% | 30% | 20% |
| Mobile Application | 50% | 30% | 20% |
| Data Pipeline | 40% | 50% | 10% |
| Embedded System | 70% | 25% | 5% |

---

## Automation Tools by Layer

### Unit Testing
- **Java:** JUnit, TestNG
- **Python:** pytest, unittest
- **JavaScript:** Jest, Mocha
- **.NET:** NUnit, xUnit

### Integration Testing
- **API Testing:** RestAssured, Supertest, Karate
- **Database:** DbUnit, Testcontainers
- **Message Queues:** Testcontainers, embedded brokers

### E2E Testing
- **Web:** Selenium, Playwright, Cypress
- **Mobile:** Appium, Espresso (Android), XCTest (iOS)
- **Desktop:** WinAppDriver, PyAutoGUI

---

## Common Mistakes

1. **Inverting the pyramid** — too many E2E tests, too few unit tests
2. **Testing implementation details** — unit tests that break with every refactor
3. **No contract testing** — integration points not validated
4. **Flaky E2E tests ignored** — flakiness normalized instead of fixed
5. **100% code coverage as goal** — coverage metric without meaningful assertions
6. **No pyramid review** — ratio never assessed or adjusted

---

## QAI Consultant Application

When generating a Test Strategy, QAI Consultant should:
1. Recommend a test pyramid ratio appropriate for the project type
2. Identify which automation tools are suitable for each layer
3. Flag if the current team approach resembles the ice cream cone anti-pattern
4. Define coverage targets per layer
5. Include pyramid balance in effort estimation
6. Recommend CI/CD integration points for each test layer
