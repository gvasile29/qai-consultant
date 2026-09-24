<!-- mcp-name: io.github.gvasile29/qai-consultant-mcp -->
![QAI Consultant](https://raw.githubusercontent.com/gvasile29/qai-consultant/master/assets/brand/qai_logo_horizontal_1680.png)

# qai-consultant-mcp

[![qai-consultant MCP server](https://glama.ai/mcp/servers/gvasile29/qai-consultant/badges/card.svg)](https://glama.ai/mcp/servers/gvasile29/qai-consultant)
[![qai-consultant MCP server](https://glama.ai/mcp/servers/gvasile29/qai-consultant/badges/score.svg)](https://glama.ai/mcp/servers/gvasile29/qai-consultant)
![MCP Registry](https://img.shields.io/badge/MCP%20Registry-listed-6B46C1?logo=anthropic)
![Awesome MCP Servers](https://img.shields.io/badge/Awesome%20MCP%20Servers-listed-blue?logo=github)

Listed on the [official MCP registry](https://registry.modelcontextprotocol.io) (`io.github.gvasile29/qai-consultant-mcp`), [Glama](https://glama.ai/mcp/servers/gvasile29/qai-consultant), and [Awesome MCP Servers](https://github.com/punkpeye/awesome-mcp-servers).

![qai-consultant-mcp answering a retrieve_qa_knowledge call in MCP Inspector](https://raw.githubusercontent.com/gvasile29/qai-consultant/master/assets/demo/qai-consultant-mcp-demo.gif)

A local, fully keyless [MCP](https://modelcontextprotocol.io) server: standards-grounded QA knowledge retrieval (OWASP, IEEE, ISO, A-SPICE, EU AI Act, plus testing methodologies and audit frameworks), deterministic QA effort estimation, QA document quality review, test-results health analysis, and QA process maturity assessment — callable from Claude Code, Claude Desktop, or any other MCP client that runs local stdio servers.

No API keys, no Pinecone, no cloud LLM calls. It runs a local embedding index over a self-authored QA knowledge base (Markdown only — the ISTQB syllabus and OWASP guide PDFs used by the web app are not bundled, for licensing reasons) and does the estimation math itself; **the client LLM writes the narrative**, this server just supplies grounding and numbers.

> This package is the MCP companion to [QAI Consultant](https://github.com/gvasile29/qai-consultant), an AI QA Architect web app / CLI. If you're looking for the full app (Risk Register / Effort Estimation / Test Strategy / Test Plan generation with a browser UI), see the [main project](https://github.com/gvasile29/qai-consultant) instead — this package is just the MCP server piece of it.

## Install

Requires [uv](https://docs.astral.sh/uv/) (for `uvx`).

```bash
uvx qai-consultant-mcp
```

**Claude Code:**
```bash
claude mcp add qai-consultant -- uvx qai-consultant-mcp
```

**Claude Desktop** (`claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "qai-consultant": {
      "command": "uvx",
      "args": ["qai-consultant-mcp"]
    }
  }
}
```

First run downloads the embedding model (`sentence-transformers/all-MiniLM-L6-v2`, served via `fastembed`'s ONNX Runtime) and builds a local index — a few seconds to a minute the first time, then it's cached.

## Tools

| Tool | What it does |
|---|---|
| `retrieve_qa_knowledge` | Grounding chunks from the knowledge base (standards summaries — OWASP Top 10, IEEE 829, ISO/IEC 25010, ISO 26262, A-SPICE, EU AI Act; testing methodologies; audit/evaluation frameworks; AI SDLC case studies), filterable by category |
| `list_kb_sources` | Every document in the knowledge base, grouped by category |
| `estimate_qa_effort` | Deterministic PERT-based effort estimate (baseline + complexity multipliers + team capacity + confidence score) — no LLM narrative, you write your own from the numbers |
| `review_qa_document` | Deterministic 0–100 quality score for an existing Test Plan/Strategy/test case list across six ISTQB/IEEE-829-grounded dimensions, with findings and resolved KB citations — no LLM scoring, you write the narrative from the findings |
| `analyze_test_results` | Deterministic health metrics from JUnit XML or CSV test execution data — flaky tests, ever-failing tests, slowest tests, and failure clustering — no LLM anywhere in this tool |
| `assess_qa_maturity` | Deterministic indicative TMMi process-maturity level (1-3, never a certified 4-5) from a free-text description or pasted document, plus a conditional 7-check EU AI Act Articles 9-15 readiness score when the input signals an AI/ML system — no LLM anywhere in this tool |

## Try It — Example Prompts

Type these directly in Claude Code or Claude Desktop once the server is attached:

- *"Using qai-consultant, what does the knowledge base say about risk-based testing?"* → `retrieve_qa_knowledge`
- *"List every document in the qai-consultant knowledge base, grouped by category."* → `list_kb_sources`
- *"Using qai-consultant's estimate_qa_effort, estimate the effort for a B2B SaaS project called 'Test Migration', React + Node.js + PostgreSQL, 2 QA / 5 dev engineers, 3-month timeline, Agile/Scrum, no notable known risks, minimal existing test automation, no special compliance requirements."* → `estimate_qa_effort`
- *"Here's a Test Plan [paste it] — use qai-consultant to review it with review_qa_document and give me the score and findings."* → `review_qa_document`
- *"Here's a JUnit XML report from my last 3 CI runs [paste them] — use qai-consultant's analyze_test_results to find flaky tests."* → `analyze_test_results`
- *"Here's how our team tests today [describe it] — use qai-consultant's assess_qa_maturity to estimate our TMMi level and the gaps to close."* → `assess_qa_maturity`

The first one (`retrieve_qa_knowledge`) is the fastest way to confirm the server actually attached.

## Prompts

- `qa_project_interview` — the project-intake interview (11 questions covering scope, tech stack, team, timeline, risks, compliance)
- `risk_register_structure` — Risk Register document structure + grounding instructions
- `test_strategy_structure` — Test Strategy document structure + grounding instructions
- `test_plan_structure` — IEEE 829-aligned Test Plan structure + grounding instructions

Each `*_structure` prompt instructs the client to ground its generation in `retrieve_qa_knowledge` results with `[Source N]` citations, and to label the output as AI-generated.

## Privacy

Usage telemetry is **off by default**. Set `QAI_TELEMETRY=1` to opt in. Even then, only the tool name, a success flag, duration, retrieval `k`/`category`, package/Python version, OS family, and a random anonymous install ID are sent — never your query text, project details, or knowledge-base content.

## Source

[github.com/gvasile29/qai-consultant](https://github.com/gvasile29/qai-consultant) — Apache 2.0 licensed.
