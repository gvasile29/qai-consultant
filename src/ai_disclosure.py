# requires: (none — dependency-free, importable from any code path)
"""ai_disclosure.py — EU AI Act Article 50 transparency notices (shared, no third-party imports).

Five responsibilities:
  - AI_INTERACTION_NOTICE: Article 50(1) — tell the user they're talking to an AI system.
  - AI_GENERATED_FOOTER / with_ai_footer(): Article 50(2) — visible "AI-generated" label
    appended to every generated document (MD body + PDF, since PDF export renders the
    same markdown string).
  - build_front_matter(): Article 50(2) machine-readable marking for Markdown saves —
    a YAML front matter block with ai_generated: true, generator name/version, and model.
  - pdf_meta_html(): the same machine-readable marking for PDF exports, as HTML <meta>
    tags that xhtml2pdf maps onto real PDF /Author, /Subject, /Keywords metadata fields
    (verified: xhtml2pdf reads <meta name="author"|"subject"|"keywords" content="..."> and
    writes them into the PDF's actual metadata dictionary, not just the rendered page text).
  - pdf_icon_html(): Article 50(4) — a base64 data-URI <img> tag embedding the EU's official
    "Fully AI-Generated" Code of Practice icon (see assets/eu_ai_icon/README_EU_AI_ICON.md)
    into a PDF export's <body>. The Streamlit sidebar embeds the same icon's SVG variants
    directly (app.py); this function exists because xhtml2pdf renders raster images via
    data URIs but not SVG.

Kept dependency-free (only stdlib + this project's own dependency-free version.py) so
every code path can import it — including the MCP server path, which imports none of
Pinecone/Mistral/OpenAI/Streamlit. `model` is threaded in as a parameter rather than
imported from agent.py here, specifically to preserve that property: agent.py pulls in
all of those.

v3.3 adopted the EU Code of Practice's published icon set — see
docs/superpowers/specs/2026-07-29-eu-ai-icon-adoption-design.md for the applicability
assessment and design rationale.
"""

from __future__ import annotations

import base64
from datetime import datetime
from pathlib import Path

from version import __version__

EU_AI_ICON_DIR = Path(__file__).resolve().parent.parent / "assets" / "eu_ai_icon"

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


def build_front_matter(
    document_type: str, project_name: str, model: str, extra: dict[str, str] | None = None
) -> str:
    """YAML front matter block for a generated Markdown document — machine-readable
    AI-generated marking (EU AI Act Article 50(2)), on top of with_ai_footer()'s
    human-visible label. Caller supplies `model` (e.g. agent.MISTRAL_MODEL) rather
    than this module importing agent.py, to stay dependency-free. `extra` appends
    additional fixed key: value lines (e.g. {"standard": "IEEE 829"}) before the
    closing delimiter.
    """
    lines = [
        "---",
        "generated_by: QAI Consultant",
        f"generator_version: {__version__}",
        "ai_generated: true",
        f"model: {model}",
        f"date: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"project: {project_name}",
        f"document_type: {document_type}",
    ]
    for key, value in (extra or {}).items():
        lines.append(f"{key}: {value}")
    lines.append("---")
    return "\n".join(lines)


def pdf_meta_html(model: str) -> str:
    """HTML <meta> tags carrying the same AI-generated marking as
    build_front_matter(), for injection into a PDF export's <head> — xhtml2pdf
    maps these onto the PDF's actual /Author, /Subject, /Keywords metadata
    fields (verified empirically, not just rendered as visible page text)."""
    return (
        f'<meta name="author" content="QAI Consultant v{__version__}" />\n'
        '  <meta name="subject" content="AI-generated content — not yet reviewed by a '
        'qualified QA professional (EU AI Act Article 50(2))" />\n'
        f'  <meta name="keywords" content="ai-generated, QAI Consultant, {model}" />'
    )


def pdf_icon_html(icon_filename: str = "eu_ai_generated_icon.png") -> str:
    """Base64-embedded <img> tag for the EU AI-Generated Content icon (Code of
    Practice on Transparency of AI-Generated Content, supporting AI Act
    Article 50(4)) — for injection into a PDF export's <body>.

    xhtml2pdf renders raster data URIs but not SVG, hence PNG here (the
    Streamlit sidebar uses the SVG variants directly instead, via
    EU_AI_ICON_DIR). Returns "" if the icon asset is missing, never raises —
    same never-crash philosophy as with_ai_footer()/pdf_meta_html(), so a
    missing/renamed asset file degrades to no icon, not a broken PDF.
    """
    icon_path = EU_AI_ICON_DIR / icon_filename
    try:
        icon_bytes = icon_path.read_bytes()
    except OSError:
        return ""
    encoded = base64.b64encode(icon_bytes).decode("ascii")
    return (
        f'<img src="data:image/png;base64,{encoded}" '
        'alt="EU AI-Generated Content label" '
        'style="height:28pt;margin-bottom:6pt;" />'
    )
