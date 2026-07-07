# Optional "Additional Context" Free-Text Input (dialogue + review)

## Context

Today the 4 generated documents (Risk Register, Effort Estimation, Test Strategy, Test Plan) are built strictly from the 11 structured dialogue answers. The user wants an optional free-text field so users can add project context the questions don't capture, plus a second chance to edit that text at the review step — improving the precision/quality of all 4 outputs.

**Decisions agreed with the user:**
- Scope: Streamlit **and** CLI.
- Review UX: single **editable pre-filled** field (add/modify/clear), not a separate append-only box.
- Max 2000 characters; field is optional (empty allowed).
- Free text goes **only into the LLM generation prompts**, NOT into the Pinecone RAG retrieval queries (avoids diluting embedding relevance).
- Effort Estimation: free text affects only the LLM narrative; deterministic PERT numbers unchanged.

**Design choice:** NOT a 12th `QUESTIONS` entry — an optional question would break the required-answer validation pipeline, the CLI retry loop, the 11-question progress bar, `test_dialogue.py:194` (`len(QUESTIONS) == 11`), and template REQUIRED_KEYS. Instead: a new `additional_context` field on `ProjectContext` + dedicated UI in each frontend.

Verified: no test asserts the exact `to_summary()` format; prompt tests assert section *presence* only — safe to append a conditional section.

## Step 1 — `src/dialogue.py`

1. Constant near line 18: `MAX_ADDITIONAL_CONTEXT_LENGTH = 2000`.
2. `ProjectContext`: add `additional_context: str = ""` after `compliance_requirements` (line ~175).
3. `to_summary()` (~177-193): after the existing `.strip()`, conditionally append:
   ```python
   if self.additional_context:
       summary += (
           "\n\nADDITIONAL CONTEXT FROM THE USER\n"
           "================================\n"
           f"{self.additional_context}"
       )
   return summary
   ```
   This automatically reaches build_risk_prompt (`risk_analyzer.py:43`), build_strategy_prompt (`strategy_generator.py:51`), build_test_plan_prompt (`test_plan_generator.py:42`). Do **not** touch `to_rag_query()` / `_build_risk_query` / `_build_test_plan_query`.
4. `InputValidator`: new dedicated method (the generic `validate()` rejects empty + caps at 500 before field dispatch, so a category set won't work):
   ```python
   def validate_additional_context(self, answer: str) -> ValidationResult:
       cleaned = answer.strip()
       if not cleaned:
           return ValidationResult(valid=True, cleaned="")
       cleaned = re.sub(DANGEROUS_CHARS, "", cleaned)  # + warn log like validate()
       if len(cleaned) > MAX_ADDITIONAL_CONTEXT_LENGTH:
           return ValidationResult(valid=False, error="Additional context is too long (max 2000 characters)...")
       return ValidationResult(valid=True, cleaned=cleaned)
   ```
5. `DialogueManager`: setter used by both frontends (~line 348):
   ```python
   def set_additional_context(self, text: str) -> ValidationResult:
       result = self._validator.validate_additional_context(text)
       if result.valid:
           self.context.additional_context = result.cleaned
       return result
   ```
   `reset()` already recreates `ProjectContext` — no change.

## Step 2 — `src/effort_estimator.py` (narrative prompt only)

In `_generate_report` (~line 491), before the narrative f-string:
```python
additional_ctx_line = (
    f"ADDITIONAL CONTEXT FROM THE USER: {context.additional_context}\n"
    if context.additional_context else ""
)
```
Insert `{additional_ctx_line}` right after the `COMPLIANCE:` line (~508). PERT/multiplier math untouched.

## Step 3 — `src/app.py` (Streamlit)

1. Promote `InputValidator` to the module-level import; remove the local import at line ~392.
2. **`render_dialogue` (~350-417):** inside the form, after the QUESTIONS loop, add an optional `st.text_area` with `key="input_additional_context"`, `max_chars=2000`, height 120, labeled "Anything else QAI should know? (optional)". Do **not** store it in `st.session_state.answers` (progress bar divides by `len(QUESTIONS)` — would show 12/11).
   - In the submit validation block: `extra_result = validator.validate_additional_context(st.session_state.get("input_additional_context", ""))`; append to `errors` if invalid.
   - In the success branch after the replay loop (~414): `dialogue.set_additional_context(extra_result.cleaned)` and `st.session_state["review_additional_context"] = extra_result.cleaned` (refresh review pre-fill — the review widget ignores `value=` once its key exists; setting here is legal because the review widget isn't instantiated during this rerun).
3. **`render_review` (~420-464):** after the Project Description block, add an editable `st.text_area(value=context.additional_context, key="review_additional_context", max_chars=2000)` labeled "edit, extend, or clear before generating".
   - **Write-back happens on the Generate click inside `render_review`** (not in `render_strategy`): validate `review_additional_context`; on error `st.error` and block the transition; on success `st.session_state.dialogue.set_additional_context(result.cleaned)`, sync `st.session_state["input_additional_context"] = result.cleaned`, then `current_step = "strategy"` + `st.rerun()`. `render_strategy` needs zero changes (reads `dialogue.get_context()` at ~519).
   - "Go Back & Edit": copy `review_additional_context` back into `input_additional_context` before switching to dialogue, so review edits aren't lost.
4. **Session cleanup — BOTH blocks** (sidebar Start Over ~173-183 and Generate Another Strategy ~758-767): after the `for q in QUESTIONS` pop-loop, also pop `"input_additional_context"` and `"review_additional_context"` (the QUESTIONS loop won't cover them).

## Step 4 — `src/cli.py`

1. **`run_dialogue` (~55-81):** after the while loop, one optional prompt — "Anything else QAI should know? (Enter to skip)", retry-until-valid via `dialogue.set_additional_context(...)`.
2. **`show_context_summary` (~84-106):** add an "Additional Context" row (`"—"` when empty; 80-char truncation like existing rows).
3. **`_run_main_loop` (~271+):** between `show_context_summary` and the Generate confirm (~285), ask `Edit the additional context before generating? [yes/no]` (default no). If yes: show current text, prompt for replacement (empty = clear — replacement semantics, since Rich `default=` would make clearing impossible), retry-until-valid. `generate_strategy()` picks up the final context — no change.

## Step 5 — Tests

**New in `tests/test_dialogue.py`** (existing style; register in the runner list):
- empty/whitespace → `valid=True, cleaned=""`
- 2000 chars valid; 2001 invalid ("too long")
- dangerous chars (`<>{}`) stripped, still valid
- `set_additional_context`: valid lands on context; invalid leaves prior value + `valid=False`
- `to_summary()` includes "ADDITIONAL CONTEXT FROM THE USER" when set; omits when empty
- `reset()` clears the field

**New in `tests/test_app_v03.py`** (source-scraping style):
- Start Over clears both new keys; Generate Another clears both new keys
- in `render_review`, `set_additional_context` appears before `current_step = "strategy"`
- `render_dialogue` contains `input_additional_context` + `max_chars=2000`

**New in `tests/test_effort_estimator.py`:** stub agent capturing the prompt → assert "ADDITIONAL CONTEXT FROM THE USER" present when field set, absent when empty (if `_generate_report` scaffolding is too heavy, extract the prompt build into a helper and test that — decide at implementation time).

**Existing tests to update: none.** (`test_11_questions_defined` passes by design; templates intentionally don't require the field; CLI flow covered via the manager unit tests — no CLI test infra exists.)

## Step 6 — Verification

```
python -m pytest tests/test_dialogue.py tests/test_app_v03.py tests/test_session_state_safety.py tests/test_templates.py tests/test_effort_estimator.py -v
python -m pytest tests/ -v      # full suite (7 pre-existing fixture errors expected without live keys)
ruff check src/ tests/
```
Manual Streamlit walk-through (`streamlit run src/app.py`):
1. Leave field empty → review shows empty editable area → generation works; no "ADDITIONAL CONTEXT" section in prompts/docs.
2. Fill at dialogue → review pre-filled → edit → Generate → all 4 docs reflect the **edited** text; Effort PERT numbers identical to run 1 for identical answers.
3. Review → "Go Back & Edit" → dialogue shows the review-edited text → resubmit → review pre-fill updated (stale-key regression).
4. ~2000 chars → UI caps; Generate succeeds.
5. "Generate Another Strategy" and "Start Over" → field empty again.

CLI (`python src/cli.py`): Enter to skip; then a run filling it; at summary choose `yes` to edit, replace, confirm; check summary row + generated docs.

## Critical files
- `src/dialogue.py` — field, validator method, setter, `to_summary()`
- `src/app.py` — dialogue form, review editable field + write-back, both cleanup blocks
- `src/cli.py` — optional prompt, summary row, pre-confirm edit
- `src/effort_estimator.py` — narrative prompt (~500)
- `tests/test_dialogue.py`, `tests/test_app_v03.py`, `tests/test_effort_estimator.py`
