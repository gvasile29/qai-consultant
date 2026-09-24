# Changelog

All notable changes to QAI Consultant are documented in this file, in
end-user terms. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [3.6.2] - 2026-09-24

### Changed
- The primary AI model is now Mistral's Ministral 14B (`ministral-14b-2512`) instead of Mistral Small. On Mistral's free plan, Mistral Small (and Medium) had been rejecting every request with "rate limit exceeded" since 2026-09-22 even at near-zero usage, so every document was actually being written by the free backup provider. Ministral 14B was chosen by running the real Risk Register, Test Strategy and Test Plan prompts, on two sample projects, through every model available on the free plan: it was the only one that completed every section, got its effort arithmetic right and did not invent facts about the project.
- Generated documents may now be up to 6,500 tokens long (was 4,000). At 4,000, every Risk Register was cut off before its final sections, on both the new primary model and the backup; the longest complete document measured was about 5,450 tokens. Generation can take somewhat longer as a result.

### Fixed
- The Risk Matrix could be silently ignored when the AI wrote its table header in bold (`| **Risk ID** | ...`), which Ministral 14B does. When that happened, the Risk Ledger table and the Executive Readout came out empty and the effort estimate added no risk buffer. Bold headers are now recognized, including in the MCP server's `estimate_qa_effort` tool.
- The nightly live check of the Mistral connection passed even while Mistral was rejecting every request, because the app silently switched to the backup provider, so the outage went unnoticed for two days. The check now disables the backup and fails whenever Mistral itself does not answer. The nightly check of the backup provider now retries for about 45 seconds when a free model is briefly overloaded, instead of failing on a momentary blip; a lasting outage still fails.

## [3.6.1] - 2026-09-23

### Changed
- The backup AI provider (used when Mistral is unavailable) now runs only on OpenRouter's free models, in a fallback chain: NVIDIA Nemotron 3 Super, then Z.ai GLM 5.2. If the first is rate-limited or removed, the second answers automatically. Previously the backup used a paid model on an account with no credits, which accrued charges and would eventually have stopped working. Chosen by running the real Risk Register prompt through 5 free candidates; two were rejected (upstream rate limits, empty output from hidden reasoning). OpenRouter's free auto-router was also tried as a last resort and rejected: in a full end-to-end run it sent the Risk Register to a content-safety classifier, which returned "User Safety: safe" instead of a document.
- Free models are much less reliable than the primary provider (they are often overloaded or rate-limited, and the free tier allows about 12 full generations a day), so the backup should be treated as best-effort.
- The "You are interacting with an AI system" notice now also warns that submitted text is sent to third-party AI providers that may log it and use it for training, and asks users not to enter confidential or personal data.

### Fixed
- An AI response with no text was silently saved as an empty document and the stage marked as failed with no explanation (seen live: a free model spent its whole output budget on hidden reasoning). An empty response from the primary provider now falls back to the backup; an empty response from the backup shows a clear "empty response — please retry" error.
- A streamed response from the backup provider could fail on keep-alive chunks that carry no content; those are now skipped.
- When the backup provider returned an error inside a normal-looking response (e.g. "Upstream error from Nvidia: Service temporarily overloaded"), users saw a cryptic "'NoneType' object is not subscriptable" message; the provider's own error is now shown. The "both providers unavailable" message no longer tells users to check API keys or `.env` files, which visitors of the hosted app can't do — it now says the AI providers are temporarily unavailable and to try again in a few minutes, and the operator hint (check the Mistral plan, OpenRouter quota, Streamlit secrets) goes to the server log instead.

## [3.6.0] - 2026-09-23

Public-app protection and an at-a-glance summary, from the external audit (`docs/audits/2026-09-23-external-audit.md`).

### Added
- **Executive Readout** above the Risk Register / Effort / Strategy / Test Plan tabs: overall risk level with a count per severity, the QA effort range, team capacity against the expected effort, the estimate's confidence, and the top 3 risks to address first (by the Risk Register's own priority). Built directly from the generated Risk Matrix and the deterministic effort numbers — no extra AI call, and nothing that isn't already in the four documents.
- **Daily generation limits** on the public app. The existing 3-runs-per-session cap reset whenever a visitor opened a new tab; two limits now persist across sessions: a global daily cap for all users (default 100 runs) and a per-visitor daily cap (default 10). Both reset at 00:00 UTC. Visitor IPs are never stored — only a date-salted hash, which can't be linked across days. If the limit service is unreachable, generation is still allowed. Self-hosters can change the limits with the optional `QAI_GLOBAL_DAILY_RUN_LIMIT` / `QAI_CLIENT_DAILY_RUN_LIMIT` settings (see `.env.example`).

## [3.5.4] - 2026-09-23

Reliability fixes from an external audit (`docs/audits/2026-09-23-external-audit.md`).

### Fixed
- Generated documents could show their opening section twice. If the primary LLM provider (Mistral) dropped the connection partway through a streamed Risk Register, Test Strategy, or Test Plan, the app restarted the whole document on the fallback provider (OpenRouter) and appended it after the partial text already on screen. Fallback now happens only if the primary fails before producing any text; a mid-response failure shows a clear "interrupted, please retry" error instead.
- The Effort Estimation's risk buffer was inflated for almost every project. It counted how often words like "critical" or "| high" appeared anywhere in the Risk Register — including risk descriptions, prose, and the Likelihood/Impact columns — so even a two-risk register hit the 35% cap. It now counts one entry per row of the Risk Matrix table, by its Risk Level. If the table can't be read, the standard 15% default applies.
- The estimate's confidence score penalized precise answers as "vague". Answers containing "na" anywhere in a word (e.g. "functional safety", "financial regulations") were scored as vague, and "None" / "N/A" (no compliance requirements, no existing automation) were treated the same as "unknown". Vague-answer keywords now match whole words only, and "None" / "N/A" count as specific answers. This also applies to the MCP `estimate_qa_effort` tool.

## [3.5.3] - 2026-09-21

### Changed
- `qai-consultant-mcp`'s local knowledge-base index (`local_index.py`) now uses `fastembed` (ONNX Runtime) instead of `sentence-transformers`/`torch` for embeddings. This removes the single largest contributor to the package's cold-start time — the root cause behind the v3.3.1/v3.4.4/v3.5.1 dependency-pinning incidents, all of which were fixed by adding more pinning rigor around this cost rather than addressing it directly. Retrieval quality is unchanged (`evals/local_index_parity.py`: recall@5=0.91, MRR=0.86, identical to the previous backend); cold import time is roughly 3x faster.
- `pyproject.toml`'s dependency list shrank from ~99 to a much smaller resolved set with `torch`, `sentence-transformers`, `langchain-community`, and their transitive chains (`scikit-learn`, `scipy`, `networkx`, `langchain-core`/`-classic`/`-protocol`/`-text-splitters`, `langsmith`) removed.
- Removed the weekly dependency-drift-canary workflow (`.github/workflows/dependency-drift-check.yml`) — no longer justified at the smaller dependency scale; re-run `uv pip compile` by hand before each MCP release instead.

### Notes
- The Streamlit app / CLI (`agent.py`, `ingest.py`, `requirements.txt`) are unaffected — they keep using `sentence-transformers`/`torch` via the Pinecone-backed RAG path, a separate system with no `uvx` cold-start constraint.

## [3.5.2] - 2026-09-15

### Fixed
- `qai-consultant-mcp==3.5.1` (published earlier the same day) could not be
  installed by any real `uvx`/`pip` consumer — `uv`/`pip` reported "no
  version of torch==2.13.0+cpu" and refused to resolve the package at all.
  Root cause: the weekly Dependency Drift Canary's automated pin
  regeneration correctly resolved `torch` against this repo's own scoped
  `[tool.uv.sources]` PyTorch-CPU index (a project-local `uv` setting) and
  baked the resulting `torch==2.13.0+cpu` pin into the published package's
  dependency list — but that `[tool.uv.*]` config is never distributed to a
  downstream consumer's `uvx qai-consultant-mcp`, which only ever resolves
  against plain PyPI. Plain PyPI has no `+cpu`-tagged torch build, so every
  fresh install failed outright, immediately, for every platform except
  macOS. Caught within minutes of the 3.5.1 publish via a real
  `uvx --from qai-consultant-mcp==3.5.1 ...` smoke test run from a neutral
  directory (not run before 3.5.1's publish). **3.5.1 has been yanked on
  PyPI** (still installable if explicitly pinned, but no longer selected by
  a plain `uvx qai-consultant-mcp`/`pip install qai-consultant-mcp`).
  Fixed by reverting `torch` to a plain `torch==2.13.0` pin (matching the
  last known-working 3.4.4) and removing the `[tool.uv.sources]`/
  `[[tool.uv.index]]` scoped-index block entirely, so the pin resolves
  identically for local project tooling and for real consumers — closing
  the gap for good rather than just for this one pin. See the new
  `CLAUDE.md` gotcha for the full incident writeup.

## [3.5.1] - 2026-09-15

### Fixed
- QA Maturity Assessment's deterministic scoring missed evidence described in
  paraphrased wording rather than the exact keyword the rubric expected —
  found via a live browser QA pass on the deployed app. Two concrete gaps
  fixed in `maturity_core.py`: `requirement_traceability` only recognized a
  ticket-ID pattern (`REQ-123`, `JIRA-42`, ...), missing a prose description
  like "traceability from requirements to test cases and defects"; and Test
  Monitoring and Control's `progress_tracking` check only matched "defect
  tracking"/"status report", missing phrasing like "weekly triage of
  defects" or "pass rate". Also tightened the narrative-generation prompt so
  it stops recommending "establish X" for a whole process area when that
  area already has partial evidence (score > 0) — it now names the specific
  missing check instead. This release also marks the first time the v3.5.0
  QA Maturity Assessment tool (`assess_qa_maturity`) reaches the published
  MCP package — the previous release cut v3.5.0 in the repo but never
  completed the PyPI publish step.

## [3.5.0] - 2026-09-09

### Added
- **QA Maturity Assessment** (`assess_qa_maturity`) — a deterministic, dependency-free process-maturity signal, closing the gap left open when this tool was deferred in v3.1 (see `MCP_PLAN.md` §2). Scores 10 TMMi process areas (Level 2 Managed + Level 3 Defined) from a free-text process description or a pasted existing document, and returns an *informal, indicative* TMMi level (1-3 — never a certified 4 or 5, per TMMi's own no-skip rule). When the description signals an AI/ML system, also scores 7 EU AI Act Articles 9-15 readiness checks; otherwise that dimension is omitted rather than falsely scored. Available as:
  - an MCP tool (`assess_qa_maturity`, deterministic-only, no LLM)
  - a Streamlit mode ("📈 Assess QA Maturity", with an LLM narrative + PDF/.md download, mirroring Document Review)
  - a CLI flag (`--maturity PATH`)
- New tier-1 eval `maturity_integrity` (level ordering, no-skip rule, EU AI Act gating, determinism, insufficient-content handling), wired into the existing `evals-det` CI gate.

## [3.4.4] - 2026-08-31

### Fixed
- `qai-consultant-mcp` could once again silently fail to attach in Claude
  Desktop, even on a machine that had connected successfully before — a
  different trigger from the v3.1.5/v3.1.6/v3.3.1 incidents, but the same
  underlying class of problem. Root cause: v3.3.1 exact-pinned only the 6
  *direct* runtime dependencies; every dependency those pull in transitively
  (scipy, scikit-learn, numpy, transformers, and ~85 others) stayed
  unpinned. On 2026-08-31, `scikit-learn` (pulled in by `sentence-transformers`)
  resolved to a scipy release `uv` hadn't cached yet; the resulting 35MB
  download, stacked on the already-known ~20-25s embedding-import cost,
  pushed a cold start past Claude Desktop's ~60s `initialize` timeout. Worse,
  the client's cancel-on-timeout killed the install mid-extraction before the
  wheel could be promoted into the permanent `uv` cache, so every subsequent
  launch repeated the exact same failed download — a self-sustaining failure
  loop that a simple retry or a Claude Desktop restart could not escape.
  Fixed by exact-pinning the *entire* resolved dependency tree (~99 entries,
  including per-Python-version variants for packages like numpy/scipy/
  scikit-learn that need a different exact version on 3.10 vs. 3.11 vs. 3.12),
  generated via `uv pip compile --universal` and embedded directly in
  `pyproject.toml`'s `dependencies` — the only place a pin can reach
  `uvx qai-consultant-mcp`, since a committed `uv.lock` never travels with the
  published PyPI package. `tests/test_packaging.py`'s exact-pin guard now
  accepts a trailing PEP 508 environment marker after the `==` pin, needed for
  those per-Python-version entries. Closes the "residual, not closed" gap
  flagged in the v3.3.1 entry below.

## [3.4.3] - 2026-08-18

### Changed
- Output screens are now part of the "Power-On Sequence" visual redesign
  too (Phase 3 of 3, the final phase): the Test Strategy results view
  (Risk Register / Effort Estimate / Test Strategy / Test Plan tabs) now
  shows a live status readout tracking which of the 4 stages is
  pending, in progress, or done, its score/summary tiles animate in
  once on first view, and buttons/tabs/expanders get the same hover
  feedback the interactive flow already has. The document review
  screen (upload-then-score an existing QA document) gets the same
  treatment: its intake form sits in a styled input tray, and its
  results tiles animate in the same way. The landing screen also picks
  up a small addendum — a labeled "What you get in ~2 minutes" section
  above its deliverable cards and stat tiles.
- With this phase, the full 3-phase "Power-On Sequence" redesign
  (landing screen → interactive flow → output screens) is complete
  across the whole app.

## [3.4.2] - 2026-08-17

### Changed
- Interactive flow is now part of the "Power-On Sequence" visual
  redesign too (Phase 2 of 3): the Project Discovery dialogue shows an
  animated progress bar in place of Streamlit's default, the review
  screen presents your project summary as tiles with a one-time
  entrance animation on first visit instead of a plain code block, and
  the sidebar gets subtle hover feedback on buttons and expanders.
  Only the output screens (Risk Register, Effort Estimate, Test
  Strategy, Test Plan) are still native Streamlit styling; a fuller
  changelog entry lands once that final phase ships.

## [3.4.1] - 2026-08-06

### Added
- Distribution links surfaced in the app itself: the sidebar's "Use QAI
  in your AI tools (MCP)" panel now links to the official MCP registry,
  Glama, and Awesome MCP Servers — previously only in `README.md`/
  `README_MCP.md`.

### Changed
- Landing page has started a visual redesign ("Power-On Sequence"): the
  intro screen — the one screen the v3.4.0 "Calibration Bench" redesign
  left unstyled — now opens with a one-shot entrance sequence (headline
  reveal, three progress gauges, a standards checklist, fading-in "How
  it works" cards), built from the existing Calibration Bench colors
  and fonts. This is the first of three planned phases (interactive
  flow and output screens are still native Streamlit styling); a fuller
  changelog entry lands once the whole redesign is complete.

## [3.4.0] - 2026-08-05

### Changed
- App visual redesign ("Calibration Bench"): a token-based color and
  typography system (IBM Plex fonts, embedded locally — no font CDN
  call) and a reusable "Signal Ledger" score/severity component,
  applied across the app. QA Document Review dimension scores, the
  Effort Estimation confidence score, Test Results Analysis metrics
  (runs, pass rate, flaky/ever-failing counts), and the Risk Register
  now render as color-coded ledger cards instead of plain markdown.
  The Risk Register table specifically required a new deterministic
  parser (severity data previously lived only inside free-text LLM
  output) so it can be re-rendered with heat-mapped severity swatches.
  The 11-question Project Discovery intake now presents each question
  in its own numbered card. This is a visual change only — no
  interaction flow, session behavior, or PDF export content changed.
  Colors meet WCAG AA contrast in both light and dark themes.

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
