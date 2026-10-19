---
name: qai-consultant
description: Use the qai-consultant MCP server for QA work - test strategies, test plans, risk registers, QA effort estimates, reviewing an existing test plan, finding flaky tests in JUnit/CSV results, or judging a team's QA process maturity (TMMi, EU AI Act). Grounds answers in a QA standards knowledge base and deterministic numbers instead of guesses.
---

# qai-consultant

This skill tells you when and how to call the tools of the `qai-consultant` MCP server. The server runs locally, needs no API keys and never calls an LLM itself. It gives you two things you can't produce reliably on your own: retrieval from a curated QA knowledge base (OWASP Top 10, IEEE 829, ISO/IEC 25010, ISO 26262, A-SPICE, the EU AI Act, testing methodologies, audit frameworks, AI SDLC case studies) and deterministic calculations. You write the narrative. The server supplies the evidence and the numbers.

## Setup

If the tools below aren't available, the server isn't attached. Tell the user to install it (requires `uv`):

```bash
claude mcp add qai-consultant -- uvx qai-consultant-mcp
```

For other clients, the command is `uvx qai-consultant-mcp` over stdio. The first launch downloads a small embedding model and builds a local index, so it can take up to a minute. After that it's cached.

The server sends anonymous usage telemetry: tool name, success flag, duration, a few coarse result values (such as the maturity level or the number of findings), and package, Python and OS versions. It doesn't send project details or document content. If the user asks, it's turned off with the environment variable `QAI_TELEMETRY=0` or `DO_NOT_TRACK=1`.

## Picking the tool

| The user wants to... | Call |
|---|---|
| Know what a standard or methodology says, or ground a claim | `retrieve_qa_knowledge` |
| See what's in the knowledge base | `list_kb_sources` |
| Estimate QA effort or check whether a timeline is realistic | `estimate_qa_effort` |
| Get feedback on a Test Plan, Test Strategy or test case list they already have | `review_qa_document` |
| Find flaky, always-failing or slow tests from CI output | `analyze_test_results` |
| Know how mature their QA process is, or whether an AI system is ready for the EU AI Act | `assess_qa_maturity` |
| Write a new Risk Register, Test Strategy or Test Plan | the matching `*_structure` prompt plus `retrieve_qa_knowledge` (see below) |

Several requests need more than one tool. A new Test Plan usually wants an effort estimate behind it. A maturity assessment reads better when you also retrieve what TMMi says about the weakest process areas.

## Tool notes

### retrieve_qa_knowledge(query, category=None, k=5, min_score=0.40)

- Write the query as the concept you need ("entry and exit criteria for system testing"), not the user's whole message.
- `category` must be exactly one of `Standard`, `Methodology`, `Article`, `Expert Knowledge`, `Audit/Evaluation`. Leave it out when unsure.
- `k` goes from 1 to 20. Use 3-5 for a focused fact and 8-10 when building a whole document section.
- When nothing scores at least `min_score`, `chunks` is empty and `low_relevance` is true with a `note`: answer from your own knowledge and say the knowledge base had no match.
- Cite what you use as `[Source N]` with the returned `source` file name. If nothing relevant comes back, say that the knowledge base doesn't cover it. Don't invent a citation.
- The knowledge base holds Markdown summaries the project wrote. It does not bundle the ISTQB syllabus or OWASP guide PDFs, so don't quote those as if you'd retrieved them.

### estimate_qa_effort(...)

It needs all 11 project fields: `project_name`, `project_description`, `project_type`, `tech_stack`, `team_qa_size`, `team_dev_size`, `timeline`, `methodology`, `known_risks`, `existing_automation`, `compliance_requirements`. `additional_context` is optional.

- Ask the user for anything missing instead of making it up. The `qa_project_interview` prompt has the full intake questions if you need to run a proper interview.
- A validation problem returns `{"error": "validation", "fields": {...}}`. Show the user which fields were rejected and why, collect fixes, and call again.
- Report the result as a range (`final_effort_min` to `final_effort_max`) together with `confidence_level`. Explain the biggest multipliers and the risk buffer in plain words. Never collapse it to one number or change the numbers.

### review_qa_document(document_text, doc_type="auto")

- Pass the full document text. `doc_type` can be `auto`, `test_plan`, `test_strategy` or `test_cases`. Use `auto` unless the user said what it is.
- Text under about 200 characters returns `doc_type="insufficient_content"` and a score of 0. That means "too short to review", not "a bad document". Ask for the full text.
- Lead with `overall_score` and the weakest of the six dimensions, then go through the findings in order of impact. Each finding's `kb_citations` is the evidence. Quote those, and don't add citations of your own to findings that have none.

### analyze_test_results(junit_xml=None, csv_text=None, reference_tests=None, flaky_min=0.2, flaky_max=0.8)

- Pass exactly one of `junit_xml` or `csv_text`.
- Flakiness needs several runs. For multiple JUnit reports, pass a list of `{"run_id": "...", "xml": "..."}` objects. A single run can show failures and slow tests but can't prove a test is flaky.
- A test is flaky only when its pass rate falls between `flaky_min` and `flaky_max` across at least 3 executions, and it counts as ever-failing only when it never passed in at least 3 executions. Tests with fewer executions are left out of both lists without any warning, so an empty `flaky` list on 1-2 runs means "not enough data", not "no flaky tests". Check `runs` and `per_run` before you call a suite stable.
- Skipped and errored executions count as "not passed". A test skipped in every run lands in `ever_failing`, and a test that passed twice and was skipped once can show up as flaky. Look at the `skipped` counts in `per_run` before you tell the user a test is broken or flaky.
- CSV needs `name`, `classname` and `status` columns (`passed`, `failed`, `error`, `skipped`). `run_id`, `duration_s` and `message` are optional.
- Use `reference_tests` (as `classname::name`) when the user wants to know which expected tests never ran.

### assess_qa_maturity(project_description)

- Pass a description of how the team tests today, or paste an existing Test Strategy or Risk Register. Short input (under about 200 characters) returns level 0. Ask for more detail.
- The result is an indicative TMMi level from 1 to 3. Always pass on the returned `disclaimer`. Never present the result as a certified level, and never suggest level 4 or 5.
- The tool looks for specific practices in the text, so a team can do something well and still get no credit if the description doesn't mention it. When a gap looks surprising, ask the user whether they actually do that practice before calling it a weakness.
- When `ai_act_relevant` is true, include `ai_act_note`. The tool does not decide whether a system is legally "high-risk" under the EU AI Act, and you shouldn't either.

## Writing new documents

For a new Risk Register, Test Strategy or IEEE 829-style Test Plan:

1. Get the project context, from the conversation or by running the `qa_project_interview` prompt.
2. Load the matching prompt: `risk_register_structure`, `test_strategy_structure` or `test_plan_structure`. It gives you the section layout.
3. For each section that makes a standards claim, call `retrieve_qa_knowledge` and cite the result.
4. For effort and schedule sections, use the numbers from `estimate_qa_effort` exactly as returned.
5. Mark the finished document as AI-generated, as the structure prompts ask.

## What not to do

- Don't call a tool and then ignore its output in favor of your own guess. If you disagree with a number or a score, show the tool's result and explain why you'd read it differently.
- Don't re-score, re-weight or round deterministic outputs into something that looks more precise than it is.
- Don't present this as an official ISTQB, TMMi or EU certification. It's an open-source assistant grounded in public standards summaries.

Source and full web app: https://github.com/gvasile29/qai-consultant (Apache 2.0)
