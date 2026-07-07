# Release Notes (v2.5.0) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship v2.5.0 — an in-app Release Notes panel in the Streamlit sidebar plus a one-time "what's new" banner, backed by a new `CHANGELOG.md`.

**Architecture:** A plain markdown `CHANGELOG.md` at the repo root is the single source of truth for release history. `src/app.py` gains a cached `load_changelog()` reader, a sidebar expander that renders it, and a session-gated banner in `main()`. No new dependencies, no LLM/RAG involvement.

**Tech Stack:** Python, Streamlit (`st.cache_data`, `st.expander`, `st.info`), pytest (existing structural/source-inspection test style — this repo does NOT use `streamlit.testing.v1.AppTest` anywhere; do not introduce it).

## Global Constraints
- Approved design spec: `docs/plans/2026-07-07-release-notes-feature.md` — do not relitigate decisions made there.
- Ships as `__version__ = "2.5.0"`, `__release_date__ = "2026-07-07"`.
- `release_notes_seen` is session-wide state; it must never appear in the "Start Over" (`render_sidebar`) or "Generate Another Strategy" (`render_strategy`) cleanup key lists.
- All new app.py tests follow the existing `read_app_source()` + `extract_function()` + substring/`.find()`-position style in `tests/test_app_v03.py`. Do not introduce `streamlit.testing.v1.AppTest`.
- Every commit message ends with:
  ```
  Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01F5kR8togUdXu7LvuEW1s9Q
  ```

---

### Task 1: Bump `src/version.py` to 2.5.0

**Files:**
- Modify: `src/version.py`
- Test: `tests/test_changelog.py` (new file)

**Interfaces:**
- Produces: `version.__version__ == "2.5.0"`, `version.__release_date__ == "2026-07-07"` — consumed by Task 2/7's cross-check and by `src/app.py`'s existing `from version import __version__`.

- [ ] **Step 1: Write the failing test** — create `tests/test_changelog.py`:
  ```python
  """
  Tests for QAI Consultant v2.5.0 release — version bump + CHANGELOG.md
  regression guards.

  Covers:
  1. version.py is bumped to 2.5.0 / 2026-07-07
  2. CHANGELOG.md exists, is non-empty, and has all expected version headings
  3. CHANGELOG.md's top heading matches version.py's __version__ (drift guard)
  """

  import re
  import sys
  from pathlib import Path

  REPO_ROOT = Path(__file__).resolve().parent.parent
  SRC_DIR = REPO_ROOT / "src"
  sys.path.insert(0, str(SRC_DIR))

  from version import __version__, __release_date__

  CHANGELOG_PATH = REPO_ROOT / "CHANGELOG.md"

  _EXPECTED_HEADING_SUBSTRINGS = [
      "[2.5.0]", "[2.0.2]", "[2.0.1]", "[2.0.0]", "[1.0.0]",
      "v0.6", "v0.5", "v0.4", "v0.3", "v0.2", "v0.1",
  ]


  def test_version_bumped_to_2_5_0():
      """version.py must be bumped for the Release Notes feature ship."""
      assert __version__ == "2.5.0", f"Expected __version__ == '2.5.0', got {__version__!r}"
      assert __release_date__ == "2026-07-07", \
          f"Expected __release_date__ == '2026-07-07', got {__release_date__!r}"
      print("  PASS: version.py bumped to 2.5.0 / 2026-07-07")
  ```

- [ ] **Step 2: Run test to verify it fails**

  Run: `python -m pytest tests/test_changelog.py -v -k test_version_bumped_to_2_5_0`
  Expected: FAIL — `AssertionError: Expected __version__ == '2.5.0', got '2.0.2'`

- [ ] **Step 3: Implement** — edit `src/version.py`:
  ```python
  __version__ = "2.5.0"
  __release_date__ = "2026-07-07"
  ```
  (leave `__author__`, `__description__`, `__license__` unchanged)

- [ ] **Step 4: Run test to verify it passes**

  Run: `python -m pytest tests/test_changelog.py -v -k test_version_bumped_to_2_5_0`
  Expected: PASS

- [ ] **Step 5: Commit**
  ```bash
  git add src/version.py tests/test_changelog.py
  git commit -m "$(cat <<'EOF'
  chore: bump version to 2.5.0

  Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01F5kR8togUdXu7LvuEW1s9Q
  EOF
  )"
  ```

---

### Task 2: Create `CHANGELOG.md`

**Files:**
- Create: `CHANGELOG.md`
- Test: `tests/test_changelog.py` (append)

**Interfaces:**
- Produces: `CHANGELOG.md` content consumed by Task 4's `load_changelog()` and Task 7's cross-check test.

- [ ] **Step 1: Write the failing tests** — append to `tests/test_changelog.py`:
  ```python
  def test_changelog_exists_and_nonempty():
      """CHANGELOG.md exists at the repo root and is non-empty."""
      assert CHANGELOG_PATH.exists(), "CHANGELOG.md is missing from the repo root"
      text = CHANGELOG_PATH.read_text(encoding="utf-8")
      assert text.strip(), "CHANGELOG.md exists but is empty"
      print("  PASS: CHANGELOG.md exists and is non-empty")


  def test_changelog_has_all_backfilled_version_headings():
      """CHANGELOG.md contains a heading for 2.5.0 and every backfilled version."""
      text = CHANGELOG_PATH.read_text(encoding="utf-8")
      missing = [s for s in _EXPECTED_HEADING_SUBSTRINGS if s not in text]
      assert not missing, f"CHANGELOG.md is missing headings for: {missing}"
      print(f"  PASS: CHANGELOG.md has all {len(_EXPECTED_HEADING_SUBSTRINGS)} expected version headings")
  ```

- [ ] **Step 2: Run tests to verify they fail**

  Run: `python -m pytest tests/test_changelog.py -v -k "exists_and_nonempty or all_backfilled"`
  Expected: both FAIL (file not found)

- [ ] **Step 3: Implement** — create `CHANGELOG.md` at the repo root with this exact content:
  ```markdown
  # Changelog

  All notable changes to QAI Consultant are documented in this file, in
  end-user terms. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

  ## [2.5.0] - 2026-07-07

  ### Added
  - In-app Release Notes: a "📋 Release Notes" panel in the sidebar now shows the full history of changes without leaving the app.
  - A one-time "what's new" banner appears the first time you open the app after an update, pointing you to the sidebar for details.

  ## [2.0.2] - 2026-07-06

  ### Added
  - An automated release-quality check now runs before every release, verifying that estimates and generated documents stay accurate and trustworthy.

  ### Fixed
  - Fixed several estimate and validation issues: duration ranges, team-size handling, project name display, confidence scoring, and fabricated version numbers appearing in generated Test Plans.
  - Fixed a crash that could occur while navigating between steps in the web app.
  - Fixed duplicated and cut-off text in generated narrative sections.
  - Increased the generation length limit so longer Test Plans and Test Strategies no longer get cut off mid-sentence.
  - Improved reliability so a temporary hiccup in one part of document generation no longer prevents the other parts from completing.

  ## [2.0.1] - 2026-06-28

  ### Fixed
  - A major stability release: fixed 27 issues affecting effort estimates, PDF downloads, session handling, generated file names, and knowledge-base search reliability.
  - Fixed an issue where reapplying a project template could silently fail to update the form.
  - Fixed PDF export freezing for certain inputs.
  - Fixed an issue where the per-session run limit could be bypassed.
  - Improved handling so a temporary knowledge-base search failure no longer stops the whole strategy from generating.

  ## [2.0.0] - 2026-05-07

  ### Changed
  - Moved to the cloud: QAI Consultant now runs on the Mistral API (with an automatic fallback provider) instead of a locally hosted model, and uses a cloud-hosted knowledge base.
  - QAI Consultant is now deployed as a hosted web app — no local installation required to use it.

  ## [1.0.0] - 2026-02-27

  ### Added
  - First stable release (MVP): hardened error handling and input validation, activity logging, a full automated test suite, and new setup (`INSTALL.md`) and contribution (`CONTRIBUTING.md`) guides.
  - The app now displays its version number in both the CLI and the web UI.

  ## Early development (v0.1 – v0.6)

  These releases predate formal version tracking and don't have exact recorded release dates.

  ### v0.6
  - Added a confidence score (0–100) to every estimate, based on four underlying factors, so you can gauge at a glance how much to trust a given number.

  ### v0.5
  - The knowledge base now keeps itself up to date automatically — new or changed reference material is picked up without a manual rebuild step.

  ### v0.4
  - Added Effort Estimation Reports: a data-driven time/effort estimate with a realistic best-case-to-worst-case range, tailored to your team's size and capacity.

  ### v0.3
  - Every Test Strategy now comes with an automatically generated Risk Register, identifying and prioritizing project risks alongside your test plan.

  ### v0.2
  - Added a feedback loop: strategies you mark as useful are saved back into the knowledge base, helping future recommendations keep improving.

  ### v0.1
  - First release: the core AI agent, a terminal (CLI) interface, and a browser-based Streamlit web app for generating Test Strategies.
  ```

- [ ] **Step 4: Run tests to verify they pass**

  Run: `python -m pytest tests/test_changelog.py -v`
  Expected: 3 passed

- [ ] **Step 5: Commit**
  ```bash
  git add CHANGELOG.md tests/test_changelog.py
  git commit -m "$(cat <<'EOF'
  docs: add CHANGELOG.md with backfilled release history

  Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01F5kR8togUdXu7LvuEW1s9Q
  EOF
  )"
  ```

---

### Task 3: Update CLAUDE.md Roadmap

**Files:**
- Modify: `CLAUDE.md` (Roadmap section)

**Interfaces:** none (docs-only; nothing parses CLAUDE.md at runtime).

- [ ] **Step 1: Implement** — in `CLAUDE.md`'s `## Roadmap` section, insert a new bullet directly after the existing `v2.0.2` line and before the `v2.1` line:
  ```markdown
  - **v2.5.0** ✅ In-app Release Notes — sidebar "📋 Release Notes" panel renders CHANGELOG.md (cached via `load_changelog()`); one-time session banner on load pointing users to it
  ```

- [ ] **Step 2: Verify**

  Run: `python -c "print(open('CLAUDE.md', encoding='utf-8').read().count('v2.5.0'))"`
  Expected: `1`

- [ ] **Step 3: Commit**
  ```bash
  git add CLAUDE.md
  git commit -m "$(cat <<'EOF'
  docs: add v2.5.0 to CLAUDE.md Roadmap

  Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01F5kR8togUdXu7LvuEW1s9Q
  EOF
  )"
  ```

---

### Task 4: `load_changelog()` helper + sidebar expander

**Files:**
- Modify: `src/app.py` (insert after `load_agent()`, ~line 139; edit `render_sidebar()`, ~line 143)
- Test: `tests/test_app_v03.py` (append)

**Interfaces:**
- Consumes: `CHANGELOG.md` (Task 2), `Path` and `logger` already imported/defined at module level in `src/app.py`.
- Produces: `app.CHANGELOG_PATH` (a `Path`), `app.load_changelog() -> str` (an `@st.cache_data`-wrapped function with `.clear()`) — consumed by Task 5's banner (shares the same `__version__` import, no direct call) and referenced directly by Task 4's own tests.

- [ ] **Step 1: Write the failing tests** — append to `tests/test_app_v03.py`, after `test_risk_analyzer_imported_at_module_level` and before the `# ── LLM smoke test` section:
  ```python
  # ── Release Notes (v2.5.0) ────────────────────────────────────────────────────

  def test_sidebar_has_release_notes_expander():
      """render_sidebar() has a 'Release Notes' expander rendering load_changelog()'s output."""
      fn = extract_function(read_app_source(), "render_sidebar")
      assert 'st.expander("📋 Release Notes")' in fn, \
          "render_sidebar() is missing the '📋 Release Notes' expander"
      assert "st.markdown(load_changelog())" in fn, \
          "render_sidebar() must render load_changelog()'s output via st.markdown(...)"
      print("  PASS: sidebar has a 'Release Notes' expander rendering load_changelog()")


  def test_load_changelog_reads_real_file():
      """load_changelog() actually reads the real CHANGELOG.md once it exists."""
      import app
      app.load_changelog.clear()
      content = app.load_changelog()
      assert content.strip(), "load_changelog() returned empty content"
      assert "2.5.0" in content, "load_changelog() content does not mention 2.5.0"
      print("  PASS: load_changelog() reads the real CHANGELOG.md")


  def test_load_changelog_fallback_on_missing_file(monkeypatch):
      """load_changelog() falls back to a plain string when the file is unreadable."""
      import app
      monkeypatch.setattr(app, "CHANGELOG_PATH", Path("Z:/definitely/does/not/exist/CHANGELOG.md"))
      app.load_changelog.clear()
      try:
          content = app.load_changelog()
          assert content == "_Release notes unavailable._", \
              f"Expected fallback string, got: {content!r}"
      finally:
          app.load_changelog.clear()
      print("  PASS: load_changelog() falls back gracefully on a missing file")
  ```

- [ ] **Step 2: Run tests to verify they fail**

  Run: `python -m pytest tests/test_app_v03.py -v -k "release_notes_expander or load_changelog"`
  Expected: all 3 FAIL/ERROR (expander string not found; `AttributeError: module 'app' has no attribute 'load_changelog'`; same for `CHANGELOG_PATH`)

- [ ] **Step 3: Implement** — edit `src/app.py`. Insert after `load_agent()` (before the `# ── Sidebar` comment):
  ```python
  # ── Changelog ──────────────────────────────────────────────────────────────────
  CHANGELOG_PATH = Path(__file__).resolve().parent.parent / "CHANGELOG.md"


  @st.cache_data(show_spinner=False)
  def load_changelog() -> str:
      """
      Read CHANGELOG.md from the repo root once per session (cached — the file
      doesn't change while a session is running). Returns a graceful fallback
      string instead of crashing if the file is missing or unreadable.
      """
      try:
          return CHANGELOG_PATH.read_text(encoding="utf-8")
      except Exception as e:
          logger.warning(f"Could not read CHANGELOG.md: {e}")
          return "_Release notes unavailable._"
  ```

  Edit `render_sidebar()` to add the expander directly under the version caption:
  ```python
  def render_sidebar():
      with st.sidebar:
          st.markdown("## 🧪 QAI Consultant")
          st.markdown("AI-powered QA Architect")
          st.caption(f"v{__version__}")
          with st.expander("📋 Release Notes"):
              st.markdown(load_changelog())
          st.divider()
  ```

- [ ] **Step 4: Run tests to verify they pass**

  Run: `python -m pytest tests/test_app_v03.py -v -k "release_notes_expander or load_changelog"`
  Expected: 3 passed

- [ ] **Step 5: Commit**
  ```bash
  git add src/app.py tests/test_app_v03.py
  git commit -m "$(cat <<'EOF'
  feat: add load_changelog() helper and sidebar Release Notes expander

  Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01F5kR8togUdXu7LvuEW1s9Q
  EOF
  )"
  ```

---

### Task 5: One-time banner in `main()`

**Files:**
- Modify: `src/app.py` (`main()`, ~line 890-894)
- Test: `tests/test_app_v03.py` (append)

**Interfaces:**
- Consumes: `st.session_state`, `__version__` (already imported in `src/app.py`).
- Produces: `st.session_state["release_notes_seen"]` flag — consumed by Task 6's absence-check tests.

- [ ] **Step 1: Write the failing tests** — append to `tests/test_app_v03.py`, directly after the Task 4 tests:
  ```python
  def test_banner_exists_and_gates_on_release_notes_seen():
      """main() shows the one-time banner gated on session_state.release_notes_seen."""
      fn = extract_function(read_app_source(), "main")
      assert 'st.session_state.get("release_notes_seen")' in fn, \
          "main() does not check st.session_state.get('release_notes_seen')"
      assert "st.session_state.release_notes_seen = True" in fn, \
          "main() does not set release_notes_seen = True"
      assert "st.info(" in fn and "Release Notes" in fn, \
          "main() does not show the release-notes banner via st.info(...)"
      print("  PASS: main() has the one-time release-notes banner gated on release_notes_seen")


  def test_banner_appears_before_render_sidebar_call():
      """The banner check must run before render_sidebar() (ordering, like
      test_review_writes_back_additional_context_before_generating)."""
      fn = extract_function(read_app_source(), "main")
      banner_pos = fn.find('st.session_state.get("release_notes_seen")')
      sidebar_pos = fn.find("render_sidebar()")
      assert banner_pos != -1, "banner gate not found in main()"
      assert sidebar_pos != -1, "render_sidebar() call not found in main()"
      assert banner_pos < sidebar_pos, \
          "the release_notes_seen banner must run before render_sidebar() is called"
      print("  PASS: banner check runs before render_sidebar() in main()")
  ```

- [ ] **Step 2: Run tests to verify they fail**

  Run: `python -m pytest tests/test_app_v03.py -v -k "test_banner"`
  Expected: both FAIL

- [ ] **Step 3: Implement** — edit `main()` in `src/app.py`, inserting the banner after the agent is stored in session state and before `render_sidebar()`:
  ```python
      # Store agent in session state for use across components
      if st.session_state.get("agent") is None:
          st.session_state.agent = agent

      if not st.session_state.get("release_notes_seen"):
          st.session_state.release_notes_seen = True
          st.info(f"✨ Updated to v{__version__} — see the sidebar's **Release Notes** for what's new.")

      render_sidebar()
  ```

- [ ] **Step 4: Run tests to verify they pass**

  Run: `python -m pytest tests/test_app_v03.py -v -k "test_banner"`
  Expected: 2 passed

- [ ] **Step 5: Commit**
  ```bash
  git add src/app.py tests/test_app_v03.py
  git commit -m "$(cat <<'EOF'
  feat: show one-time release-notes banner after agent loads

  Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01F5kR8togUdXu7LvuEW1s9Q
  EOF
  )"
  ```

---

### Task 6: Cleanup-block non-interference regression guard

**Files:**
- Test: `tests/test_app_v03.py` (append)

**Interfaces:**
- Consumes: `render_sidebar()` and `render_strategy()` source (Tasks 4-5 must not have touched their cleanup blocks).

- [ ] **Step 1: Write the test** — append to `tests/test_app_v03.py`:
  ```python
  def test_cleanup_blocks_do_not_clear_release_notes_seen():
      """Neither 'Start Over' (render_sidebar) nor 'Generate Another Strategy'
      (render_strategy) may clear release_notes_seen — it's a session-wide
      'have you seen this' flag, not per-run state (inverse of
      test_cleanup_blocks_clear_additional_context_keys, which asserts presence)."""
      source = read_app_source()
      for fn_name in ["render_sidebar", "render_strategy"]:
          fn = extract_function(source, fn_name)
          assert '"release_notes_seen"' not in fn, \
              f"{fn_name}() must NOT clear release_notes_seen"
      print("  PASS: neither cleanup block clears release_notes_seen")
  ```

- [ ] **Step 2: Run it (should pass immediately — Tasks 4-5 never touched the cleanup blocks)**

  Run: `python -m pytest tests/test_app_v03.py -v -k test_cleanup_blocks_do_not_clear_release_notes_seen`
  Expected: 1 passed

- [ ] **Step 3: Commit**
  ```bash
  git add tests/test_app_v03.py
  git commit -m "$(cat <<'EOF'
  test: guard against release_notes_seen ever entering cleanup blocks

  Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01F5kR8togUdXu7LvuEW1s9Q
  EOF
  )"
  ```

---

### Task 7: CHANGELOG.md / version.py cross-check regression guard

**Files:**
- Test: `tests/test_changelog.py` (append)

**Interfaces:**
- Consumes: `CHANGELOG_PATH` and `__version__` (already defined earlier in this file from Task 1).

- [ ] **Step 1: Write the test** — append to `tests/test_changelog.py`:
  ```python
  def test_changelog_top_version_matches_version_py():
      """The newest (topmost) CHANGELOG.md version heading must exactly match
      version.py's __version__ — catches bumping one but forgetting the other,
      without hardcoding '2.5.0' as a second magic string."""
      text = CHANGELOG_PATH.read_text(encoding="utf-8")
      match = re.search(r"## \[(\d+\.\d+\.\d+)\]", text)
      assert match, "No '## [X.Y.Z]' version heading found in CHANGELOG.md"
      assert match.group(1) == __version__, (
          f"CHANGELOG.md's top heading is [{match.group(1)}] but "
          f"version.py's __version__ is {__version__!r} — they must match."
      )
      print(f"  PASS: CHANGELOG.md top heading [{match.group(1)}] matches __version__")
  ```

- [ ] **Step 2: Run it — passes immediately since Tasks 1-2 already landed matching values**

  Run: `python -m pytest tests/test_changelog.py -v -k test_changelog_top_version_matches_version_py`
  Expected: 1 passed

- [ ] **Step 3: Prove the guard is real (manual verification, not committed)**

  Temporarily edit `src/version.py`'s `__version__` to `"9.9.9"`, rerun the same command, confirm FAIL with the exact mismatch message, then revert `src/version.py` back to `"2.5.0"` and rerun to confirm 1 passed again. Do not leave the scratch edit in place or commit it.

- [ ] **Step 4: Commit**
  ```bash
  git add tests/test_changelog.py
  git commit -m "$(cat <<'EOF'
  test: guard CHANGELOG.md top version against version.py drift

  Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01F5kR8togUdXu7LvuEW1s9Q
  EOF
  )"
  ```

---

### Task 8: Full local verification pass

**Files:** none (verification only)

- [ ] **Step 1: Run the new/changed test surface together**

  Run: `python -m pytest tests/test_changelog.py -v`
  Expected: 4 passed

  Run: `python -m pytest tests/test_app_v03.py -v`
  Expected: all passed (15 pre-existing + 7 new from Tasks 4-6)

- [ ] **Step 2: Run the full suite**

  Run: `python -m pytest tests/ -v`
  Expected: all green, no new failures relative to the pre-existing baseline. (Note: CLAUDE.md's "104 passed" baseline note is stale — the actual current baseline on this branch is higher; use `ruff check src/ tests/` + the full pytest run's own pass count as ground truth, not the stale doc number.)

- [ ] **Step 3: Run lint**

  Run: `ruff check src/ tests/`
  Expected: All checks passed!

- [ ] **Step 4: Report status** — if everything is green, this plan is complete. Do not merge/push without separate user confirmation.
