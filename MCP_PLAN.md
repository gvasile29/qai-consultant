# MCP Server Implementation Plan (v3.x)

**Status:** approved plan, implementation-ready
**Created:** 2026-07-14 (hardened same day: pinned contracts, build order, telemetry)
**Owner:** Gabi
**Supersedes:** former roadmap items v2.1 (HuggingFace KB), v2.2 (Community knowledge), v3.0 (Hosted version), v4.0 (Multi-LLM). All removed; their useful intent is absorbed here (hosted becomes v3.2 remote MCP; multi-LLM becomes irrelevant since the client brings its own LLM).

---

## 1. Vision: the MCP lens

QAI Consultant today is a one-shot document generator. The MCP server turns its real assets into tools any MCP client (Claude Code, Claude Desktop, claude.ai) can call inside a full AI SDLC workflow.

The lens that shapes every decision below: **the client LLM is stronger than our internal LLM.** So we never expose "generate a document" tools that internally call mistral-small; that chain is absurd. What we expose is what the client LLM cannot do alone:

1. **Grounding:** curated QA knowledge base retrieval (ISTQB/OWASP/IEEE/ISO summaries, methodologies, audit models, case studies).
2. **Determinism:** the PERT effort estimator with multipliers and confidence scoring. LLMs are bad at this arithmetic; our code is not.
3. **Process:** validated QA Architect workflows (the 11-question interview, Risk Register / Test Strategy / Test Plan structures) exposed as MCP prompts, not tools.

Explicitly NOT exposed: `ask()`, `ask_streaming()`, full document generation, the feedback loop. Those stay in Streamlit/CLI for users without an MCP client.

## 2. Locked decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| KB retrieval | Fully local in-memory index, zero API keys | Reuses the proven `evals/rag.py` pattern; one-step install; Pinecone stays Streamlit-only |
| Transport | stdio first (v3.0), remote Streamable HTTP later (v3.2) | Ship fast, validate demand before paying for hosting/auth |
| Repository | Same repo, no fork | See section 6; isolation is architectural, not organizational |
| Old roadmap | Deleted, not parked | Clean roadmap; intent absorbed where still relevant |
| Internal LLM in MCP path | Never | The client brings the reasoning; we bring grounding + determinism |
| PyPI package name | `qai-consultant-mcp` | Self-descriptive in client configs; does not squat the app's name |
| Telemetry | Opt-in (`QAI_TELEMETRY=1`) + passive stats | MCP community punishes silent phone-home; passive stats cost nothing |
| Telemetry backend | PostHog free tier | Event API + dashboards for zero effort; public project key is safe to embed |
| Python floor | >= 3.10 | Matches type-hint style already used (`str | None`) |

## 3. Tool surface (v3.0): pinned contracts

These signatures and schemas are the contract for the coding agent. Deviations require updating this document first.

### Tools

**`retrieve_qa_knowledge(query: str, category: str | None = None, k: int = 5)`**
Returns `{"chunks": [{"source": str, "category": str, "text": str, "score": float}], "kb_version": str}`.
`source` is the KB-relative path (e.g. `methodologies/Risk_Based_Testing.md`); `category` one of `Standard`, `Methodology`, `Article`, `Expert Knowledge`, `Audit/Evaluation` (the `ingest.py` mapping); `score` is cosine similarity; `kb_version` is the KB content hash so callers can detect drift. Invalid `category` returns the structured error below listing the valid values; it does not raise. `k` clamped to [1, 20].

**`list_kb_sources()`**
Returns `{"categories": {category: [{"source": str, "title": str}]}, "kb_version": str, "doc_count": int}`. `title` is the first `# ` heading or the filename.

**`estimate_qa_effort(project_name, project_description, project_type, tech_stack, team_qa_size, team_dev_size, timeline, methodology, known_risks, existing_automation, compliance_requirements, additional_context="")`**
All parameters `str`, mirroring the `ProjectContext` dataclass. Inputs are validated with the existing `InputValidator` rules (`dialogue.py`); validation failures return `{"error": "validation", "fields": {field: message}}`, never a crash. Success returns `dataclasses.asdict(EstimationData)` (JSON-safe: multiplier tuples become 2-element lists), i.e. the full deterministic result: baseline (`baseline_effort_min/max`, `project_duration_days`, detected type/methodology), `multipliers` + `total_multiplier`, `adjusted_effort_min/max`, `pert_activities` + PERT totals (`optimistic/most_likely/pessimistic/expected/sd`), capacity (`qa_team_size`, `available_person_days`, `utilization_rate`, `capacity_gap`), `risk_buffer_days`, `final_effort_min/max`, and `confidence_level` + `confidence_score` (0-100). No narrative: the client LLM writes its own from the numbers.

### Prompts (MCP prompts, not tools)

- `qa_project_interview`: the 11-question context-gathering dialogue as an elicitation template
- `risk_register_structure`: the Risk Register format + grounding instructions
- `test_strategy_structure`: the Test Strategy format
- `test_plan_structure`: the Test Plan format (IEEE 829 aligned)

Prompt texts are extracted from the existing prompt builders' structural sections (not the LLM-call plumbing) and instruct the client to ground sections in `retrieve_qa_knowledge` output with `[Source N]` citations, matching the app's citation convention that `evals/rag.py` already measures. Each document-structure prompt also instructs the client to include an "AI-generated" label in the produced document (see section 12: this eases our users' own EU AI Act Article 50 obligations).

### Error contract (all tools)

Tools never raise into the protocol. Failures return `{"error": "<kind>", "message": str, ...}` with `kind` in `{"validation", "invalid_argument", "index_unavailable"}`. Index build failure at server start is the one fail-fast case: exit non-zero with a clear stderr message (a server with no KB is useless).

## 4. Architecture

```
MCP client (Claude Code / Desktop / claude.ai)
  -> src/mcp_server.py        FastMCP (official `mcp` Python SDK), stdio; 3 tools + 4 prompts
       -> src/local_index.py  chunked in-memory cosine index (new)
       -> src/kb_config.py    dependency-free shared constants (new)
       -> effort core         deterministic part of EffortEstimator (refactored)
       -> src/telemetry.py    opt-in usage events (new)
```

**New: `src/kb_config.py` (dependency-free, no third-party imports)**
Single source of truth for: `EMBEDDING_MODEL`, `CHUNK_SIZE = 1000`, `CHUNK_OVERLAP = 200`, the folder-to-category mapping, and `get_source_category(path)`. Required because the MCP path cannot import the existing homes of these values: `agent.py` pulls Pinecone and `ingest.py` imports `pinecone` at module level (line 29). `agent.py`, `ingest.py`, and `evals/rag.py` are updated to import from it; a config regression test (same pattern as `test_performance_config.py`) pins the values.

**New: `src/local_index.py`**
- Same embedding model as the app, via `kb_config.EMBEDDING_MODEL` (cannot drift).
- Indexes `knowledge_base/**/*.md` only; chunks at 1000/200 like `ingest.py` (deliberately unlike `evals/rag.py`'s doc-level 4000-char index, which is adequate for eval labels; document the difference in both files).
- Embeddings cached to disk, keyed by a content hash of the KB files, so server start is fast after the first run and self-invalidates when the KB changes. Cache path via `platformdirs` (Windows `%LOCALAPPDATA%`, Linux `~/.cache`); corrupted or unreadable cache falls back to a rebuild, never a crash.
- Category tag derived from folder path via `kb_config.get_source_category`.

**Refactor: `EffortEstimator` deterministic core**
`estimate(context, risk_register)` currently requires a `QAIAgent` (used only for the narrative sections). Extract `compute_estimation(context, risk_register="") -> EstimationData` (module-level function, no agent, no LLM); `EffortEstimator.estimate()` delegates to it and adds the narrative on top. Extract-and-delegate, not reimplementation: all existing tests (`test_effort_estimator.py`, `test_confidence_v06.py`) must pass unchanged.

**New: `src/telemetry.py`** (design in section 7)

**Untouched:** `app.py` (except the announcement panel), `cli.py`, Pinecone ingestion, `LLMClient`. The MCP path imports none of: `pinecone`, `mistralai`/OpenRouter code paths, Streamlit.

## 5. Content and licensing gate (blocks PyPI publish)

The package ships only `.md` files we authored (standards summaries, methodologies, evaluation_audit, articles, expert_knowledge) plus OWASP Top 10 MD (verify CC BY-SA attribution requirements and include attribution). The ISTQB and OWASP PDFs are **excluded** from the distributed package: redistribution rights are unclear, and the local index only reads `.md` anyway. Before first publish: review every shipped `.md` for third-party text lifted verbatim. The gate is automated: a packaging test asserts the built wheel contains zero `.pdf` files (step 8).

## 6. Packaging and distribution

- **Same repo, no fork.** The MCP server lives in this repository: it must reuse `knowledge_base/`, the deterministic effort core, the embedding config, and the eval gates. A separate repo would duplicate the KB and estimator and guarantee drift, making the parity gates in section 8 meaningless. Isolation is architectural, not organizational: `app.py`/`cli.py` never import the MCP modules, the MCP path never imports Pinecone/LLM code, and the only shared-code changes (kb_config extraction, effort-core refactor) are guarded by the existing test suites. `pyproject.toml` controls exactly what ships to PyPI; Streamlit Cloud keeps deploying `app.py` from the same repo, unaffected.
- `pyproject.toml` at repo root: name `qai-consultant-mcp`, console entry point `qai-consultant-mcp = "src.mcp_server:main"` (exact module path settled at implementation), package data = whitelisted KB `.md` files, `requires-python = ">=3.10"`.
- Target install experience: `uvx qai-consultant-mcp` or one `claude mcp add` line; zero API keys, zero config.
- Client config snippets in README/INSTALL.md for Claude Desktop (`claude_desktop_config.json`), Claude Code (`claude mcp add`), and claude.ai (v3.2, once remote).
- **Known risk:** `sentence-transformers` pulls torch (heavy download, slow cold start under `uvx`). v3.0 accepts this for embedding parity with the app. If install friction proves real, evaluate `fastembed` (ONNX `all-MiniLM-L6-v2`) as a v3.0.x optimization; requires an embedding-parity eval before switching.
- **Decided 2026-07-15:** apply the same CPU-only-torch pattern from `requirements.txt` (`--extra-index-url https://download.pytorch.org/whl/cpu` + a root `uv.toml` with `index-strategy = "unsafe-best-match"`) directly in `pyproject.toml`/the packaging config at step 8, rather than rediscovering the same "No solution found when resolving dependencies" `uv` deadlock (PyTorch's CPU index mirrors an older `requests`, conflicting with `langchain-community`'s floor). Verify locally with `uv pip install --dry-run` against the built package before first publish, same as the app-side fix.

## 7. Usage monitoring

Two layers, both from day one of v3.0:

**Passive (zero code, zero consent needed):** PyPI download counts (pypistats.org / pepy.tech), GitHub stars + traffic, and Streamlit announcement-panel views if trivially countable. Reviewed manually; answers "is anyone installing this?".

**Opt-in telemetry (`src/telemetry.py`):** answers "what do the people who opted in actually use?".
- Disabled by default. Enabled only when `QAI_TELEMETRY=1`. README and the server's startup stderr line mention it once, politely, with a link to exactly what is sent.
- Backend: PostHog free tier via plain `https` capture call (public project API key embedded; that is its designed use).
- Events: `server_start` and `tool_called`. Properties: tool name, success flag, duration ms, `k`/`category` for retrieval, package version, Python minor version, OS family, and a random anonymous install id (UUID stored next to the index cache). **Never sent:** query text, project fields, KB content, file paths, hostnames, or anything free-text.
- Engineering contract: fire-and-forget from a daemon thread, 2s network timeout, every exception swallowed (telemetry must never break or slow a tool call), no retries, no buffering to disk.
- v3.2's remote server adds real server-side metrics; the opt-in client telemetry stays as-is.

## 8. Testing (every step lands with its own tests)

Standing rule from CLAUDE.md applies: run relevant tests after every change; new tests for every new feature. Specific suites:

| Suite | Covers |
|-------|--------|
| `tests/test_kb_config.py` | Pinned values (model name, 1000/200, category map); `agent.py`/`ingest.py`/`evals` import from it (drift guard) |
| `tests/test_effort_core.py` | `compute_estimation` parity with golden inputs from `evals/golden.jsonl`; no agent/LLM import in its module graph |
| `tests/test_local_index.py` | Chunk counts and boundaries, category filter, cache round-trip, hash invalidation on KB edit, corrupted-cache rebuild, k clamping |
| `tests/test_telemetry.py` | No-op when env unset; event emitted when set (mocked transport); network failure fully silent; payload contains no free-text fields |
| `tests/test_mcp_server.py` | Via the MCP SDK's in-memory client: tools + prompts registered with expected schemas; each tool happy path; invalid category error contract; `estimate_qa_effort` output equals `compute_estimation` output; validation-error shape |
| `tests/test_packaging.py` | Built wheel contains whitelisted `.md`s and zero `.pdf`s (licensing gate); entry point resolves |
| `tests/test_app_mcp_banner.py` | Streamlit announcement panel + one-time banner (patterns from `test_app_feedback_loop.py`) |
| `tests/test_ai_act_marking.py` | AI-generated marking present in every document save path (MD front matter + footer) and in PDF metadata; survives filename sanitization and PDF conversion (section 12) |

Evals extension (release gate, not tests): run `context_recall@k` and `context_precision_mrr` from `evals/rag_golden.jsonl` against the **served** `LocalIndex` (not just the eval index), with floor rows in `evals/thresholds.py`. This is the retrieval-parity gate: the index users get must be at least as good as the one we measure. Plus a CI protocol smoke test: start the server, list tools/prompts, call one tool.

## 9. Build order (the script for the coding agent)

One step = one commit (or small PR). Each step names its done-criteria; do not start step N+1 with step N red. Steps 1-2 touch shared code and are the only risky ones; everything after is additive.

1. **`src/kb_config.py` extraction.** Create module; rewire `agent.py`, `ingest.py`, `evals/rag.py` imports. Done: full existing test suite green (baseline: 104 passed, 7 pre-existing fixture errors), `test_kb_config.py` green, `python -m evals.run --det` green.
2. **Effort core refactor.** `compute_estimation()` extracted; `EffortEstimator.estimate()` delegates. Done: `test_effort_estimator.py` + `test_confidence_v06.py` pass **unchanged**, `test_effort_core.py` green, `python -m evals.estimate_integrity` green.
3. **`src/local_index.py`.** Done: `test_local_index.py` green; manual sanity: a `Risk_Based_Testing` query returns that doc in top-3.
4. **Evals retrieval-parity gate.** Served-index recall@k / MRR over `rag_golden.jsonl` + thresholds rows. Done: `python -m evals.rag` (or new runner flag) green against `LocalIndex`.
5. **`src/telemetry.py`.** Done: `test_telemetry.py` green.
6. **`src/mcp_server.py`.** Tools, prompts, telemetry hooks, fail-fast startup. Done: `test_mcp_server.py` green; manual: `claude mcp add` locally, call all 3 tools from Claude Code.
7. **Prompts content.** The 4 MCP prompts extracted from existing prompt builders. Done: covered by `test_mcp_server.py` registration + content assertions.
8. **Packaging.** `pyproject.toml`, entry point, package-data whitelist. Done: `test_packaging.py` green; fresh venv + built wheel + smoke test passes on a machine with no `.env`.
9. **Streamlit announcement + AI Act machine-readable marking.** Sidebar panel "Use QAI in your AI tools (MCP)" + one-time banner (v2.5.0 Release Notes pattern; verify session-state keys against the cleanup-lists gotcha). Machine-readable AI-generated marking in all generated outputs: YAML front matter (`ai_generated: true`, generator name + version, model) in MD saves, document metadata in PDF exports; align label format with the EU Code of Practice on AI-generated content once final (section 12). Done: `test_app_mcp_banner.py` + `test_ai_act_marking.py` green.
10. **Docs + release.** README MCP section (install, config snippets, telemetry/privacy note), INSTALL.md, CHANGELOG, `version.py` 3.0.0, tag + GitHub release, PyPI publish, Streamlit deploy (remember the deploy-lag gotcha: verify the live app, reboot if stale).

## 10. Phases

### v3.0: MCP server MVP (local stdio, keyless)
Scope: everything in section 9.
Acceptance:
- Clean machine, no API keys: `uvx qai-consultant-mcp` works; tools callable from Claude Desktop and Claude Code.
- Served-index retrieval meets the eval floors on `rag_golden.jsonl`.
- `estimate_qa_effort` numbers identical to Streamlit's deterministic core for the golden cases.
- Licensing gate passed (automated wheel check); telemetry provably silent unless opted in.
- Streamlit announcement live in the same release.
- Machine-readable AI-generated marking shipped in all Streamlit/CLI outputs, released before 2026-12-02 (Article 50(2) deadline for pre-August-2026 systems; section 12).

### v3.1: QA maturity audit tool
`assess_qa_maturity(project_description, focus_areas=None)`: retrieval over `evaluation_audit/` and `standards/eu_ai_act/` (v2.6 KB pillar) + a deterministic TMMi-inspired scoring rubric; returns gap summary JSON with cited sources. This is the differentiator (standards-grounded QA audit as a tool); kept out of v3.0 to keep the MVP scope tight.
Acceptance: rubric fully deterministic (same input, same score); every gap cites a KB source.

### v3.2: Remote MCP + distribution push
Hosted Streamable HTTP server connectable from claude.ai (absorbs the old "hosted version" ambition); auth story; MCP registry/directory submissions; server-side usage metrics complementing the opt-in client telemetry.
Acceptance: connectable from claude.ai without local install; listed in at least one public MCP registry.

## 11. Risks and open assumptions

- **Adoption timing:** QA engineers and test managers are late adopters of MCP clients. We accept building 6-12 months early; pioneer positioning is the point.
- **Dependency weight:** torch cold start may hurt the "one command" story (mitigation in section 6).
- **Licensing:** gate in section 5 must pass before any publish; this is the only hard external blocker.
- **Telemetry blind spot:** opt-in means most users are invisible; passive stats + v3.2 server-side metrics compensate. Accepted trade-off for community trust.
- **Parity is tested, not assumed:** eval index vs served index, and Streamlit estimator vs MCP estimator, both have explicit gates.
- **Shared-code risk is front-loaded:** only steps 1-2 touch existing behavior, and both are gated by the full existing suite passing unchanged.
- **Regulatory flux:** the Article 50 Code of Practice and the AI Omnibus grace period (2026-12-02) are near-final but still moving; the marking implementation in step 9 must track the final label format, and section 12 must be re-reviewed when the final Commission guidelines land.

## 12. EU AI Act compliance (self-assessment, 2026-07-14; Omnibus status updated 2026-07-15)

Not legal advice; based on the implementation timeline and the Article 50 practical guide at artificialintelligenceact.eu (May 2026). Re-review when the final Commission guidelines and the Code of Practice on AI-generated content are published.

**Omnibus status update (2026-07-15):** the "provisional agreement, May 2026" framing below is superseded. Independent fact-check research done for the v2.6 KB pillar (`knowledge_base/standards/eu_ai_act/EU_AI_Act_Overview.md`) confirmed the Digital Omnibus on AI was formally **adopted** — European Parliament vote 16 June 2026 (423-57, 174 abstentions), Council final adoption 29 June 2026 — pending only Official Journal publication (expected before 2026-08-02) to enter into force. It is no longer an unresolved proposal. Confirmed changes relevant here: the **2026-12-02** Article 50(2) machine-readable-marking grace period (for systems already on the market before 2026-08-02) is corroborated by the adopted text, not merely this project's working assumption. Full detail and sourcing in the KB doc itself; still re-review this section once Official Journal publication lands and the final Code of Practice on AI-generated content is published.

**Classification.** QAI Consultant (Streamlit/CLI and MCP server) is not an Annex III high-risk system and performs no prohibited practice: minimal-risk AI system with Article 50 transparency obligations. Free public availability in the EU counts as placing on the market, so the provider obligations are ours. The open-source carve-out (Art 2(12)) explicitly does NOT exempt from Article 50.

**Per component:**
- **Streamlit/CLI (generative):** Art 50(2) applies: synthetic text outputs must be marked machine-readable and detectable as AI-generated. Applies 2026-08-02; systems on the market before that date have until **2026-12-02** for the machine-readable marking (AI Omnibus provisional agreement, May 2026). Art 50(1) (inform users they interact with AI) is arguably satisfied by the app's self-presentation as an AI agent, but we add an explicit disclosure line anyway rather than relying on the "obvious to a reasonable user" exception.
- **MCP server (v3.0):** generates no synthetic content: retrieval returns verbatim KB excerpts, the estimator returns deterministic numbers. Art 50(2) marking of generated documents sits with the client that generates them (Claude, etc.). This boundary is a designed compliance property of the MCP lens; document it in the README.
- **Our users:** Art 50(4) (disclosure of AI-generated text published to inform the public) is the deployer's obligation, i.e. theirs, not ours. Our visible labels and the label instruction in the MCP prompts make their compliance easier.
- **AI literacy (Art 4, in force since 2025-02-02):** README/docs state capabilities, limitations, and that outputs require professional QA review before use.
- **Telemetry:** a GDPR question more than an AI Act one; opt-in consent, anonymous install id, no free-text payloads, and a README statement of exactly what is sent keep exposure minimal.

**Actions (all folded into the roadmap):**
1. ✅ **v2.5.2 patch, shipped 2026-07-14 (ahead of the 2026-08-02 deadline):** explicit "you are interacting with an AI system" disclosure in the Streamlit UI + visible "AI-generated" label line in every generated document (MD footer + PDF footer). Implemented as `src/ai_disclosure.py` (`AI_INTERACTION_NOTICE`, `with_ai_footer()`); no architecture impact.
2. **v3.0 step 9, ship before 2026-12-02:** machine-readable marking (YAML front matter in MD, metadata in PDF), tracked by `test_ai_act_marking.py`; align with the standardized EU "AI" label once the Code of Practice finalizes.
3. **v2.6 KB pillar `standards/eu_ai_act/`:** self-authored summaries: risk-tier model, roles and obligations (provider/deployer/importer), Article 50 transparency in practice, Articles 9-15 testing implications for high-risk systems (risk management, data governance, accuracy, robustness, cybersecurity: exactly QAI's domain), conformity assessment + post-market monitoring, timeline. Lands under `standards/` so the existing ingest category mapping needs no change; add `evals/rag_golden.jsonl` cases. Benefits the live app immediately and becomes MCP-served content in v3.0 and audit-tool source in v3.1.
4. **MCP prompts (v3.0):** label instruction in every document-structure prompt (section 3).
5. **v3.1:** AI Act obligations join the maturity-audit sources.
