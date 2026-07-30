# MCP Dependency Pinning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop `qai-consultant-mcp` from intermittently failing to attach in Claude Desktop by exact-pinning all 6 runtime dependencies in `pyproject.toml`, so `uvx` never re-resolves and reinstalls the ~88-package environment just because an unrelated upstream package published a new release.

**Architecture:** No runtime code changes. This is a packaging-metadata change (`pyproject.toml`'s `[project] dependencies`) plus a regression test that keeps it pinned, plus the standard version-bump release paperwork (v3.3.1).

**Tech Stack:** Python packaging (`pyproject.toml`, setuptools), `pytest` for the regression test — plain text/regex parsing, no new dependency (no `tomllib`/`tomli`, since CI's Python 3.10 matrix entry has no stdlib `tomllib`).

## Global Constraints

- Exact versions to pin (verified via `pip show` against the currently working dev environment): `mcp==1.28.1`, `langchain-community==0.4.2`, `sentence-transformers==2.7.0` (unchanged), `platformdirs==4.11.0`, `torch==2.13.0` (unchanged), `defusedxml==0.7.1`.
- No changes to `mcp_server.py`, `local_index.py`, or any other runtime module — spec explicitly scopes this to packaging only.
- Version bump target: **3.3.1** (patch release, current is 3.3.0).
- Publishing to PyPI and creating the git tag are explicit, user-triggered steps outside this plan — same pattern as v3.1.4/v3.1.5/v3.1.6. This plan's tasks end with a PR-ready branch, not a publish.
- Follow the repo's Release Checklist (`CLAUDE.md`): `version.py`, `pyproject.toml` version, `CHANGELOG.md`, `README.md` all move together. `README_MCP.md` is unchanged this time — no MCP tool-surface change, and grep confirms it doesn't reference the version number at all.

---

### Task 1: Add and satisfy the dependency-pinning regression test

**Files:**
- Modify: `tests/test_packaging.py` (add new test function + `import re`)
- Modify: `pyproject.toml:24-31` (the `dependencies = [...]` block)

**Interfaces:**
- Consumes: nothing from other tasks (first task).
- Produces: a passing `test_all_dependencies_are_exact_pinned` test that all later tasks (and future PRs) run against. No new functions/exports — this is a test + a data change.

- [ ] **Step 1: Write the failing test**

Add this to `tests/test_packaging.py`. Put it near the top-level test functions (after the existing `import` block, before or after the `built_wheel` fixture — it doesn't need that fixture, since it reads `pyproject.toml` directly, not the built wheel).

First, add `import re` to the existing import block at the top of the file (currently `import subprocess`, `import sys`, `import zipfile`, `from pathlib import Path`, `import pytest`) — add `import re` alongside them, keeping alphabetical stdlib-import order (`re` goes after `zipfile`... actually alphabetically `re` < `subprocess` < `sys` < `zipfile`, so insert it first):

```python
import re
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest
```

Then add the new test function anywhere at module level (e.g. right after the `_FORBIDDEN_PATH_FRAGMENTS` constant, before the `built_wheel` fixture):

```python
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

    pin_pattern = re.compile(r"^[A-Za-z0-9_.-]+==[\w.]+$")
    unpinned = [entry for entry in entries if not pin_pattern.match(entry)]
    assert not unpinned, (
        f"These dependencies are not exact-pinned with '==': {unpinned}. "
        "A loose bound lets uv re-resolve on an unrelated upstream release "
        "and reinstall everything on the next launch -- see CLAUDE.md's "
        "MCP dependency-pinning gotcha."
    )
    print(f"  PASS: all {len(entries)} dependencies are exact-pinned")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_packaging.py::test_all_dependencies_are_exact_pinned -v`

Expected: **FAIL**, with the assertion listing the 4 currently-unpinned entries:
`['mcp>=1.8.0,<2.0.0', 'langchain-community>=0.3.30', 'platformdirs>=4.0.0', 'defusedxml>=0.7.1']`

- [ ] **Step 3: Pin the dependencies in pyproject.toml**

Open `pyproject.toml` and replace the `dependencies = [...]` block (currently at lines 24-31):

```toml
dependencies = [
    "mcp>=1.8.0,<2.0.0",
    "langchain-community>=0.3.30",
    "sentence-transformers==2.7.0",
    "platformdirs>=4.0.0",
    "torch==2.13.0",
    "defusedxml>=0.7.1",
]
```

with:

```toml
dependencies = [
    "mcp==1.28.1",
    "langchain-community==0.4.2",
    "sentence-transformers==2.7.0",
    "platformdirs==4.11.0",
    "torch==2.13.0",
    "defusedxml==0.7.1",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_packaging.py::test_all_dependencies_are_exact_pinned -v`

Expected: **PASS** — `PASS: all 6 dependencies are exact-pinned`

- [ ] **Step 5: Run the full packaging test file to make sure nothing else broke**

Run: `python -m pytest tests/test_packaging.py -v`

Expected: all tests **PASS** (the wheel-building tests don't inspect dependency version strings, only the file/module shape, so they should be unaffected — but confirm).

- [ ] **Step 6: Commit**

```bash
git add tests/test_packaging.py pyproject.toml
git commit -m "fix: exact-pin all qai-consultant-mcp runtime dependencies

Loose bounds on mcp/langchain-community/platformdirs/defusedxml let uv
re-resolve and reinstall all ~88 packages whenever any of them (or a
transitive dependency) publishes a new PyPI release, regardless of
which qai-consultant-mcp version the user has pinned. Combined with the
~20-25s sentence-transformers/torch import cost, this could push
Claude Desktop attach past its ~60s initialize timeout. Exact-pinning
removes the re-resolution trigger."
```

---

### Task 2: Version bump to 3.3.1 (version.py, pyproject.toml, CHANGELOG.md)

**Files:**
- Modify: `src/version.py`
- Modify: `pyproject.toml:7` (`[project] version`)
- Modify: `CHANGELOG.md` (new top entry)

**Interfaces:**
- Consumes: nothing from Task 1's test/code changes directly, but must land after Task 1 so the CHANGELOG entry can accurately describe what shipped.
- Produces: a version state that `tests/test_changelog.py` validates (`test_pyproject_version_matches_version_py`, `test_changelog_top_version_matches_version_py`, `test_changelog_top_entry_has_content`).

- [ ] **Step 1: Update `src/version.py`**

Current content:
```python
__version__ = "3.3.0"
__release_date__ = "2026-07-29"
```

Change to:
```python
__version__ = "3.3.1"
__release_date__ = "2026-07-30"
```

(Leave `__author__`, `__description__`, `__license__` unchanged.)

- [ ] **Step 2: Update `pyproject.toml`'s version field**

Find `version = "3.3.0"` (line 7, in the `[project]` table) and change it to:
```toml
version = "3.3.1"
```

- [ ] **Step 3: Add a new CHANGELOG.md entry**

Insert this new section immediately after the `# Changelog` header block and its intro paragraph, immediately before the existing `## [3.3.0] - 2026-07-29` heading (i.e. as the new topmost version entry):

```markdown
## [3.3.1] - 2026-07-30

### Fixed
- `qai-consultant-mcp` could intermittently fail to attach in Claude
  Desktop even on a warm cache. Four of the package's six runtime
  dependencies (`mcp`, `langchain-community`, `platformdirs`,
  `defusedxml`) had loose version bounds instead of exact pins — when
  any of them (or the resolver's chosen version of a transitive
  dependency) published a new release on PyPI, `uvx` would re-resolve
  and reinstall the full ~88-package environment on the next launch,
  regardless of which `qai-consultant-mcp` version was pinned in a
  user's Claude Desktop config. That reinstall (~26-30s) combined with
  the already-known ~20-25s `sentence-transformers`/`torch` import cost
  could push past Claude Desktop's ~60s `initialize` timeout. All six
  runtime dependencies are now exact-pinned, and a new test
  (`test_all_dependencies_are_exact_pinned`) fails the build if a loose
  bound is reintroduced. Design rationale:
  `docs/superpowers/specs/2026-07-30-mcp-dependency-pinning-design.md`.
```

- [ ] **Step 4: Run the changelog/version regression tests**

Run: `python -m pytest tests/test_changelog.py -v`

Expected: all 5 tests **PASS**, in particular:
- `test_changelog_top_version_matches_version_py` — top heading is now `[3.3.1]`, matching `__version__`
- `test_pyproject_version_matches_version_py` — `pyproject.toml`'s version matches `src/version.py`
- `test_changelog_top_entry_has_content` — the new entry has a real `### Fixed` bullet, not a bare heading

- [ ] **Step 5: Commit**

```bash
git add src/version.py pyproject.toml CHANGELOG.md
git commit -m "release: v3.3.1 -- exact-pin MCP runtime dependencies"
```

---

### Task 3: Update README.md and CLAUDE.md roadmap entries

**Files:**
- Modify: `README.md:21` (version badge)
- Modify: `README.md:276-277` (Roadmap list — insert new bullet between the existing `v3.3` and `v3.4` lines)
- Modify: `CLAUDE.md:246-247` (Roadmap list — same insertion point)

**Interfaces:**
- Consumes: the v3.3.1 version number and CHANGELOG summary from Task 2.
- Produces: nothing consumed by later tasks — this is the last content-editing task before final verification.

- [ ] **Step 1: Update the README.md version badge**

Find (line 21):
```markdown
![Version](https://img.shields.io/badge/version-3.3.0-green.svg)
```
Change to:
```markdown
![Version](https://img.shields.io/badge/version-3.3.1-green.svg)
```

- [ ] **Step 2: Insert a new Roadmap bullet in README.md**

Find the existing `v3.3` bullet (currently the line right before the `v3.4` bullet):
```markdown
- **v3.3** ✅ Adopted the EU's official AI-generated-content icon (Code of Practice, AI Act Article 50(4)) in the Streamlit sidebar and all generated-document PDF exports, reinforcing the existing text/metadata disclosure
- **v3.4** App visual redesign ("Calibration Bench") — token-based color/typography system and a reusable score/severity component
```
Insert a new line between them:
```markdown
- **v3.3** ✅ Adopted the EU's official AI-generated-content icon (Code of Practice, AI Act Article 50(4)) in the Streamlit sidebar and all generated-document PDF exports, reinforcing the existing text/metadata disclosure
- **v3.3.1** ✅ Fix — `qai-consultant-mcp` could intermittently fail to attach in Claude Desktop because 4 of its 6 runtime dependencies had loose version bounds, letting `uv` re-resolve and reinstall on any unrelated upstream release; all dependencies are now exact-pinned
- **v3.4** App visual redesign ("Calibration Bench") — token-based color/typography system and a reusable score/severity component
```

- [ ] **Step 3: Insert the matching detailed entry in CLAUDE.md**

Find the existing `v3.3` bullet in `CLAUDE.md`'s Roadmap section (currently the line right before the `v3.4` bullet, around line 246-247):
```markdown
- **v3.3** ✅ Adopted the EU's official "Fully AI-Generated" icon from the Code of Practice on Transparency of AI-Generated Content (AI Act Article 50(4)) as a visual reinforcement of the v2.5.2/v2.6 text/metadata disclosure: `assets/eu_ai_icon/` (vendored SVG + PNG, no attribution required per the EU's license), `ai_disclosure.py`'s new `pdf_icon_html()` (base64 data-URI `<img>` tag — xhtml2pdf renders raster images but not SVG, hence PNG here), `pdf_export.py`'s new `extra_body_html` param on `markdown_to_pdf()`, and a theme-aware icon above the sidebar's `AI_INTERACTION_NOTICE` in `app.py` (required scoping the header-logo centering CSS from a blanket `[data-testid="stImage"]` rule to a keyed `st.container(key="header-logo")`, since this is the app's second `st.image()` call). Markdown `.md` downloads, the CLI, and the MCP server are unaffected — text-only channels where an image reference wouldn't render. Design spec: `docs/superpowers/specs/2026-07-29-eu-ai-icon-adoption-design.md`.
- **v3.4** App visual redesign ("Calibration Bench") — token-based color/typography system (IBM Plex, embedded as base64 so there's no client-side font CDN call) plus a reusable "Signal Ledger" score/severity component, wired into Document Review, Effort confidence, Results Analysis, and Risk Register (the last needs a small new deterministic parser, `src/risk_ledger.py`, since its severity data currently lives only inside free-text LLM markdown). Visual-only — no interaction-flow, session-state, or PDF-export changes. Full spec: `docs/superpowers/plans/2026-07-23-calibration-bench-redesign.md`.
```
Insert a new line between them:
```markdown
- **v3.3.1** ✅ Fix: `qai-consultant-mcp` could intermittently fail to attach in Claude Desktop even on a warm embedding cache — a *different* root cause from the v3.1.6 fix above. Found investigating real Claude Desktop logs (`%APPDATA%\Claude\logs\mcp-server-qai-consultant.log`): 4 of the package's 6 runtime dependencies (`mcp`, `langchain-community`, `platformdirs`, `defusedxml`) had loose version bounds rather than exact pins. Whenever any of them — or a transitive dependency uv's resolver picks — published a new PyPI release between two launches, `uvx qai-consultant-mcp` would re-resolve the environment and reinstall all ~88 packages (~26-30s logged as `Installed 88 packages in ...`), *regardless* of which `qai-consultant-mcp` version a user had pinned in their own Claude Desktop config — the drift came from unrelated upstream packages, not from our own release cadence. Stacked with the already-known ~20-25s `sentence-transformers`/`torch` import cost (v3.1.6 gotcha above), this routinely approached or exceeded Claude Desktop's ~60s `initialize` timeout: one observed launch got a response at 59.1s, another was cancelled by the client at 59.9s before the server replied. Fixed by exact-pinning all 6 dependencies to their currently-verified-working versions (`mcp==1.28.1`, `langchain-community==0.4.2`, `sentence-transformers==2.7.0`, `platformdirs==4.11.0`, `torch==2.13.0`, `defusedxml==0.7.1`), plus a new regression test (`tests/test_packaging.py::test_all_dependencies_are_exact_pinned`) that fails the build if a loose bound is reintroduced — this is the same class of gap that caused the v3.1.5 incident (an unbounded `mcp` floor), just from a different package and without needing an upstream *breaking* release to trigger it, only *any* release. A `uv.lock` in the repo was considered and ruled out: `uvx qai-consultant-mcp` installs the published PyPI package, not a clone of this repo, so a lockfile committed here never reaches the resolver an end user's `uvx` runs. The other half of the timing budget (the ~20-25s embedding-library import itself) remains unaddressed, as previously noted in the v3.1.6 gotcha — a lighter embedding backend is still tracked as separate future work, not part of this fix. Design spec: `docs/superpowers/specs/2026-07-30-mcp-dependency-pinning-design.md`.
```

- [ ] **Step 4: Sanity-check the version string landed correctly**

Run: `grep -c "3.3.1" README.md CLAUDE.md`

Expected: both files report a count `>= 1` (README.md should show 2: badge + roadmap bullet; CLAUDE.md should show 1: roadmap bullet — mentioned once, in the new bullet's own heading).

- [ ] **Step 5: Commit**

```bash
git add README.md CLAUDE.md
git commit -m "docs: update README/CLAUDE.md roadmap for v3.3.1 MCP dependency pinning"
```

---

### Task 4: Final full-suite verification and branch push

**Files:** none (verification-only task).

**Interfaces:**
- Consumes: the complete set of changes from Tasks 1-3.
- Produces: a pushed branch ready for PR — the terminal deliverable of this plan.

- [ ] **Step 1: Run the full test suite**

Run: `python -m pytest tests/ -v`

Expected: all tests **PASS** (no regressions introduced by the dependency pin, version bump, or docs changes). If anything unrelated is already failing on `master` before this branch's changes, note it, but this branch must not introduce any *new* failures.

- [ ] **Step 2: Run lint**

Run: `ruff check src/ tests/`

Expected: no new violations (this plan doesn't touch `src/`, only `tests/test_packaging.py` — the added test function should follow the same style as the rest of the file).

- [ ] **Step 3: Confirm the branch is `fix/mcp-exact-pin-dependencies` and push it**

This plan's changes should already be on the `fix/mcp-exact-pin-dependencies` branch (created during the brainstorming/spec phase, which already holds the design-spec commit). Confirm and push:

```bash
git branch --show-current
git log --oneline origin/master..HEAD
git push -u origin fix/mcp-exact-pin-dependencies
```

Expected: `git branch --show-current` prints `fix/mcp-exact-pin-dependencies`; the log shows the spec commit plus this plan's 3 new commits (Tasks 1-3); the push succeeds.

- [ ] **Step 4: Open the PR**

```bash
gh pr create --title "fix: exact-pin qai-consultant-mcp runtime dependencies (v3.3.1)" --body "$(cat <<'EOF'
## Summary
- Exact-pins all 6 runtime dependencies in pyproject.toml (mcp, langchain-community, sentence-transformers, platformdirs, torch, defusedxml) so uv never re-resolves/reinstalls the ~88-package environment just because an unrelated upstream package published a new release.
- Adds tests/test_packaging.py::test_all_dependencies_are_exact_pinned as a permanent regression guard.
- Version bump to 3.3.1 with full release-checklist docs (CHANGELOG.md, README.md, CLAUDE.md).
- Design spec: docs/superpowers/specs/2026-07-30-mcp-dependency-pinning-design.md

## Test plan
- [ ] CI green (test/lint/typecheck/security/evals-det/coverage)
- [ ] After merge: user publishes to PyPI + tags v3.3.1 (manual, per repo convention)
- [ ] After publish: `uvx qai-consultant-mcp` twice from a cleared uv cache — confirm no `Installed NN packages` line on the second launch

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

Expected: PR created successfully; report the PR URL.

**Note:** publishing to PyPI and creating the git tag are explicit steps for the user to run after this PR merges — not part of this plan, per the spec's "Release ownership" section.
