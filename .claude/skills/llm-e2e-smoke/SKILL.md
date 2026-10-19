---
name: llm-e2e-smoke
description: Run one real end-to-end generation (Risk Register, Effort, Strategy, Test Plan) against the live LLM providers and check the saved output content. Use after any change to MISTRAL_MODEL, OPENROUTER_MODELS, LLM_NUM_PREDICT/temperature, a prompt builder, risk_ledger parsing, or LLMClient's streaming/fallback code, before claiming the change works.
---

# LLM end-to-end smoke

Unit tests mock the providers, and stage badges in the UI only show that *something* streamed. Both have passed while real output was broken:
- v3.6.1: OpenRouter's auto-router answered a Risk Register prompt with "User Safety: safe".
- ~3 weeks of Mistral Free-plan 429s went unnoticed because `LLMClient` fell back silently.

So check the saved documents, not the badges.

## Run

```bash
PYTHONIOENCODING=utf-8 python scripts/llm_e2e_smoke.py                     # web_app template
PYTHONIOENCODING=utf-8 python scripts/llm_e2e_smoke.py --template automotive
PYTHONIOENCODING=utf-8 python scripts/llm_e2e_smoke.py --require-mistral   # model/provider changes
```

Run it in the background. A full run takes a few minutes. Exit codes:
- 0 = pass.
- 1 = a content check failed. Your change, or the model, produced bad output.
- 2 = could not run. Setup failed (keys, Pinecone), or both providers failed so no LLM document was produced. That is an outage, not a regression. Check `logs/qai_consultant.log` and retry later.

Use `--require-mistral` whenever the change concerns the primary model. A run that "passes" via OpenRouter fallback is exactly how the 429 outage stayed hidden.

## What it checks

- All 4 documents are ≥1500 chars, both in memory and in the saved `output/*.md`.
- No known garbage markers (safety-classifier output, refusals).
- The Risk Matrix parses to ≥3 rows via `risk_ledger.parse_risk_matrix` (what the Risk Ledger UI renders).
- `effort_data` is present.
- Each saved document passes `output_guards.lint_output()`: no lone `**`, no "ISTQB-mandated"/"unusable", no unqualified "No dedicated/prior/existing X" absence claims (the 2026-10 exploratory-QA defects). A FAIL here means a prompt or model change regressed honesty, not that the lint is flaky.
- It counts and prints every Mistral→OpenRouter fallback or mid-stream failure warning.

## After it passes

The script catches empty and garbage output, not bad advice. Open the Risk Register and Test Strategy it printed paths for and skim them: right project, a sensible risk table, no truncation mid-section (`LLM_NUM_PREDICT` too low shows up as a document that stops abruptly).

## Cost

Each run uses one full generation of the shared quota: 4 streamed calls plus 1 narrative call. If it falls back, that is ~5 of OpenRouter's 50 free requests/day. Don't loop it. One run per meaningful change is the intent.

For UI-level changes, use the `browser-ui-testing` skill instead or in addition.
