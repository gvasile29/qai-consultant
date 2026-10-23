"""
QAI Consultant — MCP prompts (v3.0 step 7).

Prompt templates (the three *_structure ones take one optional project_name
argument) extracted from this project's own
document generators (risk_analyzer.py's build_risk_prompt,
strategy_generator.py's build_strategy_prompt, test_plan_generator.py's
build_test_plan_prompt) — their STRUCTURAL sections only, not the LLM-call
plumbing (RAG prefetch, streaming, output-file saving) that stays
Streamlit/CLI-only (this server never generates text itself).

A client (Claude Code, Claude Desktop, claude.ai) uses qa_project_interview
to run the same 11-question intake the app's dialogue.py does, then uses
the *_structure prompts to produce Risk Register / Test Strategy / Test
Plan documents in the same structure the app itself produces — grounded
via this server's retrieve_qa_knowledge tool instead of a second internal
LLM call, and estimate_qa_effort instead of guessing effort numbers.
"""

from qai_consultant.core.dialogue import QUESTIONS

_CITATION_INSTRUCTION = (
    "Ground every substantive section in retrieve_qa_knowledge results: call it with "
    "queries relevant to each section and cite the supporting document inline by the "
    "`source` value it returns, e.g. [source: methodologies/Risk_Based_Testing.md]. "
    "Cite only chunks whose text really supports the statement (prefer \"match\": "
    "\"strong\"), and if the tool's `note` says the knowledge base has no direct match "
    "or does not contain a named source, say so instead of citing an unrelated chunk. "
    "Never state a specific fact (version number, date, tool name) that the user did "
    'not provide — write "not specified" instead of inventing one.'
)

_AI_LABEL_INSTRUCTION = (
    "Include a visible 'AI-generated content — not yet reviewed by a qualified QA "
    "professional, review required before use' label at the end of the produced "
    "document (EU AI Act Article 50(2) transparency)."
)

_PROJECT_NAME_PLACEHOLDER = "<Project Name>"


def _project_title(project_name: str) -> tuple[str, str]:
    """(title text, extra instruction) for the document heading. Without a
    project_name the heading keeps an explicit <Project Name> marker plus an
    instruction to replace it, so the client never has to guess a substitution."""
    name = (project_name or "").strip()
    if name:
        return name, ""
    return _PROJECT_NAME_PLACEHOLDER, (
        f"Replace {_PROJECT_NAME_PLACEHOLDER} in the title with the project name from the "
        "user's context (the project_name answer of qa_project_interview); if it is not "
        "known, ask the user rather than inventing one.\n\n"
    )


def qa_project_interview() -> str:
    """The 11-question project-intake interview (dialogue.QUESTIONS), as an
    elicitation template a client runs before calling estimate_qa_effort or
    any of the *_structure prompts below — both assume this context already
    exists."""
    lines = [
        "Gather the following 11 pieces of project context from the user, one question "
        "at a time, before generating any QA deliverable. Use the hint to clarify what "
        "kind of answer is expected; a vague or missing answer should be followed up on, "
        "not silently accepted (e.g. \"a few\" is not a team size, \"soon\" is not a timeline).",
        "",
    ]
    for i, q in enumerate(QUESTIONS, 1):
        lines.append(f"{i}. **{q['key']}** — {q['question']}")
        lines.append(f"   _Hint: {q['hint']}_")
    lines.append("")
    lines.append(
        "Optionally, ask if there's any additional context worth noting beyond these "
        "11 questions (free text, no fixed format — corresponds to additional_context)."
    )
    lines.append(
        "Once gathered, this context maps directly onto estimate_qa_effort's parameters, "
        "and is what the risk_register_structure / test_strategy_structure / "
        "test_plan_structure prompts assume is already known."
    )
    return "\n".join(lines)


def risk_register_structure(project_name: str = "") -> str:
    """The Risk Register document structure, extracted from
    risk_analyzer.build_risk_prompt()'s structural section. ``project_name``
    (optional) fills the document title."""
    title, fill_in = _project_title(project_name)
    return f"""Generate a Risk Register for the project using EXACTLY this structure:

{fill_in}# Risk Register: {title}

## Executive Summary
2-3 sentences summarizing the overall risk profile. State clearly if the project is
Low / Medium / High / Critical risk overall.

## Risk Matrix Overview

| Risk ID | Risk Description | Likelihood | Impact | Risk Level | Priority |
|---|---|---|---|---|---|
| R01 | ... | High/Medium/Low | High/Medium/Low | Critical/High/Medium/Low | 1/2/3/... |

List the 5-7 MOST CRITICAL risks, sorted by priority — a shorter register where every
listed risk gets full detail below beats a longer one that runs out of space partway through.

## Detailed Risk Analysis

For each risk listed in the matrix above:

### R01: [Risk Title]
- **Category:** Technical / Process / Compliance / Resource / External
- **Description:** what the risk is and why it exists for this project
- **Likelihood:** High / Medium / Low — explain why
- **Impact:** High / Medium / Low — explain what happens if it materializes
- **Risk Level:** Critical / High / Medium / Low
- **Early Warning Signs:** signals indicating this risk is materializing
- **Mitigation Strategy:** concrete, specific actions to reduce this risk
- **Contingency Plan:** what to do if the risk materializes despite mitigation

## Risk-Based Testing Priorities

| Priority | Area to Test | Risk Level | Recommended Test Types |
|---|---|---|---|
| 1 | ... | Critical | ... |

## Recommendations for QA Strategy
Top 3-5 specific recommendations for this project based on the risk profile.

{_CITATION_INSTRUCTION}

{_AI_LABEL_INSTRUCTION}
"""


def test_strategy_structure(project_name: str = "") -> str:
    """The Test Strategy document structure, extracted from
    strategy_generator.build_strategy_prompt()'s structural section.
    ``project_name`` (optional) fills the document title."""
    title, fill_in = _project_title(project_name)
    return f"""Generate a Test Strategy document using EXACTLY this structure:

{fill_in}# Test Strategy: {title}

## 1. Project Overview
## 2. Scope — What Will Be Tested
## 3. Scope — What Will NOT Be Tested
## 4. Risk Assessment
Top 5-7 risks (High/Medium/Low), each with likelihood, impact, and mitigation —
prioritize covering fewer risks completely over listing more and running out of space.
## 5. Test Types Recommended
For each: why it's needed and at what phase it should be performed.
## 6. Test Approach & Methodology
Reference the team's methodology; include shift-left recommendations if applicable.
## 7. Entry & Exit Criteria
## 8. Resources & Man Power Estimation
Based on team size and timeline — be honest about gaps or resource constraints. Call
estimate_qa_effort for a deterministic PERT-based number rather than guessing.
## 9. Tools & Environment
Recommend specific tools per test type, based on the tech stack.
## 10. Key Risks & Mitigations
Top 3-5 project-specific risks with concrete mitigations.
## 11. References
QA standards and methodologies referenced in this strategy.

Be specific, practical, and tailored to this exact project. Avoid generic statements.

{_CITATION_INSTRUCTION}

{_AI_LABEL_INSTRUCTION}
"""


def test_plan_structure(project_name: str = "") -> str:
    """The Test Plan document structure, extracted from
    test_plan_generator.build_test_plan_prompt()'s structural section.
    ``project_name`` (optional) fills the document title."""
    title, fill_in = _project_title(project_name)
    return f"""Generate a Test Plan aligned with IEEE 829, using EXACTLY this structure:

{fill_in}# Test Plan: {title}

## 1. Introduction
State how this Test Plan relates to the Test Strategy.
## 2. Test Items
Based strictly on the tech stack given. Include a version number ONLY if stated
explicitly by the user; otherwise write "version not specified" — never invent one.
## 3. Features to be Tested
Prioritized by risk level (Critical -> High -> Medium -> Low), derived from the Risk Register.
## 4. Features NOT to be Tested
With justification for each exclusion.
## 5. Test Approach
Per test level (Unit, Integration, System, Acceptance, Performance, Security): techniques,
tools (based on tech stack), automation vs. manual split, AI tool usage and human review gates.
## 6. Entry and Exit Criteria
### Entry Criteria
### Exit Criteria
### Suspension and Resumption Criteria
## 7. Test Deliverables
Test cases, test data, test reports, defect reports, test summary report.
## 8. Testing Schedule

| Phase | Activities | Duration | Owner |
|---|---|---|---|
| Test Planning | Test plan finalisation, environment setup | ... | QA Lead |
| Test Design | Test case design, test data preparation | ... | QA Engineers |
| Test Execution | Functional + integration testing | ... | QA Engineers |
| Security Testing | OWASP checks, penetration testing | ... | QA Lead |
| Performance Testing | Load and stress testing | ... | QA Engineers |
| Regression & UAT | Regression suite, user acceptance | ... | QA + Dev |

Base this on the project's timeline and QA/dev team sizes.
## 9. Environmental Needs
Hardware, software, network requirements; test data and data masking needs; access/permissions.

Never state a specific fact (version number, date, tool name) that was not provided by
the user; write "not specified" instead of inventing one. A fabricated fact in an
official QA deliverable is worse than an admitted gap.

{_CITATION_INSTRUCTION}

{_AI_LABEL_INSTRUCTION}
"""
