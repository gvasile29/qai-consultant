"""
Tests for src/kb_config.py — shared knowledge-base configuration + drift guards.

kb_config.py is the single source of truth for the embedding model, chunking
parameters, and the folder-to-category mapping, shared by agent.py,
ingest.py, evals/rag.py, and (from v3.0 step 3) the MCP server's
local_index.py. These tests pin the values themselves and confirm the other
modules import from kb_config rather than carrying their own copies, so the
values can't silently drift apart again.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

import kb_config
import agent
import ingest


def test_kb_config_has_no_third_party_imports():
    """kb_config.py must stay dependency-free (stdlib only) — the MCP server
    path cannot import pinecone (ingest.py) or Streamlit-adjacent code
    (agent.py), and this module is the one place both sides can share."""
    source = (SRC_DIR / "kb_config.py").read_text(encoding="utf-8")
    import ast
    tree = ast.parse(source)
    stdlib_allowed = {"pathlib"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top_level = alias.name.split(".")[0]
                assert top_level in stdlib_allowed, (
                    f"kb_config.py imports non-stdlib module '{alias.name}' — "
                    "this breaks its use from the dependency-free MCP server path."
                )
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                top_level = node.module.split(".")[0]
                assert top_level in stdlib_allowed, (
                    f"kb_config.py imports from non-stdlib module '{node.module}' — "
                    "this breaks its use from the dependency-free MCP server path."
                )


def test_embedding_model_value():
    assert kb_config.EMBEDDING_MODEL == "sentence-transformers/all-MiniLM-L6-v2"


def test_chunk_size_and_overlap_values():
    assert kb_config.CHUNK_SIZE == 1000
    assert kb_config.CHUNK_OVERLAP == 200
    assert kb_config.CHUNK_OVERLAP < kb_config.CHUNK_SIZE


def test_source_categories_mapping():
    expected = {
        "standards": "Standard",
        "methodologies": "Methodology",
        "articles": "Article",
        "expert_knowledge": "Expert Knowledge",
        "evaluation_audit": "Audit/Evaluation",
    }
    assert kb_config.SOURCE_CATEGORIES == expected


def test_get_source_category_top_level_folder():
    assert kb_config.get_source_category(Path("standards/ISO_IEC_25010_Quality_Model.md")) == "Standard"
    assert kb_config.get_source_category(Path("methodologies/Risk_Based_Testing.md")) == "Methodology"


def test_get_source_category_matches_nested_subfolder():
    """A subfolder under a mapped top-level folder (e.g. standards/istqb/,
    standards/eu_ai_act/) inherits the parent's category without its own
    SOURCE_CATEGORIES entry."""
    assert kb_config.get_source_category(Path("standards/istqb/CTFL.pdf")) == "Standard"
    assert kb_config.get_source_category(
        Path("standards/eu_ai_act/EU_AI_Act_Overview.md")
    ) == "Standard"


def test_get_source_category_unmapped_folder_returns_general():
    assert kb_config.get_source_category(Path("generated_strategies/foo.md")) == "General"


def test_agent_reexports_embedding_model_from_kb_config():
    """agent.py imports EMBEDDING_MODEL from kb_config rather than defining
    its own copy — existing callers (evals fallback, tests) reference
    agent.EMBEDDING_MODEL directly, so it must stay available there too."""
    assert agent.EMBEDDING_MODEL is kb_config.EMBEDDING_MODEL


def test_ingest_reexports_from_kb_config():
    assert ingest.EMBEDDING_MODEL is kb_config.EMBEDDING_MODEL
    assert ingest.CHUNK_SIZE is kb_config.CHUNK_SIZE
    assert ingest.CHUNK_OVERLAP is kb_config.CHUNK_OVERLAP
    assert ingest.get_source_category is kb_config.get_source_category


def test_ingest_no_longer_defines_its_own_source_categories():
    """ingest.py must not carry a second copy of SOURCE_CATEGORIES — a
    regression here means the category map could drift between ingest.py
    and kb_config again."""
    assert not hasattr(ingest, "SOURCE_CATEGORIES"), (
        "ingest.py still defines its own SOURCE_CATEGORIES — it should use "
        "kb_config.get_source_category() exclusively."
    )
