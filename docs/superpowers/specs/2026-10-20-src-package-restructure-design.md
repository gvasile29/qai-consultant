# Design: restructure `src/` into the `qai_consultant` package

Date: 2026-10-20
Status: design approved in conversation; written spec awaiting review
Depends on: the tests restructure (`chore/restructure-tests`) being merged first

## Goal

`src/` is 40 flat modules (12.4k lines). Group them into a real package by
dependency tier and feature, mirroring the `tests/<level>/<feature>/` layout, so
a contributor can tell from the path what a module is and what it may depend on.

Success criteria:

1. Same behaviour: the full suite passes with the same test count before and after (1025 at time of writing).
2. Every documented command still works: `streamlit run src/app.py`, `python src/cli.py`, `python src/ingest.py`, `python src/mcp_server.py`, and `uvx qai-consultant-mcp`.
3. The keyless guarantee of the MCP wheel is enforced by a test instead of by convention.
4. No `sys.path` manipulation remains in `src/`, `tests/`, `evals/` or `scripts/`.

Non-goals: no behaviour change, no module splitting or merging, no renaming of
public MCP tool names, no dependency changes.

## Decisions (made with the user)

- **Scope includes the PyPI wheel.** Module names and the console entry point change, so this ships as a new release. The release is a separate follow-up PR (suggested version 3.9.0) following the `release-checklist` skill, then PyPI publish and registry sync.
- **Package name:** `qai_consultant`, under `src/`.
- **`src/app.py` stays a real script.** Streamlit re-executes the entry script on every interaction; a shim that only imports a module runs once and freezes the UI. Its helpers move into the package.
- **Absolute imports** everywhere, e.g. `from qai_consultant.core.effort_core import estimate`.

## Layout

Dependency direction is strictly `common` <- `core` <- `mcp` for the wheel tiers. App-side tiers may import any wheel tier, never the reverse.

| Subpackage | Modules (old name -> new path) | In wheel |
|---|---|---|
| `common/` | `version`, `logger`, `kb_config`, `telemetry`, `text_checks` | yes |
| `core/` | `dialogue`, `effort_core`, `review_core`, `results_core`, `maturity_core`, `risk_ledger` | yes |
| `mcp/` | `mcp_server` -> `server`, `prompts`, `local_index` | yes |
| `rag/` | `agent`, `ingest` | no |
| `generation/` | `risk_analyzer`, `strategy_generator`, `test_plan_generator`, `effort_estimator`, `review_generator`, `maturity_generator`, `doc_bundle`, `templates`, `executive_readout` | no |
| `compliance/` | `output_guards`, `ai_disclosure`, `pdf_export`, `source_labels` | no |
| `ui/` | `components`, `theme`, `_theme_fonts`, `kb_manifest` | no |
| `observability/` | `usage_guard`, `visit_counter`, `adoption_metrics` | no |

Verified from the actual import graph (AST scan, 2026-10-20): every wheel module
imports only other wheel modules, and the wheel tiers are acyclic
(`dialogue -> logger`, `effort_core -> dialogue, risk_ledger`,
`telemetry -> kb_config, version`, `maturity_core/review_core -> text_checks`,
`local_index -> kb_config`, `mcp_server -> core + local_index + prompts + telemetry`).

Files in `src/` after the move:

- `app.py`: unchanged location, real Streamlit script, imports from the package.
- `cli.py`, `ingest.py`, `mcp_server.py`: thin shims (import `main` from the package and call it under `__main__`) so documented commands keep working. They are not in the wheel. `cli` and `ingest` also live in the package (`qai_consultant/cli.py`, `qai_consultant/rag/ingest.py`).
- `qai_consultant/__init__.py`: empty (no imports), so importing a wheel subpackage never pulls the app side in.

## Packaging

- `pyproject.toml`: replace `py-modules` with `[tool.setuptools.packages.find]` (`where = ["src"]`, include `qai_consultant`, `qai_consultant.common*`, `qai_consultant.core*`, `qai_consultant.mcp*`). The `knowledge_base` package-dir mapping and the exact-pin rule are untouched.
- Console script: `qai-consultant-mcp = "qai_consultant.mcp.server:main"`.
- The licensing gate (`tests/system/release/test_packaging.py`: zero PDFs/HTML in the wheel) and the exact-pin test keep running unchanged. A new assertion checks that the built wheel contains only the three wheel subpackages.
- `server.json`, `README_MCP.md` and `uvx qai-consultant-mcp` usage are unchanged apart from the version.

## Enforcement test (replaces the convention)

`tests/system/release/test_wheel_import_graph.py` AST-walks every module in
`common/`, `core/` and `mcp/` and asserts that its imports (including lazy ones
inside functions) are limited to the stdlib, the declared wheel dependencies, and
`qai_consultant.common|core|mcp` respecting the tier order `common <- core <- mcp`.
It fails on `pinecone`, `mistralai`, `openai`, `streamlit`, `langchain*`, or any
app-side subpackage. This also replaces the manual "keyless import graph" step in
`.claude/agents/mcp-surface-reviewer.md`.

## Migration mechanics

One scripted pass (same approach as the tests restructure), reviewed as a diff:

1. `git mv` each module to its new path (preserves history).
2. Rewrite imports with an AST-aware rewriter, not regex: `import x`, `from x import y`, and lazy in-function imports, in `src/`, `tests/`, `evals/`, `scripts/`.
3. Rewrite string references that name modules: `mock.patch("agent.X")`, `monkeypatch.setattr("module.attr")`, `importlib`, and `sys.modules` stubs in evals. These are the main risk, since a pure import rewrite misses them and tests fail at runtime, not at import time.
4. Remove the 7 `sys.path` hacks; add `pythonpath = ["src"]` to `[tool.pytest.ini_options]`; evals and scripts import the package.
5. Update path references in CI workflows, skills, `.claude/agents`, CLAUDE.md (architecture table, commands, import-graph rule), INSTALL.md, CONTRIBUTING.md and the README files. Historical docs (`docs/plans`, `docs/postmortems`, CHANGELOG entries) stay as written.
6. Add a CHANGELOG entry and the new-module rows to CLAUDE.md in the same PR.

## Gotchas and risks

- **Windows stdio deadlock:** `server.main()` must still call `index.warmup_embedder()` before `mcp.run()`. Moved verbatim; `scripts/verify_mcp_stdio_no_deadlock.py` is part of verification (see `docs/postmortems/2026-07-30-mcp-windows-stdio-deadlock.md`).
- **`qai_consultant.mcp` vs the `mcp` SDK:** absolute imports mean `import mcp` still resolves to the SDK, but running a file from inside `qai_consultant/` with that directory on `sys.path` would shadow it. Mitigation: documented commands only use the `src/` shims, and a test imports the SDK from within the package to prove resolution.
- **Mock and patch targets** named by string (step 3) break silently at runtime; the suite count must match exactly and any collection error fails the gate.
- **Streamlit Cloud:** the entry stays `src/app.py` with `src/` as `sys.path[0]`, so `qai_consultant` is importable with no install. Verify with a local `streamlit run src/app.py` and one real generation run (`llm-e2e-smoke`), then watch the deploy after merge (known deploy lag).
- **`tests/system/release/test_skill_doc.py`** parses `min_score` from `mcp_server.py`; its target path changes to `qai_consultant/mcp/server.py`.
- **Stale artefacts:** `build/`, `dist/` and `src/qai_consultant_mcp.egg-info/` must be deleted before building, so a stale `build/lib` cannot mask import errors.
- **Cold-start budget:** the package layout adds no dependencies and the exact-pinned lock is not regenerated. Verified by timing `uvx --from <built wheel>` start-up against the current release.

## Verification (the PR's `## Verified` section)

1. `pytest tests/` passes with the same count as before the move; `ruff`, `mypy src/`, `bandit -r src/ -ll`, and the coverage floor of 60.
2. The new import-graph test and the wheel-contents assertion pass.
3. Build the wheel from a clean tree, install it into a fresh venv with no repo on the path, run `qai-consultant-mcp` over stdio, list the tools, and call `estimate_qa_effort` and `retrieve_qa_knowledge`.
4. `uvx --from <built wheel> qai-consultant-mcp` from an empty directory (the install path real users take), with start-up time recorded.
5. `scripts/verify_mcp_stdio_no_deadlock.py` and `scripts/mcp_release_check.py --preflight`.
6. `streamlit run src/app.py` through the `browser-ui-testing` skill, plus one full generation run via `llm-e2e-smoke`.
7. `python src/cli.py --review`, `--results` and `--maturity` on the repo fixtures.

## Out of scope / follow-ups

- The release PR (version bump, PyPI publish, registry sync) is separate.
- Splitting `app.py` (2074 lines) and `effort_core.py` (948 lines) is a separate decision; this change only moves files.
