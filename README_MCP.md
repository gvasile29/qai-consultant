# qai-consultant-mcp

A local, fully keyless [MCP](https://modelcontextprotocol.io) server: standards-grounded QA knowledge retrieval (ISTQB, OWASP, IEEE, ISO, EU AI Act) and deterministic QA effort estimation — callable directly from Claude Code, Claude Desktop, or claude.ai.

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
