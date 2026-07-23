# MCP Distribution Plan (publish 3.1.3 to PyPI, then list in MCP directories)

**Date:** 2026-07-22
**Author:** Gabi (planned with Claude), for implementation by Claude Code
**Goal:** Make MCP adoption the primary growth objective. Get the current `qai-consultant-mcp` (v3.1.3, with the F1/F2 tools) onto PyPI, verify it installs and runs cleanly with `uvx` on a clean machine, then list it in the public MCP directories where technical QA engineers and SDETs discover servers.

---

## Why this plan exists (context)

The ideal user is a QA Lead / Test Manager, but the realistic audience for an MCP server is the more technical, hands-on QA engineer / SDET who already runs an MCP client (Claude Code, Claude Desktop, Cursor). MCP adoption is the chosen near-term objective because it plays to the project's real strengths: a keyless local server, deterministic tools, a PyPI package, and no gatekeeper (no company budget required to try it).

### The blocker discovered on 2026-07-22

- **Local code:** 3.1.3 (`src/version.py`, `pyproject.toml`, `CHANGELOG.md` top entry all say 3.1.3; git tag `v3.1.3` exists).
- **PyPI live version:** **3.0.2** (uploaded 2026-07-15, via `twine`, Trusted Publishing = No).
- **Consequence:** anyone installing `qai-consultant-mcp` today gets the 3.0.2 tool surface, which is **missing the two v3.1 tools** that are the strongest differentiators for a directory listing:
  - `review_qa_document` (F1: deterministic 0-100 QA document quality review across 6 ISTQB/IEEE-829 dimensions)
  - `analyze_test_results` (F2: JUnit XML / CSV flaky / ever-failing / slowest / failure-cluster analysis)

So the hard dependency is: **publish 3.1.3 to PyPI before listing anywhere.** Listing first would send traffic to the weaker 3.0.2 build.

### What is NOT in scope

- **Remote MCP (hosted Streamable HTTP server, the hard half of roadmap v3.2) is explicitly out of scope.** Do not build hosting. The local stdio package installed via `uvx qai-consultant-mcp` is exactly what the directories list. Remote hosting is a later improvement, justified only after we see real demand.
- No new product features. This is a release + distribution task, not a coding-feature task.

---

## Guardrails (read before doing anything irreversible)

1. **Publishing to PyPI is irreversible.** A version number, once uploaded, can never be re-uploaded or overwritten (only "yanked"). Do not run the actual `twine upload` step without Gabi's explicit go-ahead. Everything up to and including building + a `--repository testpypi` dry run is fine to do autonomously; the real upload to production PyPI is human-gated.
2. **Git tags / GitHub releases / merging to `master` also stay human-gated**, consistent with how CLAUDE.md already treats these. Prepare them, show the diff, then stop and ask.
3. **Requires a secret Gabi must supply:** a PyPI API token (for `twine`). Do not ask for it in chat; Claude Code should instruct Gabi to set it locally (`~/.pypirc` or the `TWINE_PASSWORD` env var) and run the upload step himself if he prefers. **Use a project-scoped token** (PyPI lets you scope a token to just the `qai-consultant-mcp` project), not an account-wide token — standard least-privilege practice, and it caps the blast radius if the token ever leaks.
4. **Preserve the warmup-ordering fix.** CLAUDE.md documents a Windows-specific deadlock (fixed in v3.0.2) where the embedding model's first inference must happen via `index.search("warmup", k=1)` on the main thread *before* `mcp.run()`. Verify this code path is present and unchanged in the 3.1.3 build before publishing. A regression here bricks every real client silently.

---

## Phase 0 — Pre-flight verification (no side effects)

Confirm the release is actually coherent before touching PyPI.

- [x] **Branch/master sync.** Resolved per Decisions #2 below: `ci/coverage-guardrails` was merged into `master` on 2026-07-22. Just confirm `master` contains the 3.1.3 code and the `v3.1.3` tag points at the right commit on `master`.
- [x] **Version alignment (CLAUDE.md release checklist).** Confirm all of these agree on 3.1.3: `src/version.py` (`__version__` + `__release_date__`), `pyproject.toml` `[project] version`, `CHANGELOG.md` top heading, `README.md` version badge, `README_MCP.md` description/tools table. `tests/test_changelog.py` guards version.py <-> CHANGELOG only, so eyeball the two READMEs manually.
- [x] **Tool surface in the READMEs matches reality.** `README_MCP.md` and the root `README.md` MCP tools table must list all 5 tools (`retrieve_qa_knowledge`, `list_kb_sources`, `estimate_qa_effort`, `review_qa_document`, `analyze_test_results`). The live PyPI 3.0.2 page only lists the first 3, so this is exactly the drift to fix.
- [x] **Full local gate is green:** `python -m pytest tests/ -v`, `ruff check src/ tests/`, `mypy src/`, `bandit -r src/ -ll`, and `python -m evals.run --det`. Do not publish on a red suite. (Note: an independent triple re-run surfaced 1-in-3 flakiness in `tests/test_risk_analyzer.py::test_risk_register_sections`, a live-Mistral-call test — inherent network/LLM nondeterminism, not a 3.1.3 regression. Gabi reviewed and accepted this as known, non-blocking; follow-up tracked separately, out of this plan's scope.)
- [x] **CI is actually green on `master`, not just local.** Local-green is not sufficient on its own — CLAUDE.md documents a real case (the coverage gate) where Windows-measured local results diverged from the Linux `ubuntu-latest` CI runner's numbers because fewer tests execute there. Check the latest GitHub Actions run for the `master` commit that `v3.1.3` tags (`gh run list --branch master` / the Actions tab) and confirm every blocking job (`test`, `lint`, `typecheck`, `security-bandit`, `evals-det`, `coverage`) passed there, not only on the dev machine.

**Acceptance:** everything above is consistent and green, or any inconsistency is written up for Gabi to resolve.

---

## Phase 1 — Build the 3.1.3 artifacts

- [x] Clean any stale build output: remove `build/`, `dist/`, `*.egg-info` (do not commit these).
- [x] Build sdist + wheel: `python -m build` (or `uv build`).
- [x] **Run the packaging gate against the real artifact:** `python -m pytest tests/test_packaging.py -v`. This test builds the real wheel and asserts zero PDFs/HTML are included and that the whitelisted `.md` knowledge-base set exact-matches the repo. It is the guard against accidentally shipping licensed standards PDFs. Must pass. (9/9, zero PDFs/HTML. Also caught, and this same task session fixed, a real blocker: `pyproject.toml` was missing `defusedxml` as a declared dependency — see Phase 2 note below.)
- [x] Inspect the built wheel's contents manually as a second check: `python -m zipfile -l dist/qai_consultant_mcp-3.1.3-py3-none-any.whl`. Confirm the 9 flat modules + whitelisted KB `.md` files are present, no PDFs/HTML, and `src/mcp_server.py` / `src/local_index.py` are in. (Actual shipped module count is 11, not 9 — `review_core.py`/`results_core.py` were added in v3.1 without updating that CLAUDE.md roadmap sentence. All 11 confirmed present; doc-nit follow-up, not a packaging defect.)
- [x] Confirm the version embedded in the artifact filename is `3.1.3`.

**Acceptance:** `dist/qai_consultant_mcp-3.1.3.tar.gz` and `...-3.1.3-py3-none-any.whl` exist and pass `test_packaging.py`.

---

## Phase 2 — Clean-machine smoke test (the critical one)

The point is to reproduce a brand-new user's first experience, because the v3.0.2 deadlock proved that unit tests (which mock Pinecone and the stdio loop) do not catch the failure mode that matters most.

- [x] **Cover the platform where the deadlock actually happened, plus at least one other.** The v3.0.x warmup deadlock (see CLAUDE.md gotcha) was Windows-specific — root-caused to `stdio_server()`'s reader thread racing the embedding model's first inference under Windows' process loader lock. Run the clean-machine test on Windows (non-negotiable, it's the platform that broke before) **and** on at least one of macOS/Linux, since most real MCP client users won't be on Windows and a Windows-only regression test would miss a different platform-specific issue. (Windows + Linux/Docker `python:3.11-slim` both run, both green.)
- [x] Create a fresh virtual environment / clean cache so no repo code is on the path.
- [x] Install the just-built artifact in isolation (e.g. `uvx --from ./dist/qai_consultant_mcp-3.1.3-py3-none-any.whl qai-consultant-mcp`, or `pip install` the wheel into the clean venv and run the entry point). (First attempt on Windows crashed at startup with `ModuleNotFoundError: No module named 'defusedxml'` — `src/results_core.py` imports it unconditionally but `pyproject.toml`'s `[project] dependencies` never listed it, only `requirements.txt` did, so every prior dev/CI/eval run stayed green despite the gap. Fixed same-session, commit `c3e69f8` — added `defusedxml>=0.7.1` to `pyproject.toml`, rebuilt `dist/`, re-passed `test_packaging.py` (9/9), and re-ran this smoke test clean: all 5 tools passed over real stdio, "SMOKE TEST PASSED" in 9.7s. Fix reviewed and approved.)
- [x] **Drive it over real stdio as an MCP client would**, not just import it. Minimum viable check: start the server, then issue a `list_kb_sources` call AND a `retrieve_qa_knowledge` call. The retrieval call is the one that triggers the first real embedding-model inference and hit the deadlock in 3.0.x. It must return, not hang.
- [x] Exercise both new tools end to end at least once: `review_qa_document` on a small sample doc, and `analyze_test_results` on a small JUnit XML (there are fixtures under `evals/fixtures/results/` and `evals/fixtures/review/` to reuse). For `analyze_test_results`, test the multi-run JSON-array argument shape too (the FastMCP `pre_parse_json` gotcha in CLAUDE.md).
- [x] Confirm first-run behavior is acceptable: the first call downloads the `all-MiniLM-L6-v2` model and builds the index (a minute or two), then caches. Note the timing so the README sets the right expectation. (Windows smoke test completed end-to-end, all 5 tools, in 9.7s on the run measured.)

**Acceptance:** on a clean machine, all 5 tools respond correctly over stdio, and nothing hangs. If anything hangs, STOP: the warmup ordering or a new regression is the cause, do not publish.

---

## Phase 3 — Publish to PyPI (HUMAN-GATED)

Do not execute the upload without Gabi's explicit approval.

- [x] (Optional but recommended) Dry-run to **TestPyPI** first. **Skipped**: no TestPyPI credentials were available (TestPyPI requires its own separate account/token from production PyPI, and only a production `~/.pypirc` was set up). Substituted with local-only verification instead (`test_packaging.py` + `twine check dist/*` against the freshly rebuilt artifacts), which caught no issues.
- [x] Verify metadata renders: `twine check dist/*` PASSED on both the sdist and the wheel — this runs the same README/long-description renderer PyPI itself uses, so this is equivalent coverage to a TestPyPI preview for rendering purposes (though it doesn't verify PyPI's own page chrome).
- [x] **Production upload:** `twine upload dist/*`, run directly in this session after Gabi set up `~/.pypirc` and gave explicit go-ahead. Note: the artifacts were **rebuilt from current `master` HEAD** (not the pre-existing `v3.1.3` git tag) — the tag was discovered to be 36 commits stale and missing the `defusedxml` fix; see the tag-move note under Phase 4 below. Succeeded: https://pypi.org/project/qai-consultant-mcp/3.1.3/
- [ ] Consider enabling **Trusted Publishing** (GitHub Actions OIDC) for future releases so tokens are not needed and publish is reproducible from CI. Still a nice-to-have follow-up, not part of this release.

**Acceptance:** `https://pypi.org/project/qai-consultant-mcp/` shows **3.1.3** as the latest release.

**If a critical bug is found post-publish:** a PyPI upload can never be overwritten or deleted, only **yanked** (`twine` / the PyPI web UI's "Yank release" action — marks the version as "should not be used" without removing it, so existing pins still resolve but new installs/`uvx` calls skip it). Yanking is reversible (can be un-yanked). Fix forward with a new patch version rather than trying to "undo" 3.1.3; do not delay a yank waiting for the fix if the bug is severe (e.g. a regression of the warmup deadlock) — yank first, then fix and republish.

---

## Phase 4 — Post-publish verification

- [x] From a clean, isolated venv with nothing local on the path: `uvx --refresh --from qai-consultant-mcp==3.1.3 qai-consultant-mcp` pulling from **production PyPI**, driven over real stdio (`mcp.client.stdio`). Ran all 5 tools, not just the minimum 2: `list_kb_sources`, `retrieve_qa_knowledge`, `estimate_qa_effort`, `review_qa_document`, `analyze_test_results` (both single-run and the multi-run JSON-array shape). No hang — warmup ordering fix confirmed intact on the real published package. "SMOKE TEST PASSED (production PyPI 3.1.3)".
- [x] Confirmed via `https://pypi.org/pypi/qai-consultant-mcp/json` that `info.version == "3.1.3"`. Direct HTML fetch of the project page hit PyPI's bot-challenge wall (unrelated to the release); `twine check` already validated the tools-table/README rendering pre-upload, and the smoke test's live tool listing is the stronger proof the shipped package matches.
- [x] **Tag/GitHub release housekeeping:** discovered the existing `v3.1.3` git tag was stale (36 commits behind `master`, predated the `defusedxml` fix) — force-moved it to current `master` HEAD (`6990560`) as an **annotated** tag (matching the `v3.1.1`/`v3.1.2` convention; first attempt created a lightweight tag by mistake, caught and corrected), pushed to origin. A GitHub release for `v3.1.3` already existed (published 2026-07-21, notes match the CHANGELOG) — since GitHub releases track by tag name, it now automatically points at the corrected commit. No new release needed.

**Acceptance:** a first-time user running the documented one-liner gets a working 3.1.3 server.

---

## Phase 5 — List in MCP directories (the actual distribution)

Only start this after Phase 4 passes. Each listing points at the PyPI package / GitHub repo; none require hosting.

For each target, prepare the submission (fork/PR, form fields, or config entry), show Gabi the exact content, and let him submit or approve. Standard listing metadata to reuse everywhere:

- **Name:** QAI Consultant (MCP server)
- **Install:** `uvx qai-consultant-mcp`
- **One-line pitch (lead with the differentiator, not generic retrieval):** "Bring ISTQB / OWASP / IEEE / ISO / EU AI Act QA standards into your LLM client, keyless: standards-grounded retrieval, deterministic effort estimation, and QA document quality review."
- **Repo:** https://github.com/gvasile29/qai-consultant
- **License:** Apache-2.0
- **Tools:** the 5-tool table from README_MCP.md.

Targets, in priority order:

- [ ] **Official Anthropic MCP registry** (the `modelcontextprotocol` ecosystem registry). This is the highest-signal listing. Follow its current submission process (server.json / registry schema as required at implementation time; verify the exact format, do not assume).
- [ ] **Awesome MCP servers lists on GitHub** (the well-known `awesome-mcp-servers` repos). Open a PR adding the server under the appropriate category (developer tools / testing). Match the existing entry format in each list exactly.
- [ ] **Smithery** (smithery.ai) — submit / register the server.
- [ ] **Glama** (glama.ai/mcp) — submit the server.
- [ ] **mcp.so** — submit the server.

> Note: directory names, URLs, and submission mechanics change quickly. At implementation time, verify each directory's current submission process rather than trusting these names blindly. Do a fresh web check.

**Acceptance:** submissions prepared (and, where Gabi approves, submitted) to at least the Anthropic registry + one awesome-list PR + two of the three third-party directories.

**Track submission status** so five parallel submissions don't get lost (a checklist in an issue, or a small table appended here — whichever Gabi prefers when this phase starts):

| Directory | Submitted (date) | Status | Notes |
|---|---|---|---|
| Anthropic MCP registry | | | |
| awesome-mcp-servers | | | |
| Smithery | | | |
| Glama | | | |
| mcp.so | | | |

---

## Phase 6 — Make the listing convert (README + demo)

A directory entry only works if the click-through lands on something convincing.

- [ ] **README_MCP.md polish:** ensure the install one-liner, the 5-tool table, and a 2-3 line "why this exists" are the first thing a reader sees. Set the correct first-run expectation (model download timing).
- [ ] **Add a short demo GIF** (~15s) showing a tool call answering inside an MCP client (e.g. `review_qa_document` scoring a Test Plan, or `retrieve_qa_knowledge` citing a standard). Put it near the top of README_MCP.md and the root README. Without a visual, directory click-throughs rarely install.
- [ ] **GitHub repo discoverability:** confirm repo topics include `mcp`, `model-context-protocol`, `qa`, `testing`, `quality-assurance` (already used as PyPI tags), plus `istqb` if desired.

**Acceptance:** README_MCP.md leads with install + tools + demo GIF; repo has the right topics.

---

## Measurement (define "adoption" up front, avoid vanity metrics)

A PyPI download is not an active user. Decide what counts as real adoption before the traffic arrives:

- **Primary signal:** at least one real tool call (e.g. a `retrieve_qa_knowledge` or `review_qa_document` invocation) via the opt-in telemetry (`QAI_TELEMETRY=1`, PostHog, already wired in `src/telemetry.py`). Note that telemetry is off by default, so this undercounts; treat it as a floor, not a total.
- **Secondary signals:** PyPI download trend (as a coarse interest proxy, not activation), GitHub stars, directory listing views if available.
- Optional follow-up: server-side usage metrics (the other half of roadmap v3.2) if/when a hosted variant exists. Out of scope here.
- **First check-in: 2 weeks after Phase 5 submissions go live.** Look at the primary signal (telemetry tool-call events) plus the secondary signals together; a single 2-week PyPI download count alone is not a verdict, but it's the point to first glance at the data rather than letting it go unreviewed indefinitely.

---

## Decisions (confirmed by Gabi 2026-07-22)

1. **Publishing method: manual PyPI API token via `twine`.** Do NOT set up Trusted Publishing for this release. Gabi supplies the token locally (`~/.pypirc` or `TWINE_PASSWORD` env var); the production upload is his to run/approve. (Trusted Publishing can be revisited as a later follow-up, not part of this release.)
2. **Merge-to-master: done.** 3.1.3 is on `master`; the `ci/coverage-guardrails` branch was merged into `master` on 2026-07-22. Phase 0's branch-sync check is therefore satisfied, but still confirm the `v3.1.3` tag points at the correct `master` commit before building.
3. **Autonomy for Claude Code: approach confirmed.** It MAY, without asking: build artifacts, run the full test/lint/typecheck/eval suite, and do the TestPyPI dry-run. It MUST stop and get Gabi's explicit approval before: the production `twine upload` to PyPI, pushing any git tag / creating a GitHub release, and submitting to any external directory.

---

## TL;DR execution order

1. Phase 0: verify 3.1.3 is coherent and green.
2. Phase 1: build wheel + sdist, pass `test_packaging.py`.
3. Phase 2: clean-machine `uvx` stdio smoke test of all 5 tools (catch any warmup deadlock).
4. Phase 3: (human-gated) `twine upload` 3.1.3 to PyPI.
5. Phase 4: verify `uvx qai-consultant-mcp` from PyPI now serves 3.1.3.
6. Phase 5: submit to MCP directories (Anthropic registry first).
7. Phase 6: README + demo GIF so click-throughs convert.

The one hard rule: **nothing gets listed anywhere until PyPI serves 3.1.3.**
