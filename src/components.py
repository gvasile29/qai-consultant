"""
QAI Consultant -- reusable Streamlit HTML/CSS components.

Consolidates four previously separate modules (ledger_components.py,
landing_hero.py, interactive_flow_style.py, output_screen_style.py) that
were split by which "Power-On Sequence" redesign PR touched them, not by
functional boundary -- see docs/superpowers/plans/2026-09-17-architecture-cleanup.md.
All functions are pure (a token dict plus plain arguments -> an HTML string);
callers render the result via st.markdown(html, unsafe_allow_html=True). No
Streamlit dependency in this module itself, so every function here is
directly unit-testable without a Streamlit runtime -- see tests/test_components.py.

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


def executive_readout_html(readout) -> str:
    """Render an executive_readout.ExecutiveReadout as a .ledger-card with a
    key/value table.risk-ledger body. None returns "" so callers can skip
    rendering. Every value is escaped -- risk descriptions are LLM output."""
    if readout is None:
        return ""

    rows = []
    if readout.overall_risk:
        tier = severity_tier(readout.overall_risk)
        rows.append(
            "<tr><td class=\"rid\">Overall risk</td><td>"
            f'<span class="sev {tier}">{_html.escape(readout.overall_risk)}</span> '
            f"{_html.escape(readout.risk_breakdown)}</td></tr>"
        )
    if readout.effort_range:
        rows.append(f'<tr><td class="rid">QA effort</td><td>{_html.escape(readout.effort_range)}</td></tr>')
    if readout.capacity:
        cap_tier = "fail" if readout.capacity_deficit else "pass"
        rows.append(
            f'<tr><td class="rid">Team capacity</td><td><span class="sev {cap_tier}">'
            f'{"Deficit" if readout.capacity_deficit else "OK"}</span> {_html.escape(readout.capacity)}</td></tr>'
        )
    if readout.confidence:
        rows.append(f'<tr><td class="rid">Confidence</td><td>{_html.escape(readout.confidence)}</td></tr>')
    for i, (risk_id, description) in enumerate(readout.address_first):
        label = "Address first" if i == 0 else ""
        rows.append(
            f'<tr><td class="rid">{label}</td>'
            f"<td><strong>{_html.escape(risk_id)}</strong> — {_html.escape(description)}</td></tr>"
        )

    if not rows:
        return ""
    return (
        '<div class="ledger-card">'
        '<div class="idx">Executive readout</div>'
        f'<table class="risk-ledger"><tbody>{"".join(rows)}</tbody></table>'
        "</div>"
    )


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
