<!-- mcp-name: io.github.gvasile29/qai-consultant-mcp -->
![QAI Consultant](https://raw.githubusercontent.com/gvasile29/qai-consultant/master/assets/brand/qai_logo_horizontal_1680.png)

# qai-consultant-mcp

[![qai-consultant MCP server](https://glama.ai/mcp/servers/gvasile29/qai-consultant/badges/card.svg)](https://glama.ai/mcp/servers/gvasile29/qai-consultant)
[![qai-consultant MCP server](https://glama.ai/mcp/servers/gvasile29/qai-consultant/badges/score.svg)](https://glama.ai/mcp/servers/gvasile29/qai-consultant)
![MCP Registry](https://img.shields.io/badge/MCP%20Registry-listed-6B46C1?logo=anthropic)
![Awesome MCP Servers](https://img.shields.io/badge/Awesome%20MCP%20Servers-listed-blue?logo=github)

Listed on the [official MCP registry](https://registry.modelcontextprotocol.io) (`io.github.gvasile29/qai-consultant-mcp`), [Glama](https://glama.ai/mcp/servers/gvasile29/qai-consultant), and [Awesome MCP Servers](https://github.com/punkpeye/awesome-mcp-servers).

![qai-consultant-mcp answering a retrieve_qa_knowledge call in MCP Inspector](https://raw.githubusercontent.com/gvasile29/qai-consultant/master/assets/demo/qai-consultant-mcp-demo.gif)

A local, fully keyless [MCP](https://modelcontextprotocol.io) server: standards-grounded QA knowledge retrieval (ISTQB, OWASP, IEEE, ISO, EU AI Act), deterministic QA effort estimation, QA document quality review, and test-results health analysis — callable directly from Claude Code, Claude Desktop, or claude.ai.

No API keys, no Pinecone, no cloud LLM calls. It runs a local embedding index over a self-authored QA knowledge base and does the estimation math itself; **the client LLM writes the narrative**, this server just supplies grounding and numbers.

> This package is the MCP companion to [QAI Consultant](https://github.com/gvasile29/qai-consultant), an AI QA Architect web app / CLI. If you're looking for the full app (Test Strategy / Risk Register / Effort Report generation with a browser UI), see the [main project](https://github.com/gvasile29/qai-consultant) instead — this package is just the MCP server piece of it.

## Install

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

First run downloads the embedding model (`sentence-transformers/all-MiniLM-L6-v2`, CPU-only) and builds a local index — this takes a minute or two the first time, then it's cached.

## Tools

| Tool | What it does |
|---|---|
| `retrieve_qa_knowledge` | Grounding chunks from the knowledge base (ISTQB, OWASP, IEEE, ISO standards; testing methodologies; audit/evaluation frameworks; the EU AI Act), filterable by category |
| `list_kb_sources` | Every document in the knowledge base, grouped by category |
| `estimate_qa_effort` | Deterministic PERT-based effort estimate (baseline + complexity multipliers + team capacity + confidence score) — no LLM narrative, you write your own from the numbers |
| `review_qa_document` | Deterministic 0–100 quality score for an existing Test Plan/Strategy/test case list across six ISTQB/IEEE-829-grounded dimensions, with findings and resolved KB citations — no LLM scoring, you write the narrative from the findings |
| `analyze_test_results` | Deterministic health metrics from JUnit XML or CSV test execution data — flaky tests, ever-failing tests, slowest tests, and failure clustering — no LLM anywhere in this tool |

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
