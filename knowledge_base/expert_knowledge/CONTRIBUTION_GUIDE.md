# Expert Knowledge — Contribution Guide

Welcome to the Expert Knowledge section of QAI Consultant! 🎉

This folder is the most valuable part of the entire knowledge base. While standards and methodologies can be found in books and online, **expert knowledge comes only from real experience** — and that's what makes QAI Consultant truly intelligent.

This guide explains what we're looking for, how to contribute, and gives you concrete examples to follow.

---

## What is Expert Knowledge?

Expert knowledge is the kind of insight that a senior QA professional has after years of working on real projects. It's the answer to questions like:

- *"I've seen this type of project before — here's what usually goes wrong"*
- *"When a client tells me X, I know I should ask about Y"*
- *"This methodology sounds good in theory, but in practice, teams struggle with Z"*

This is knowledge you **won't find in ISTQB syllabuses or books**. It lives in people's heads — and we want to capture it here.

---

## Why Does This Matter for QAI Consultant?

QAI Consultant's goal is to think like a senior QA Architect. To do that, it needs to learn from real experience, not just theory.

The difference between a generic AI response and a QAI Consultant response should be:

> ❌ Generic: *"You should perform risk-based testing and prioritize high-impact areas."*

> ✅ QAI Consultant: *"For a fintech project with a 3-month deadline and a small team, the biggest risk is usually the payment processing flow and third-party integrations. Start there. Teams often underestimate the time needed to set up test environments for payment gateways — plan at least 2 weeks for that alone."*

That second response comes from **expert knowledge**. That's what we're building here.

---

## What to Contribute

We're looking for knowledge in these categories:

### 1. 🔍 Project Type Insights
Real observations about specific types of projects.

**Questions to answer:**
- What are the most common risks in this type of project?
- What do teams usually underestimate?
- What testing types are most critical?
- What questions should a QA ask at the start of this project?

**Project types we need coverage for:**
- Web applications (e-commerce, SaaS, portals)
- Mobile applications (iOS, Android, hybrid)
- APIs and microservices
- Embedded systems
- Data pipelines and ETL
- Financial systems (banking, payments, trading)
- Healthcare systems
- IoT systems
- Legacy system migrations

---

### 2. ⚠️ Common Mistakes and Lessons Learned
Real mistakes you've seen teams make — and what to do instead.

**Format:**
- What was the mistake?
- Why did it happen?
- What was the consequence?
- What should have been done instead?

---

### 3. 💬 Real Scenarios and How to Handle Them
Concrete situations a QA professional faces and how an experienced person would respond.

**Examples of scenarios:**
- "The client wants to skip testing to meet the deadline. What do you do?"
- "The team has no automated tests and needs to add them to a legacy system. Where do you start?"
- "You're a QA joining a project mid-sprint with no documentation. How do you get up to speed?"

---

### 4. 📏 Estimation Insights
Real data points and rules of thumb for estimating QA effort.

**Examples:**
- How much testing effort is typical for a project of X size?
- What factors increase or decrease QA effort?
- How do you estimate exploratory testing time?

---

### 5. 🤝 Stakeholder and Team Dynamics
Soft skills and communication insights that experienced QA professionals have learned.

**Examples:**
- How to communicate risk to a non-technical manager
- How to push back on unrealistic timelines
- How to get developers to care about quality

---

## How to Structure Your Contribution

Each contribution should be a markdown file in this folder. Use the following template:

---

### File Naming Convention

```
[Category]_[Topic].md
```

**Examples:**
- `ProjectType_Fintech.md`
- `Lessons_Learned_Integration_Testing.md`
- `Estimation_Mobile_Projects.md`
- `Scenario_No_Time_For_Testing.md`

---

### Contribution Template

```markdown
# [Title of your contribution]

**Contributor:** [Your name or GitHub handle]
**Date:** [Month Year]
**Experience context:** [Brief background — e.g., "Based on 5 years working on fintech projects"]

---

## Context

[Describe the situation, project type, or scenario this knowledge applies to]

---

## The Insight

[The actual expert knowledge — be specific, be honest, be practical]

---

## Why This Matters

[Why should QAI Consultant know this? How does it change the advice given?]

---

## Example

[A concrete example that illustrates the insight — real or anonymized]

---

## Common Mistakes Related to This

[What do less experienced QAs get wrong here?]

---

## QAI Consultant Should...

[Finish this sentence — what should the agent do or recommend based on this knowledge?]
```

---

## Contribution Examples

Here are two complete examples to show you what good contributions look like:

---

### Example 1 — Project Type Insight

**File:** `ProjectType_Fintech.md`

```markdown
# Expert Knowledge — Fintech and Payment Systems

**Contributor:** Gabi V.
**Date:** February 2026
**Experience context:** Based on working on BESS trading platforms and financial market integrations

---

## Context

Fintech projects — including payment systems, trading platforms, banking apps, 
and financial data pipelines — have unique testing challenges compared to 
standard web or mobile applications.

---

## The Insight

The biggest risk in fintech projects is almost never the happy path. 
Everyone tests "pay $100 successfully." The bugs that cause real damage are:

- What happens when a payment is initiated but the network drops mid-transaction?
- What happens when the same transaction is submitted twice in 2 seconds?
- What happens when an external API returns an unexpected response code?
- What happens when the system processes a negative amount?

These edge cases are where financial systems fail — and the consequences 
are real money lost or regulatory violations.

---

## Why This Matters

QA teams on fintech projects often focus on functional correctness 
(does the calculation produce the right number?) but underinvest in:
- Transaction integrity testing
- Idempotency testing
- Third-party API failure simulation
- Data reconciliation testing

---

## Example

On a trading platform project, a team spent 80% of test effort on UI 
and happy path flows. The production bug that caused the incident was 
a race condition when two orders were submitted simultaneously — 
a scenario that was never tested because "it would never happen."
It happened on day 3 in production.

---

## Common Mistakes Related to This

- Testing only with "clean" data — real financial data is messy
- Not testing what happens when external APIs are down
- Assuming transactions are atomic without verifying it
- Missing reconciliation testing between systems

---

## QAI Consultant Should...

When generating a Test Strategy for a fintech project, always include:
1. Transaction integrity and idempotency test cases
2. Third-party API failure simulation scenarios
3. Data reconciliation testing between systems
4. Negative amount and boundary value testing for all monetary fields
5. Concurrent transaction testing
```

---

### Example 2 — Scenario Insight

**File:** `Scenario_Deadline_Pressure.md`

```markdown
# Expert Knowledge — Handling "Skip Testing to Meet Deadline" Pressure

**Contributor:** [Your name]
**Date:** [Month Year]
**Experience context:** Common situation in consulting and product development

---

## Context

At some point in almost every project, a manager or client will suggest 
reducing or skipping testing to meet a deadline. This is one of the most 
common and most dangerous situations a QA professional faces.

---

## The Insight

The worst response is to simply agree to skip testing without documenting 
the decision and its risks. The second worst response is to refuse 
and create conflict without offering alternatives.

The right approach is to:
1. Acknowledge the business pressure (it's real)
2. Reframe the conversation from "skip testing" to "what risk are we accepting?"
3. Present a risk-based reduced scope (test the critical stuff, skip the low risk)
4. Document whatever is decided — in writing, with stakeholder sign-off

---

## Why This Matters

When testing is skipped and a production incident occurs, QA is often blamed. 
Having documented the risk decision protects the team and creates 
accountability at the right level.

---

## Example

"I understand we need to ship by Friday. Let me show you what we can cover 
by Friday and what we'd be leaving untested. The payment flow and user auth 
are low risk — we've tested those extensively. The new reporting module 
hasn't been tested at all. If we ship that untested, we're accepting the 
risk of incorrect financial reports going to clients. Is that a risk 
the business is comfortable taking?"

---

## Common Mistakes Related to This

- Agreeing verbally to skip testing without documentation
- Refusing without offering alternatives
- Not quantifying what "skip testing" actually means in terms of risk

---

## QAI Consultant Should...

When a project has tight deadlines, proactively recommend:
1. A risk-based scope reduction (test critical paths only)
2. A residual risk document template for stakeholder sign-off
3. A minimum viable test scope for the specific project type
```

---

## How to Submit Your Contribution

1. Create a new `.md` file in this folder following the naming convention
2. Use the template above
3. Commit and push to the repository
4. Open a Pull Request with a short description of what you added

---

## Questions?

If you're unsure whether something qualifies as expert knowledge, ask yourself:

> *"Would a junior QA engineer know this from reading a book or taking an ISTQB course?"*

If the answer is **no** — it's expert knowledge. Write it down. 🚀
