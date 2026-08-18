"""
QAI Consultant -- Landing page hero ("Power-On Sequence", Phase 1 of the
2026-08-06 redesign -- see
docs/superpowers/specs/2026-08-06-landing-power-on-redesign-design.md).

Builds a self-contained HTML+CSS block for the landing screen's hero +
"How it works" cards. All animations are one-shot on page load (a
headline readout reveal, three progress gauges sweeping to rest, a
staggered standards checklist, fading-in cards) -- nothing loops
forever, matching the "instrument powering on, not a marketing site"
concept the direction was chosen for.

No Streamlit dependency -- callers pass the app.py-derived tokens dict
(theme.LIGHT_TOKENS or theme.DARK_TOKENS) and render the result via
st.markdown(html, unsafe_allow_html=True), same as ledger_components.py.

All CSS here is scoped to "pom-" prefixed classes and lives in this
module's own <style> block -- it is NOT added to theme.py's build_css(),
so it can't leak onto the Phase 2/3 screens that load theme.py's global
stylesheet, and it must never reuse ".ledger-card" (that belongs to the
Phase-2 dialogue screen; as of Phase 2, interactive_flow_style.py owns
a ".ledger-card:hover" rule for it -- this module must never add its
own competing rule for that class, since two modules styling the same
selector would be a genuine conflict, not just an outdated fact. Seeing
".ledger-card" reused here at all was a caught error in an earlier
draft of the design spec).
Relies on theme.py's existing global `prefers-reduced-motion` rule
(build_css()) to zero out `animation-duration`/`transition-duration`
for users who've turned off motion -- deliberately not duplicated
here. That global rule does NOT zero `animation-delay`, though, so
this module defines its own scoped `prefers-reduced-motion` block
(below, in build_landing_hero_html()'s <style>) to zero the delays on
its own "pom-" elements -- without it, elements with a nonzero delay
(the staggered standards badges, the cards) sit at their
`animation-fill-mode: both` "from" state (`opacity: 0`) for the full
original delay before snapping in, which is the opposite of "reduced
motion." Do not remove this module-local block as "redundant" with
theme.py's rule -- the two cover different CSS properties.
"""


def build_landing_hero_html(tokens: dict) -> str:
    """Pure function: token dict -> hero + "How it works" HTML block.
    Directly unit-testable without a Streamlit runtime -- see
    tests/test_landing_hero.py."""
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

/* theme.py's global prefers-reduced-motion rule (build_css()) only zeroes
   animation-duration/transition-duration -- it never touches
   animation-delay. Left alone, every "pom-" element with a nonzero delay
   (the standards badges, the cards) sits at its pre-animation state
   (opacity: 0) for the full original delay before snapping in, which is
   the opposite of "reduced motion": content stays invisible instead of
   just arriving without the animated flourish. Zero the delays here,
   scoped to this module's own classes, so reduced-motion users see the
   finished layout immediately. */
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
    deliverable cards + stat tiles HTML block. A Phase-3 addendum (folded
    into the Phase 3 spec at the user's request, though it's landing-screen
    content) finishing what Phase 1 left native Streamlit. Continues
    build_landing_hero_html()'s "How it works" cards' visual language and
    animation-delay cadence (which ends at 2.0s) -- reuses the existing
    .pom-card/.pom-cidx/.pom-ctitle/.pom-cbody classes and pom-card-in
    keyframe (defined in that function's <style> block, always rendered
    first on the same screen by render_intro()) rather than redefining
    them. Directly unit-testable -- see tests/test_landing_hero.py.

    Opens with a ".pom-readout" mono eyebrow line (the same class
    build_landing_hero_html() defines and uses for its own "calibration
    sequence" line, always rendered first on the same screen) -- without
    it this was the landing screen's only unlabeled content block, having
    dropped the pre-existing "#### 🎯 What you get in ~2 minutes" markdown
    heading with nothing replacing it."""
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
