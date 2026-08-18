# Output screens redesign — Phase 3 of 3

**Date:** 2026-08-17
**Status:** Approved

## Problem

Phase 1 (`docs/superpowers/specs/2026-08-06-landing-power-on-redesign-design.md`, shipped v3.4.1) established the "Power-On Sequence" visual language on the landing screen. Phase 2 (`docs/superpowers/specs/2026-08-06-interactive-flow-power-on-redesign-design.md`, shipped v3.4.2) carried it to the dialogue, review, and sidebar screens. The output screens — `render_strategy()`'s 4-tab result view (Risk Register / Effort Estimation / Test Strategy / Test Plan) and `render_doc_review()`'s upload-then-score flow — still look like the pre-v3.4 app in places: `st.tabs()` is unstyled native Streamlit, both screens' headers are plain `st.markdown("## ...")` with no eyebrow treatment, content-area buttons and expanders have no hover state (Phase 2 gave that only to the sidebar), and `render_doc_review()`'s upload/paste step has none of the `.ledger-card` treatment the 11-question dialogue gives each of its inputs.

Separately, `render_strategy()`'s generation pipeline runs 4 sequential LLM/deterministic stages (Risk → Effort → Strategy → Plan) inside one blocking script execution — the only place in the app with a genuinely sequential multi-stage process. Nothing currently visualizes that sequence to the user beyond each stage's own streaming markdown output.

## Scope

This spec covers Phase 3, the last of the 3-phase redesign: `render_strategy()` (all 4 tabs, the generation pipeline, the feedback loop) and `render_doc_review()` (both the intake step and the results/narrative step). It also covers a light re-evaluation of the pre-existing Calibration Bench components (`ledger_components.py`'s `signal_ledger_html()`/`risk_ledger_table_html()`) under the now-confirmed Phase 1/2 visual language — see "Signal Ledger / Risk Ledger re-evaluation" below.

**Addendum folded in at user request:** `render_intro()`'s "What you get in ~2 minutes" block is landing-screen content and technically Phase 1 scope, not Phase 3 — Phase 1's own spec covered the hero headline, gauges, standards row, and "How it works" cards, but left this block native Streamlit. Rather than file it as a separate Phase 1 addendum, it's specified here (see "Addendum: landing screen deliverables section" below) since it's small and the user asked to track it in this document. Implementation-wise it stays landing-screen work — it extends `landing_hero.py`, not `output_screen_style.py`.

## Signal Ledger / Risk Ledger re-evaluation

`signal_ledger_html()` and `risk_ledger_table_html()` (`ledger_components.py`) already render off `theme.py`'s token dict and the same Plex Mono/Sans fonts Phases 1-2 use — the mono uppercase label + tabular-nums score pattern in `.signal-ledger` reads as the same instrument-panel language `landing_hero.py`'s gauges and `interactive_flow_style.py`'s eyebrow labels use. Assessment: **no migration needed.** This spec does not modify `theme.py` or `ledger_components.py`. The claim is verified, not assumed — the Playwright visual-verification task (see Testing below) includes a side-by-side screenshot of a Signal Ledger tile next to Phase 3's new components specifically to catch a mismatch if this assessment turns out wrong; a real mismatch found there is grounds to reopen this decision within the same implementation pass, not defer it to a future phase.

## Key technical constraint: which reruns replay a mount animation

`render_strategy()`'s tab content, once `results_complete` is `True`, stays visible across reruns triggered by: typing in the feedback `st.text_input("improvement_note")` (reruns on every keystroke while not inside a form), and `st.download_button` clicks (Streamlit reruns the script after a download-button click, same as a regular button). `render_doc_review()`'s results step similarly reruns on its own download-button clicks. A naive mount-triggered entrance animation on the score tiles or stage sequence would replay on every one of these, same failure mode Phase 2 documented for the review screen.

**Resolution:** gate each screen's one-shot entrance behind its own `st.session_state` "seen" flag, the established idiom (`mcp_announcement_seen`, Phase 2's `review_intro_animated`): `output_intro_animated` for `render_strategy()`'s result view, `doc_review_intro_animated` for `render_doc_review()`'s results step. The stage-sequence indicator (below) is explicitly **not** gated this way — it is a live status readout driven by which `session_state` keys are populated, not a mount animation, the same distinction Phase 2 drew for the dialogue's progress bar.

## Design

### New module: `output_screen_style.py`

Same architecture as `landing_hero.py` (Phase 1) and `interactive_flow_style.py` (Phase 2): pure functions, `tokens: dict` in, HTML/CSS string out, no Streamlit import, unit-testable without a runtime. `theme.py` is not modified — same constraint carried through all 3 phases. Not added to `pyproject.toml`'s MCP-package `py-modules` whitelist (Streamlit-app-only, like the other 3 style modules).

### `render_strategy()`

- **Header eyebrow:** a mono uppercase line above `## 📄 Generated Test Strategy`, reusing the label style `.dialogue-eyebrow` established (`build_output_eyebrow_html(tokens, label)` — shared with `render_doc_review()`, see below).
- **Stage sequence indicator:** `build_stage_sequence_html(tokens, stages)` where `stages` is an ordered list of `(label, status)` with `status` in `{"pending", "active", "done"}`, rendered into an `st.empty()` placeholder created before the 4-stage block and updated before/after each stage. Status is derived directly from which of `risk_register`/`effort_report`/`strategy`/`test_plan` are already in `session_state` (not a new state variable) — the stage currently being generated (the one whose `st.write_stream()`/`st.spinner()` call is in flight) is `active`, completed ones are `done`, later ones are `pending`. After `results_complete`, the same function renders a static "all 4 done" readout above the tabs on every subsequent rerun — it's a status readout, not an animation, so it doesn't need `output_intro_animated` gating.
- **Tab bar:** CSS targeting `[data-testid="stTabs"]` — Plex Mono uppercase tab labels, `accent`-colored active-tab indicator replacing Streamlit's default. No entrance animation (persistent chrome, client-side tab switching doesn't rerun the script).
- **Content polish:** hover states on `.stButton button` (download buttons, "Generate Another Strategy", the 3 feedback buttons) and `[data-testid="stExpander"] summary` ("Knowledge Sources Used" expanders in tabs 1/3/4) — same visual treatment Phase 2 gave the sidebar, extended to main content. Gated by nothing (hover is stateless).
- **Score-tile entrance:** the Signal Ledger tiles already rendered in tabs 1 (Risk severity table) and 2 (Effort confidence) get the same staggered fade-in Phase 2 gave the review screen's summary tiles, gated behind `output_intro_animated` (set `True` after first full render). Following the exact precedent Phase 2 set for `review_intro_animated` (itself following `mcp_announcement_seen`): this flag is excluded from both the "Generate Another Strategy" and "Start Over" cleanup lists. A second generation run in the same session simply won't replay the tile entrance a second time — harmless, and consistent with the established pattern rather than adding cleanup-list churn for a cosmetic replay.

### `render_doc_review()`

- **Header eyebrow:** same `build_output_eyebrow_html()` above `## 📝 Review an Existing QA Document`.
- **Input tray:** the doc-type selectbox, file uploader, and paste `st.text_area` (the pre-`review_result` branch) wrapped in `st.container(key="doc-review-input")`, styled via a `.st-key-doc-review-input` CSS rule to read as a `.ledger-card`-equivalent input tray — same per-instance scoping technique `app.py`'s header-logo container already uses (v3.3 precedent), applied here to a new key.
- **Results step:** the existing `signal_ledger_html()` overall-score tile and per-dimension score row get the same staggered fade-in as `render_strategy()`'s score tiles, gated behind `doc_review_intro_animated`. Same precedent as `output_intro_animated` above: excluded from `REVIEW_MODE_STATE_KEYS` (the existing shared cleanup list this mode uses — see `app.py`'s Architecture table entry for `REVIEW_MODE_STATE_KEYS`), not added to it.
- **Content polish:** same button/expander hover treatment as `render_strategy()` (shared CSS, not duplicated — see "Shared vs. per-screen output" below) applied to "🔍 Review Document," "🤖 Generate narrative review," the findings expanders, download buttons, and "🔄 Review Another Document" / "← Back to Home."

### Shared vs. per-screen output

`build_output_eyebrow_html(tokens, label)` and the content-polish CSS (`build_content_polish_css(tokens)`) are single functions each, called from both `render_strategy()` and `render_doc_review()` — they're identical needs on both screens, not two near-duplicate implementations. `build_stage_sequence_html()` is used only by `render_strategy()` (the only screen with a multi-stage pipeline).

### What's explicitly unchanged

- `theme.py` is not modified — no new tokens, no new fonts, no new global rules (same constraint as Phases 1-2).
- `ledger_components.py` is not modified (see "Signal Ledger / Risk Ledger re-evaluation" above).
- No changes to `render_dialogue()`, `render_review()`, or `render_sidebar()` — those are Phase 2, done. `render_intro()` gets exactly one addition (a call to the new `build_landing_deliverables_html()`) — see "Addendum: landing screen deliverables section" below; nothing else about it changes.
- No changes to the generation pipeline's actual logic (RAG prefetch, LLM calls, PDF precompute, save-to-disk, resumability guards, `StopException`/`RerunException` handling) — the stage-sequence indicator reads `session_state`, it does not alter what gets written to it or when.
- No changes to `review_core.py`/`review_document()`'s scoring logic, `risk_ledger.py`'s parsing, or any deterministic-analysis code.
- No changes to form validation, session-state field names (other than the two new `*_intro_animated` flags), or navigation/routing behavior.

## Addendum: landing screen deliverables section

`render_intro()`'s "What you get in ~2 minutes" block (`app.py:395-423`, immediately below `build_landing_hero_html()`'s output) was left native Streamlit when Phase 1 shipped: `landing_hero.py` styled the headline, the 3 progress gauges, the standards row, and the "How it works" cards, but not this separate block of 4 `st.success()` deliverable boxes (Risk Register / Effort Estimation / Test Strategy / Test Plan) and 4 `st.metric()` stat tiles (Time to results / Standards / Deliverables / Cost).

**Where the code lives:** extended inside `landing_hero.py` — not `output_screen_style.py`. This is landing-screen content, and `landing_hero.py` already owns all of `render_intro()`'s custom markup; splitting one screen's HTML across two style modules would break the "one module owns one screen's custom markup" boundary every phase so far has kept.

**New pure function:** `build_landing_deliverables_html(tokens) -> str`, called from `render_intro()` right after the existing `build_landing_hero_html()` call (same lazy-import, same `st.markdown(..., unsafe_allow_html=True)` pattern).

- **4 deliverable cards** reuse the `.pom-card` treatment already established for "How it works" (same background/border, same hover lift, same `pom-card-in` fade-in) — `pom-cidx` holds the icon (⚠️/📊/📋/📝) instead of a step number, `pom-ctitle`/`pom-cbody` carry the existing 4 `st.success()` blocks' copy verbatim (no rewrite of the marketing text itself).
- **4 stat tiles** (Time to results / Standards / Deliverables / Cost) become a new `.pom-stat` component — mono uppercase label, a large `Plex Mono` tabular-nums value, a dim sub-line — replacing `st.metric()`'s native look while keeping the same three-line (label / value / delta) information shape the current copy already uses.

**Animation:** one-shot on load, continuing `landing_hero.py`'s existing delay cadence past the "How it works" cards (which currently end at 2.0s) — no new session-state gating needed, since `render_intro()` renders once per session in the common case, the same assumption Phase 1's own spec relies on for its own animations.

**Reduced motion:** extend `landing_hero.py`'s existing module-local `prefers-reduced-motion` block (it zeroes `animation-delay` for its own classes because `theme.py`'s global rule only zeroes duration — see that module's docstring) to include the new deliverable-card and stat-tile classes, rather than adding a second scoped block.

## Testing

- Unit tests for `output_screen_style.py`'s pure functions (`build_output_eyebrow_html()`, `build_stage_sequence_html()` across all `pending`/`active`/`done` combinations, `build_content_polish_css()`), following `landing_hero.py`/`interactive_flow_style.py`'s pattern — no Streamlit runtime needed.
- Playwright visual verification (extending the `scripts/verify_landing_visual.py` / `scripts/verify_interactive_flow_visual.py` pattern): the stage sequence indicator through all 4 transitions during a real generation run, the score-tile entrance firing once and not replaying after a feedback-text edit or a download-button click, the doc-review input tray's appearance, and — per the re-evaluation note above — a side-by-side screenshot of an existing Signal Ledger tile against the new eyebrow/stage-sequence components to visually confirm they read as one system. Reduced-motion pass confirming all new animation is disabled, same as Phases 1-2.
- A unit test for `landing_hero.py`'s new `build_landing_deliverables_html()`, same pattern as `tests/test_landing_hero.py`'s existing tests. The visual-verification script extends `scripts/verify_landing_visual.py` (not the interactive-flow one) to screenshot the new deliverable cards and stat tiles, since this addendum's code lives on the landing screen.

## Non-goals

- No changes to `theme.py` or `ledger_components.py` beyond the verification described above.
- No new Playwright Page Object Model test suite (separate work stream, per the original brainstorm — same non-goal Phases 1-2 carried).
- No version bump / CHANGELOG entry planning yet — this is the last of the 3 phases, so the accumulated CHANGELOG entry across all 3 is written when this phase ships, not before.
- No redesign of the PDF export output (`pdf_export.py`) — out of scope, a text/print medium with its own existing styling, untouched by any of the 3 phases.
