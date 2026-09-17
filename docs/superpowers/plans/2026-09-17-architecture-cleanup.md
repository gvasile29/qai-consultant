# Architecture Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove two confirmed over-engineering findings from the 2026-09-16 architecture audit: (1) 11 dead one-line delegating-wrapper methods in `src/effort_estimator.py` kept only because tests called them directly, and (2) four Streamlit-styling modules (`ledger_components.py`, `landing_hero.py`, `interactive_flow_style.py`, `output_screen_style.py`) split by which redesign PR touched them rather than by functional boundary, consolidated into one `src/components.py`.

**Architecture:** Task 1 repoints every test call site from `est._wrapper(...)` to the real `effort_core.function(...)` it already forwards to, then deletes the now-unused wrapper methods and the now-unused `import effort_core` line. Tasks 2-5 incrementally move each of the four styling modules' full content into a new `src/components.py` (one module per task — `ledger_components.py` first since it has no dependency on the other three, then `landing_hero.py`, `interactive_flow_style.py`, `output_screen_style.py` in their original phase order), updating every `from <old_module> import ...` call site in `src/app.py` to `from components import ...` and merging each module's test file into `tests/test_components.py` as it's folded in. `src/theme.py` and `src/_theme_fonts.py` are explicitly NOT touched — see Decisions below.

**Tech Stack:** Python 3.10+, pytest (no new libraries).

**Spec:** none — this plan implements confirmed audit findings directly (see the parent conversation's 4-angle over-engineering audit, 2026-09-16); the findings themselves are specific and low-risk enough that a separate design-spec document was not required.

## Global Constraints

- Every function's signature and behavior must stay byte-identical through the moves in Tasks 2-5 — this is a pure relocation, not a rewrite. Do not "improve" the CSS/HTML/logic while moving it.
- `src/theme.py` and `src/_theme_fonts.py` stay untouched and stay separate files (see Decisions below) — do not fold them into `components.py`.
- `src/risk_ledger.py` stays untouched and separate — it's a markdown-table parser, not a styling module, and `ledger_components.py`'s `risk_ledger_table_html()` depends on its `severity_tier()` function.
- After each task, the full test suite (`python -m pytest tests/ -v`) must pass with no fewer passing tests than before that task started (a moved/merged test must still run, not silently vanish from collection).
- `ruff check src/ tests/` must pass after every task (config: `ruff.toml`, `F401`/unused-import is globally ignored — see Task 1 Step 3's note — but nothing else is).

## Decisions

- **`_theme_fonts.py` stays separate, not merged into `theme.py`.** It is pure generated data (base64 `woff2` font strings) — reading the file directly produces over 150,000 tokens of base64 text. Merging it into `theme.py` would make that file's actual logic (tokens, `build_css()`) unreadable in the same pass a developer opens it for. This is a legitimate split (data vs. logic), unlike the four modules being merged below (split purely by "which PR touched it").
- **Test files are merged along with their source modules**, into `tests/test_components.py`, organized under the same section-comment structure as `components.py`. Rationale: "files that change together should live together" applies equally to tests — leaving 4 separate ~90-130 line test files each importing from a single merged module would recreate the exact fragmentation this plan removes, just one file later. `tests/test_theme.py` stays separate (mirrors `theme.py` staying separate).
- **Merge order is Ledger → Landing → Dialogue/Sidebar → Output**, matching the modules' original build order (Phase 1/2/3 of the "Power-On Sequence" redesign) and dependency order (`ledger_components.py` has no dependency on the other three; none of the four depend on each other, so any order is functionally safe — this order was chosen only to keep the running diff's section ordering intuitive).

---

## File Structure

| File | Change |
|---|---|
| `src/effort_estimator.py` | 11 wrapper methods deleted (lines ~65-90, ~278-282); `import effort_core` (line 32) deleted |
| `tests/test_effort_estimator.py` | `import effort_core` added; wrapper calls repointed to `effort_core.*` |
| `tests/test_confidence_v06.py` | `import effort_core` added; wrapper calls repointed to `effort_core.*` |
| `src/components.py` | New — created in Task 2, appended to in Tasks 3-5 |
| `src/ledger_components.py`, `src/landing_hero.py`, `src/interactive_flow_style.py`, `src/output_screen_style.py` | Deleted (one per task, as each is folded in) |
| `tests/test_components.py` | New — created in Task 2, appended to in Tasks 3-5 |
| `tests/test_ledger_components.py`, `tests/test_landing_hero.py`, `tests/test_interactive_flow_style.py`, `tests/test_output_screen_style.py` | Deleted (one per task, as each is folded in) |
| `src/app.py` | 15 import call sites updated across Tasks 2-5 (module name only — imported names unchanged) |
| `CLAUDE.md` | Architecture table rows updated for the new module layout (Task 6) |

---

### Task 1: Delete `effort_estimator.py`'s dead delegating wrappers

**Files:**
- Modify: `src/effort_estimator.py:32` (delete import), `src/effort_estimator.py:59-90` (delete comment + 9 methods), `src/effort_estimator.py:276-282` (delete comment + 2 methods)
- Modify: `tests/test_effort_estimator.py`
- Modify: `tests/test_confidence_v06.py`

**Interfaces:**
- Consumes: `effort_core.detect_project_type(context, data)`, `effort_core.calculate_baseline(context, data)`, `effort_core.apply_multipliers(context, data)`, `effort_core.pert_breakdown(data)`, `effort_core.team_capacity(context, data)`, `effort_core.risk_buffer(risk_register, data)`, `effort_core.calculate_data_quality(context, data)`, `effort_core.finalize(data)`, `effort_core.calculate_confidence(data) -> str`, `effort_core.parse_duration(timeline: str) -> int`, `effort_core.parse_team_size(team_str: str) -> int` — all already exist in `src/effort_core.py`, confirmed identical signatures to the wrappers being removed.
- Produces: nothing new — `EffortEstimator.estimate()`'s public behavior is unchanged; only its private wrapper methods are removed.

- [ ] **Step 1: Run the baseline test suite and record the pass count**

Run: `python -m pytest tests/test_effort_estimator.py tests/test_confidence_v06.py -v`
Expected: all currently pass (record the count — Step 5 must match it exactly, since this is a pure refactor with zero behavior change).

- [ ] **Step 2: Update `tests/test_confidence_v06.py`'s wrapper calls**

Add `import effort_core` after the existing `sys.path.insert(0, str(SRC_DIR))` line (this file currently has no `effort_core` import — confirmed by reading it):

```python
sys.path.insert(0, str(SRC_DIR))

import effort_core
from dialogue import ProjectContext
from effort_estimator import EffortEstimator, EstimationData
```

Then replace every occurrence (23 call sites) of:
- `est._calculate_confidence(data)` → `effort_core.calculate_confidence(data)`
- `est._calculate_data_quality(ctx, data)` → `effort_core.calculate_data_quality(ctx, data)`

Use a global find-and-replace for each of those two exact strings across the whole file (`replace_all`) — every occurrence has identical argument names (`data`, `ctx`), confirmed by grep. Leave every `est = make_dummy_estimator()` line in place even where `est` becomes otherwise unused in that test function afterward (one function, around line 536, still uses `est.estimate(ctx)` — the real public API, not a wrapper — so `make_dummy_estimator()` itself is still needed and must not be removed; leaving a now-partially-unused local variable in the other functions is a deliberate, safe tradeoff over risking a per-function judgment call on ~20 call sites).

- [ ] **Step 3: Update `tests/test_effort_estimator.py`'s wrapper calls**

Add `import effort_core` after the existing `from effort_estimator import ...` line:

```python
from effort_estimator import EffortEstimator, EstimationData, BASELINE_QA_PERCENT
import effort_core
```

Then replace every occurrence of these 9 exact strings (global find-and-replace, `replace_all`, across the whole file):
- `est._detect_project_type(BMW_EFFORT_CONTEXT, data)` → `effort_core.detect_project_type(BMW_EFFORT_CONTEXT, data)`
- `est._calculate_baseline(BMW_EFFORT_CONTEXT, data)` → `effort_core.calculate_baseline(BMW_EFFORT_CONTEXT, data)`
- `est._apply_multipliers(BMW_EFFORT_CONTEXT, data)` → `effort_core.apply_multipliers(BMW_EFFORT_CONTEXT, data)`
- `est._pert_breakdown(data)` → `effort_core.pert_breakdown(data)`
- `est._team_capacity(BMW_EFFORT_CONTEXT, data)` → `effort_core.team_capacity(BMW_EFFORT_CONTEXT, data)`
- `est._risk_buffer("", data)` → `effort_core.risk_buffer("", data)`
- `est._calculate_data_quality(BMW_EFFORT_CONTEXT, data)` → `effort_core.calculate_data_quality(BMW_EFFORT_CONTEXT, data)`
- `est._finalize(data)` → `effort_core.finalize(data)`

And these 2 (in the duration/team-size parsing tests, which don't use `BMW_EFFORT_CONTEXT`):
- `est._parse_duration(` → `effort_core.parse_duration(`
- `est._parse_team_size(` → `effort_core.parse_team_size(`

Every one of these test functions still calls `est = make_dummy_estimator()` at the top for the duration/team-size tests only to get a throwaway `EffortEstimator` instance that no longer does anything after this change; leave those `est = make_dummy_estimator()` lines in place too, same tradeoff as Step 2 (do not hand-verify each of the ~15 test functions for whether `est` became fully dead — safe-by-construction global replace, not a per-function audit).

- [ ] **Step 4: Delete the wrapper methods and the now-dead import in `src/effort_estimator.py`**

Delete lines 59-90 (the comment block and all 9 wrapper methods):

```python
    # ── Deterministic pipeline — thin delegating wrappers ──────────────────────
    # The actual logic lives in effort_core.py (no agent/LLM dependency, so it's
    # importable from the MCP server path). Kept here as instance methods, rather
    # than removed, purely for backward compatibility: existing tests call these
    # directly (e.g. est._detect_project_type(context, data)).

    def _detect_project_type(self, context: ProjectContext, data: EstimationData):
        return effort_core.detect_project_type(context, data)

    def _calculate_baseline(self, context: ProjectContext, data: EstimationData):
        return effort_core.calculate_baseline(context, data)

    def _apply_multipliers(self, context: ProjectContext, data: EstimationData):
        return effort_core.apply_multipliers(context, data)

    def _pert_breakdown(self, data: EstimationData):
        return effort_core.pert_breakdown(data)

    def _team_capacity(self, context: ProjectContext, data: EstimationData):
        return effort_core.team_capacity(context, data)

    def _risk_buffer(self, risk_register: str, data: EstimationData):
        return effort_core.risk_buffer(risk_register, data)

    def _calculate_data_quality(self, context: ProjectContext, data: EstimationData):
        return effort_core.calculate_data_quality(context, data)

    def _finalize(self, data: EstimationData):
        return effort_core.finalize(data)

    def _calculate_confidence(self, data: EstimationData) -> str:
        return effort_core.calculate_confidence(data)

```

leaving the `# ── Report Generation ──...` comment and `_generate_report()` that immediately follow untouched.

Delete lines 276-282 (the comment block and the 2 helper wrappers):

```python
    # ── Helpers — thin delegating wrappers (logic in effort_core.py) ───────────

    def _parse_duration(self, timeline: str) -> int:
        return effort_core.parse_duration(timeline)

    def _parse_team_size(self, team_str: str) -> int:
        return effort_core.parse_team_size(team_str)

```

leaving `save()`, which immediately follows, untouched.

Delete the now-unused module-level import at line 32:

```python
import effort_core
```

(`ruff.toml` globally ignores `F401`/unused-import — see its comment "some imports needed for re-export" — so this wouldn't be caught by lint either way; it's removed here because it no longer serves any purpose in this file, not because CI would flag it. The other three currently-unused names imported at lines 34-37 — `ACTIVITY_BREAKDOWN`, `MAX_PLAUSIBLE_DURATION_DAYS`, `RISK_BUFFER` — are pre-existing, unrelated dead re-exports and are out of scope for this task; `BASELINE_QA_PERCENT` from that same import block IS used, by `tests/test_effort_estimator.py:44`, so the whole `from effort_core import (...)` block at lines 33-40 stays, only the separate bare `import effort_core` at line 32 is removed.)

- [ ] **Step 5: Run the test suite again and confirm the same pass count as Step 1**

Run: `python -m pytest tests/test_effort_estimator.py tests/test_confidence_v06.py -v`
Expected: PASS, identical count to Step 1 (zero behavior change — this step's only job is proving that).

- [ ] **Step 6: Run the full test suite and lint**

Run: `python -m pytest tests/ -v && ruff check src/ tests/`
Expected: PASS — confirms nothing else in the codebase called the deleted wrapper methods (only the two files touched in Steps 2-3 did, per the earlier grep across all of `tests/`).

- [ ] **Step 7: Commit**

```bash
git add src/effort_estimator.py tests/test_effort_estimator.py tests/test_confidence_v06.py
git commit -m "$(cat <<'EOF'
refactor: delete dead delegating wrappers in effort_estimator.py

11 one-line methods (_detect_project_type, _calculate_baseline,
_apply_multipliers, _pert_breakdown, _team_capacity, _risk_buffer,
_calculate_data_quality, _finalize, _calculate_confidence,
_parse_duration, _parse_team_size) did nothing but forward to
effort_core.py functions, kept only because tests called them
directly. Repointed all ~45 call sites in test_effort_estimator.py
and test_confidence_v06.py to call effort_core's functions directly
instead, then deleted the wrappers and the now-unused `import
effort_core` line. Zero behavior change — same test pass count
before and after.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_013xJEqRuCdtixjGy8hpg3jB
EOF
)"
```

---

### Task 2: Create `src/components.py`, fold in `ledger_components.py`

**Files:**
- Create: `src/components.py`
- Create: `tests/test_components.py`
- Delete: `src/ledger_components.py`, `tests/test_ledger_components.py`
- Modify: `src/app.py` (4 import call sites: lines 635, 984, 1019, 1267, 1479 — 5 sites, all `from ledger_components import ...`)
- Modify: `tests/test_app_v03.py` (6 import call sites: lines 450, 467, 475, 483, 492, 499)

**Interfaces:**
- Produces: `components.score_tier(score: int) -> str`, `components.signal_ledger_html(label: str, score: int, sub: str = "", tier: str | None = None) -> str`, `components.risk_ledger_table_html(rows: list) -> str` — same names, same signatures, same behavior as the deleted `ledger_components.py`'s functions. Later tasks (3-5) append their own sections to this same file.
- Consumes: `risk_ledger.severity_tier` (unchanged, `risk_ledger.py` is not part of this consolidation).

- [ ] **Step 1: Create `src/components.py` with the Ledger section**

```python
"""
QAI Consultant -- reusable Streamlit HTML/CSS components.

Consolidates four previously separate modules (ledger_components.py,
landing_hero.py, interactive_flow_style.py, output_screen_style.py) that
were split by which "Power-On Sequence" redesign PR touched them, not by
functional boundary -- see
docs/superpowers/plans/2026-09-17-architecture-cleanup.md. All functions
are pure (a token dict plus plain arguments -> an HTML string); callers
render the result via st.markdown(html, unsafe_allow_html=True). No
Streamlit dependency in this module itself, so every function here is
directly unit-testable without a Streamlit runtime -- see
tests/test_components.py.

All user-supplied text (labels, descriptions, project-context field
values) is HTML-escaped via html.escape() before interpolation -- this
renders LLM-generated and user-uploaded content, so unescaped
interpolation would be a stored-XSS path via unsafe_allow_html=True.

theme.py is NOT modified by anything here and stays a separate file (it
owns tokens + base CSS, including the shared .ledger-card base rule);
functions below only ever add scoped CSS additions (e.g.
.ledger-card:hover) that compose safely with theme.py's rules regardless
of <style> tag load order.
"""
import html as _html

from risk_ledger import severity_tier


# ── Ledger: score/severity HTML (Signal Ledger, Risk Ledger table) ─────────

def score_tier(score: int) -> str:
    """Map a 0-100 score to a Signal Ledger tier. >=80 pass, 50-79 hold,
    <50 fail -- the same thresholds used app-wide."""
    if score >= 80:
        return "pass"
    if score >= 50:
        return "hold"
    return "fail"


def signal_ledger_html(label: str, score: int, sub: str = "", tier: str | None = None) -> str:
    """A compact score readout: an uppercase mono label, a large tabular
    score, an optional sub-line, and a 10-segment meter. `tier` overrides
    the auto-computed pass/hold/fail class when the caller's score isn't a
    "higher is better toward 100" quality score (e.g. it's fine to leave
    unset for Review/Results scores, and explicit for anything where the
    caller has better domain judgment than the generic 80/50 split)."""
    resolved_tier = tier or score_tier(score)
    filled = max(0, min(10, round(score / 10)))
    meter = "".join(
        f'<i class="on {resolved_tier}"></i>' if i < filled else "<i></i>"
        for i in range(10)
    )
    sub_html = f'<div class="sl-sub">{_html.escape(sub)}</div>' if sub else ""
    return (
        '<div class="signal-ledger">'
        f'<div class="sl-label">{_html.escape(label)}</div>'
        f'<div class="sl-score {resolved_tier}">{score}</div>'
        f"{sub_html}"
        f'<div class="sl-meter">{meter}</div>'
        "</div>"
    )


def risk_ledger_table_html(rows: list) -> str:
    """Render parsed Risk Matrix rows (risk_ledger.parse_risk_matrix()'s
    output shape) as a <table class="risk-ledger">. Empty input returns ""
    so callers can `if html: st.markdown(html, ...)` without a blank
    table appearing."""
    if not rows:
        return ""

    body_rows = []
    for row in rows:
        tier = severity_tier(row.get("risk_level", ""))
        body_rows.append(
            "<tr>"
            f'<td class="rid">{_html.escape(row.get("risk_id", ""))}</td>'
            f'<td><span class="sev {tier}">{_html.escape(row.get("risk_level", ""))}</span></td>'
            f'<td>{_html.escape(row.get("description", ""))}</td>'
            f'<td>{_html.escape(row.get("likelihood", ""))}</td>'
            f'<td>{_html.escape(row.get("impact", ""))}</td>'
            f'<td class="rid">{_html.escape(row.get("priority", ""))}</td>'
            "</tr>"
        )

    return (
        '<table class="risk-ledger">'
        "<thead><tr>"
        "<th>ID</th><th>Severity</th><th>Risk</th>"
        "<th>Likelihood</th><th>Impact</th><th>Priority</th>"
        "</tr></thead>"
        f"<tbody>{''.join(body_rows)}</tbody>"
        "</table>"
    )
```

- [ ] **Step 2: Create `tests/test_components.py` with `test_ledger_components.py`'s content**

Read `tests/test_ledger_components.py` in full, then write `tests/test_components.py` with the identical file content except its `from ledger_components import (...)` line becomes `from components import (...)` (same imported names) and its module docstring's first line changes from referencing `ledger_components.py` to referencing `components.py`'s Ledger section. Do not change any test function body, fixture, or assertion.

- [ ] **Step 3: Delete the old module and test file**

```bash
git rm src/ledger_components.py tests/test_ledger_components.py
```

- [ ] **Step 4: Update `src/app.py`'s 5 import call sites**

Run `grep -n "from ledger_components import" src/app.py` to confirm current line numbers (approximately 635, 984, 1019, 1267, 1479 as of this plan's writing — earlier tasks don't touch `app.py`, but re-check anyway). These 5 call sites do NOT all share the same indentation (they sit at different nesting depth inside different functions), so match on the import statement text only, without leading whitespace, and let `replace_all` handle each line's own indentation:

Using the Edit tool, replace (matching only this substring, not the full line, so differing leading whitespace across call sites doesn't block the match):

- old_string: `from ledger_components import signal_ledger_html` / new_string: `from components import signal_ledger_html` / `replace_all: true` — matches all 4 occurrences of this specific import (lines 635, 1019, 1267, 1479)
- old_string: `from ledger_components import risk_ledger_table_html` / new_string: `from components import risk_ledger_table_html` — 1 occurrence (line 984), `replace_all` not required but harmless

- [ ] **Step 5: Update `tests/test_app_v03.py`'s 6 import call sites**

Replace every occurrence of `from ledger_components import` with `from components import` (`replace_all` — all 6 occurrences import one of `risk_ledger_table_html`, `signal_ledger_html`, or `score_tier`, and every occurrence uses the identical `from ledger_components import <name>` phrasing per the earlier grep, so the module-name swap is safe as a blind global replace here too).

- [ ] **Step 6: Run the full test suite**

Run: `python -m pytest tests/ -v`
Expected: PASS, including `tests/test_components.py` (with the same test count `test_ledger_components.py` had) and `tests/test_app_v03.py`.

- [ ] **Step 7: Commit**

```bash
git add src/components.py tests/test_components.py src/app.py tests/test_app_v03.py
git commit -m "$(cat <<'EOF'
refactor: fold ledger_components.py into new components.py

First of four styling-module merges (see
docs/superpowers/plans/2026-09-17-architecture-cleanup.md) -- these
modules were split by which redesign PR touched them, not by
functional boundary. Pure move: score_tier/signal_ledger_html/
risk_ledger_table_html keep identical signatures and behavior.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_013xJEqRuCdtixjGy8hpg3jB
EOF
)"
```

---

### Task 3: Fold `landing_hero.py` into `components.py`

**Files:**
- Modify: `src/components.py` (append)
- Modify: `tests/test_components.py` (append)
- Delete: `src/landing_hero.py`, `tests/test_landing_hero.py`
- Modify: `src/app.py` (2 import call sites, lines ~416, ~424)

**Interfaces:**
- Consumes: nothing from Task 2 (independent section).
- Produces: `components.build_landing_hero_html(tokens: dict) -> str`, `components.build_landing_deliverables_html(tokens: dict) -> str` — same names/signatures/behavior as the deleted `landing_hero.py`.

- [ ] **Step 1: Append the Landing section to `src/components.py`**

Add after the end of the Ledger section (after `risk_ledger_table_html`'s closing `)`  and the blank lines that follow it):

```python
# ── Landing: hero + "How it works" / "What you get" (Phase 1) ─────────────
# All animations here are one-shot on page load. Relies on theme.py's
# global prefers-reduced-motion rule (build_css()) to zero out
# animation-duration/transition-duration, but that rule does NOT zero
# animation-delay -- left alone, a "pom-" element with a nonzero delay
# would sit at its pre-animation opacity:0 state for the full delay
# before snapping in, which is the opposite of "reduced motion". Each of
# the two functions below defines its own scoped prefers-reduced-motion
# block to zero its own delays; do not remove either as "redundant" with
# theme.py's rule -- they cover different CSS properties.

def build_landing_hero_html(tokens: dict) -> str:
    """Pure function: token dict -> hero + "How it works" HTML block."""
    return f"""
<style>
@keyframes pom-reveal {{ from {{ clip-path: inset(0 100% 0 0); }} to {{ clip-path: inset(0 0 0 0); }} }}
@keyframes pom-fill-risk {{ from {{ width: 0%; }} to {{ width: 82%; }} }}
@keyframes pom-fill-effort {{ from {{ width: 0%; }} to {{ width: 58%; }} }}
@keyframes pom-fill-strategy {{ from {{ width: 0%; }} to {{ width: 94%; }} }}
@keyframes pom-tick {{ from {{ opacity: 0; transform: translateY(4px); }} to {{ opacity: 1; transform: translateY(0); }} }}
@keyframes pom-card-in {{ from {{ opacity: 0; transform: translateY(10px); }} to {{ opacity: 1; transform: translateY(0); }} }}

.pom-hero {{ padding: 0.5rem 0 1.5rem; }}
.pom-headline {{ font-family: 'Plex Sans', sans-serif; font-weight: 700; font-size: 2rem; line-height: 1.18; color: {tokens['ink']}; margin-bottom: 0.4rem; overflow: hidden; }}
.pom-headline span {{ display: inline-block; animation: pom-reveal 0.9s steps(30) 0.1s both; }}
.pom-readout {{ font-family: 'Plex Mono', monospace; font-size: 0.78rem; color: {tokens['ink_dim']}; margin-bottom: 1.4rem; }}

.pom-gauges {{ display: flex; gap: 0.8rem; margin-bottom: 1.6rem; max-width: 480px; }}
.pom-gauge {{ flex: 1; }}
.pom-gauge .pom-glabel {{ font-family: 'Plex Mono', monospace; font-size: 0.62rem; letter-spacing: 0.06em; text-transform: uppercase; color: {tokens['ink_dim']}; margin-bottom: 0.25rem; }}
.pom-gauge .pom-gtrack {{ height: 6px; background: {tokens['surface_2']}; border-radius: 3px; overflow: hidden; }}
.pom-gauge .pom-gfill {{ height: 100%; }}
.pom-gauge.risk .pom-gfill {{ background: {tokens['pass_']}; animation: pom-fill-risk 1.4s ease-out 0.5s both; }}
.pom-gauge.effort .pom-gfill {{ background: {tokens['hold']}; animation: pom-fill-effort 1.4s ease-out 0.7s both; }}
.pom-gauge.strategy .pom-gfill {{ background: {tokens['accent']}; animation: pom-fill-strategy 1.4s ease-out 0.9s both; }}

.pom-standards {{ display: flex; gap: 0.5rem; flex-wrap: wrap; margin-bottom: 1.8rem; }}
.pom-standards span {{ font-family: 'Plex Mono', monospace; font-size: 0.62rem; letter-spacing: 0.03em; color: {tokens['accent']}; border: 1px solid {tokens['line']}; padding: 0.15rem 0.5rem; border-radius: 4px; opacity: 0; animation: pom-tick 0.3s ease-out both; }}
.pom-standards span:nth-child(1) {{ animation-delay: 1.1s; }}
.pom-standards span:nth-child(2) {{ animation-delay: 1.25s; }}
.pom-standards span:nth-child(3) {{ animation-delay: 1.4s; }}
.pom-standards span:nth-child(4) {{ animation-delay: 1.55s; }}

.pom-cards {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.9rem; }}
@media (max-width: 640px) {{ .pom-cards {{ grid-template-columns: 1fr; }} }}
.pom-card {{ background: {tokens['surface']}; border: 1px solid {tokens['line']}; border-radius: 8px; padding: 1rem 1.1rem; opacity: 0; animation: pom-card-in 0.5s ease-out both; transition: transform 0.2s ease-out, box-shadow 0.2s ease-out, border-color 0.2s ease-out; }}
.pom-card:hover {{ border-color: {tokens['accent']}; box-shadow: 0 4px 14px rgba(0,0,0,0.08); transform: translateY(-2px); }}
.pom-card:nth-child(1) {{ animation-delay: 1.7s; }}
.pom-card:nth-child(2) {{ animation-delay: 1.85s; }}
.pom-card:nth-child(3) {{ animation-delay: 2.0s; }}
.pom-card .pom-cidx {{ font-family: 'Plex Mono', monospace; font-size: 0.62rem; color: {tokens['ink_dim']}; margin-bottom: 0.35rem; }}
.pom-card .pom-ctitle {{ font-family: 'Plex Sans', sans-serif; font-weight: 600; font-size: 0.92rem; color: {tokens['ink']}; margin-bottom: 0.2rem; }}
.pom-card .pom-cbody {{ font-family: 'Plex Sans', sans-serif; font-size: 0.8rem; color: {tokens['ink_dim']}; }}

@media (prefers-reduced-motion: reduce) {{
  .pom-headline span, .pom-gauge .pom-gfill, .pom-standards span, .pom-card {{
    animation-delay: 0s !important;
  }}
}}
</style>

<div class="pom-hero">
  <div class="pom-headline"><span>Your AI QA Architect, grounded in standards.</span></div>
  <div class="pom-readout">&gt; calibration sequence: 3 instruments online</div>
  <div class="pom-gauges">
    <div class="pom-gauge risk"><div class="pom-glabel">Risk</div><div class="pom-gtrack"><div class="pom-gfill"></div></div></div>
    <div class="pom-gauge effort"><div class="pom-glabel">Effort</div><div class="pom-gtrack"><div class="pom-gfill"></div></div></div>
    <div class="pom-gauge strategy"><div class="pom-glabel">Strategy</div><div class="pom-gtrack"><div class="pom-gfill"></div></div></div>
  </div>
  <div class="pom-standards">
    <span>&#10003; ISTQB</span>
    <span>&#10003; OWASP</span>
    <span>&#10003; IEEE 829</span>
    <span>&#10003; ISO 25010</span>
  </div>
  <div class="pom-cards">
    <div class="pom-card"><div class="pom-cidx">01</div><div class="pom-ctitle">Answer a few questions</div><div class="pom-cbody">About your project.</div></div>
    <div class="pom-card"><div class="pom-cidx">02</div><div class="pom-ctitle">AI analyzes</div><div class="pom-cbody">Using QA methodologies &amp; standards.</div></div>
    <div class="pom-card"><div class="pom-cidx">03</div><div class="pom-ctitle">Download your strategy</div><div class="pom-cbody">Tailored Test Strategy (Markdown &amp; PDF).</div></div>
  </div>
</div>
"""


def build_landing_deliverables_html(tokens: dict) -> str:
    """Pure function: token dict -> the "What you get in ~2 minutes"
    deliverable cards + stat tiles HTML block. Reuses
    build_landing_hero_html()'s .pom-card/.pom-cidx/.pom-ctitle/.pom-cbody
    classes and pom-card-in keyframe (defined above, always rendered
    first on the same screen) rather than redefining them, and continues
    its animation-delay cadence (which ends at 2.0s)."""
    deliverables = [
        ("⚠️", "Risk Register", "Prioritized risks with likelihood, impact &amp; mitigation — before a single line of code is written."),
        ("📊", "Effort Estimation", "PERT-based timeline with team capacity analysis and a confidence score (0–100)."),
        ("📋", "Test Strategy", "ISTQB-aligned approach tailored to your stack, methodology, and compliance requirements."),
        ("📝", "Test Plan", "IEEE 829-aligned plan with test items, entry/exit criteria, schedule, and AI tool oversight."),
    ]
    stats = [
        ("Time to results", "~2 min", "vs. hours of manual work"),
        ("Standards", "ISTQB · OWASP · ISO", "7,100+ knowledge vectors"),
        ("Deliverables", "4 documents", "Risk · Effort · Strategy · Plan"),
        ("Cost", "Free", "No sign-up required"),
    ]
    deliverable_cards = "".join(
        f'<div class="pom-card"><div class="pom-cidx">{icon}</div>'
        f'<div class="pom-ctitle">{title}</div><div class="pom-cbody">{body}</div></div>'
        for icon, title, body in deliverables
    )
    deliverable_delay_rules = "\n".join(
        f".pom-deliverables .pom-card:nth-child({i}) {{ animation-delay: {2.15 + (i - 1) * 0.15:.2f}s; }}"
        for i in range(1, len(deliverables) + 1)
    )
    stat_tiles = "".join(
        f'<div class="pom-stat"><div class="pom-slabel">{label}</div>'
        f'<div class="pom-svalue">{value}</div><div class="pom-ssub">{sub}</div></div>'
        for label, value, sub in stats
    )
    stat_delay_rules = "\n".join(
        f".pom-stats .pom-stat:nth-child({i}) {{ animation-delay: {2.85 + (i - 1) * 0.1:.2f}s; }}"
        for i in range(1, len(stats) + 1)
    )
    return f"""
<style>
.pom-deliverables {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 0.9rem; margin-bottom: 1.6rem; }}
@media (max-width: 640px) {{ .pom-deliverables {{ grid-template-columns: 1fr; }} }}
{deliverable_delay_rules}
.pom-stats {{ display: flex; gap: 1.4rem; flex-wrap: wrap; }}
.pom-stat {{ opacity: 0; animation: pom-card-in 0.5s ease-out both; }}
{stat_delay_rules}
.pom-stat .pom-slabel {{ font-family: 'Plex Mono', monospace; font-size: 0.62rem; letter-spacing: 0.06em; text-transform: uppercase; color: {tokens['ink_dim']}; margin-bottom: 0.25rem; }}
.pom-stat .pom-svalue {{ font-family: 'Plex Mono', monospace; font-size: 1.1rem; font-weight: 500; color: {tokens['ink']}; }}
.pom-stat .pom-ssub {{ font-family: 'Plex Sans', sans-serif; font-size: 0.72rem; color: {tokens['ink_dim']}; }}
@media (prefers-reduced-motion: reduce) {{
  .pom-deliverables .pom-card, .pom-stat {{
    animation-delay: 0s !important;
  }}
}}
</style>
<div class="pom-readout">&gt; what you get in ~2 minutes</div>
<div class="pom-deliverables">{deliverable_cards}</div>
<div class="pom-stats">{stat_tiles}</div>
"""
```

- [ ] **Step 2: Append `test_landing_hero.py`'s content to `tests/test_components.py`**

Read `tests/test_landing_hero.py` in full. Append its test functions (not its module docstring or imports, which `test_components.py` already has/will be reconciled) to the end of `tests/test_components.py`, under a new section comment `# ── Landing ─────────────────────────────────────────────────────────────`. Its `from landing_hero import build_landing_hero_html` / `from landing_hero import build_landing_deliverables_html` lines are dropped entirely — add `build_landing_hero_html, build_landing_deliverables_html` to `test_components.py`'s existing top-level `from components import (...)` line instead (do not add a second, separate import line).

- [ ] **Step 3: Delete the old module and test file**

```bash
git rm src/landing_hero.py tests/test_landing_hero.py
```

- [ ] **Step 4: Update `src/app.py`'s 2 import call sites**

Run `grep -n "from landing_hero import" src/app.py` to confirm current line numbers (approximately 416, 424 as of this plan's writing). Using the Edit tool, match on the import statement text only (without leading whitespace, since indentation may differ from what's shown here):

- old_string: `from landing_hero import build_landing_hero_html` / new_string: `from components import build_landing_hero_html`
- old_string: `from landing_hero import build_landing_deliverables_html` / new_string: `from components import build_landing_deliverables_html`

- [ ] **Step 5: Run the full test suite**

Run: `python -m pytest tests/ -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/components.py tests/test_components.py src/app.py
git commit -m "$(cat <<'EOF'
refactor: fold landing_hero.py into components.py

Second of four styling-module merges (see
docs/superpowers/plans/2026-09-17-architecture-cleanup.md). Pure move:
build_landing_hero_html/build_landing_deliverables_html keep identical
signatures and behavior.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_013xJEqRuCdtixjGy8hpg3jB
EOF
)"
```

---

### Task 4: Fold `interactive_flow_style.py` into `components.py`

**Files:**
- Modify: `src/components.py` (append)
- Modify: `tests/test_components.py` (append)
- Delete: `src/interactive_flow_style.py`, `tests/test_interactive_flow_style.py`
- Modify: `src/app.py` (3 import call sites, lines ~278, ~485, ~586)

**Interfaces:**
- Consumes: nothing from Tasks 2-3 (independent section).
- Produces: `components.build_dialogue_header_html(tokens: dict, answered: int, total: int) -> str`, `components.build_review_summary_html(tokens: dict, context, animate: bool) -> str`, `components.build_sidebar_polish_css(tokens: dict) -> str` — same names/signatures/behavior as the deleted `interactive_flow_style.py`.

- [ ] **Step 1: Append the Dialogue/Sidebar section to `src/components.py`**

Add after the end of the Landing section:

```python
# ── Dialogue & Sidebar: interactive-flow styling (Phase 2) ─────────────────
# The dialogue and review screens rerun on user interaction (template
# selection, "Additional context" edits) -- unlike the landing screen
# (rendered once per session). Mount-triggered CSS keyframe animations
# would replay every time, which is why the dialogue screen below gets NO
# entrance animation (only a CSS *transition* on the progress bar, which
# is expected to re-fire on every value change), and the review screen's
# one-shot entrance is controlled entirely by the caller-supplied
# `animate` flag (app.py derives it from a session_state "seen" flag).
# The sidebar gets no entrance animation either -- it persists across
# every screen and rerun in the app.
#
# .ledger-card's base rule lives in theme.py; the :hover rule below
# composes with it safely regardless of <style> tag load order (an
# additive pseudo-class selector, not an override) -- this is the only
# place in this file that styles a theme.py-owned class.

def build_dialogue_header_html(tokens: dict, answered: int, total: int) -> str:
    """Pure function: token dict + progress counts -> dialogue header HTML
    (eyebrow label + animated-width progress bar) plus the .ledger-card
    hover rule."""
    pct = round((answered / total) * 100) if total else 0
    return f"""
<style>
.ledger-card:hover {{ border-color: {tokens['accent']}; box-shadow: 0 4px 14px rgba(0,0,0,0.08); transform: translateY(-2px); transition: transform 0.2s ease-out, box-shadow 0.2s ease-out, border-color 0.2s ease-out; }}
.dialogue-eyebrow {{ font-family: 'Plex Mono', monospace; font-size: 0.7rem; letter-spacing: 0.06em; text-transform: uppercase; color: {tokens['ink_dim']}; margin-bottom: 0.4rem; }}
.dialogue-progress-track {{ height: 6px; background: {tokens['surface_2']}; border-radius: 3px; overflow: hidden; margin: 0.6rem 0 1.2rem; }}
.dialogue-progress-fill {{ height: 100%; background: {tokens['accent']}; transition: width 0.4s ease-out; }}
</style>
<div class="dialogue-eyebrow">&gt; project discovery sequence: {answered}/{total} instruments calibrated</div>
<div class="dialogue-progress-track"><div class="dialogue-progress-fill" style="width: {pct}%;"></div></div>
"""


def build_review_summary_html(tokens: dict, context, animate: bool) -> str:
    """Pure function: token dict + a duck-typed project-context object
    (any object exposing project_name, project_type, tech_stack,
    methodology, timeline, team_qa_size, team_dev_size, known_risks,
    existing_automation, compliance_requirements) + whether to play the
    one-shot entrance -> review summary tiles HTML. All field values are
    HTML-escaped."""
    fields = [
        ("Project Name", context.project_name),
        ("Project Type", context.project_type),
        ("Tech Stack", context.tech_stack),
        ("Methodology", context.methodology),
        ("Timeline", context.timeline),
        ("QA Team Size", context.team_qa_size),
        ("Dev Team Size", context.team_dev_size),
        ("Known Risks", context.known_risks),
        ("Existing Automation", context.existing_automation),
        ("Compliance", context.compliance_requirements),
    ]
    animate_class = " animate" if animate else ""
    delay_rules = "\n".join(
        f".review-grid.animate .review-tile:nth-child({i}) {{ animation-delay: {i * 0.05:.2f}s; }}"
        for i in range(1, len(fields) + 1)
    )
    tiles = "".join(
        f'<div class="review-tile"><div class="rt-label">{_html.escape(label)}</div>'
        f'<div class="rt-value">{_html.escape(value)}</div></div>'
        for label, value in fields
    )
    return f"""
<style>
.review-grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 0.7rem; margin-bottom: 1rem; }}
@media (max-width: 640px) {{ .review-grid {{ grid-template-columns: 1fr; }} }}
.review-tile {{ background: {tokens['surface']}; border: 1px solid {tokens['line']}; border-radius: 8px; padding: 0.8rem 1rem; }}
.review-tile .rt-label {{ font-family: 'Plex Mono', monospace; font-size: 0.62rem; letter-spacing: 0.06em; text-transform: uppercase; color: {tokens['ink_dim']}; margin-bottom: 0.3rem; }}
.review-tile .rt-value {{ font-family: 'Plex Sans', sans-serif; font-size: 0.92rem; color: {tokens['ink']}; word-break: break-word; }}
@keyframes review-tile-in {{ from {{ opacity: 0; transform: translateY(8px); }} to {{ opacity: 1; transform: translateY(0); }} }}
.review-grid.animate .review-tile {{ opacity: 0; animation: review-tile-in 0.4s ease-out forwards; }}
{delay_rules}
@media (prefers-reduced-motion: reduce) {{
    .review-grid.animate .review-tile {{ animation-delay: 0s !important; }}
}}
</style>
<div class="review-grid{animate_class}">{tiles}</div>
"""


def build_sidebar_polish_css(tokens: dict) -> str:
    """Pure function: token dict -> sidebar hover-state CSS only -- no
    entrance animations, since the sidebar persists across every screen
    and rerun in the app."""
    return f"""
<style>
[data-testid="stSidebar"] button:hover {{ border-color: {tokens['accent']}; color: {tokens['accent']}; transition: border-color 0.15s ease-out, color 0.15s ease-out; }}
[data-testid="stSidebar"] [data-testid="stExpander"] summary:hover {{ color: {tokens['accent']}; transition: color 0.15s ease-out; }}
</style>
"""
```

- [ ] **Step 2: Append `test_interactive_flow_style.py`'s content to `tests/test_components.py`**

Read `tests/test_interactive_flow_style.py` in full. Append its test functions to the end of `tests/test_components.py`, under a new section comment `# ── Dialogue & Sidebar ──────────────────────────────────────────────────`. Add `build_dialogue_header_html, build_review_summary_html, build_sidebar_polish_css` to `test_components.py`'s existing `from components import (...)` line instead of a separate import.

- [ ] **Step 3: Delete the old module and test file**

```bash
git rm src/interactive_flow_style.py tests/test_interactive_flow_style.py
```

- [ ] **Step 4: Update `src/app.py`'s 3 import call sites**

Run `grep -n "from interactive_flow_style import" src/app.py` to confirm current line numbers (approximately 278, 485, 586 as of this plan's writing). Using the Edit tool, match on the import statement text only (without leading whitespace, since these three sit at different indentation depths):

- old_string: `from interactive_flow_style import build_sidebar_polish_css` / new_string: `from components import build_sidebar_polish_css`
- old_string: `from interactive_flow_style import build_dialogue_header_html` / new_string: `from components import build_dialogue_header_html`
- old_string: `from interactive_flow_style import build_review_summary_html` / new_string: `from components import build_review_summary_html`

(three distinct import names, each occurring once — no `replace_all` needed.)

- [ ] **Step 5: Run the full test suite**

Run: `python -m pytest tests/ -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/components.py tests/test_components.py src/app.py
git commit -m "$(cat <<'EOF'
refactor: fold interactive_flow_style.py into components.py

Third of four styling-module merges (see
docs/superpowers/plans/2026-09-17-architecture-cleanup.md). Pure move:
build_dialogue_header_html/build_review_summary_html/
build_sidebar_polish_css keep identical signatures and behavior.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_013xJEqRuCdtixjGy8hpg3jB
EOF
)"
```

---

### Task 5: Fold `output_screen_style.py` into `components.py`

**Files:**
- Modify: `src/components.py` (append)
- Modify: `tests/test_components.py` (append)
- Delete: `src/output_screen_style.py`, `tests/test_output_screen_style.py`
- Modify: `src/app.py` (5 import call sites, lines ~739, ~1196, ~1210, ~1414, ~1430)

**Interfaces:**
- Consumes: nothing from Tasks 2-4 (independent section).
- Produces: `components.build_output_eyebrow_html(tokens: dict, label: str) -> str`, `components.build_stage_sequence_html(tokens: dict, stages: list) -> str`, `components.build_content_polish_css(tokens: dict) -> str`, `components.build_doc_review_input_tray_css(tokens: dict) -> str` — same names/signatures/behavior as the deleted `output_screen_style.py`.

- [ ] **Step 1: Append the Output section to `src/components.py`**

Add after the end of the Dialogue & Sidebar section:

```python
# ── Output screens: strategy + doc-review styling (Phase 3) ───────────────
# Selectors here are verified against this app's real rendered Streamlit
# 1.59.1 DOM (data-testid/aria attributes), not guessed. The stage-sequence
# indicator's "active" dot uses a looping pulse animation -- unlike every
# other animation in this file, which are all one-shot -- because it
# signals a real, currently-running background process (an in-flight LLM
# call), not decorative motion; theme.py's global prefers-reduced-motion
# rule already disables it (it has no animation-delay for that rule to
# miss, unlike the Landing section above).

def build_output_eyebrow_html(tokens: dict, label: str) -> str:
    """Pure function: token dict + a caller-supplied label -> a mono
    uppercase eyebrow line, reusing the label style
    .dialogue-eyebrow established above. `label` is HTML-escaped."""
    return f"""
<style>
.output-eyebrow {{ font-family: 'Plex Mono', monospace; font-size: 0.7rem; letter-spacing: 0.06em; text-transform: uppercase; color: {tokens['ink_dim']}; margin-bottom: 0.4rem; }}
</style>
<div class="output-eyebrow">&gt; {_html.escape(label)}</div>
"""


def build_stage_sequence_html(tokens: dict, stages: list) -> str:
    """Pure function: token dict + an ordered list of (label, status)
    tuples (status is "pending", "active", "done", or "failed") -> a
    horizontal stage-status readout. Used only by render_strategy(). Not
    gated by any session-state "seen" flag: it is a live status readout
    driven by whichever stages are already in session_state, not a mount
    animation, so it must render correctly every time it is called.

    "failed" exists because render_strategy()'s per-stage try/except sets
    a stage's session-state key to "" (not None) when its LLM call fails,
    so the stage stays present-but-empty rather than reverting to unset --
    the caller must distinguish that from a real result and pass "failed",
    not "done", or this live status readout would falsely show green
    success next to its own red st.error message."""
    items = "".join(
        f'<div class="stage-item {status}"><span class="stage-dot"></span>{_html.escape(label)}</div>'
        for label, status in stages
    )
    return f"""
<style>
.stage-sequence {{ display: flex; gap: 0.6rem; margin-bottom: 1.2rem; flex-wrap: wrap; }}
.stage-item {{ display: flex; align-items: center; gap: 0.4rem; font-family: 'Plex Mono', monospace; font-size: 0.68rem; letter-spacing: 0.04em; text-transform: uppercase; padding: 0.3rem 0.7rem; border: 1px solid {tokens['line']}; border-radius: 4px; color: {tokens['ink_dim']}; }}
.stage-item .stage-dot {{ width: 7px; height: 7px; border-radius: 50%; background: {tokens['line']}; display: inline-block; }}
.stage-item.pending {{ opacity: 0.55; }}
.stage-item.active {{ color: {tokens['ink']}; border-color: {tokens['accent']}; }}
.stage-item.active .stage-dot {{ background: {tokens['accent']}; animation: stage-pulse 1.2s ease-in-out infinite; }}
.stage-item.done {{ color: {tokens['ink']}; border-color: {tokens['pass_']}; }}
.stage-item.done .stage-dot {{ background: {tokens['pass_']}; }}
.stage-item.failed {{ color: {tokens['ink']}; border-color: {tokens['fail']}; }}
.stage-item.failed .stage-dot {{ background: {tokens['fail']}; }}
@keyframes stage-pulse {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0.35; }} }}
</style>
<div class="stage-sequence">{items}</div>
"""


def build_content_polish_css(tokens: dict) -> str:
    """Pure function: token dict -> CSS shared by render_strategy() and
    render_doc_review(): main-content button/expander hover states (same
    treatment build_sidebar_polish_css() gives the sidebar above, scoped
    to [data-testid="stMain"] instead of [data-testid="stSidebar"] so both
    rule sets coexist without conflict), a themed tab bar, and the
    .output-tiles score-tile entrance animation.

    The hover `color` override is split into its own rule that excludes
    `type="primary"` buttons (Streamlit 1.59.1 renders the `<button>`
    itself with `data-testid="stBaseButton-primary"`/`"-secondary"`).
    Streamlit's default `primaryColor` (#FF4B4B, red) already gives a
    primary button's label white-on-red contrast; repainting that label to
    this app's blue accent on hover leaves it barely legible against the
    still-red fill (~1.56:1 in the light theme, far under WCAG AA's
    4.5:1). `border-color` has no such problem and stays unscoped."""
    return f"""
<style>
[data-testid="stMain"] [data-testid="stButton"] button:hover,
[data-testid="stMain"] [data-testid="stDownloadButton"] button:hover {{
    border-color: {tokens['accent']};
    transition: border-color 0.15s ease-out, color 0.15s ease-out;
}}
[data-testid="stMain"] [data-testid="stButton"] button:not([data-testid$="-primary"]):hover,
[data-testid="stMain"] [data-testid="stDownloadButton"] button:not([data-testid$="-primary"]):hover {{
    color: {tokens['accent']};
}}
[data-testid="stMain"] [data-testid="stExpander"] summary:hover {{
    color: {tokens['accent']};
    transition: color 0.15s ease-out;
}}
[data-testid="stTabs"] [data-testid="stTab"] p {{
    font-family: 'Plex Mono', monospace;
    font-size: 0.78rem;
    letter-spacing: 0.03em;
    text-transform: uppercase;
}}
[data-testid="stTabs"] [data-testid="stTab"][aria-selected="true"] p {{
    color: {tokens['accent']};
}}
[data-testid="stTabs"] .react-aria-SelectionIndicator {{
    background: {tokens['accent']} !important;
}}
@keyframes output-tiles-in {{ from {{ opacity: 0; transform: translateY(8px); }} to {{ opacity: 1; transform: translateY(0); }} }}
.output-tiles.animate {{ animation: output-tiles-in 0.4s ease-out both; }}
</style>
"""


def build_doc_review_input_tray_css(tokens: dict) -> str:
    """Pure function: token dict -> CSS styling the
    st.container(key="doc-review-input") wrapper around render_doc_review()'s
    intake widgets (doc-type selectbox, file uploader, paste text area) as a
    .ledger-card-equivalent input tray. Uses Streamlit's key= scoping
    technique (a container's key="foo" generates a st-key-foo CSS class)
    rather than reusing .ledger-card itself, which is scoped to the
    dialogue screen's per-question cards above."""
    return f"""
<style>
/* Deliberately kept byte-for-byte in sync with theme.py's .ledger-card
   background/border/padding/margin block (build_css()) -- edit both
   together if that ruleset ever changes. */
.st-key-doc-review-input {{
    background: {tokens['surface']};
    border: 1px solid {tokens['line']};
    padding: 1.1rem 1.3rem;
    margin-bottom: 1rem;
}}
</style>
"""
```

- [ ] **Step 2: Append `test_output_screen_style.py`'s content to `tests/test_components.py`**

Read `tests/test_output_screen_style.py` in full. Append its test functions to the end of `tests/test_components.py`, under a new section comment `# ── Output screens ──────────────────────────────────────────────────────`. Add `build_output_eyebrow_html, build_stage_sequence_html, build_content_polish_css, build_doc_review_input_tray_css` to `test_components.py`'s existing `from components import (...)` line instead of a separate import.

- [ ] **Step 3: Delete the old module and test file**

```bash
git rm src/output_screen_style.py tests/test_output_screen_style.py
```

- [ ] **Step 4: Update `src/app.py`'s 5 import call sites**

Locate with `grep -n "from output_screen_style import" src/app.py` (approximately lines 739, 1196, 1210, 1414, 1430) and replace each occurrence of `from output_screen_style import` with `from components import` (`replace_all` is safe here — only the module name changes, the imported-name lists after `import` are copied through unchanged regardless of which names each specific line lists).

- [ ] **Step 5: Run the full test suite**

Run: `python -m pytest tests/ -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/components.py tests/test_components.py src/app.py
git commit -m "$(cat <<'EOF'
refactor: fold output_screen_style.py into components.py

Last of four styling-module merges (see
docs/superpowers/plans/2026-09-17-architecture-cleanup.md). Pure move:
build_output_eyebrow_html/build_stage_sequence_html/
build_content_polish_css/build_doc_review_input_tray_css keep identical
signatures and behavior. Six Streamlit-styling modules split by which
redesign PR touched them are now two: theme.py (tokens + base CSS) and
components.py (everything else).

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_013xJEqRuCdtixjGy8hpg3jB
EOF
)"
```

---

### Task 6: Final verification and CLAUDE.md update

**Files:**
- Modify: `CLAUDE.md`

**Interfaces:**
- Consumes: Tasks 1-5's completed, committed changes.

- [ ] **Step 1: Confirm no stale references remain**

Run: `grep -rln "ledger_components\|landing_hero\|interactive_flow_style\|output_screen_style" src/ tests/ 2>/dev/null`
Expected: no matches (confirms every import call site and every test file was actually updated, not just the ones enumerated in Tasks 2-5's steps — this catches anything missed).

- [ ] **Step 2: Run the full test suite, lint, and the deterministic eval gate**

Run: `python -m pytest tests/ -v && ruff check src/ tests/ && python -m evals.run --det`
Expected: PASS.

- [ ] **Step 3: Update CLAUDE.md's architecture table**

Locate the `ledger_components.py` row (anchor: `` | `ledger_components.py` | (v3.4) ``), the `landing_hero.py` row (anchor: `` | `landing_hero.py` | (v3.4.1) ``), the `interactive_flow_style.py` row (anchor: `` | `interactive_flow_style.py` | (v3.4.2) ``), and the `output_screen_style.py` row (anchor: `` | `output_screen_style.py` | (v3.4.3) ``). Delete all four rows and replace them with a single new row in the same position as the first one:

```markdown
| `components.py` | (v3.6, consolidated from `ledger_components.py`/`landing_hero.py`/`interactive_flow_style.py`/`output_screen_style.py`) Reusable Streamlit HTML/CSS component builders — Signal Ledger + Risk Ledger table (`score_tier`, `signal_ledger_html`, `risk_ledger_table_html`), the landing hero + "How it works"/"What you get" cards (`build_landing_hero_html`, `build_landing_deliverables_html`), dialogue/review/sidebar styling (`build_dialogue_header_html`, `build_review_summary_html`, `build_sidebar_polish_css`), and output-screen styling (`build_output_eyebrow_html`, `build_stage_sequence_html`, `build_content_polish_css`, `build_doc_review_input_tray_css`). All pure functions (token dict [+ plain args] → HTML string), no Streamlit dependency, directly unit-testable — see `tests/test_components.py`. The four source modules were split by which "Power-On Sequence" redesign PR touched them (v3.4-v3.4.3), not by functional boundary; consolidated per `docs/superpowers/plans/2026-09-17-architecture-cleanup.md`. `theme.py`/`_theme_fonts.py` are untouched and stay separate (tokens/base CSS, and generated font data respectively) |
```

- [ ] **Step 4: Update CLAUDE.md's `effort_estimator.py` row**

Locate the row (anchor: `` | `effort_estimator.py` | ``). If it mentions the deleted wrapper methods or a "thin wrappers for tests that call them directly" phrase (check the `effort_core.py` row's text too — it currently says `` its private `_foo` methods stay as thin wrappers for tests that call them directly, but the real logic lives here ``), update that sentence to reflect their removal: replace `` its private `_foo` methods stay as thin wrappers for tests that call them directly, but the real logic lives here `` with `` tests call effort_core's functions directly (v3.6 — the wrapper methods that used to exist purely for tests were deleted) ``.

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md
git commit -m "$(cat <<'EOF'
docs: update CLAUDE.md for the architecture cleanup

Reflects the effort_estimator.py wrapper removal and the four-into-one
styling module consolidation (components.py) from
docs/superpowers/plans/2026-09-17-architecture-cleanup.md.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_013xJEqRuCdtixjGy8hpg3jB
EOF
)"
```
