# Changelog

All notable changes to QAI Consultant are documented in this file, in
end-user terms. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

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
  bound is reintroduced. Note this closes the most common trigger, not
  every possible one: those six packages' own dependencies aren't pinned
  and could in principle still force a reinstall. Design rationale:
  `docs/superpowers/specs/2026-07-30-mcp-dependency-pinning-design.md`.

## [3.3.0] - 2026-07-29

### Added
- Adopted the EU's official "Fully AI-Generated" icon from the Code of
  Practice on Transparency of AI-Generated Content (supporting AI Act
  Article 50(4)) as a visual reinforcement of the existing text/metadata AI
  disclosure (v2.5.2/v2.6). The icon now appears in the Streamlit sidebar
  (theme-aware, above the existing "you are interacting with an AI system"
  notice) and in every generated document's PDF export (Risk Register,
  Effort Estimation, Test Strategy, Test Plan, QA Document Quality Review).
  Markdown `.md` downloads, the CLI, and the MCP server are unaffected —
  they keep the existing text-only disclosure, since none of those are
  rendered surfaces for an image. Design rationale:
  `docs/superpowers/specs/2026-07-29-eu-ai-icon-adoption-design.md`.

## [3.1.6] - 2026-07-29

### Fixed
- `qai-consultant-mcp` failed to attach in Claude Desktop with "could not attach" (a client-side handshake timeout, not a crash) on a cold cache. The server used to force a full embedding of the entire knowledge base — every chunk of every KB document — before it could respond to the very first `initialize` message, which could take longer than a client's connection timeout on a fresh install. The server now does a minimal one-time warmup of the embedding model before responding to `initialize`, and builds the full knowledge base index lazily on the first real request instead. Verified with a real subprocess-and-piped-stdio test (the same way Claude Desktop/Claude Code actually launch it): no hang on the first real tool call under a cold cache. Separately, importing the underlying ML libraries (`sentence-transformers`/`torch`) still takes roughly 20-25 seconds on a typical machine regardless of this fix — a deeper optimization (a lighter embedding backend) is tracked as a future improvement, not part of this release.

## [3.1.5] - 2026-07-29

### Fixed
- `qai-consultant-mcp` failed to start for every new install (`ModuleNotFoundError: No module named 'mcp.server.fastmcp'`) after the upstream `mcp` SDK released a breaking 2.0.0 that removed the `FastMCP` module the server is built on. `mcp` was pinned to `>=1.8.0,<2.0.0` in `pyproject.toml`; this release republishes the package with that pin in effect, so `uvx qai-consultant-mcp` resolves a working `mcp` version again. The same unbounded floor also broke `tests/test_mcp_server.py` in CI; the pin was applied there too.

## [3.1.4] - 2026-07-23

### Changed
- Added the `mcp-name: io.github.gvasile29/qai-consultant-mcp` marker to `README_MCP.md` (the package's PyPI long description), a prerequisite for listing `qai-consultant-mcp` in the official Anthropic MCP registry — no functional change.

## [3.1.3] - 2026-07-21

### Fixed
- The sidebar visit counter's label was in Romanian ("vizite") while the rest of the app's UI copy is in English — it now reads "visits" to match.

## [3.1.2] - 2026-07-21

### Fixed
- The sidebar visit counter (introduced in 3.1.1) never actually incremented — Pinecone rejects the all-zero placeholder vector it used internally, so every update silently failed and the counter never appeared. It now works correctly.

## [3.1.1] - 2026-07-21

### Added
- A visit counter is now shown in the sidebar, tracking the total number of times the app has been opened over time.

## [3.1.0] - 2026-07-20

### Added
- QA Document Quality Review: paste or upload an existing Test Plan, Test Strategy, or test case list to get an instant, deterministic 0–100 quality score across six ISTQB/IEEE-grounded dimensions (structure, objectives & scope, entry/exit criteria, traceability, measurability, risk coverage), plus a findings list explaining exactly what's missing or weak — with an optional AI-written narrative review grounded in the knowledge base on top. Available in the web app ("Review an existing QA document"), the CLI (`--review path/to/doc.md`), and the MCP server (`review_qa_document` tool) for use directly inside Claude Code, Claude Desktop, or claude.ai.
- Test Results Analysis: attach your own JUnit XML or CSV test execution reports and QAI Consultant will surface flaky tests, always-failing tests, the slowest tests, and clustered failure patterns — all computed deterministically, no AI guesswork. When attached before generating a Test Strategy, the Risk Register is now grounded in this real execution data (clearly cited as `[Execution Data]`) instead of only the project-intake interview. Available in the web app (an "Attach test execution results" option before generating), the CLI (`--results run1.xml run2.xml`), and the MCP server (`analyze_test_results` tool).

## [3.0.0] - 2026-07-15

### Added
- QAI Consultant is now also available as a local, keyless MCP server (`qai-consultant-mcp`) — call it directly from Claude Code, Claude Desktop, or claude.ai with `uvx qai-consultant-mcp`, no API keys required. It exposes standards-grounded knowledge retrieval and deterministic PERT-based QA effort estimation as tools, plus prompts for the project-intake interview and Risk Register / Test Strategy / Test Plan structures, so any MCP client can ground its own QA planning in the same knowledge base this app uses.
- A "Use QAI in your AI tools (MCP)" panel in the app sidebar, with a one-time banner pointing to it.
- Usage telemetry for the MCP server is available but off by default — it only activates if you explicitly opt in, and never includes your query text or project details.
- Every generated document now also carries a machine-readable "AI-generated" marking (in addition to the existing visible label) — both in the Markdown file's metadata and in the PDF's document properties — ahead of the EU AI Act's Article 50(2) deadline for existing systems (2026-12-02).

### Changed
- Internal refactor: the knowledge-base configuration and the deterministic effort-estimation math now live in their own modules, shared between the web app and the new MCP server, so both stay in sync automatically. No user-facing behavior changed.

## [2.6.0] - 2026-07-14

### Added
- Expanded the knowledge base with a new EU AI Act reference document covering risk tiers, provider and deployer obligations, transparency obligations, testing implications for high-risk systems, conformity assessment, and key deadlines — so generated strategies can now be grounded in the Act when relevant to a project.

## [2.5.2] - 2026-07-14

### Added
- A clear "you are interacting with an AI system" notice now appears in the app sidebar, ahead of the EU AI Act's transparency requirements taking effect on 2026-08-02.
- Every generated document (Risk Register, Effort Estimation, Test Strategy, Test Plan) now carries a visible "AI-generated content" label in its Markdown and PDF versions, noting that it hasn't been reviewed by a human and needs sign-off from a qualified QA professional before use.

## [2.5.1] - 2026-07-08

### Added
- Expanded the knowledge base with a new "audit & evaluation" collection: process/test maturity models, audit methodology, security and regulatory compliance audits, and real-world case studies of process failures — so generated strategies can better anticipate what an audit will actually check for.

### Fixed
- Fixed a knowledge-base loading bug on Windows where several documents either failed to load entirely or were loaded with corrupted text (garbled special characters) due to an incorrect text encoding. All knowledge-base content is now loaded and indexed correctly.

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
