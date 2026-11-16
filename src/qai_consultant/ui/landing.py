"""
QAI Consultant -- the landing page ("Mission control" redesign, phase 1).

The landing page is one st.components.v2 component: a hero, a carousel of
the four documents, the three modes, the kick-off note and the MCP block.
build_mission_landing_html() is pure (tokens + flags -> an HTML string) and
unit-testable without a Streamlit runtime; render_mission_landing() mounts
it and returns the mode a visitor picked, or None.

The component's HTML lives in a shadow root, so its CSS cannot leak into the
rest of the app. Fonts come from theme.py's document-level @font-face rules,
which reach into shadow roots. Buttons send a mode id back to Python through
setTriggerValue("go", ...); that value comes from the browser, so
landing_target() only lets the known APP_MODES ids through.

AppTest renders the component as an UnknownElement and cannot click it:
landing navigation is checked with Playwright (scripts/verify_landing_visual.py).
"""
import html as _html

from qai_consultant.compliance.ai_disclosure import AI_INTERACTION_NOTICE_SHORT
from qai_consultant.ui.components import APP_MODES, GENERATION_TIME_ESTIMATE, GENERATION_TIME_ESTIMATE_LONG

COMPONENT_NAME = "qai_mission_landing"
COMPONENT_KEY = "mission-landing"

_DOCUMENTS = (
    ("Risk Register", "Prioritized risks with likelihood, impact and mitigation, before a single line of code is written.", "Likelihood × impact"),
    ("Effort Estimation", "PERT-based timeline with team capacity analysis and a confidence score from 0 to 100.", "Computed, not generated"),
    ("Test Strategy", "ISTQB-aligned approach tailored to your stack, methodology and compliance requirements.", "Cited from the knowledge base"),
    ("Test Plan", "IEEE 829-aligned plan with test items, entry and exit criteria, schedule and AI tool oversight.", "Markdown and PDF"),
)

_MISSIONS = {
    "strategy": "For a new project or release. 11 questions in, four documents out.",
    "doc_review": "A 0 to 100 score across six dimensions for a Test Plan, Test Strategy or test case list you already have.",
    "maturity": "An indicative TMMi level across ten process areas, plus EU AI Act readiness for AI systems.",
}

_STATS = (
    ("Time to results", GENERATION_TIME_ESTIMATE),
    ("Deliverables", "4 documents"),
    ("Knowledge base", "7,100+ vectors"),
    ("Cost", "Free, no sign-up"),
)

_MCP_TOOLS = (
    "retrieve_qa_knowledge", "estimate_qa_effort", "review_qa_document",
    "analyze_test_results", "assess_qa_maturity", "list_kb_sources",
)

GITHUB_URL = "https://github.com/gvasile29/qai-consultant"
MCP_GUIDE_URL = f"{GITHUB_URL}/blob/master/README_MCP.md"


def landing_target(action) -> str | None:
    """The mode id a landing button sent, if it is a known mode; else None.
    The value arrives from the browser, so anything else (a list or a dict
    included) is dropped."""
    if not isinstance(action, str):
        return None
    return action if action in {mode_id for mode_id, _idx, _label in APP_MODES} else None


def _rgba(hex_color: str, alpha: float) -> str:
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    return f"rgba({r}, {g}, {b}, {alpha})"


def _logo_svg(ink: str, pixel: str, size: int) -> str:
    cells = [(15, 0), (30, 0), (45, 0), (0, 15), (60, 15), (0, 30), (60, 30),
             (0, 45), (60, 45), (15, 60), (30, 60), (45, 60)]
    rects = "".join(f'<rect x="{x}" y="{y}" width="12" height="12" rx="3"/>' for x, y in cells)
    return (
        f'<svg role="img" aria-label="QAI Consultant logo" width="{size}" height="{size}" viewBox="0 0 72 72">'
        f'<g fill="{ink}">{rects}</g><rect x="60" y="60" width="12" height="12" rx="3" fill="{pixel}"/></svg>'
    )


_ARROW_LEFT = '<svg aria-hidden="true" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="square"><path d="M15 5l-7 7 7 7"/></svg>'
_ARROW_RIGHT = '<svg aria-hidden="true" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="square"><path d="M9 5l7 7-7 7"/></svg>'


def build_mission_landing_html(tokens: dict, *, dark: bool, version: str) -> str:
    """Pure function: theme tokens + theme flag + app version -> the whole
    landing page as one HTML string (styles included) for the component.

    Every button that changes screen carries data-go with an APP_MODES id;
    every in-page jump carries data-scroll with a CSS selector, looked up in
    the component first and then in the page (".st-key-landing-details" is
    the native "more detail" section below the component)."""
    t = tokens
    # Brand rule (assets/brand/README_BRAND.md): the defect pixel is #2DD4BF on
    # dark backgrounds and #14B8A6 on light ones; never another color.
    pixel = "#2DD4BF" if dark else "#14B8A6"
    star = _rgba(t["ink"], 0.55 if dark else 0.22)
    star_dim = _rgba(t["ink"], 0.3 if dark else 0.12)
    glow = _rgba(t["accent"], 0.16 if dark else 0.12)
    labels = {mode_id: label for mode_id, _idx, label in APP_MODES}
    nav_short = {"strategy": "Strategy", "doc_review": "Review", "maturity": "Maturity"}

    nav = "".join(
        f'<button type="button" class="ql-nav-link" data-go="{mode_id}">{nav_short[mode_id]}</button>'
        for mode_id, _idx, _label in APP_MODES
    )
    stats = "".join(
        f'<div class="ql-stat"><span class="ql-mono-label">{_html.escape(label)}</span>'
        f'<span class="ql-stat-value">{_html.escape(value)}</span></div>'
        for label, value in _STATS
    )
    cards = "".join(
        f'<article class="ql-card" aria-roledescription="slide" aria-label="{i} of {len(_DOCUMENTS)}: {_html.escape(title)}">'
        f'<span class="ql-card-num" aria-hidden="true">{i:02d}</span>'
        f'<div class="ql-card-body"><h3>{_html.escape(title)}</h3><p>{_html.escape(body)}</p>'
        f'<span class="ql-mono-label ql-accent">{_html.escape(tag)}</span></div></article>'
        for i, (title, body, tag) in enumerate(_DOCUMENTS, start=1)
    )
    missions = "".join(
        f'<button type="button" class="ql-mission" data-go="{mode_id}">'
        f'<span class="ql-mission-idx">{idx}</span>'
        f'<span class="ql-mission-title">{_html.escape(labels[mode_id])}</span>'
        f'<span class="ql-mission-body">{_html.escape(_MISSIONS[mode_id])}</span>'
        f'<span class="ql-mission-go" aria-hidden="true">{_ARROW_RIGHT}</span></button>'
        for mode_id, idx, _label in APP_MODES
    )
    tools = " · ".join(_MCP_TOOLS)

    return f"""
<style>
:host {{ display: block; }}
.ql {{ container-type: inline-size; background: {t['page']}; color: {t['ink']}; font-family: 'Plex Sans', -apple-system, "Segoe UI", sans-serif; }}
.ql *, .ql *::before, .ql *::after {{ box-sizing: border-box; }}
.ql h1, .ql h2, .ql h3 {{ font-family: 'Plex Cond', 'Plex Sans', sans-serif; font-weight: 700; text-transform: uppercase; margin: 0; color: {t['ink']}; }}
.ql p {{ margin: 0; }}
.ql a {{ color: {t['accent']}; }}
/* :where() keeps this reset at zero specificity: as ".ql button" it beat
   ".ql-cta" and painted the CTA label in the ink color on the accent fill. */
:where(.ql button) {{ font: inherit; color: inherit; }}
.ql :focus-visible {{ outline: 2px solid {t['accent']}; outline-offset: 3px; }}
.ql-wrap {{ max-width: 1240px; margin: 0 auto; padding: 0 clamp(1.25rem, 4cqi, 2.75rem); }}
.ql-mono-label {{ font-family: 'Plex Mono', monospace; font-size: 0.75rem; letter-spacing: 0.14em; text-transform: uppercase; color: {t['ink_dim']}; }}
.ql-accent {{ color: {t['accent']}; }}

@keyframes ql-rise {{ from {{ opacity: 0; transform: translateY(22px); }} to {{ opacity: 1; transform: translateY(0); }} }}
@keyframes ql-fade {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}
@keyframes ql-draw {{ from {{ stroke-dashoffset: 900; }} to {{ stroke-dashoffset: 0; }} }}
@keyframes ql-twinkle {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0.5; }} }}
@keyframes ql-blink {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0.15; }} }}

/* Hero */
.ql-hero {{ position: relative; overflow: hidden; display: flex; flex-direction: column; justify-content: space-between; min-height: 640px; }}
.ql-hero > .ql-wrap {{ width: 100%; }}  /* auto margins in a flex column would shrink-wrap and center it */
.ql-stars {{ position: absolute; inset: 0; pointer-events: none; background-image: radial-gradient({star} 1px, transparent 1.6px), radial-gradient({star_dim} 1px, transparent 1.6px); background-size: 290px 250px, 170px 210px; background-position: 40px 60px, 120px 20px; animation: ql-twinkle 7s ease-in-out infinite; }}
.ql-arc {{ position: absolute; right: 3%; top: 76px; width: 44%; max-width: 560px; height: auto; pointer-events: none; }}
.ql-arc path.ql-trail {{ stroke-dasharray: 900; animation: ql-draw 2.6s ease-out 0.4s both; }}
.ql-arc .ql-rocket {{ animation: ql-fade 0.6s ease-out 2.6s both; }}
.ql-top {{ position: relative; display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 1rem; padding-top: 1.1rem; padding-bottom: 1.1rem; }}
.ql-brand {{ display: flex; align-items: center; gap: 0.7rem; font-family: 'Plex Cond', sans-serif; font-weight: 700; font-size: 0.95rem; letter-spacing: 0.16em; text-transform: uppercase; }}
.ql-nav {{ display: flex; flex-wrap: wrap; align-items: center; gap: 0.25rem 1.5rem; }}
.ql-nav-link, .ql-nav a {{ background: none; border: 0; padding: 0.75rem 0; cursor: pointer; font-size: 0.8rem; font-weight: 600; letter-spacing: 0.14em; text-transform: uppercase; color: {t['ink']}; text-decoration: none; }}
.ql-nav-link:hover, .ql-nav a:hover {{ color: {t['accent']}; }}
.ql-hero-copy {{ position: relative; display: flex; flex-direction: column; gap: 1.5rem; padding-top: 2.5rem; padding-bottom: 1rem; }}
.ql-hero-copy > * {{ max-width: 760px; animation: ql-rise 0.7s ease-out both; }}
.ql-hero-copy > :nth-child(2) {{ animation-delay: 0.1s; }}
.ql-hero-copy > :nth-child(3) {{ animation-delay: 0.22s; }}
.ql-hero-copy > :nth-child(4) {{ animation-delay: 0.34s; }}
.ql-hero-copy > :nth-child(5) {{ animation-delay: 0.42s; }}
.ql-hero h1 {{ font-size: clamp(2.6rem, 7cqi, 5rem); line-height: 0.98; letter-spacing: 0.005em; text-wrap: balance; }}
.ql-lede {{ max-width: 560px; font-size: 1.12rem; line-height: 1.6; color: {t['ink_dim']}; }}
.ql-ctas {{ display: flex; flex-wrap: wrap; align-items: center; gap: 0.75rem 1.5rem; }}
.ql-cta {{ display: inline-flex; align-items: center; min-height: 3.5rem; padding: 0 2rem; border: 2px solid {t['accent']}; background: {t['accent']}; color: {t['page']}; cursor: pointer; font-size: 0.85rem; font-weight: 600; letter-spacing: 0.16em; text-transform: uppercase; transition: filter 0.2s ease-out; }}
.ql-cta:hover {{ filter: brightness(1.08); }}
.ql-link-cta {{ display: inline-flex; align-items: center; min-height: 3.5rem; padding: 0 0.25rem; border: 0; background: none; cursor: pointer; font-size: 0.85rem; font-weight: 600; letter-spacing: 0.16em; text-transform: uppercase; color: {t['ink']}; }}
.ql-link-cta:hover {{ color: {t['accent']}; }}
.ql-notice {{ max-width: 560px; font-size: 0.85rem; line-height: 1.55; color: {t['ink_dim']}; }}
.ql-horizon {{ position: relative; margin-top: 3.5rem; animation: ql-fade 1s ease-out 0.9s both; }}
.ql-horizon svg {{ display: block; width: 100%; height: 96px; }}
.ql-band {{ background: {t['surface']}; box-shadow: 0 -30px 90px {glow}; }}
.ql-stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(min(200px, 100%), 1fr)); gap: 1.25rem; padding-top: 0.25rem; padding-bottom: 2.25rem; }}
.ql-stat {{ display: flex; flex-direction: column; gap: 0.4rem; }}
.ql-stat-value {{ font-family: 'Plex Mono', monospace; font-size: 1.35rem; font-weight: 500; }}

/* Sections */
.ql-section {{ border-top: 1px solid {t['line']}; padding: clamp(3.5rem, 8cqi, 6.5rem) 0; }}
.ql-head {{ display: flex; flex-wrap: wrap; align-items: flex-end; justify-content: space-between; gap: 1.5rem; margin-bottom: 2.75rem; }}
.ql-head > div:first-child {{ display: flex; flex-direction: column; gap: 0.85rem; }}
.ql-section h2 {{ font-size: clamp(1.9rem, 4.2cqi, 3.2rem); line-height: 1; }}

/* Carousel */
.ql-controls {{ display: flex; align-items: center; gap: 1rem; }}
.ql-counter {{ font-family: 'Plex Mono', monospace; font-size: 0.95rem; color: {t['ink_dim']}; min-width: 4.5em; text-align: right; }}
.ql-arrow {{ width: 3.25rem; height: 3.25rem; display: inline-flex; align-items: center; justify-content: center; border: 1px solid {t['line']}; background: transparent; color: {t['ink']}; cursor: pointer; transition: border-color 0.2s ease-out, color 0.2s ease-out; }}
.ql-arrow:hover:not(:disabled) {{ border-color: {t['accent']}; color: {t['accent']}; }}
.ql-arrow:disabled {{ opacity: 0.35; cursor: default; }}
.ql-track {{ display: flex; gap: 1.25rem; overflow-x: auto; scroll-snap-type: x mandatory; scroll-behavior: smooth; scrollbar-width: none; padding-bottom: 0.25rem; }}
.ql-track::-webkit-scrollbar {{ display: none; }}
.ql-card {{ flex: 0 0 min(420px, 84cqi); scroll-snap-align: start; min-height: 400px; display: flex; flex-direction: column; justify-content: space-between; gap: 1.75rem; padding: 2rem; background: {t['surface']}; border: 1px solid {t['line']}; transition: border-color 0.25s ease-out, transform 0.25s ease-out; }}
.ql-card:hover {{ border-color: {t['accent']}; transform: translateY(-4px); }}
.ql-card-num {{ font-family: 'Plex Cond', sans-serif; font-weight: 700; font-size: 5.5rem; line-height: 1; color: {t['line']}; }}
.ql-card-body {{ display: flex; flex-direction: column; gap: 0.85rem; }}
.ql-card h3 {{ font-size: 1.55rem; }}
.ql-card p {{ font-size: 1rem; line-height: 1.6; color: {t['ink_dim']}; }}

/* Missions */
.ql-missions {{ display: flex; flex-direction: column; border-bottom: 1px solid {t['line']}; }}
.ql-mission {{ display: grid; grid-template-columns: 3rem minmax(0, 1.2fr) minmax(0, 1fr) 2rem; align-items: center; gap: 0.75rem 2rem; width: 100%; padding: 2rem 0.5rem 2rem 0; text-align: left; background: none; border: 0; border-top: 1px solid {t['line']}; cursor: pointer; transition: padding-left 0.25s ease-out; }}
.ql-mission:hover {{ padding-left: 1.25rem; }}
.ql-mission-idx {{ font-family: 'Plex Mono', monospace; font-size: 0.95rem; color: {t['accent']}; }}
.ql-mission-title {{ font-family: 'Plex Cond', sans-serif; font-weight: 700; font-size: clamp(1.35rem, 3cqi, 2.1rem); text-transform: uppercase; line-height: 1.05; transition: color 0.25s ease-out; }}
.ql-mission:hover .ql-mission-title {{ color: {t['accent']}; }}
.ql-mission-body {{ font-size: 1rem; line-height: 1.55; color: {t['ink_dim']}; }}
.ql-mission-go {{ color: {t['accent']}; justify-self: end; }}

/* Kick-off note */
.ql-note {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(min(320px, 100%), 1fr)); gap: 1.5rem 3rem; }}
.ql-note p {{ font-size: 1.05rem; line-height: 1.7; color: {t['ink_dim']}; }}
.ql-note strong {{ color: {t['ink']}; font-weight: 600; }}

/* Ground station */
.ql-ground {{ background: {t['surface']}; }}
.ql-ground-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(min(400px, 100%), 1fr)); gap: 3rem; align-items: center; }}
.ql-ground-copy {{ display: flex; flex-direction: column; gap: 1.1rem; }}
.ql-ground-copy p {{ max-width: 520px; font-size: 1.05rem; line-height: 1.6; color: {t['ink_dim']}; }}
.ql-ground-copy a {{ align-self: flex-start; padding: 0.75rem 0; font-size: 0.85rem; font-weight: 600; letter-spacing: 0.16em; text-transform: uppercase; text-decoration: none; }}
.ql-terminal {{ background: {t['page']}; border: 1px solid {t['line']}; padding: 1.75rem; font-family: 'Plex Mono', monospace; font-size: 0.95rem; line-height: 2; overflow-x: auto; }}
.ql-terminal .ql-dim {{ color: {t['ink_dim']}; }}
.ql-caret {{ display: inline-block; width: 0.55em; height: 1.1em; margin-left: 0.4em; vertical-align: -0.2em; background: {t['accent']}; animation: ql-blink 1.1s steps(2) infinite; }}
.ql-tools {{ overflow-wrap: anywhere; }}

.ql-foot {{ border-top: 1px solid {t['line']}; }}
.ql-foot .ql-wrap {{ display: flex; flex-wrap: wrap; justify-content: space-between; gap: 1rem; padding-top: 1.75rem; padding-bottom: 1.75rem; font-size: 0.85rem; color: {t['ink_dim']}; }}

@container (max-width: 880px) {{
  .ql-arc {{ display: none; }}
  .ql-hero {{ min-height: 0; }}
  .ql-mission {{ grid-template-columns: 2.5rem minmax(0, 1fr) 1.5rem; }}
  .ql-mission-body {{ grid-column: 2 / 3; }}
  .ql-mission-go {{ grid-row: 1; grid-column: 3; }}
}}
@container (max-width: 640px) {{
  .ql-nav {{ display: none; }}
  .ql-hero-copy {{ padding-top: 1.25rem; }}
  .ql-horizon svg {{ height: 56px; }}
}}
@media (prefers-reduced-motion: reduce) {{
  .ql *, .ql *::before, .ql *::after {{ animation: none !important; transition: none !important; }}
  .ql-track {{ scroll-behavior: auto; }}
}}
</style>

<div class="ql">
  <section class="ql-hero" aria-label="QAI Consultant">
    <div class="ql-stars" aria-hidden="true"></div>
    <svg class="ql-arc" aria-hidden="true" viewBox="0 0 600 520">
      <path class="ql-trail" d="M10 500 C 200 470, 430 330, 560 50" fill="none" stroke="{t['accent']}" stroke-width="1.5"/>
      <g class="ql-rocket" transform="translate(560 50) rotate(24)">
        <path d="M0 -22 C 9 -10, 9 8, 6 16 L -6 16 C -9 8, -9 -10, 0 -22 Z" fill="{t['ink']}"/>
        <path d="M-6 8 L -13 20 L -6 16 Z M6 8 L 13 20 L 6 16 Z" fill="{t['ink_dim']}"/>
        <rect x="-3" y="16" width="6" height="5" fill="{t['accent']}"/>
      </g>
    </svg>
    <header class="ql-top ql-wrap">
      <div class="ql-brand">{_logo_svg(t['ink'], pixel, 28)}<span>QAI Consultant</span></div>
      <nav class="ql-nav" aria-label="Modes">
        {nav}
        <button type="button" class="ql-nav-link" data-scroll="#ql-ground">MCP</button>
        <a href="{GITHUB_URL}" target="_blank" rel="noopener">GitHub</a>
      </nav>
    </header>
    <div class="ql-hero-copy ql-wrap">
      <span class="ql-mono-label ql-accent">Open source · free · no sign-up</span>
      <h1>Clear your release for launch.</h1>
      <p class="ql-lede">Your AI QA architect, grounded in ISTQB, OWASP and ISO. Answer 11 questions and get four documents in {GENERATION_TIME_ESTIMATE_LONG}.</p>
      <div class="ql-ctas">
        <button type="button" class="ql-cta" data-go="strategy">Start pre-flight</button>
        <button type="button" class="ql-link-cta" data-scroll=".st-key-landing-details">See example output</button>
      </div>
      <p class="ql-notice">{_html.escape(AI_INTERACTION_NOTICE_SHORT)}</p>
    </div>
    <div class="ql-horizon">
      <svg viewBox="0 0 1440 110" preserveAspectRatio="none" aria-hidden="true">
        <path d="M0 110 Q720 -90 1440 110 Z" fill="{t['surface']}"/>
        <path d="M0 110 Q720 -90 1440 110" fill="none" stroke="{t['accent']}" stroke-width="1.5" vector-effect="non-scaling-stroke"/>
      </svg>
      <div class="ql-band"><div class="ql-stats ql-wrap">{stats}</div></div>
    </div>
  </section>

  <section class="ql-section" id="ql-manifest" aria-roledescription="carousel" aria-label="What comes back">
    <div class="ql-wrap">
      <div class="ql-head">
        <div><span class="ql-mono-label ql-accent">Flight manifest</span><h2>What comes back</h2></div>
        <div class="ql-controls">
          <span class="ql-counter" aria-live="polite">01 / {len(_DOCUMENTS):02d}</span>
          <button type="button" class="ql-arrow" data-dir="-1" aria-label="Previous document">{_ARROW_LEFT}</button>
          <button type="button" class="ql-arrow" data-dir="1" aria-label="Next document">{_ARROW_RIGHT}</button>
        </div>
      </div>
      <div class="ql-track" tabindex="0" aria-label="Documents, scroll sideways">{cards}</div>
    </div>
  </section>

  <section class="ql-section" aria-label="Three missions">
    <div class="ql-wrap">
      <div class="ql-head"><div><span class="ql-mono-label ql-accent">Three missions</span><h2>Pick your starting point</h2></div></div>
      <div class="ql-missions">{missions}</div>
    </div>
  </section>

  <section class="ql-section" aria-label="When to use it">
    <div class="ql-wrap">
      <div class="ql-head"><div><span class="ql-mono-label ql-accent">Best used at project kick-off</span><h2>Before the first sprint</h2></div></div>
      <div class="ql-note">
        <p>Early on there's no code, no architecture doc and no detailed spec to hand an AI assistant. That's the gap this fills: <strong>four baseline documents</strong> (Risk Register, Effort Estimation, Test Strategy, Test Plan) grounded in ISTQB, OWASP and ISO.</p>
        <p>Then drop them into Claude Code or your AI IDE as project context. The next round of output gets specific to your project instead of generic.</p>
      </div>
    </div>
  </section>

  <section class="ql-section ql-ground" id="ql-ground" aria-label="MCP server">
    <div class="ql-wrap ql-ground-grid">
      <div class="ql-ground-copy">
        <span class="ql-mono-label ql-accent">Ground station</span>
        <h2>The same engine, inside your AI tools</h2>
        <p>A local MCP server with no API keys. It supplies retrieval and deterministic numbers, and your assistant writes the narrative. Setup for Claude Desktop and other clients is in the install guide.</p>
        <a href="{MCP_GUIDE_URL}" target="_blank" rel="noopener">MCP install guide</a>
      </div>
      <div class="ql-terminal">
        <div class="ql-dim"># add it to Claude Code</div>
        <div class="ql-tools"><span class="ql-accent">$</span> claude mcp add qai-consultant -- uvx qai-consultant-mcp<span class="ql-caret" aria-hidden="true"></span></div>
        <div class="ql-dim"># {len(_MCP_TOOLS)} tools</div>
        <div class="ql-tools">{tools}</div>
        <div class="ql-dim"># anonymous telemetry is on by default; QAI_TELEMETRY=0 turns it off</div>
      </div>
    </div>
  </section>

  <footer class="ql-foot">
    <div class="ql-wrap">
      <span>Generated documents are marked as AI-generated.</span>
      <span>v{_html.escape(version)} · Apache-2.0 · release notes are in the sidebar</span>
    </div>
  </footer>
</div>
"""


def build_landing_frame_css(tokens: dict) -> str:
    """Pure function: token dict -> page CSS for the landing screen. The
    component runs edge to edge inside the main column; the native "more
    detail" block under it (st.container(key="landing-more")) gets the
    column's padding back. Scoped with :has() so it only applies while the
    landing component is on the page. The top padding clears Streamlit's
    header bar, which holds the sidebar reopen button."""
    return f"""
<style>
[data-testid="stMainBlockContainer"]:has(.st-key-{COMPONENT_KEY}) {{ padding: 3.5rem 0 4rem; max-width: 100%; }}
.st-key-landing-more {{ width: 100%; max-width: 1240px; margin: 0 auto; padding: 1.5rem clamp(1.25rem, 4vw, 2.75rem) 0; }}
.st-key-landing-more .adopt-eyebrow {{ margin-top: 1rem; }}
</style>
"""


# Mounts the HTML once per change of `data` (a theme switch rebuilds it), so
# the carousel keeps its position across reruns. Buttons with data-go send the
# mode id to Python; data-scroll jumps inside the component, then the page.
_JS = """
export default function (component) {
  const { data, setTriggerValue, parentElement } = component;
  let host = parentElement.querySelector(".qai-landing-host");
  if (!host) {
    host = document.createElement("div");
    host.className = "qai-landing-host";
    parentElement.appendChild(host);
  }
  if (host.__qaiSource === data) return;
  host.__qaiSource = data;
  host.innerHTML = data;
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  host.querySelectorAll("[data-go]").forEach((el) => {
    el.addEventListener("click", () => setTriggerValue("go", el.dataset.go));
  });
  host.querySelectorAll("[data-scroll]").forEach((el) => {
    el.addEventListener("click", () => {
      const selector = el.dataset.scroll;
      const target = host.querySelector(selector) || document.querySelector(selector);
      if (target) target.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" });
    });
  });

  const track = host.querySelector(".ql-track");
  const counter = host.querySelector(".ql-counter");
  const arrows = host.querySelectorAll(".ql-arrow");
  if (!track) return;
  const cards = track.querySelectorAll(".ql-card");
  const step = () => (cards.length > 1 ? cards[1].offsetLeft - cards[0].offsetLeft : track.clientWidth);
  const pad = (n) => String(n).padStart(2, "0");
  const update = () => {
    const index = Math.min(cards.length - 1, Math.round(track.scrollLeft / Math.max(step(), 1)));
    const atEnd = track.scrollLeft + track.clientWidth >= track.scrollWidth - 2;
    if (counter) counter.textContent = pad(atEnd ? cards.length : index + 1) + " / " + pad(cards.length);
    arrows.forEach((a) => {
      a.disabled = a.dataset.dir === "-1" ? track.scrollLeft <= 2 : atEnd;
    });
  };
  arrows.forEach((a) => {
    a.addEventListener("click", () => {
      track.scrollBy({ left: Number(a.dataset.dir) * step(), behavior: reduce ? "auto" : "smooth" });
    });
  });
  track.addEventListener("scroll", () => window.requestAnimationFrame(update), { passive: true });
  // One resize listener at a time, on window: the host element is new each
  // time a visitor comes back to the landing page, so a handle kept on it
  // would be lost and the old listener would stay.
  if (window.__qaiLandingResize) window.removeEventListener("resize", window.__qaiLandingResize);
  window.__qaiLandingResize = update;
  window.addEventListener("resize", update);
  update();
}
"""


def _component():
    # Registered on every render, not cached: the registry belongs to the
    # Streamlit runtime, so a renderer cached across runtimes (AppTest makes
    # one per test) points at a name the new registry never saw. Registering
    # an identical definition again is silent in Streamlit 1.59.1.
    import streamlit as st  # app-side only; kept out of the pure builder's import path

    return st.components.v2.component(COMPONENT_NAME, js=_JS)


def render_mission_landing(tokens: dict, *, dark: bool, version: str) -> str | None:
    """Mount the landing component; return the mode a visitor picked, or None."""
    result = _component()(
        data=build_mission_landing_html(tokens, dark=dark, version=version),
        key=COMPONENT_KEY,
        on_go_change=lambda: None,
    )
    return landing_target(getattr(result, "go", None))
