# MCP Server — Design Rationale & Deferred Work

**Original plan created:** 2026-07-14. v3.0 (MCP server MVP) and v3.1 (Evaluation Package) are both fully shipped — see `CLAUDE.md`'s Roadmap and architecture sections for what was built and how; that is now the source of truth for implementation detail. This file was trimmed after shipping to keep only what `CLAUDE.md` doesn't already capture: the rationale behind superseding the old roadmap, and the spec for the one deferred tool.

**Supersedes:** former roadmap items v2.1 (HuggingFace KB), v2.2 (Community knowledge), v3.0 (Hosted version), v4.0 (Multi-LLM). All removed 2026-07-14; their useful intent is absorbed here (hosted becomes v3.2 remote MCP; multi-LLM becomes irrelevant since the client brings its own LLM).

---

## 1. Vision: the MCP lens

QAI Consultant today is a one-shot document generator. The MCP server turns its real assets into tools any MCP client (Claude Code, Claude Desktop, claude.ai) can call inside a full AI SDLC workflow.

The lens that shapes every decision below: **the client LLM is stronger than our internal LLM.** So we never expose "generate a document" tools that internally call mistral-small; that chain is absurd. What we expose is what the client LLM cannot do alone:

1. **Grounding:** curated QA knowledge base retrieval (ISTQB/OWASP/IEEE/ISO summaries, methodologies, audit models, case studies).
2. **Determinism:** the PERT effort estimator with multipliers and confidence scoring. LLMs are bad at this arithmetic; our code is not.
3. **Process:** validated QA Architect workflows (the 11-question interview, Risk Register / Test Strategy / Test Plan structures) exposed as MCP prompts, not tools.

Explicitly NOT exposed: `ask()`, `ask_streaming()`, full document generation, the feedback loop. Those stay in Streamlit/CLI for users without an MCP client.

## 2. Deferred: QA maturity audit tool

`assess_qa_maturity(project_description, focus_areas=None)`: retrieval over `evaluation_audit/` and `standards/eu_ai_act/` (v2.6 KB pillar) + a deterministic TMMi-inspired scoring rubric; returns gap summary JSON with cited sources. The v3.1 plan scoped only F1 (`review_qa_document`) and F2 (`analyze_test_results`) in detail and left this tool's rubric undefined beyond the one-line spec above, so it was deliberately deferred rather than building an under-specified rubric from a single sentence — not dropped, just unscheduled. When it lands, it should share the rubric/citation-format infrastructure F1/F2 already established (dimension-weight normalization, `citation_queries` resolved via the caller's index, never-raising error contract) rather than inventing a second pattern.

Acceptance: rubric fully deterministic (same input, same score); every gap cites a KB source.
