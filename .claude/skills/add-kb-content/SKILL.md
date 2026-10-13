---
name: add-kb-content
description: The steps for adding or changing a document under knowledge_base/ in this repo — category folder, kb_manifest.py, the MCP wheel's licensing whitelist, Pinecone re-ingest, and a RAG eval case. Use whenever a file is added, moved, renamed, or deleted under knowledge_base/.
---

# Add KB content

Content under `knowledge_base/` feeds two surfaces that each have their own gate. Pinecone (Streamlit/CLI RAG) ingests everything, PDFs included. The MCP wheel (`LocalIndex`) ships only whitelisted self-authored `.md`. A new file can land in one surface and silently miss the other, so walk every step.

## 1. Place the file

- The top-level folder sets the metadata category via `src/kb_config.py`'s `SOURCE_CATEGORIES`: `standards/` = Standard, `methodologies/` = Methodology, `articles/` = Article, `expert_knowledge/` = Expert Knowledge, `evaluation_audit/` = Audit/Evaluation. A file outside these folders falls back to the generic `"General"` category.
- Use `.md` (UTF-8) where you can. `.pdf` reaches Pinecone only and never ships in the MCP package.
- Never put curated content in `generated_strategies/`. That folder holds user-feedback output, and the manifest test forbids referencing it.
- Methodology guides end with a "QAI Consultant application" section. Match that if adding one.

## 2. Licensing gate (MCP wheel)

Third-party text whose redistribution rights are unclear must not ship. Decide before touching `pyproject.toml`:

- **Self-authored `.md` in an already-whitelisted folder** (see `[tool.setuptools.package-data]`): it ships automatically. Make sure nothing in it is lifted verbatim from a third-party standard.
- **New nested folder** (e.g. `standards/foo/`): it is *not* shipped until you add both `"knowledge_base.standards.foo" = ["*.md"]` to `pyproject.toml` and the folder to `_WHITELISTED_MD_FOLDERS` in `tests/test_packaging.py`. Leaving it out is the right choice for third-party material.
- PDFs and HTML are blocked by `exclude-package-data` and asserted by `test_wheel_contains_zero_pdf_files`. Don't work around it.

## 3. Sidebar manifest

`KB_MANIFEST` in `src/kb_manifest.py` (emoji, label, paths relative to `knowledge_base/`) lists some content by folder and some by individual file:

- **Picked up automatically:** a new file inside a folder-level entry (`methodologies`, `evaluation_audit`, `articles`, `expert_knowledge`, `standards/istqb`, `standards/owasp`).
- **Needs its own entry:** a new file directly under `standards/` (those are listed one file at a time, e.g. `standards/IEEE_829_Test_Documentation.md`), or any new nested folder. `tests/test_kb_manifest.py` only checks top-level folders, so it will *not* catch the missing entry. Without one, the sidebar silently never shows the new standard.
- **New top-level subfolder:** add an entry. Here the test does fail if you forget.

Also update CLAUDE.md's "Knowledge Base → Contents" bullet if counts or pillars changed.

## 4. Eval case

Add at least one line to `evals/rag_golden.jsonl` for a query the new doc should be retrieved for:

```json
{"query": "<a question only this doc answers well>", "expects": ["<filename stem or distinctive substring>"], "judge": true}
```

## 5. Verify locally

```bash
python -m pytest tests/test_kb_manifest.py tests/test_packaging.py -v
python -m evals.local_index_parity      # keyless: chunk-level recall/MRR over what the MCP server serves
```

`python -m evals.run` (the doc-level RAG tier) is opt-in. Ask before running it. With keys in `.env`, its judged metrics make ~3 LLM calls per `"judge": true` case in `evals/rag_golden.jsonl` (~70 calls today). If Mistral is 429ing, they fall back to OpenRouter and can use up its whole 50/day free tier, which also breaks the live app's fallback for the rest of the day.

## 6. Re-ingest Pinecone (only after merge)

`python src/ingest.py` writes to the **production** `knowledge-base` namespace that the live Streamlit app reads. Run it only after the PR merges, and tell the user before running it. It is the one step here that changes shared state outside the repo.

## 7. MCP release note

A content change in a whitelisted folder changes what `qai-consultant-mcp` serves, but it reaches users only through a new PyPI release. Say so in the PR. Don't bump the version unprompted; that's the `release-checklist` skill's job when the user asks for a release.
