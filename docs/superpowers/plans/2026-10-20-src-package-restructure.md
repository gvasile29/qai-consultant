# `src/` -> `qai_consultant` package Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the 40 flat modules in `src/` into the `qai_consultant` package, grouped by dependency tier and feature, with no behaviour change.

**Architecture:** One scripted pass (`git mv` + AST-based import rewrite + targeted string rewrites) moves modules into `src/qai_consultant/{common,core,mcp,rag,generation,compliance,ui,observability}/`. `src/app.py` stays a real Streamlit script; `cli.py`, `ingest.py`, `mcp_server.py` become thin shims in `src/`. The wheel ships only `common`, `core`, `mcp`, and a new test enforces that those three never import the app side.

**Tech Stack:** Python 3.11, setuptools (pyproject), pytest, ruff, mypy, bandit, Streamlit, FastMCP.

**Spec:** `docs/superpowers/specs/2026-10-20-src-package-restructure-design.md`

## Global Constraints

- Wheel tiers, dependency direction `common` <- `core` <- `mcp`; app-side tiers may import wheel tiers, never the reverse.
- Package name `qai_consultant`; `qai_consultant/__init__.py` is empty (no imports).
- Console script: `qai-consultant-mcp = "qai_consultant.mcp.server:main"`.
- `src/app.py` stays at its path and stays a real script (not a shim).
- `server.main()` keeps calling `index.warmup_embedder()` before `mcp.run()` (moved verbatim).
- Absolute imports everywhere; no relative imports.
- Test count after the move must equal the count before (baseline 1025 on `master` at the time of writing; re-measure in Task 1 and use that number).
- No dependency changes; `[project] dependencies` untouched (exact-pin test keeps passing).
- Historical docs (`docs/plans`, `docs/postmortems`, older `docs/superpowers/*`, CHANGELOG entries) are not rewritten.
- No Claude attribution in commits or the PR (user rule).
- Files may carry a UTF-8 BOM and CRLF endings; every rewrite must preserve both.

## Review Focus

- **Stale string patch targets** (`patch("agent.X")`, `patch("telemetry.X")`, `patch("local_index.X")`; 45 today) keep importing nothing at collection time and fail only at runtime or, worse, patch a dead name. Pinned by the legacy-reference guard test in Task 1.
- **Wheel imports an app-side module** (e.g. someone adds `from qai_consultant.rag import agent` in `core/`). Pinned by the tier-order test in Task 1.
- **`import mcp` resolves to our subpackage instead of the SDK.** Pinned by the SDK-resolution test in Task 1.
- **Importing `qai_consultant` pulls in heavy modules** (non-empty `__init__.py`). Pinned by the empty-`__init__` test in Task 1.
- **`src/app.py` turned into a shim** (UI freezes after first render). Pinned by a size/content guard in Task 1 and by the live Streamlit run in Task 5.
- **Files with BOM/CRLF rewritten to LF/no-BOM** (noisy diffs, and BOM files break `ast.parse` if read naively). Pinned by the rewriter's own self-test in Task 2.

---

## Pre-flight (do once, before Task 1)

- [ ] **Step 1: Confirm the tests restructure is merged**

Run: `git fetch origin && git log origin/master --oneline -5 | grep -i "group tests by level"`
Expected: one matching line. If empty, stop: this plan depends on `tests/<level>/<feature>/` existing.

- [ ] **Step 2: Branch from master**

```bash
git checkout -q master && git pull -q --ff-only origin master
git checkout -q -b chore/restructure-src
git cherry-pick 760ca9d   # the spec; skip if the spec is already on master
```

- [ ] **Step 3: Record the baseline**

Run: `python -m pytest tests/ -q -p no:cacheprovider 2>&1 | grep -E "passed|failed|error" | tail -2`
Expected: `N passed` with no failures. Write N down; every later gate compares against it.

---

### Task 1: Write the enforcement tests (red)

**Files:**
- Create: `tests/system/release/test_package_layout.py`

**Interfaces:**
- Produces: tests that fail until Tasks 3-4 land; they define the target layout (`TIERS`, `APP_SUBPACKAGES`) used by every later task.

- [ ] **Step 1: Write the tests**

```python
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
```

- [ ] **Step 2: Run it and confirm it fails for the right reason**

Run: `python -m pytest tests/system/release/test_package_layout.py -q -p no:cacheprovider 2>&1 | tail -15`
Expected: FAIL (`missing subpackage common`, `ModuleNotFoundError: qai_consultant`, `src/cli.py` has no `qai_consultant.cli`). Not an import error in the test file itself.

- [ ] **Step 3: Commit**

```bash
git add tests/system/release/test_package_layout.py
git commit -m "test: add failing layout and import-tier guards for the qai_consultant package"
```

---

### Task 2: Build and self-test the rewriter

**Files:**
- Create: `scripts/_restructure_src.py` (one-off; deleted in Task 6, never merged)
- Test: run its `--selftest`

**Interfaces:**
- Produces: `MAP: dict[str, tuple[str, str]]` (old module -> (subpackage, new leaf)), `dotted(mod) -> str`, `rewrite_text(text) -> str` (imports + patch strings + path refs), CLI `python scripts/_restructure_src.py [--selftest|--apply]`.

- [ ] **Step 1: Write the script**

```python
"""One-off migration (spec 2026-10-20): flat src/ modules -> qai_consultant package.

    python scripts/_restructure_src.py --selftest   # pure-function checks, no file changes
    python scripts/_restructure_src.py --apply      # git mv + rewrite src/tests/evals/scripts
"""
import ast
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path.cwd()
PKG = "qai_consultant"

MAP: dict[str, tuple[str, str]] = {}
for sub, mods in {
    "common": "version logger kb_config telemetry text_checks",
    "core": "dialogue effort_core review_core results_core maturity_core risk_ledger",
    "mcp": "prompts local_index",
    "rag": "agent ingest",
    "generation": "risk_analyzer strategy_generator test_plan_generator effort_estimator "
                  "review_generator maturity_generator doc_bundle templates executive_readout",
    "compliance": "output_guards ai_disclosure pdf_export source_labels",
    "ui": "components theme _theme_fonts kb_manifest",
    "observability": "usage_guard visit_counter adoption_metrics",
}.items():
    for m in mods.split():
        MAP[m] = (sub, m)
MAP["mcp_server"] = ("mcp", "server")
MAP["cli"] = ("", "cli")  # lives at qai_consultant/cli.py


def pkg_of(mod: str) -> str:
    sub, _ = MAP[mod]
    return f"{PKG}.{sub}" if sub else PKG


def dotted(mod: str) -> str:
    return f"{pkg_of(mod)}.{MAP[mod][1]}"


def new_path(mod: str) -> Path:
    sub, leaf = MAP[mod]
    return ROOT / "src" / PKG / sub / f"{leaf}.py" if sub else ROOT / "src" / PKG / f"{leaf}.py"


def rewrite_imports(text: str) -> str:
    bom = text.startswith("﻿")
    body = text[1:] if bom else text
    tree = ast.parse(body)
    nl = "\r\n" if "\r\n" in body else "\n"
    lines = body.splitlines(keepends=True)
    starts = [0]
    for ln in lines:
        starts.append(starts[-1] + len(ln))

    def off(lineno: int, col: int) -> int:  # ast col_offset is UTF-8 bytes
        return starts[lineno - 1] + len(lines[lineno - 1].encode()[:col].decode())

    edits = []
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom) and n.level == 0 and n.module in MAP:
            a, b = off(n.lineno, n.col_offset), off(n.end_lineno, n.end_col_offset)
            seg = body[a:b]
            new = re.sub(r"^from\s+" + re.escape(n.module) + r"\b", f"from {dotted(n.module)}", seg, count=1)
            edits.append((a, b, new))
        elif isinstance(n, ast.Import) and any(al.name in MAP for al in n.names):
            a, b = off(n.lineno, n.col_offset), off(n.end_lineno, n.end_col_offset)
            indent = lines[n.lineno - 1][: n.col_offset]
            out = []
            for al in n.names:
                if al.name in MAP:
                    leaf = MAP[al.name][1]
                    bind = al.asname or al.name
                    out.append(f"from {pkg_of(al.name)} import {leaf}" + (f" as {bind}" if bind != leaf else ""))
                else:
                    out.append(f"import {al.name}" + (f" as {al.asname}" if al.asname else ""))
            edits.append((a, b, (nl + indent).join(out)))
    for a, b, new in sorted(edits, reverse=True):
        body = body[:a] + new + body[b:]
    return ("﻿" if bom else "") + body


_PATCH = re.compile(r"""(\bpatch(?:\.object)?\(\s*)(["'])(%s)(?=[.\"'])""" % "|".join(map(re.escape, MAP)))
_SRC_PATH = re.compile(r"\bsrc/(%s)\.py\b" % "|".join(map(re.escape, MAP)))
_SRC_JOIN = re.compile(r"""(["'])src\1\s*/\s*(["'])(%s)\.py\2""" % "|".join(map(re.escape, MAP)))


def rewrite_strings(text: str) -> str:
    text = _PATCH.sub(lambda m: f"{m.group(1)}{m.group(2)}{dotted(m.group(3))}", text)

    def path_repl(m):
        sub, leaf = MAP[m.group(1)]
        return f"src/{PKG}/{sub + '/' if sub else ''}{leaf}.py"

    text = _SRC_PATH.sub(path_repl, text)

    def join_repl(m):
        sub, leaf = MAP[m.group(3)]
        q = m.group(1)
        parts = [PKG] + ([sub] if sub else []) + [f"{leaf}.py"]
        return f"{q}src{q} / " + " / ".join(f"{q}{p}{q}" for p in parts)

    return _SRC_JOIN.sub(join_repl, text)


_SYSPATH = re.compile(r"^[ \t]*sys\.path\.insert\(0,[^\n]*\)[ \t]*\r?\n", re.M)


def rewrite_text(text: str, drop_syspath: bool = False) -> str:
    text = rewrite_strings(rewrite_imports(text))
    return _SYSPATH.sub("", text) if drop_syspath else text


def _selftest() -> None:
    src = (
        "﻿import sys\r\nfrom agent import QAIAgent\r\nimport mcp_server\r\n"
        "import dialogue as d, json\r\nfrom unittest.mock import patch\r\n"
        "def f():\r\n    from effort_core import x\r\n"
        "    with patch(\"agent.QAIAgent\"), patch.object(mcp_server, 'main'):\r\n        pass\r\n"
        "P = REPO / \"src\" / \"mcp_server.py\"\r\nQ = 'src/app.py src/ingest.py'\r\n"
    )
    out = rewrite_text(src)
    assert out.startswith("﻿"), "BOM lost"
    assert "\r\n" in out and "\n" not in out.replace("\r\n", ""), "CRLF lost"
    for needle in [
        "from qai_consultant.rag.agent import QAIAgent",
        "from qai_consultant.mcp import server as mcp_server",
        "from qai_consultant.core import dialogue as d\r\nimport json",
        "    from qai_consultant.core.effort_core import x",
        'patch("qai_consultant.rag.agent.QAIAgent")',
        "patch.object(mcp_server, 'main')",
        '"src" / "qai_consultant" / "mcp" / "server.py"',
        "src/app.py src/qai_consultant/rag/ingest.py",
    ]:
        assert needle in out, f"missing: {needle!r}\n{out}"
    ast.parse(out.lstrip("﻿"))
    print("selftest ok")


def apply() -> None:
    moves = [(ROOT / "src" / f"{m}.py", new_path(m)) for m in MAP]
    for old, new in moves:
        if not old.exists():
            sys.exit(f"missing {old}")
    (ROOT / "src" / PKG).mkdir(exist_ok=True)
    (ROOT / "src" / PKG / "__init__.py").write_bytes(b"")
    for sub in {s for s, _ in MAP.values() if s}:
        (ROOT / "src" / PKG / sub).mkdir(exist_ok=True)
        (ROOT / "src" / PKG / sub / "__init__.py").write_bytes(b"")
    for old, new in moves:
        subprocess.run(["git", "mv", str(old), str(new)], check=True)
    n = 0
    for base in ("src", "tests", "evals", "scripts"):
        for p in (ROOT / base).rglob("*.py"):
            if "__pycache__" in p.parts or p.name == "_restructure_src.py" or p.name == "test_package_layout.py":
                continue
            raw = p.read_bytes().decode("utf-8")
            new = rewrite_text(raw, drop_syspath=base in ("src", "tests"))
            if new != raw:
                p.write_bytes(new.encode("utf-8"))
                n += 1
    print(f"moved {len(moves)} modules, rewrote {n} files")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
    elif "--apply" in sys.argv:
        apply()
    else:
        sys.exit(__doc__)
```

- [ ] **Step 2: Run the self-test**

Run: `python scripts/_restructure_src.py --selftest`
Expected: `selftest ok`. If an assertion fails, fix the script (not the assertion) and rerun. This pins the BOM/CRLF review-focus item.

- [ ] **Step 3: Dry-check the module list against reality**

Run: `python - <<'EOF'
import sys; sys.argv=["x"]; sys.path.insert(0,"scripts")
import _restructure_src as r
from pathlib import Path
have={p.stem for p in Path("src").glob("*.py")}
print("unmapped:", sorted(have - set(r.MAP) - {"app"}))
print("mapped but missing:", sorted(set(r.MAP) - have))
EOF`
Expected: both lists empty. Anything unmapped means a module was added since the spec; add it to `MAP` in the matching tier before continuing (and to the spec table).

(Not committed: this script is working scaffolding, removed in Task 6.)

---

### Task 3: Apply the move and get the suite green

**Files:**
- Modify: everything under `src/`, `tests/`, `evals/`, `scripts/` the script touches
- Create: `src/qai_consultant/**/__init__.py` (empty)
- Modify: `pyproject.toml` (`[tool.pytest.ini_options]` gets `pythonpath`)

**Interfaces:**
- Consumes: `scripts/_restructure_src.py --apply` from Task 2.
- Produces: the importable `qai_consultant` package; `src/app.py` importing from it.

- [ ] **Step 1: Make sure the tree is clean and the stale build output is gone**

```bash
git status --short            # expect empty
rm -rf build dist src/qai_consultant_mcp.egg-info
```

- [ ] **Step 2: Apply the script**

Run: `python scripts/_restructure_src.py --apply`
Expected: `moved 37 modules, rewrote <~120> files` (the number of files is informational; the module count must equal the length of `MAP`).

- [ ] **Step 3: Let pytest find the package without `sys.path` hacks**

In `pyproject.toml`, under `[tool.pytest.ini_options]`, add `pythonpath = ["src"]` directly below `testpaths = ["tests"]`.

- [ ] **Step 4: Fix what the regexes cannot know**

Run each, and fix every hit by hand in the file named:

```bash
# bare src-relative path pieces the join regex did not catch
grep -rnE "(SRC|SRC_DIR|src_dir)\s*/\s*[\"'][a-z_]+\.py[\"']" tests evals scripts src
# stub modules installed under legacy names (evals/estimate_integrity.py lines ~36-50, ~225-243)
grep -rnE "sys\.modules\[[\"'][a-z_]+[\"']\]|sys\.modules\.(get|pop)\(" evals tests scripts
# files that exec/loads a source file by path
grep -rnE "spec_from_file_location|runpy|exec\(compile" tests evals scripts
```

Rules for the manual edits:
- `sys.modules["agent"] = stub` becomes `sys.modules["qai_consultant.rag.agent"] = stub` (same for `.get`/`.pop`), and the stub must also be set as the `agent` attribute on `sys.modules["qai_consultant.rag"]` if the importer does `from qai_consultant.rag import agent`.
- In `tests/unit/estimation/test_effort_core.py` the keyless check lists forbidden module names (`agent`, ...) to assert absent from `sys.modules`; change them to `qai_consultant.rag.agent` etc., and add `qai_consultant.generation`, `qai_consultant.rag`, `qai_consultant.ui`.
- `tests/unit/observability/test_adoption_metrics.py:161` loads `scripts/usage_report.py` by path: unchanged, but check `scripts/usage_report.py` still imports correctly (its own bootstrap keeps one `sys.path.insert(0, <repo>/src)`; see Task 5 Step 2 about scripts/evals).

- [ ] **Step 5: Re-add the one allowed bootstrap line to scripts and evals**

`scripts/*.py` and `evals/__init__.py` are run as `python scripts/x.py` / `python -m evals.run` with no install, so `qai_consultant` is only importable if `src/` is on the path. The script kept their `sys.path.insert` lines (it only drops them from `src/` and `tests/`). Confirm: `grep -rn "sys.path.insert" scripts evals` shows exactly the existing bootstrap lines and each still points at `src`.

- [ ] **Step 6: Fix imports that ruff flags after the rewrite, then lint**

Run: `ruff check src/ tests/ --fix && ruff check src/ tests/`
Expected: `All checks passed!` (the `--fix` removes `import sys` left unused after the `sys.path` removal). If `E402` appears in `src/app.py`, move the offending import above the code that triggered it; do not add `noqa`.

- [ ] **Step 7: Run the fast levels first**

Run: `python -m pytest tests/unit -q -p no:cacheprovider -x 2>&1 | tail -15`
Expected: all pass. A failure here is almost always a missed string target; fix it in the test (not in `src`) and rerun. Then `python -m pytest tests/integration tests/e2e -q -p no:cacheprovider 2>&1 | tail -8`.

- [ ] **Step 8: Run the system level (Streamlit AppTest, CLI, MCP)**

Run: `python -m pytest tests/system -q -p no:cacheprovider --deselect tests/system/release/test_package_layout.py 2>&1 | tail -15`
Expected: pass except possibly `tests/system/release/test_packaging.py` (fixed in Task 4) and `test_skill_doc.py` if its path rewrite needs a hand check (it parses `min_score` from the moved `server.py`; confirm it now reads `src/qai_consultant/mcp/server.py`).

- [ ] **Step 9: Commit (shims and packaging land in Task 4, so this commit is intermediate)**

```bash
git add -A
git commit -m "refactor: move src modules into the qai_consultant package"
```

---

### Task 4: Shims, packaging and the green layout guards

**Files:**
- Create: `src/cli.py`, `src/ingest.py`, `src/mcp_server.py` (shims; the real files already moved)
- Modify: `pyproject.toml` (`[tool.setuptools]`, scripts entry point), `tests/system/release/test_packaging.py`

**Interfaces:**
- Consumes: `qai_consultant.cli.main`, `qai_consultant.rag.ingest.main`, `qai_consultant.mcp.server.main`.
- Produces: unchanged documented commands; a wheel containing only the three wheel tiers plus `knowledge_base`.

- [ ] **Step 1: Confirm each moved module exposes `main`**

Run: `grep -nE "^def main|^if __name__" src/qai_consultant/cli.py src/qai_consultant/rag/ingest.py src/qai_consultant/mcp/server.py`
Expected: a `def main` in each. If `ingest.py` or `cli.py` runs its logic at module level or under `if __name__ == "__main__":` with inline code instead of `main()`, wrap that block in `def main(): ...` first (a pure refactor; keep the `__main__` guard calling it).

- [ ] **Step 2: Write the three shims** (identical shape; replace the import line for each)

`src/mcp_server.py`:
```python
"""Shim so `python src/mcp_server.py` keeps working; real code: qai_consultant.mcp.server."""
from qai_consultant.mcp.server import main

if __name__ == "__main__":
    main()
```
`src/cli.py` imports `from qai_consultant.cli import main`; `src/ingest.py` imports `from qai_consultant.rag.ingest import main`. Same docstring pattern naming the target module.

- [ ] **Step 3: Switch packaging**

In `pyproject.toml` replace the `py-modules` block and its comment header ("setuptools: flat modules from src/...") with:

```toml
# ── setuptools: the qai_consultant package (wheel tiers only) + knowledge_base ──
# common/core/mcp are the keyless tiers that ship to PyPI; rag/generation/
# compliance/ui/observability are app-side and must never be in the wheel
# (tests/system/release/test_package_layout.py enforces the import direction).
[tool.setuptools]
include-package-data = true
```

and change the existing find block to search both roots:

```toml
[tool.setuptools.packages.find]
where = [".", "src"]
include = [
    "knowledge_base*",
    "qai_consultant", "qai_consultant.common*", "qai_consultant.core*", "qai_consultant.mcp*",
]
namespaces = true
```

Keep `[tool.setuptools.package-dir]` as is. Change `[project.scripts]` to `qai-consultant-mcp = "qai_consultant.mcp.server:main"`.

Verify with a real build (this is the one spot the spec flags as uncertain, so the build decides):

```bash
rm -rf build dist && python -m build --wheel -q && python - <<'EOF'
import zipfile, glob
names = zipfile.ZipFile(glob.glob("dist/*.whl")[0]).namelist()
pk = sorted({n.split("/")[1] for n in names if n.startswith("qai_consultant/") and n.count("/") >= 2})
print("subpackages:", pk)
print("app-side leaked:", [n for n in names if any(f"qai_consultant/{a}/" in n for a in ("rag","generation","compliance","ui","observability"))])
print("knowledge_base files:", sum(n.startswith("knowledge_base/") for n in names))
EOF
```
Expected: `subpackages: ['common', 'core', 'mcp']`, `app-side leaked: []`, `knowledge_base files:` the same count as the current release's wheel (compare with `python -m build` on `master` if unsure).

Fallback if `where = [".", "src"]` produces a wrong or empty `qai_consultant` (setuptools ignores `package-dir` for multi-root find): drop `where`/`include` from the find block and list packages explicitly:

```toml
[tool.setuptools]
packages = ["qai_consultant", "qai_consultant.common", "qai_consultant.core", "qai_consultant.mcp"]

[tool.setuptools.package-dir]
"qai_consultant" = "src/qai_consultant"
```
and give `knowledge_base` the same explicit treatment (listing its sub-packages from `find knowledge_base -name '*.md' -printf '%h\n' | sort -u`), then re-run the build check above. Use whichever passes; delete the other from the file.

- [ ] **Step 4: Update the packaging test**

In `tests/system/release/test_packaging.py`: replace the expected flat module list (around line 26, names like `"mcp_server.py"`) with the expected package files (`qai_consultant/mcp/server.py`, `qai_consultant/core/dialogue.py`, ...), keep the assertion that none of the app-side modules (`agent.py`, `app.py`, `strategy_generator.py`, ...) are present but match them as `qai_consultant/<tier>/...` paths, and change the entry-point assertion (line ~194) to `qai-consultant-mcp = qai_consultant.mcp.server:main`.

- [ ] **Step 5: Run the new guards and the packaging tests**

Run: `python -m pytest tests/system/release -q -p no:cacheprovider 2>&1 | tail -15`
Expected: everything passes, including all of `test_package_layout.py`. This is the red-to-green moment for Task 1's tests.

- [ ] **Step 6: Prove the shims run**

```bash
python src/cli.py --help 2>&1 | head -5
python -c "import runpy,sys; sys.argv=['src/ingest.py','--help']; runpy.run_path('src/ingest.py', run_name='__main__')" 2>&1 | head -5
python scripts/verify_mcp_stdio_no_deadlock.py 2>&1 | tail -5
```
Expected: usage text for the first two (if `ingest.py` has no `--help`, a clean start-up message without a traceback is enough; it must not touch Pinecone, so do not run it without arguments), and the deadlock script's success line.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "build: ship common/core/mcp as the qai_consultant package and add src shims"
```

---

### Task 5: References, docs and the full gate

**Files:**
- Modify: `.github/workflows/*.yml`, `.claude/skills/**`, `.claude/agents/mcp-surface-reviewer.md`, `CLAUDE.md`, `INSTALL.md`, `CONTRIBUTING.md`, `README*.md`, `CHANGELOG.md`, `docs/superpowers/specs/2026-10-20-src-package-restructure-design.md`, `scripts/mcp_release_check.py`, `scripts/regenerate_mcp_lock.py`

**Interfaces:**
- Consumes: the final module paths from Task 3.

- [ ] **Step 1: Find every remaining mention of an old module path**

Run:
```bash
grep -rnE "src/(version|logger|kb_config|telemetry|text_checks|dialogue|effort_core|review_core|results_core|maturity_core|risk_ledger|prompts|local_index|agent|risk_analyzer|strategy_generator|test_plan_generator|effort_estimator|review_generator|maturity_generator|doc_bundle|templates|executive_readout|output_guards|ai_disclosure|pdf_export|source_labels|components|theme|_theme_fonts|kb_manifest|usage_guard|visit_counter|adoption_metrics)\.py" \
  --include=*.md --include=*.yml --include=*.json --include=*.toml --include=*.sh --include=*.py . \
  | grep -vE "^\./(build|dist|docs/plans|docs/postmortems|docs/superpowers/(specs|plans)/20(26-0|26-10-(0|1))|CHANGELOG|\.remember|output)"
```
Update each hit to the new path. In `CLAUDE.md` this includes the Source Files table (rename the first column to the new relative paths and add a short "Package layout" paragraph with the tier table from the spec), the "Key Configuration" note about `src/agent.py`, and the MCP lens note about the import graph. The documented commands (`streamlit run src/app.py`, `python src/cli.py`, `python src/ingest.py`, `python src/mcp_server.py`) stay as they are.

- [ ] **Step 2: Reconcile the spec with what was built**

In the spec, change success criterion 4 and migration step 4 to: no `sys.path` manipulation in `src/` or `tests/`; `scripts/` and `evals/` keep a single one-line bootstrap pointing at `src/` because they run without an install. Record the final `packages.find` form chosen in Task 4.

- [ ] **Step 3: Update the keyless-graph reviewer and CI references**

- `.claude/agents/mcp-surface-reviewer.md`: replace the manual "keyless import graph" walk with "run `pytest tests/system/release/test_package_layout.py`" plus the list of wheel tiers.
- `.github/workflows/ci.yml`: no path changes needed (`ruff check src/ tests/`, `mypy src/`, `bandit -r src/ -ll`, `--cov=src` all still apply); confirm `mypy src/` resolves the package (add `mypy_path = "src"` and `explicit_package_bases = true` under `[tool.mypy]` only if mypy reports duplicate-module errors).
- `.github/workflows/live-contract-tests.yml` already points at the new e2e path from the tests restructure.

- [ ] **Step 4: CHANGELOG entry (unreleased)**

Add an entry at the top of `CHANGELOG.md` under a new `## [Unreleased]` heading (the version bump belongs to the release PR) with bullets: package layout, new import-tier guard, console-script entry point change, `src/` shims, and "no behaviour change".

- [ ] **Step 5: Full gate**

```bash
ruff check src/ tests/
mypy src/
bandit -r src/ -ll -q
bash .claude/skills/claude-md-hygiene/check.sh
python -m pytest tests/ -q -p no:warnings -p no:cacheprovider --cov=src --cov-fail-under=60 2>&1 | grep -E "passed|failed|error|Required" | tail -4
```
Expected: all clean; `N+<new tests> passed` where the delta over the Task 0 baseline is exactly the number of tests in `test_package_layout.py` (8). If the delta differs, something was lost or duplicated: stop and diff the collected test ids against the baseline (`pytest --collect-only -q` before/after).

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "docs: update paths, docs and reviewer rules for the qai_consultant package"
```

---

### Task 6: Verify on the real surfaces and clean up

**Files:**
- Delete: `scripts/_restructure_src.py`

**Interfaces:**
- Consumes: everything above. Produces the evidence for the PR's `## Verified` section.

- [ ] **Step 1: Wheel in a clean venv, real stdio session**

```bash
rm -rf build dist && python -m build --wheel -q
python -m venv "$TEMP/v" && "$TEMP/v/Scripts/python" -m pip install -q dist/*.whl
cd "$TEMP" && "$TEMP/v/Scripts/qai-consultant-mcp" --help 2>&1 | head -3; cd -
```
Then drive it over stdio with the repo's existing client helper (`scripts/mcp_release_check.py` documents the call shape): list tools, call `estimate_qa_effort` and `retrieve_qa_knowledge`. Expected: 6 tools listed, both calls return results, no import errors. Record the outputs.

- [ ] **Step 2: The path real users take**

Run from an empty directory: `cd "$TEMP/empty" && time uvx --from "<abs path to dist/*.whl>" qai-consultant-mcp --help`
Expected: starts without resolution errors; note the wall time next to the same command for the currently published release (`uvx qai-consultant-mcp==<current>`) and confirm there is no meaningful regression.

- [ ] **Step 3: Release preflight**

Run: `python scripts/mcp_release_check.py --preflight`
Expected: pass. (This checks version sync, entry point, and wheel contents; if it hard-codes the old `py-modules` or entry-point string, update the script and rerun.)

- [ ] **Step 4: Streamlit, live**

Follow the `browser-ui-testing` skill: `streamlit run src/app.py`, load the landing page, start a dialogue, advance two questions, confirm no traceback and that typed input survives a rerun. Then run the `llm-e2e-smoke` skill for one full Risk/Effort/Strategy/Plan generation and read the saved `output/*.md`.
Expected: app renders and a document is produced. This pins the "app.py must remain a real script" review-focus item.

- [ ] **Step 5: CLI modes on repo fixtures**

```bash
python src/cli.py --review evals/fixtures/review/<a strong fixture>.md
python src/cli.py --results evals/fixtures/results/<a junit fixture>.xml
python src/cli.py --maturity evals/fixtures/maturity/<a description fixture>.txt
```
Use real filenames from `ls evals/fixtures/*/`. Expected: each prints a report without traceback (LLM-narrative sections may fall back if keys are absent; the deterministic scores must print).

- [ ] **Step 6: Remove the scaffolding and commit**

```bash
git rm -q --cached scripts/_restructure_src.py 2>/dev/null; rm -f scripts/_restructure_src.py
git status --short   # expect nothing about the script
```
If the script was never `git add`ed (Task 2 left it untracked and Task 3's `git add -A` may have included it), confirm with `git log --stat -3 | grep _restructure`; if it is in history, add a `git rm` commit: `git commit -m "chore: drop one-off restructure script"`.

---

### Task 7: Ship

- [ ] **Step 1:** Invoke the `ship-pr` skill. Its fresh-context reviewer must be told this is a pure move: the questions to ask are "did any behaviour change", "can a wheel module now import an app module", and "is any documented command broken".
- [ ] **Step 2:** The PR body (via `writing-pr`) carries the Task 6 evidence under `## Verified`, and states that the release (version bump, PyPI publish, registry sync) is a follow-up PR following the `release-checklist` skill.
- [ ] **Step 3:** After merge, watch the Streamlit Cloud deploy for the known stale-code lag; if the app serves old code after 10 minutes, push a trivial commit to the tracked branch to force a fresh clone (see CLAUDE.md Gotchas).
