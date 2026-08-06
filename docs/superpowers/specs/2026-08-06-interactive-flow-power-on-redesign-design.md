# Interactive flow redesign — Phase 2 of 3

**Date:** 2026-08-06
**Status:** Approved

## Problem

Phase 1 (`docs/superpowers/specs/2026-08-06-landing-power-on-redesign-design.md`, shipped as v3.4.1) established the "Power-On Sequence" visual language on the landing screen only. The rest of the interactive flow — the 11-question dialogue (`render_dialogue()`), the review screen (`render_review()`), and the sidebar (`render_sidebar()`) — still looks like the pre-v3.4 app in places: `render_review()` renders the project summary as plain `st.code()` blocks in two `st.columns()`, and while the dialogue's `.ledger-card` question wrapper already has v3.4 styling, it has no `:hover` rule (the same gap Phase 1 found and fixed for its own new cards) and no visual response to the page's own progress.

## Scope

This spec covers Phase 2 of the 3-phase redesign: the dialogue, review, and sidebar screens. Phase 3 (Risk Register / Effort / Strategy / Test Plan output screens, and re-evaluating the existing Calibration Bench components under the confirmed language) is separate, later work.

## Key technical constraint: Streamlit reruns vs. one-shot animation

Unlike the landing screen (rendered once per session in the common case), `render_dialogue()` reruns on template-dropdown change and "Apply template", and `render_review()` reruns on every edit to the "Additional context" `st.text_area` (outside a form, so it reruns on change). A naive port of Phase 1's mount-triggered CSS entrance animations would replay every time, reading as broken/nagging rather than "instrument powering on."

**Resolution:** gate one-shot entrance sequences behind a `st.session_state` "seen" flag, the same idiom the codebase already uses for `mcp_announcement_seen` (`app.py`) and the visit counter. Only `render_review()` actually needs one (`review_intro_animated`) — per the per-screen breakdown below, the dialogue screen ends up with no mount-triggered entrance animation at all (its 11-card rerun frequency ruled that out entirely, not just the need for gating), so there's no `dialogue_intro_animated` flag to create.

Not everything gets gated this way — see per-screen breakdown below for what's exempt because it's driven by value transitions, not mount events.

## Design

### Dialogue (`render_dialogue()`)

- **Question cards (`.ledger-card`):** add a `.ledger-card:hover` rule (border + lift, matching the pattern already established for Phase 1's `.pom-card`). **Correction from an earlier draft of this spec:** `.ledger-card`'s base rule is defined in `theme.py`, which this phase does not modify (see "What's explicitly unchanged" below) — the new hover rule instead lives in this phase's own new module's self-contained `<style>` block (same architecture as Phase 1's `landing_hero.py`), injected only on the dialogue screen. This is safe: `.ledger-card:hover` is an additive selector (a different state) that composes with the existing base `.ledger-card` rule regardless of which stylesheet loads first — it doesn't override or depend on load order. No per-card entrance animation — with 11 cards re-rendering on every template-dropdown rerun, a staggered fade-in would replay distractingly often; a static-but-responsive card serves the "calibrated instrument" feeling better here than repeated motion would.
- **Progress bar:** replace the native `st.progress` with a custom themed bar (reusing the `pom-gfill`-style token-driven fill already proven in Phase 1) with a CSS `transition` on width — not a keyframe animation — so it smoothly animates between values on every rerun where the answered-count changes. This is intentionally exempt from the session-flag gating: a transition on value change is expected to fire every time the value changes, that's what makes it feel alive rather than a static number.
- **Header:** light touch only — reuse the existing mono "eyebrow" label style from Phase 1 (`.pom-readout`-equivalent) above the "Project Discovery" heading; no reveal animation (this text is stable across every rerun on this screen, an entrance animation on it would replay constantly).

### Review (`render_review()`)

- **Project summary:** replace the two `st.columns()` of plain `st.code()` blocks with a set of small ledger-styled tiles (label + value), visually consistent with `.ledger-card` but read-only (no index number, no hover — this is a summary, not an input target). Reuses existing tokens, no new colors.
- **One-shot entrance:** the summary tiles get a staggered fade-in, gated behind `st.session_state.review_intro_animated` (set `True` after first render) so editing "Additional context" afterward doesn't replay it.
- **Existing `signal_ledger_html()` results-analysis metrics** (already Calibration Bench-styled since an earlier release) are unchanged — this phase doesn't touch that code path.

### Sidebar (`render_sidebar()`)

- Visual polish only: typography/spacing consistency with the established tokens, and a hover state on the "🔄 Start Over" button and the two expanders. **No entrance animations anywhere in the sidebar** — it persists across every screen and rerun in the app, so a mount-triggered animation here would be the most repetitive possible instance of the exact problem this spec's "Key technical constraint" section describes.

### What's explicitly unchanged

- `theme.py` is still not modified — no new tokens, no new fonts, no new global CSS rules (same constraint as Phase 1).
- No changes to `render_intro()` (Phase 1, done), `render_strategy()`, or `render_doc_review()` (Phase 3, not started).
- No changes to form validation logic, session-state field names (other than the two new `*_intro_animated` flags), or navigation/routing behavior in any of the three screens.
- The new `*_intro_animated` flags follow the existing `mcp_announcement_seen` precedent for session-state cleanup: they are session-wide "have you seen this" flags, not per-generation-run state, so — like `mcp_announcement_seen` — they must be excluded from both "Start Over" and "Generate Another Strategy" cleanup lists (clearing them would just replay the entrance once more, which is harmless, but excluding them keeps the pattern consistent and avoids unnecessary code in the cleanup blocks).

## Testing

- Unit tests for any new pure HTML-building functions (following `landing_hero.py`'s pattern from Phase 1 — no Streamlit dependency, testable without a runtime).
- Playwright visual verification (extending `scripts/verify_landing_visual.py`'s pattern from Phase 1) confirming: the dialogue's progress bar transitions smoothly, the review screen's entrance animates once and does NOT replay after editing "Additional context," and reduced-motion disables all of it (relying on `theme.py`'s existing global rule for duration/transition, plus the same per-module `animation-delay` fix pattern Phase 1 established if any new element uses a nonzero delay).

## Non-goals

- Phase 3 (output screens) is not part of this spec.
- No new Playwright Page Object Model test suite (separate work stream, per the original brainstorm).
- No version bump / CHANGELOG entry planning yet — follows the same "accumulate across phases" decision made for Phase 1 (see the v3.4.1 CHANGELOG entry's own note).
