# BDD & TDD — Methodology Guide

Source: Compiled from Dan North (BDD originator), Kent Beck (TDD originator), and industry best practices.

---

## Overview

BDD (Behavior-Driven Development) and TDD (Test-Driven Development) are development practices that use tests to drive the design and implementation of software. Both shift testing left — to before code is written.

---

## TDD — Test-Driven Development

### What is TDD?

TDD is a development technique where tests are written before the production code. The cycle is short and iterative.

### The Red-Green-Refactor Cycle

```
    ┌─────────────────────────────────┐
    │                                 │
    ▼                                 │
  RED                                 │
Write a failing test                  │
(test doesn't pass because            │
code doesn't exist yet)               │
    │                                 │
    ▼                                 │
  GREEN                               │
Write the minimum code                │
to make the test pass                 │
    │                                 │
    ▼                                 │
  REFACTOR                            │
Clean up the code                     │
without breaking the test ────────────┘
```

### TDD Rules (Kent Beck)
1. Write no production code unless it is to make a failing test pass
2. Write only enough of a test to demonstrate a failure
3. Write only enough production code to make the test pass

### Benefits of TDD
- Forces clear thinking about requirements before coding
- Creates a comprehensive unit test suite automatically
- Makes refactoring safe
- Reduces debugging time
- Produces more modular, testable code design

### When TDD Works Best
- New functionality being built from scratch
- Complex business logic
- APIs and services
- Algorithmic code

### When TDD is Difficult
- Legacy code without tests
- UI-heavy applications
- Exploratory or prototype code
- Working with external systems that are hard to mock

---

## BDD — Behavior-Driven Development

### What is BDD?

BDD extends TDD by using natural language to describe the behavior of the system. It bridges the communication gap between business stakeholders and technical teams.

BDD was created by Dan North as an answer to "what should I test?" — focusing on behaviors rather than implementation.

### BDD Core Principle

**Test behaviors, not implementations.**

Instead of testing how code works internally, test what the system does from the user's perspective.

---

## Gherkin Language

BDD scenarios are written in Gherkin — a structured natural language format that both business and technical people can read and write.

### Gherkin Keywords

```gherkin
Feature: [name of the feature being described]
  [optional description]

  Background:
    Given [shared preconditions for all scenarios]

  Scenario: [name of the specific behavior]
    Given [initial context / precondition]
    When [action taken by the user or system]
    Then [expected outcome]
    And [additional outcome]
    But [exception or negative outcome]

  Scenario Outline: [parameterized scenario]
    Given a user with <role>
    When they access <resource>
    Then they see <result>

    Examples:
      | role  | resource     | result        |
      | admin | dashboard    | full access   |
      | user  | dashboard    | limited view  |
```

### Gherkin Example — E-commerce

```gherkin
Feature: Shopping Cart

  Background:
    Given a registered user is logged in

  Scenario: Add item to cart
    Given a product "Laptop" is available with price $999
    When the user clicks "Add to Cart"
    Then the cart should contain 1 item
    And the cart total should show $999

  Scenario: Remove item from cart
    Given the cart contains 1 "Laptop"
    When the user clicks "Remove"
    Then the cart should be empty
    And the cart total should show $0

  Scenario Outline: Apply discount code
    Given the cart total is $100
    When the user applies discount code "<code>"
    Then the cart total should be "<final_price>"

    Examples:
      | code      | final_price |
      | SAVE10    | $90         |
      | SAVE20    | $80         |
      | INVALID   | $100        |
```

---

## The Three Amigos

BDD is most effective when three perspectives collaborate on writing scenarios:

- **Business / Product Owner** — defines what behavior is needed (the "why")
- **Developer** — understands what is technically feasible (the "how")
- **QA** — identifies edge cases and what could go wrong (the "what if")

### Three Amigos Session Process
1. Select a user story or feature
2. Product Owner explains the desired behavior
3. QA and Dev ask clarifying questions
4. Together they write Gherkin scenarios
5. Scenarios become the acceptance criteria
6. Developers use scenarios to drive implementation
7. QA uses scenarios to automate acceptance tests

---

## BDD Tools

| Language | Tool |
|---|---|
| Java | Cucumber-JVM, JBehave |
| Python | Behave, pytest-bdd |
| JavaScript | Cucumber.js, Jest-Cucumber |
| Ruby | Cucumber (original) |
| .NET | SpecFlow |
| Any | Karate (API-focused BDD) |

---

## BDD vs TDD vs Traditional Testing

| Aspect | Traditional | TDD | BDD |
|---|---|---|---|
| Tests written | After code | Before code | Before code |
| Language | Technical | Technical | Natural language |
| Who writes | QA | Developer | Team together |
| Focus | Verification | Design | Behavior/Communication |
| Audience | Testers | Developers | Everyone |
| Artifacts | Test cases | Unit tests | Living documentation |

---

## Living Documentation

BDD scenarios serve as living documentation — they describe the system's behavior in plain language AND are executable as automated tests.

**Benefits:**
- Documentation never gets out of sync with code (it IS the test)
- Business stakeholders can read and validate acceptance criteria
- New team members understand system behavior quickly
- Regression suite grows naturally with features

---

## Common BDD Mistakes

1. **Scenario as implementation steps** — describing HOW not WHAT
   ```gherkin
   # Bad — implementation detail
   When the user clicks the "submit" button at coordinates (100, 200)
   
   # Good — behavior
   When the user submits the registration form
   ```

2. **Too many scenarios per feature** — scenario explosion, hard to maintain

3. **QA writes all scenarios alone** — loses the collaborative benefit

4. **No Three Amigos sessions** — scenarios don't reflect business intent

5. **Automating all scenarios** — some scenarios are better as manual/exploratory

6. **Vague steps** — steps that mean different things in different contexts

---

## When to Use BDD

**Best suited for:**
- Features with complex business rules
- Projects with active business stakeholder involvement
- Teams that struggle with requirements clarity
- Systems where acceptance criteria are ambiguous

**Less suitable for:**
- Pure technical components (APIs, libraries)
- Performance testing
- Teams without business stakeholder engagement
- Projects with very stable, well-understood requirements

---

## QAI Consultant Application

When including BDD/TDD in a Test Strategy, QAI Consultant should:
1. Recommend BDD when business logic is complex or requirements are ambiguous
2. Suggest Three Amigos sessions as part of sprint planning
3. Recommend appropriate BDD tooling based on the project's tech stack
4. Define which scenarios should be automated vs manual
5. Include BDD scenario writing in effort estimation
6. Recommend TDD for core business logic and algorithmic components
7. Flag anti-patterns relevant to the team's current approach
