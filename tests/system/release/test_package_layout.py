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


def _package_parts(path: Path, pkg_root: Path = PKG) -> list[str]:
    """Dotted package a module lives in, e.g. src/qai_consultant/core/x.py -> [qai_consultant, core]."""
    rel = path.relative_to(pkg_root.parent).with_suffix("")
    return list(rel.parts[:-1])


def _imports(path: Path, pkg_root: Path = PKG):
    """Yield (top_level_name, dotted_name) for every import, lazy ones included.

    Covers absolute and relative `from` imports (resolved against the module's
    own package), `from qai_consultant import rag` (alias as next segment), and
    importlib.import_module("...") / __import__("...") with a literal argument.
    """
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    pkg = _package_parts(path, pkg_root)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                yield a.name.split(".")[0], a.name
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = pkg[: len(pkg) - (node.level - 1)]
                resolved = ".".join(base + (node.module.split(".") if node.module else []))
            else:
                resolved = node.module or ""
            if not resolved:
                continue
            yield resolved.split(".")[0], resolved
            for a in node.names:
                yield resolved.split(".")[0], f"{resolved}.{a.name}"
        elif isinstance(node, ast.Call) and node.args:
            fn = node.func
            name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", None)
            arg = node.args[0]
            if name in {"import_module", "__import__"} and isinstance(arg, ast.Constant)                     and isinstance(arg.value, str):
                yield arg.value.split(".")[0], arg.value


def _tier_offenders(tier: str, path: Path, pkg_root: Path = PKG) -> list[str]:
    offenders = []
    label = path.relative_to(pkg_root.parent)
    for top, dotted in _imports(path, pkg_root):
        if top in FORBIDDEN_TOP_LEVEL:
            offenders.append(f"{label}: forbidden dependency {dotted}")
        if top == "qai_consultant":
            parts = dotted.split(".")
            target = parts[1] if len(parts) > 1 else None
            if target in APP_SUBPACKAGES or target in {"cli"}:
                offenders.append(f"{label}: imports app-side {dotted}")
            elif target in TIERS and TIERS[target] > TIERS[tier]:
                offenders.append(f"{label}: {tier} imports higher tier {dotted}")
        if top in LEGACY_NAMES:
            offenders.append(f"{label}: legacy flat import {dotted}")
    return offenders


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
        offenders += _tier_offenders(tier, path)
    assert not offenders, "\n".join(offenders)


def _scan_snippet(tmp_path: Path, tier: str, code: str) -> list[str]:
    pkg_root = tmp_path / "qai_consultant"
    mod = pkg_root / tier / "x.py"
    mod.parent.mkdir(parents=True)
    mod.write_text(code, encoding="utf-8")
    return _tier_offenders(tier, mod, pkg_root)


import pytest  # noqa: E402


@pytest.mark.parametrize("tier,code", [
    ("core", "from ..rag import agent\n"),
    ("core", "from ..rag.agent import QAIAgent\n"),
    ("common", "from ..core import dialogue\n"),
    ("core", "from qai_consultant import rag\n"),
    ("core", "from qai_consultant import generation as g\n"),
    ("common", "from .. import mcp\n"),
    ("core", "import importlib\nimportlib.import_module('qai_consultant.ui.theme')\n"),
    ("core", "__import__('qai_consultant.rag.agent')\n"),
    ("core", "import importlib\nimportlib.import_module('agent')\n"),
    ("core", "import importlib\nimportlib.import_module('streamlit')\n"),
])
def test_tier_scanner_catches_hidden_violations(tmp_path, tier, code):
    """Mutation proof: each blind spot is reported when a violating module exists."""
    assert _scan_snippet(tmp_path, tier, code), code


@pytest.mark.parametrize("tier,code", [
    ("mcp", "from ..core import dialogue\n"),
    ("mcp", "from qai_consultant import core\n"),
    ("core", "from . import effort_core\n"),
    ("core", "import importlib\nimportlib.import_module('json')\n"),
])
def test_tier_scanner_allows_legal_imports(tmp_path, tier, code):
    assert _scan_snippet(tmp_path, tier, code) == []


def test_importing_mcp_server_pulls_in_no_app_side_or_heavy_modules():
    """Runtime check complementing the static scan: a clean interpreter.

    `rich` is not in the list: the mcp SDK itself imports it, so it is always loaded;
    the static scan still bans a direct `import rich` from wheel modules."""
    import os
    import subprocess
    import sys

    # -I ignores PYTHONPATH and user site, so hand the interpreter the parent's
    # site-packages dirs explicitly (the isolation we care about is the module graph).
    site_dirs = [p for p in sys.path if "site-packages" in p]
    code = (
        f"import sys; sys.path.insert(0, {str(SRC)!r}); sys.path.extend({site_dirs!r}); import qai_consultant.mcp.server\n"
        "bad = [m for m in sys.modules if m.split('.')[0] in "
        "{'streamlit','pinecone','mistralai'} or m.startswith('langchain') "
        "or m.startswith(tuple('qai_consultant.'+t for t in "
        "('rag','generation','compliance','ui','observability','cli')))]\n"
        "print(bad); sys.exit(1 if bad else 0)\n"
    )
    env = {**os.environ, "PYTHONPATH": str(SRC), "QAI_TELEMETRY": "0"}
    r = subprocess.run([sys.executable, "-I", "-c", code], env=env,
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stdout + r.stderr


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
