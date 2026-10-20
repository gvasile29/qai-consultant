"""Guards for the qai_consultant package layout (spec 2026-10-20).

The wheel ships only common/core/mcp. These tests replace the old convention
"the MCP server stays keyless" with a failing check.
"""
import ast
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SRC = REPO_ROOT / "src"
PKG = SRC / "qai_consultant"

TIERS = {"common": 0, "core": 1, "mcp": 2}
APP_SUBPACKAGES = {"rag", "generation", "compliance", "ui", "observability"}
# Third-party / app-side modules a wheel module must never import.
FORBIDDEN_TOP_LEVEL = {
    "pinecone", "mistralai", "openai", "streamlit", "langchain",
    "langchain_community", "langchain_core", "langchain_huggingface",
    "sentence_transformers", "torch", "transformers", "xhtml2pdf", "rich",
    "dotenv",
}
LEGACY_NAMES = {
    "agent", "dialogue", "effort_core", "effort_estimator", "local_index",
    "mcp_server", "kb_config", "logger", "telemetry", "version", "prompts",
    "review_core", "results_core", "maturity_core", "risk_ledger",
    "text_checks", "risk_analyzer", "strategy_generator",
    "test_plan_generator", "review_generator", "maturity_generator",
    "doc_bundle", "templates", "executive_readout", "output_guards",
    "ai_disclosure", "pdf_export", "source_labels", "components", "theme",
    "_theme_fonts", "kb_manifest", "usage_guard", "visit_counter",
    "adoption_metrics", "ingest",
}


def _imports(path: Path):
    """Yield (top_level_name, dotted_name) for every import, lazy ones included."""
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                yield a.name.split(".")[0], a.name
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            yield node.module.split(".")[0], node.module


def _wheel_modules():
    for tier in TIERS:
        for p in sorted((PKG / tier).rglob("*.py")):
            yield tier, p


def test_wheel_tiers_exist_and_app_tiers_exist():
    for name in list(TIERS) + sorted(APP_SUBPACKAGES):
        assert (PKG / name / "__init__.py").is_file(), f"missing subpackage {name}"


def test_package_init_files_are_empty_of_imports():
    """Importing qai_consultant (or a tier) must never drag the app side in."""
    for init in PKG.rglob("__init__.py"):
        tree = ast.parse(init.read_text(encoding="utf-8-sig"))
        assert not [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))], init


def test_wheel_modules_import_only_lower_or_equal_tiers_and_no_heavy_deps():
    offenders = []
    for tier, path in _wheel_modules():
        for top, dotted in _imports(path):
            if top in FORBIDDEN_TOP_LEVEL:
                offenders.append(f"{path.relative_to(SRC)}: forbidden dependency {dotted}")
            if top == "qai_consultant":
                parts = dotted.split(".")
                target = parts[1] if len(parts) > 1 else None
                if target in APP_SUBPACKAGES or target in {"cli"}:
                    offenders.append(f"{path.relative_to(SRC)}: imports app-side {dotted}")
                elif target in TIERS and TIERS[target] > TIERS[tier]:
                    offenders.append(f"{path.relative_to(SRC)}: {tier} imports higher tier {dotted}")
            if top in LEGACY_NAMES:
                offenders.append(f"{path.relative_to(SRC)}: legacy flat import {dotted}")
    assert not offenders, "\n".join(offenders)


def test_no_legacy_flat_module_references_remain():
    """Catches stale string patch targets and bare imports in src/tests/evals/scripts."""
    offenders = []
    roots = [SRC, REPO_ROOT / "tests", REPO_ROOT / "evals", REPO_ROOT / "scripts"]
    for root in roots:
        for path in root.rglob("*.py"):
            if "__pycache__" in path.parts or path.name == "test_package_layout.py":
                continue
            text = path.read_text(encoding="utf-8-sig")
            tree = ast.parse(text)
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                    if node.module.split(".")[0] in LEGACY_NAMES:
                        offenders.append(f"{path.relative_to(REPO_ROOT)}:{node.lineno} from {node.module}")
                elif isinstance(node, ast.Import):
                    for a in node.names:
                        if a.name.split(".")[0] in LEGACY_NAMES:
                            offenders.append(f"{path.relative_to(REPO_ROOT)}:{node.lineno} import {a.name}")
                elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                    head = node.value.split(".")[0]
                    looks_dotted = node.value.replace(".", "").replace("_", "").isalnum()
                    if "." in node.value and head in LEGACY_NAMES and looks_dotted and not node.value.endswith((".py", ".md", ".json", ".toml", ".yml", ".txt")):
                        offenders.append(f"{path.relative_to(REPO_ROOT)}:{node.lineno} string {node.value!r}")
    assert not offenders, "\n".join(offenders[:40])


def test_mcp_subpackage_does_not_shadow_the_sdk():
    from qai_consultant.mcp import server

    assert server.FastMCP.__module__.startswith("mcp."), server.FastMCP.__module__
    assert not server.FastMCP.__module__.startswith("qai_consultant")


def test_app_py_is_still_a_real_streamlit_script():
    text = (SRC / "app.py").read_text(encoding="utf-8-sig")
    assert len(text.splitlines()) > 500, "src/app.py must stay the real script, not a shim"
    assert "from qai_consultant" in text
    assert "st.set_page_config" in text


def test_shims_exist_and_delegate():
    expected = {
        "cli.py": "qai_consultant.cli",
        "ingest.py": "qai_consultant.rag.ingest",
        "mcp_server.py": "qai_consultant.mcp.server",
    }
    for name, target in expected.items():
        text = (SRC / name).read_text(encoding="utf-8-sig")
        assert target in text and "__main__" in text, name
        assert len(text.splitlines()) < 20, f"{name} must stay a thin shim"


def test_wheel_config_ships_only_the_three_wheel_tiers():
    cfg = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8-sig"))
    assert cfg["project"]["scripts"]["qai-consultant-mcp"] == "qai_consultant.mcp.server:main"
    assert "py-modules" not in cfg["tool"]["setuptools"]
    blob = str(cfg["tool"]["setuptools"])
    for tier in TIERS:
        assert f"qai_consultant.{tier}" in blob, tier
    for app in APP_SUBPACKAGES:
        assert f"qai_consultant.{app}" not in blob, app
