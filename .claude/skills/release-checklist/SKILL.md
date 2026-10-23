---
name: release-checklist
description: The exact files to update together whenever a version bump ships in this repo (src/qai_consultant/common/version.py, pyproject.toml, CHANGELOG.md, README.md, README_MCP.md, CLAUDE.md). Use whenever bumping __version__ or preparing a release PR.
---

# Release Checklist (QAI Consultant)

**Whenever a version bump ships (a new `__version__` in `src/qai_consultant/common/version.py`), update all of the following together in the same change — do this automatically as part of the release, don't wait to be asked file-by-file:**

- `src/qai_consultant/common/version.py` — `__version__` and `__release_date__`
- `pyproject.toml` — `[project] version`, kept in lockstep with `src/qai_consultant/common/version.py` (`tests/system/release/test_packaging.py` doesn't check this, but drift here breaks the published wheel's version)
- `CHANGELOG.md` — new `## [X.Y.Z] - YYYY-MM-DD` entry at the top, in end-user terms (Keep a Changelog format, see existing entries for tone)
- `README.md` (root) — version badge, intro paragraph if the feature set changed, MCP tools table if the tool surface changed, Roadmap section
- `README_MCP.md` — description line + tools table if the MCP tool surface changed
- `CLAUDE.md` — architecture table rows for new/changed modules with non-obvious constraints, new Gotchas discovered during the work, Roadmap section (keep new entries terse — see the last step below)

**Merge gate: never merge a release PR to `master` before `CHANGELOG.md` has the new version's entry in the same PR.** The version bump and the changelog entry must land together, not as a follow-up commit — a merged release with a stale top-of-file changelog is exactly what this checklist exists to prevent.

`tests/system/release/test_changelog.py` only guards `version.py` ↔ `CHANGELOG.md` drift (`__version__` matches the top heading) — it does **not** catch a stale `README.md` or `README_MCP.md`. Found the hard way in v3.1: a docs pass updated `CHANGELOG.md`/`README_MCP.md`/`CLAUDE.md`/`MCP_PLAN.md` but missed the root `README.md` entirely (stale version badge, stale MCP tools table, stale Roadmap line), caught only when the user asked directly. Treat the list above as one atomic step of every release, not an optional follow-up.

**Run the `claude-md-hygiene` skill** after touching CLAUDE.md's Roadmap/Gotchas above:

```bash
bash .claude/skills/claude-md-hygiene/check.sh
```

Keep new entries terse (one line for Roadmap, rule + one-line why + doc link for Gotchas) and push real narrative into `CHANGELOG.md`/`docs/postmortems/` instead — this is what keeps CLAUDE.md from bloating back up release over release.

**If this release changes `qai-consultant-mcp`'s published tool surface** (any module under `src/qai_consultant/{common,core,mcp}/` or the knowledge base whitelist), run before asking for the human-gated `twine upload`:

```bash
python scripts/mcp_release_check.py --preflight       # tests/lint/mypy/bandit/build/twine-check/smoke-install
```

and after the upload actually happens:

```bash
python scripts/mcp_release_check.py --live-version     # confirms PyPI's info.version really matches src/qai_consultant/common/version.py
```

The live-version check exists because a version bump merged to `master` is not the same as a version published to PyPI — see the matching Gotcha in CLAUDE.md; this is what would have caught v3.5.0 sitting unpublished for days.

**If a module under `src/` is moved or renamed**, update Glama's build step too (admin -> Dockerfile -> Build steps; it is not in the repo). Its warmup step imports `LocalIndex` by module path, and the #133 refactor broke it silently until the v3.9.1 auto-release build failed with `No module named 'local_index'`. Current step: `uv run python -c "from qai_consultant.mcp.local_index import LocalIndex; LocalIndex().search('warmup', k=1)"`. Test with the **Build** button, then **Build & Release**.

**If a direct dependency in `pyproject.toml` needs a version bump**, regenerate the full transitive lock instead of hand-editing one line (see the "single-package Dependabot PR" Gotcha for why a partial edit corrupts the resolved set):

```bash
python scripts/regenerate_mcp_lock.py            # regenerates, shows a diff, writes, then verifies exact-pinning + pip-audit
```
