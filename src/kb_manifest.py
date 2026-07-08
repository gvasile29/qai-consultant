"""
Knowledge Base manifest — the single source of truth for what the Streamlit
sidebar's "Knowledge Base" panel advertises to users.

WHY THIS EXISTS: the sidebar used to be a hand-written markdown bullet list
that silently drifted out of sync with knowledge_base/ (e.g. the
evaluation_audit/ folder was added and ingested but never surfaced in the
UI). KB_MANIFEST is now the one place that maps curated display groups to
real paths under knowledge_base/, and app.py checks each path's existence
before rendering a bullet — so a bullet can never claim content that isn't
actually there, and tests/test_kb_manifest.py guards that every real
top-level subfolder (except generated_strategies/) is represented here.

Each entry is a dict with:
  - "emoji": str            — leading icon for the bullet
  - "label": str            — display text after the emoji
  - "paths": list[str]      — one or more paths RELATIVE TO knowledge_base/
                               (a subfolder like "evaluation_audit", a nested
                               subfolder like "standards/istqb", or a specific
                               file like "standards/IEEE_829_Test_Documentation.md").
                               The entry is shown if AT LEAST ONE of its paths
                               exists on disk.

knowledge_base/generated_strategies/ is deliberately NOT covered by any
entry here: it holds user-feedback-derived content, not a curated KB
pillar, and should not be advertised as one.
"""

KB_MANIFEST = [
    {
        "emoji": "📘",
        "label": "ISTQB Syllabuses",
        "paths": ["standards/istqb"],
    },
    {
        "emoji": "🔒",
        "label": "OWASP Testing Guides",
        "paths": ["standards/owasp"],
    },
    {
        "emoji": "🚗",
        "label": "ISO 26262 & A-SPICE",
        "paths": [
            "standards/ISO_26262_Automotive_Safety.md",
            "standards/ASPICE_Process_Reference_Model.md",
        ],
    },
    {
        "emoji": "📋",
        "label": "IEEE 829",
        "paths": ["standards/IEEE_829_Test_Documentation.md"],
    },
    {
        "emoji": "⚙️",
        "label": "ISO/IEC 25010",
        "paths": ["standards/ISO_IEC_25010_Quality_Model.md"],
    },
    {
        "emoji": "🧭",
        "label": "Testing Methodologies",
        "paths": ["methodologies"],
    },
    {
        "emoji": "🔍",
        "label": "Audit & Process Evaluation",
        "paths": ["evaluation_audit"],
    },
    {
        "emoji": "📰",
        "label": "AI-SDLC Articles & Case Studies",
        "paths": ["articles"],
    },
    {
        "emoji": "🧠",
        "label": "Expert Knowledge",
        "paths": ["expert_knowledge"],
    },
]
