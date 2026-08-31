"""
Tests for pyproject.toml — the qai-consultant-mcp package's licensing gate
and packaging shape (v3.0 step 8).

Builds the actual wheel (once per test session, via a module-scoped
fixture) and inspects its real contents — this IS the licensing gate from
MCP_PLAN.md section 5: the ISTQB/OWASP PDFs (and the OWASP Top10 HTML
duplicate) must never reach the distributed package regardless of
whatever the pyproject.toml config *looks* like it should do. A fresh-venv
install + real stdio smoke test (uvx-style) is done manually — see the
step 8 commit message — since it needs network + ~1-2 minutes to pull
torch/sentence-transformers, too slow for every CI run.
"""

import re
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

_EXPECTED_PY_MODULES = {
    "mcp_server.py", "dialogue.py", "effort_core.py", "local_index.py",
    "telemetry.py", "prompts.py", "kb_config.py", "logger.py", "version.py",
    "review_core.py", "results_core.py",
}

# Must match pyproject.toml's [tool.setuptools.package-data] whitelist exactly —
# any folder NOT listed here must not ship, even if it only contains .md files
# (e.g. a hypothetical future notes/ folder someone adds without updating either
# this test or pyproject.toml should fail loudly, not ship silently).
_WHITELISTED_MD_FOLDERS = [
    "knowledge_base",
    "knowledge_base/methodologies",
    "knowledge_base/evaluation_audit",
    "knowledge_base/expert_knowledge",
    "knowledge_base/articles",
    "knowledge_base/articles/ai_sdlc",
    "knowledge_base/standards",
    "knowledge_base/standards/eu_ai_act",
    "knowledge_base/standards/owasp",
]

# Folders that exist under knowledge_base/ but must NEVER ship (PDFs, HTML, or
# not meant for redistribution) — asserted absent explicitly, not just "not in
# the whitelist above", so a rename doesn't silently stop testing for them.
_FORBIDDEN_PATH_FRAGMENTS = ["standards/istqb/", "generated_strategies/"]


def test_all_dependencies_are_exact_pinned():
    """
    Every entry in [project] dependencies must be exact-pinned (`==`).

    A loose bound (`>=`, `~=`, or a bare name) lets `uv` re-resolve to a
    newer upstream release between two `uvx qai-consultant-mcp` launches,
    even when the user hasn't changed anything on their end. That forces
    a full ~88-package reinstall (~26-30s) on top of the already-known
    ~20-25s sentence-transformers/torch import cost, which can push the
    total past Claude Desktop's ~60s `initialize` timeout and cause a
    silent attach failure. See the MCP dependency-pinning gotcha in
    CLAUDE.md for the incident this guards against.

    Since v3.4.4 the list is a full transitive lock (~99 entries, generated
    via `uv pip compile --universal`), not just the 6 direct imports -- a
    2026-08-31 incident showed an unpinned *transitive* dep (scipy, pulled
    in by scikit-learn) can reintroduce the exact same failure even with
    every direct dependency exact-pinned. A trailing PEP 508 environment
    marker (`; python_full_version < '3.11'` etc.) is allowed after the
    `==` pin -- some transitive deps genuinely need a different exact
    version per Python version/platform (e.g. numpy/scipy/scikit-learn each
    appear 2-3 times, once per supported Python minor version) -- but the
    version itself must still be an exact `==` pin, never a range.

    Parsed as plain text/regex, not a TOML library, since CI's Python
    3.10 matrix entry has no stdlib `tomllib` and this repo doesn't
    otherwise depend on a TOML parser.
    """
    pyproject_text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r"dependencies\s*=\s*\[(.*?)\]", pyproject_text, re.DOTALL)
    assert match, "Could not find a [project] dependencies list in pyproject.toml"

    entries = [
        line.strip().rstrip(",").strip('"').strip("'")
        for line in match.group(1).splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    assert entries, "Parsed dependencies list from pyproject.toml is empty"

    pin_pattern = re.compile(r"^[A-Za-z0-9_.-]+==[\w.+]+(\s*;\s*.+)?$")
    unpinned = [entry for entry in entries if not pin_pattern.match(entry)]
    assert not unpinned, (
        f"These dependencies are not exact-pinned with '==': {unpinned}. "
        "A loose bound lets uv re-resolve on an unrelated upstream release "
        "and reinstall everything on the next launch -- see CLAUDE.md's "
        "MCP dependency-pinning gotcha."
    )
    print(f"  PASS: all {len(entries)} dependencies are exact-pinned")


@pytest.fixture(scope="module")
def built_wheel(tmp_path_factory) -> Path:
    out_dir = tmp_path_factory.mktemp("qai_mcp_dist")
    result = subprocess.run(
        [sys.executable, "-m", "build", "--wheel", "--no-isolation", "--outdir", str(out_dir)],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=180,
    )
    assert result.returncode == 0, (
        f"Building the wheel failed.\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    wheels = list(out_dir.glob("*.whl"))
    assert len(wheels) == 1, f"Expected exactly one built wheel, found: {wheels}"
    return wheels[0]


@pytest.fixture(scope="module")
def wheel_namelist(built_wheel) -> list[str]:
    with zipfile.ZipFile(built_wheel) as z:
        return z.namelist()


def test_wheel_contains_zero_pdf_files(wheel_namelist):
    pdfs = [n for n in wheel_namelist if n.lower().endswith(".pdf")]
    assert pdfs == [], f"Wheel must ship zero PDFs (licensing gate): found {pdfs}"


def test_wheel_contains_zero_html_files(wheel_namelist):
    htmls = [n for n in wheel_namelist if n.lower().endswith(".html")]
    assert htmls == [], f"Wheel must not ship the OWASP Top10 HTML duplicate: found {htmls}"


def test_wheel_excludes_forbidden_paths(wheel_namelist):
    for fragment in _FORBIDDEN_PATH_FRAGMENTS:
        matches = [n for n in wheel_namelist if fragment in n]
        assert matches == [], f"Wheel must not contain anything under '{fragment}': {matches}"


def test_wheel_contains_expected_py_modules(wheel_namelist):
    found = {n for n in wheel_namelist if n.endswith(".py") and "/" not in n}
    assert found == _EXPECTED_PY_MODULES


def test_wheel_does_not_ship_agent_or_app_modules(wheel_namelist):
    """The MCP path must never ship agent.py, ingest.py, app.py, cli.py,
    effort_estimator.py, risk_analyzer.py, strategy_generator.py,
    test_plan_generator.py, or ai_disclosure.py — none are in its import
    graph (see mcp_server.py's docstring), and shipping them would be dead
    weight plus a licensing/dependency-drag surprise (they import Pinecone/
    Mistral/OpenAI/Streamlit)."""
    forbidden = {
        "agent.py", "ingest.py", "app.py", "cli.py",
        "effort_estimator.py", "risk_analyzer.py",
        "strategy_generator.py", "test_plan_generator.py", "ai_disclosure.py",
    }
    found = {n for n in wheel_namelist if n.endswith(".py") and "/" not in n}
    overlap = found & forbidden
    assert overlap == set(), f"Wheel must not ship: {overlap}"


def test_wheel_md_files_match_repo_whitelist_exactly(wheel_namelist):
    """Every .md file under the whitelisted folders (non-recursive per
    folder — each nested folder must be separately whitelisted) must be in
    the wheel, and nothing else .md-shaped should be."""
    expected: set[str] = set()
    for folder in _WHITELISTED_MD_FOLDERS:
        for md_path in (REPO_ROOT / folder).glob("*.md"):
            expected.add(f"{folder}/{md_path.name}")

    found = {n for n in wheel_namelist if n.startswith("knowledge_base/") and n.endswith(".md")}
    assert found == expected


def test_wheel_md_file_count_is_nonzero(wheel_namelist):
    md_files = [n for n in wheel_namelist if n.startswith("knowledge_base/") and n.endswith(".md")]
    assert len(md_files) > 0, "The wheel must ship at least some KB content"


def test_entry_point_resolves_to_mcp_server_main(wheel_namelist):
    dist_info_entries = [n for n in wheel_namelist if n.endswith("entry_points.txt")]
    assert len(dist_info_entries) == 1


def test_entry_point_content(built_wheel):
    with zipfile.ZipFile(built_wheel) as z:
        entry_points_file = next(n for n in z.namelist() if n.endswith("entry_points.txt"))
        content = z.read(entry_points_file).decode("utf-8")
    assert "qai-consultant-mcp = mcp_server:main" in content
