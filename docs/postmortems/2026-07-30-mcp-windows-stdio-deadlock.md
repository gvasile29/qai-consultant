# Postmortem: MCP server deadlock on Windows stdio (v3.0.0/v3.0.1, fixed v3.0.2; cold-start regression fixed v3.1.6)

**Status:** Fixed. **Affected releases:** qai-consultant-mcp 3.0.0, 3.0.1 (deadlock); 3.1.0-3.1.5 (cold-start timeout regression). **Linked from:** CLAUDE.md's "MCP server: embedding-model warmup must happen before `mcp.run()`" Gotcha.

## Incident 1: indefinite deadlock on the first real tool call (v3.0.0/v3.0.1)

`mcp_server.py`'s `main()` calls `index.warmup_embedder()` on the main thread right after `_get_index()`, before starting the stdio server. Found via a real end-to-end test (v3.0.2) of the *published* `uvx qai-consultant-mcp` subprocess over real stdio: without the warmup, the server deadlocks indefinitely on the first `retrieve_qa_knowledge` call — happens even with a warm on-disk index cache (where `list_kb_sources` never touches the embedding model at all, so it's genuinely the *first* real model call that triggers it).

Root cause is Windows-specific: the `mcp` SDK's `stdio_server()` runs a concurrent `stdin_reader()` task blocked in `ReadFile()` on the piped stdin; when the embedding model's first real inference call (`HuggingFaceEmbeddings` construction + `encode()`, native torch/MKL thread + DLL init) instead happens lazily inside a FastMCP-dispatched worker thread — i.e. concurrently with that reader — the two threads deadlock on the process loader lock.

Confirmed via 7 isolated repros: plain sequential calls, a bare `ThreadPoolExecutor` worker, and `anyio.to_thread.run_sync` inside an asyncio loop all worked fine in-process; only the genuine subprocess-with-piped-stdio server loop hung, and only until the warmup call was moved before `mcp.run()`. `OMP_NUM_THREADS=1`/`MKL_NUM_THREADS=1`/`KMP_DUPLICATE_LIB_OK=TRUE`/`HF_HUB_OFFLINE=1` were all tried and did **not** fix it — the warmup ordering is the actual fix.

This affected the live PyPI package (3.0.0 and 3.0.1) for every real client (Claude Code, Claude Desktop, claude.ai) — any session that called a knowledge-retrieval tool would hang forever with no error.

**Fix:** move the embedding model's first real inference to the main thread, before `mcp.run()` starts `stdio_server()`'s concurrent stdin-reader task.

**Rule that survives in CLAUDE.md:** never move the model's first real inference back to being lazy/first-call-triggered without re-verifying this via a real subprocess-with-piped-stdio test.

## Incident 2: the warmup fix itself caused a cold-start "could not attach" (v3.1.0-v3.1.5, fixed v3.1.6)

The original warmup call was `index.search("warmup", k=1)`, which went through `LocalIndex`'s ordinary search path — on a cache miss, this synchronously embedded the *entire* KB corpus (`embed_documents()` over every chunk of every document) before the server could respond to even the first `initialize` message. Combined with Claude Desktop being MSIX-sandboxed (its own virtualized `%LOCALAPPDATA%`, confirmed via a duplicate `uv` package cache path under `AppData\Local\Packages\Claude_<id>\LocalCache\Local\`, completely separate from the system-wide cache), every attach attempt started from a genuinely cold on-disk index cache with no way to pre-warm it from outside. Claude Desktop's `initialize` request gives up after ~60s and cancels — this looked to users like "could not attach," not a crash.

**Fix (v3.1.6):** split `LocalIndex` into a new cheap `warmup_embedder()` (constructs the embedding model + one `embed_query()` call — the minimum needed to satisfy Incident 1's fix, which is about the *native runtime's first initialization* racing the stdin-reader thread, not about every subsequent call) and the expensive `_ensure_built()` (full corpus embed), now lazy and deferred to the first real `search()`/`list_sources()` call. Verified via a real subprocess-with-piped-stdio E2E test (`mcp.client.stdio.stdio_client`, matching exactly how Claude Desktop/Claude Code launch the server) with the on-disk index cache forced cold: no hang on the first real tool call.

**Residual, not fixed by v3.1.6:** even with everything fully cached, `initialize` still took roughly 20-25 seconds on a typical Windows machine — isolated to `import sentence_transformers` alone taking ~15s (torch adds another ~5s), not network calls or embedding time. Uncomfortably close to a 60s client budget on a slower machine. **This is the root cause later addressed directly in v3.5.3's fastembed backend switch** (see `docs/superpowers/specs/2026-09-17-mcp-embedding-backend-simplification-design.md`) rather than continuing to work around it.

**Trade-off accepted:** a corrupted/unreadable KB file no longer fails the server at startup, only lazily on the first real tool call — acceptable since the shipped KB is package content, not user-editable, and the more common startup failure (embedding model unavailable) still fails fast via `warmup_embedder()`.
