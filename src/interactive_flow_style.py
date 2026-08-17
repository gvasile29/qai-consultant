"""
QAI Consultant -- Phase 2 interactive-flow styling ("Power-On Sequence",
continuing Phase 1's landing_hero.py -- see
docs/superpowers/specs/2026-08-06-interactive-flow-power-on-redesign-design.md).

Three pure functions, one per screen (dialogue, review, sidebar), each
building a self-contained HTML+CSS string. No Streamlit dependency --
callers pass the app.py-derived tokens dict (theme.LIGHT_TOKENS or
theme.DARK_TOKENS) and render the result via
st.markdown(html, unsafe_allow_html=True), same as landing_hero.py and
ledger_components.py.

theme.py is NOT modified by this module. .ledger-card's base rule stays
there untouched; the :hover rule added here composes with it safely
regardless of <style> tag load order (an additive pseudo-class selector,
not an override). All CSS here is scoped to its own class names
(dialogue-*, review-*) plus the one .ledger-card:hover addition, and
lives in this module's own <style> blocks -- never added to theme.py's
build_css().

Unlike the landing screen (rendered once per session in the common
case), the dialogue and review screens rerun on user interaction
(template selection, "Additional context" edits). Mount-triggered CSS
keyframe animations would replay every time, which is why:
- the dialogue screen gets NO entrance animation at all (only a CSS
  *transition* on the progress bar's width, which is expected to
  re-fire on every value change -- that's what makes a progress bar
  feel alive, not a bug);
- the review screen's one-shot entrance is controlled entirely by the
  caller-supplied `animate` flag, which app.py derives from a
  session_state "seen" flag (the same idiom already used for
  mcp_announcement_seen);
- the sidebar gets no entrance animation at all -- it persists across
  every screen and rerun in the app.
"""
import html as _html


def build_dialogue_header_html(tokens: dict, answered: int, total: int) -> str:
    """Pure function: token dict + progress counts -> dialogue header HTML
    (eyebrow label + animated-width progress bar) plus the .ledger-card
    hover rule. Directly unit-testable -- see
    tests/test_interactive_flow_style.py."""
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
    HTML-escaped (user-supplied text, same XSS concern
    ledger_components.py documents)."""
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
