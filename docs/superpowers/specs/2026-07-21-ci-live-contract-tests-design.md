# CI Quality Gates (Part 4: Live API-Contract Tests) — Design

**Date:** 2026-07-21
**Status:** Approved by user, pending spec review

## Problem

All existing CI (the `test`/`lint` jobs, plus Parts 1-3 of this series) is
keyless — nothing exercises the real, live behavior of Pinecone or the
Mistral/OpenRouter APIs this app depends on. The v3.1.1/v3.1.2 visit-counter
incident is the concrete example: `src/visit_counter.py`'s unit tests
(`tests/test_visit_counter.py`) mock the Pinecone client entirely, so they
stayed green throughout even though every real `index.upsert()` call in
production was failing with `[400] Dense vectors must contain at least one
non-zero value` — an API-level contract violation no amount of mocking could
have caught. Nothing currently exists to catch this *class* of bug before it
reaches production again, for Pinecone or for the Mistral/OpenRouter LLM
calls.

## Scope

Fourth and last of the four CI-improvement sub-projects from the original
brainstorm (Part 1 = mypy/bandit/pip-audit, Part 2 = evals gate, Part 3 =
coverage + release guardrails — each its own spec). This spec covers: a
scheduled (never PR-blocking) workflow that exercises real Pinecone and
Mistral/OpenRouter API calls.

## Cadence and trigger: scheduled, never PR-blocking

A **separate** workflow file, `.github/workflows/live-contract-tests.yml` —
deliberately not a job inside `ci.yml`. It triggers only on:

```yaml
on:
  schedule:
    - cron: '0 3 * * *'   # nightly, 03:00 UTC
  workflow_dispatch: {}    # manual trigger, so this can be verified on demand
                           # without waiting a full day for the first cron run
```

Because neither `push` nor `pull_request` triggers this workflow, it can
never appear in a PR's checks list and can never block a merge — this is a
structural guarantee, not a policy relying on `continue-on-error`. A failing
nightly run shows up as a red run in the Actions tab; GitHub's default
notification behavior emails the workflow's author/repo watchers on a failed
scheduled run, so no extra alerting integration is needed for v1.

## Resources: production keys, isolated Pinecone namespace

Reuses the same `MISTRAL_API_KEY`, `OPENROUTER_API_KEY`, `PINECONE_API_KEY`,
and `PINECONE_INDEX_NAME` already used by the production Streamlit app and
its Pinecone index — no second Pinecone project/index or second Mistral key
to provision or pay for separately. The Pinecone contract test writes to a
**new, dedicated namespace, `ci-contract-tests`** — isolated from both
`knowledge-base` (the RAG content) and `app-metrics` (the visit counter),
so a test run can never collide with or corrupt real data, following the
same isolation pattern already established for `visit_counter.py`'s
`app-metrics` namespace.

**Prerequisite the user must do manually:** add `MISTRAL_API_KEY`,
`OPENROUTER_API_KEY`, `PINECONE_API_KEY`, `PINECONE_INDEX_NAME` as GitHub
Actions repository secrets (Settings → Secrets and variables → Actions).
These likely only exist today in Streamlit Cloud's secrets store, a
separate system from GitHub Actions secrets. Entering credentials is
something only the user does themselves, never something to automate here.
Until these secrets are added, the workflow still runs (on schedule or
manual dispatch) but every test inside it SKIPs silently (see below) — the
job shows green, but the gate isn't actually active yet. This is called out
explicitly so it isn't mistaken for "already working."

## What gets contract-tested

New file, `tests/test_live_contracts.py`, following the exact pattern
already used by `test_risk_analyzer.py`/`test_app_v03.py` for live-LLM
tests: each test SKIPs itself (via a fixture checking for the relevant
key(s), not a hard failure) when the needed API key(s) aren't configured —
so a bare `pytest tests/` run, locally or in the existing `test` CI job,
continues to skip these silently exactly as it does today for the other
live tests, and only the nightly/manually-dispatched workflow (which
injects the real secrets as env vars) actually executes them.

**1. `test_pinecone_roundtrip`** — upserts one real (non-zero, 384-dim, same
shape as `visit_counter.DUMMY_VECTOR`) vector into the `ci-contract-tests`
namespace under a fixed test ID, fetches it back, asserts the metadata
round-trips correctly, then deletes it in a `finally` block (so the
namespace never accumulates garbage, even if an assertion fails mid-test).
This is exactly the shape of test that would have caught the all-zero-vector
rejection before it ever reached production.

**2. `test_mistral_completion`** — sends a trivial prompt ("Reply with the
single word OK.") through the app's own `LLMClient` (forcing the Mistral
path, not letting it fall back), asserts a non-empty response. Catches
auth breakage, a renamed/deprecated model, or a changed response shape
upstream.

**3. `test_openrouter_completion`** — same shape of test, forcing the
OpenRouter fallback path instead of Mistral. Catches the same class of
issue on the fallback provider, which otherwise only gets exercised in
production during an actual Mistral outage — the worst possible time to
discover the fallback itself is broken.

## Explicitly out of scope

- Any Slack/webhook/issue-auto-creation alerting beyond GitHub's default
  failed-scheduled-workflow email — can be added later if the default
  notification proves insufficient in practice.
- Testing any other external dependency (e.g. HuggingFace embedding model
  downloads) — scoped to exactly the two contract-breaking-prone
  dependencies (Pinecone's vector API, the two LLM providers) motivated by
  the actual incident.
- Provisioning a fully separate Pinecone project/index or a separate Mistral
  key for testing — the user chose to reuse production credentials with
  namespace isolation instead.
- Parts 1-3 (mypy/bandit/pip-audit, evals gate, coverage/guardrails) —
  separate specs, already written.

## Testing / verification plan

- Add the 4 GitHub Actions secrets first (manual, by the user) — without
  them, verification below would only demonstrate the skip path, not the
  real contract checks.
- Trigger the workflow manually via `workflow_dispatch` (`gh workflow run
  live-contract-tests.yml` or the Actions tab "Run workflow" button) rather
  than waiting for the nightly cron.
- Confirm all three tests actually execute (not skip) and pass.
- Confirm the `ci-contract-tests` Pinecone namespace is empty again after
  the run (the roundtrip test's cleanup worked) via
  `index.describe_index_stats()` or the Pinecone console.
- As a negative-path sanity check: temporarily point `PINECONE_INDEX_NAME`
  (via a workflow-level env override, not touching the real secret) at a
  nonexistent index name for one manual dispatch run, confirm
  `test_pinecone_roundtrip` actually fails loudly rather than silently
  passing or skipping; revert.
