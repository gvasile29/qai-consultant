# requires: (none — dependency-free, importable from any code path)
"""ai_disclosure.py — EU AI Act Article 50 transparency notices (shared, no third-party imports).

Two responsibilities:
  - AI_INTERACTION_NOTICE: Article 50(1) — tell the user they're talking to an AI system.
  - AI_GENERATED_FOOTER / with_ai_footer(): Article 50(2) — visible "AI-generated" label
    appended to every generated document (MD body + PDF, since PDF export renders the
    same markdown string).

Machine-readable marking (YAML front matter, PDF metadata) is out of scope here —
that's v3.0 (see MCP_PLAN.md section 12, action 2).
"""

from __future__ import annotations

AI_INTERACTION_NOTICE = (
    "🤖 **You are interacting with an AI system.** QAI Consultant uses an AI system "
    "(Mistral / OpenRouter LLMs) to generate the Risk Register, Effort Estimation, "
    "Test Strategy, and Test Plan. All outputs require review by a qualified QA "
    "professional before use."
)

AI_GENERATED_FOOTER = (
    "*🤖 AI-generated content — produced by QAI Consultant using an AI system "
    "(Mistral / OpenRouter LLM). This document has not been reviewed by a human and "
    "requires validation by a qualified QA professional before use "
    "(EU AI Act Article 50 transparency notice).*"
)


def with_ai_footer(text: str) -> str:
    """Append the visible AI-generated disclosure footer to markdown content.

    Falsy input (e.g. an empty string from a failed generation step) passes through
    unchanged rather than producing a footer-only "document".
    """
    if not text:
        return text
    return f"{text.rstrip()}\n\n---\n\n{AI_GENERATED_FOOTER}\n"
