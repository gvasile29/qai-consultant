"""
QAI Consultant — Shared knowledge-base configuration.

Dependency-free (stdlib only): the single source of truth for the embedding
model name, chunking parameters, and the knowledge_base/ folder-to-category
mapping. ``agent.py``, ``ingest.py``, ``evals/rag.py``, and the MCP server's
``local_index.py`` all import from here instead of each carrying their own
copy, so the values can't silently drift apart.

Kept free of third-party imports on purpose: ``ingest.py`` imports
``pinecone`` at module level and ``agent.py`` imports Streamlit-adjacent
code, so neither can be imported from the MCP server path (which must stay
keyless and Streamlit/Pinecone-free). This module is the one place both
sides can share without pulling in the other's dependencies.
"""

from pathlib import Path

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200

# Folder name (anywhere in a knowledge_base/ path) -> metadata category tag.
SOURCE_CATEGORIES = {
    "standards": "Standard",
    "methodologies": "Methodology",
    "articles": "Article",
    "expert_knowledge": "Expert Knowledge",
    "evaluation_audit": "Audit/Evaluation",
}


def get_source_category(file_path: Path) -> str:
    """Category tag for a knowledge_base/ file, derived from its folder path.

    Matches by top-level folder name so subfolders (e.g. standards/istqb/,
    standards/eu_ai_act/) inherit their parent's category without needing
    their own entry. Falls back to "General" for anything unmapped.
    """
    for part in Path(file_path).parts:
        if part in SOURCE_CATEGORIES:
            return SOURCE_CATEGORIES[part]
    return "General"
