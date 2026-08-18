"""
QAI Consultant -- Phase 3 output-screen styling ("Power-On Sequence",
continuing Phase 1's landing_hero.py and Phase 2's interactive_flow_style.py
-- see docs/superpowers/specs/2026-08-17-output-screens-power-on-redesign-design.md).

Four pure functions: a header eyebrow and a shared content-polish CSS block
(both used by render_strategy() AND render_doc_review()), a 4-stage
sequence status readout (render_strategy() only -- the only screen with a
genuinely sequential multi-stage pipeline), and an input-tray CSS block
(render_doc_review() only). No Streamlit dependency -- callers pass the
app.py-derived tokens dict (theme.LIGHT_TOKENS or theme.DARK_TOKENS) and
render the result via st.markdown(html, unsafe_allow_html=True), same as
landing_hero.py, interactive_flow_style.py, and ledger_components.py.

theme.py is NOT modified by this module. All CSS here is scoped to its own
class names (output-eyebrow, stage-*, output-tiles) plus data-testid/
aria-attribute selectors verified against this app's real rendered DOM
(Streamlit 1.59.1 -- see tests/test_output_screen_style.py's docstring
reference and this module's own plan Task 1 Step 0 for how), never added
to theme.py's build_css().

The stage-sequence indicator's "active" dot uses a looping pulse animation
-- unlike every other animation in this 3-phase redesign, which are all
one-shot. This is deliberate: it signals a real, currently-running
background process (an in-flight LLM call), the same category of thing
st.spinner()'s own built-in animation already represents elsewhere in this
app -- a status signal, not decorative motion. theme.py's existing global
prefers-reduced-motion rule (build_css(), zeroing animation-duration)
already disables it for reduced-motion users; no module-local delay
override is needed here, unlike landing_hero.py/interactive_flow_style.py,
because this animation has no animation-delay for that global rule to miss.
"""
import html as _html


def build_output_eyebrow_html(tokens: dict, label: str) -> str:
    """Pure function: token dict + a caller-supplied label -> a mono
    uppercase eyebrow line, reusing the label style
    interactive_flow_style.py's .dialogue-eyebrow established. Both current
    call sites pass a hardcoded string literal (never user input), but
    `label` is HTML-escaped anyway -- consistent with every sibling builder
    in this codebase (e.g. build_stage_sequence_html()'s stage labels) that
    escapes caller-facing text as a matter of course rather than relying on
    the call site staying trusted forever."""
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
    animation, so it must render correctly every time it is called,
    regardless of how many times the screen has been shown before.

    "failed" exists because render_strategy()'s per-stage try/except sets
    a stage's session-state key to "" (not None) when its LLM call fails,
    so the stage stays present-but-empty rather than reverting to unset --
    the caller (_render_stages() in app.py) must distinguish that from a
    real result and pass "failed", not "done", or this live status readout
    would falsely show green success next to its own red st.error message,
    exactly during the LLM-outage scenario the try/except exists to
    survive (found in code review of v3.4.3's final diff)."""
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
    treatment interactive_flow_style.py's build_sidebar_polish_css() gave
    the sidebar in Phase 2, scoped to [data-testid="stMain"] instead of
    [data-testid="stSidebar"] so both rule sets coexist without conflict),
    a themed tab bar, and the .output-tiles score-tile entrance animation.
    Selectors verified against this app's real Streamlit 1.59.1 DOM -- see
    this module's docstring and tests/test_output_screen_style.py.

    The hover `color` override is split into its own rule that excludes
    `type="primary"` buttons (Streamlit 1.59.1 renders the `<button>` itself
    with `data-testid="stBaseButton-primary"`/`"-secondary"`, confirmed via a
    live local Streamlit + Playwright DOM probe -- `el.outerHTML` on the
    landing screen's primary and secondary buttons). Streamlit's default
    `primaryColor` (#FF4B4B, red) already gives a primary button's label
    white-on-red contrast; repainting that label to this app's blue accent on
    hover leaves it barely legible against the still-red fill (~1.56:1 in the
    light theme, far under WCAG AA's 4.5:1). `border-color` has no such
    problem and stays unscoped -- it never fights a button's own fill/text
    contrast. See CLAUDE.md's Gotchas entry on this."""
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
    technique (a container's key="foo" generates a st-key-foo CSS class) --
    the same per-instance scoping app.py's header-logo container already
    uses (v3.3 precedent) -- rather than reusing .ledger-card itself, which
    belongs to the Phase-2 dialogue screen's per-question cards."""
    return f"""
<style>
/* Deliberately kept byte-for-byte in sync with theme.py's .ledger-card
   background/border/padding/margin block (build_css()) -- update both
   together if that ruleset ever changes. Not reused directly (see the
   docstring above: .ledger-card is scoped to the Phase-2 dialogue cards). */
.st-key-doc-review-input {{
    background: {tokens['surface']};
    border: 1px solid {tokens['line']};
    padding: 1.1rem 1.3rem;
    margin-bottom: 1rem;
}}
</style>
"""
