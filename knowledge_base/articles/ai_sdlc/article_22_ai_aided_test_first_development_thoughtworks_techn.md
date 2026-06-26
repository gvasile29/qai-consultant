---
title: AI-aided test-first development — Thoughtworks Technology Radar
source: https://www.thoughtworks.com/en-us/radar/techniques/ai-aided-test-first-development
category: AI SDLC Adoption
tags: AI, SDLC, software development, testing, quality assurance
---

# AI-aided Test-First Development

**Source:** Thoughtworks Technology Radar  
**Published:** April 26, 2023  
**Assessment Rating:** Assess — Worth exploring with the goal of understanding how it will affect your enterprise.

---

## Overview

Thoughtworks Technology Radar features AI-aided test-first development as a tracked technique, classifying it at the **Assess** ring — indicating it is worth exploring to understand its enterprise impact.

---

## Full Radar Entry

> "Like many in the software industry, we've been exploring the rapidly evolving AI tools that can support us in writing code. We see many people feed ChatGPT with an implementation, and then ask it to generate tests for that implementation. However, because we're big believers in TDD, and we don't always want to feed an external model with our potentially sensitive implementation code, one of our experiments in this space is a technique we call AI-aided test-first development. In this approach, we get ChatGPT to generate tests for us, and then a developer implements the functionality. Specifically, we first describe the tech stack and the design patterns we're using in a prompt "fragment" that is reusable across multiple use cases. Then we describe the specific feature we want to implement, including the acceptance criteria. Based on all that, we ask ChatGPT to generate an implementation plan for that feature in our architectural style and tech stack. Once we sanity check that implementation plan, we ask it to generate tests for our acceptance criteria.
>
> This approach has worked surprisingly well for us: It required the team to come up with a concise description of their architectural style and helped junior developers and new team members code features aligned with the team's existing style. The main drawback of this approach is that even though we don't give the model our source code, we still feed it potentially sensitive information such as our tech stack and feature descriptions. Teams should ensure they're working with their legal advisors to avoid any intellectual property issues, at least until a "for business" version of these AI tools becomes available."

---

## Key Takeaways

- **Reversed workflow:** Instead of generating tests from existing implementations, teams use an LLM to generate tests *before* writing production code — preserving TDD discipline.
- **Prompt fragments as team style guides:** Reusable prompts encoding the team's tech stack and architectural patterns ensure AI-generated tests align with team conventions.
- **Step-by-step process:**
  1. Create a reusable prompt fragment describing the tech stack and design patterns.
  2. Describe the specific feature with acceptance criteria.
  3. Request an LLM-generated implementation plan aligned with the team's style.
  4. Validate the implementation plan ("sanity check").
  5. Request tests generated from the acceptance criteria.
  6. Implement functionality to pass those tests.
- **Onboarding benefit:** Helped junior developers and new team members write code consistent with existing team standards.
- **Privacy trade-off:** Even without sharing source code, teams still expose potentially sensitive information — technology stack, architectural patterns, and feature descriptions — to external AI models.
- **Legal recommendation:** Teams should consult legal advisors about intellectual property concerns before adopting this technique, particularly until enterprise-grade AI tools with appropriate data handling become available.

---

## Relevance to QA and Test Strategy

This technique directly reinforces test-first quality practices in AI-assisted development contexts:

- **TDD discipline preserved:** AI generates tests before production code, keeping quality considerations front and centre in the development workflow rather than as an afterthought.
- **QA governance role:** QA engineers must review and validate AI-generated test stubs for completeness, coverage, and alignment with actual acceptance criteria — AI cannot replace QA judgement.
- **Architectural consistency:** The prompt-fragment approach means test scaffolding reflects the team's actual architecture, reducing the risk of superficial or misaligned tests.
- **Risk for Test Strategies:** Exposure of tech stack and feature details to external LLMs is a supply-chain risk that Test Strategies for AI-assisted teams should explicitly address.
