# Visit Counter — Design

**Date:** 2026-07-21
**Status:** Approved by user, pending spec review

## Problem

The user wants to track how many times the Streamlit app has been accessed,
and to show that count visibly inside the app itself (sidebar).

## Constraints

- The app is deployed on Streamlit Community Cloud, which restarts the
  running process on every redeploy/reboot (see the "Streamlit deploy lag"
  gotcha in `CLAUDE.md`). Any counter held only in Python process memory or
  on local disk would reset on every release — unacceptable given how
  frequently this project ships versions.
- No brand-new external service/account should be required. `PINECONE_API_KEY`
  is already configured (`.env` locally, Streamlit Cloud secrets in
  production) and used by `src/agent.py` / `src/ingest.py`.
- Must never crash or slow down the app if the counter backend is
  unreachable — same fire-and-forget-safety philosophy as
  `src/telemetry.py` and the RAG-prefetch `try/except` pattern in
  `strategy_generator.py`.
- No personally identifying information is collected — a single aggregate
  integer, not per-visitor tracking. No change to `AI_INTERACTION_NOTICE`
  (EU AI Act Article 50 disclosure) is needed, since that notice concerns AI
  interaction transparency, not traffic analytics.

## What counts as a "visit"

One increment per new browser session (i.e., once per Streamlit script
execution where `st.session_state` is fresh) — not once per rerun. Streamlit
reruns the whole script on every widget interaction (click, form submit,
etc.), so counting every rerun would measure "activity," not "visitors."

## Storage: reuse Pinecone, new namespace

No new Pinecone index. The existing index (`PINECONE_INDEX_NAME`) gets a new,
dedicated namespace, `app-metrics`, fully isolated from the RAG namespace
(`knowledge-base`) so the counter vector can never surface in
`retrieve_knowledge()` search results.

Inside that namespace, a single vector with a fixed ID, `visit_counter`:

- **Vector values:** a dummy zero-vector, dimension 384 (matches
  `all-MiniLM-L6-v2`, the embedding model already used everywhere in this
  project — `kb_config.EMBEDDING_MODEL`). The vector itself carries no
  semantic meaning; Pinecone requires one structurally for any upsert.
- **Metadata:** `{"count": <int>}` — the actual value.

Increment is a **fetch → read count → upsert count+1** cycle. This is not
atomic. Under genuinely concurrent hits on the same running container, a
race could under-count by a small amount. Given this is a visit counter (not
a billing or security-critical value), that tradeoff is accepted rather than
adding a dedicated atomic KV service.

## New module: `src/visit_counter.py`

A small, dependency-isolated module (imports `pinecone` directly, same as
`ingest.py`) — used only from `app.py`, never imported by the MCP server
path, so it doesn't need to stay keyless/Pinecone-free like `kb_config.py`.

```python
def get_and_increment_visit_count() -> Optional[int]:
    """
    Fetch the current visit_counter vector from the app-metrics namespace,
    increment its count metadata by 1, upsert it back, and return the new
    total. Returns None on any failure (missing credentials, network error,
    index unreachable) — never raises. If the counter vector doesn't exist
    yet (first-ever visit), treats the current count as 0.
    """
```

Internally: connect to Pinecone the same way `agent.py` does
(`Pinecone(api_key=...)`, `_get_secret("PINECONE_INDEX_NAME")`), call
`index.fetch(ids=["visit_counter"], namespace="app-metrics")`, read
`metadata.count` (default 0 if the ID isn't found), upsert
`{"id": "visit_counter", "values": <dummy 384-dim zero vector>, "metadata":
{"count": new_count}}` in the same namespace, return `new_count`. The whole
body is wrapped in `try/except Exception: return None`.

## Flow in `app.py`

At the top of the script (once per session):

```python
if "visit_counted" not in st.session_state:
    st.session_state.visit_count = get_and_increment_visit_count()
    st.session_state.visit_counted = True
```

Subsequent reruns within the same session reuse `st.session_state.visit_count`
— Pinecone is never called more than once per session.

`render_sidebar()` shows, directly under the existing version caption:

```python
if st.session_state.get("visit_count") is not None:
    st.caption(f"👀 {st.session_state.visit_count:,} visits")
```

If the increment failed (`visit_count is None`), the caption line is simply
absent for that session — no stale or guessed value is ever shown. This
matches the project's existing philosophy of per-step isolation over
best-effort caching (`generate_all()`'s per-step `try/except`, the RAG
futures' fallback-to-`[]`).

## Interaction with existing session-state cleanup

`visit_count` and `visit_counted` are **excluded** from the key lists cleared
by "Start Over" and "Generate Another Strategy" in `render_sidebar()`. A
visit is defined per page load (browser session), not per generation
attempt — clicking "Start Over" mid-session must not re-increment the
counter.

## Testing

New `tests/test_visit_counter.py`, following the mocking style of
`test_llm_client.py` (mock the Pinecone client, no real network calls):

- First-ever visit: `index.fetch()` returns no match for the ID → treated as
  `count=0` → function returns `1` and upserts `count=1`.
- Normal increment: `index.fetch()` returns `metadata.count=N` → function
  returns `N+1` and upserts accordingly.
- Failure path: `index.fetch()` (or the Pinecone client constructor) raises
  → function returns `None`, does not raise.

## Explicitly out of scope

- No counter in `src/cli.py` — the CLI is a local, single-user tool; a
  "total visits" figure has no meaning there.
- No dashboard, no per-day/per-week breakdown, no unique-visitor
  deduplication beyond "once per browser session" — just a single running
  total, shown as plain text.
- No changes to `AI_INTERACTION_NOTICE` or other EU AI Act disclosure code.
