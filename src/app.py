"""
QAI Consultant — Streamlit Web UI
Browser-based interface for generating Test Strategy documents.
"""

import os
import sys


from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent))

import streamlit as st
from streamlit.runtime.scriptrunner import RerunException, StopException
from agent import MISTRAL_MODEL, QAIAgent, clean_markdown_html
from ai_disclosure import AI_INTERACTION_NOTICE, pdf_icon_html, pdf_meta_html, with_ai_footer
from dialogue import DialogueManager, InputValidator, QUESTIONS
from strategy_generator import StrategyGenerator, build_strategy_prompt, SYSTEM_PROMPT
from risk_analyzer import RiskAnalyzer, append_execution_data_appendix
from effort_estimator import EffortEstimator
from agent import QAIConnectionError, QAIKnowledgeBaseError
from logger import setup_logging, get_logger
from version import __version__
from templates import TEMPLATES, TEMPLATE_OPTIONS
from pdf_export import markdown_to_pdf
from test_plan_generator import TestPlanGenerator
from kb_manifest import KB_MANIFEST
from review_core import MIN_CONTENT_CHARS as REVIEW_MIN_CONTENT_CHARS, review_document
from review_generator import (
    REVIEW_SYSTEM_PROMPT,
    build_review_prompt,
    build_review_report_markdown,
    save_review_report,
)
from results_core import (
    analyze as compute_results_analysis,
    parse_junit_xml,
    parse_results_csv,
    summarize_for_prompt,
)
from visit_counter import get_and_increment_visit_count

setup_logging()
logger = get_logger(__name__)

BRAND_DIR = Path(__file__).resolve().parent.parent / "assets" / "brand"
EU_AI_ICON_DIR = Path(__file__).resolve().parent.parent / "assets" / "eu_ai_icon"

# ── Page Config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="QAI Consultant",
    page_icon=str(BRAND_DIR / "qai_favicon_32.png"),
    layout="wide",
    initial_sidebar_state="expanded",
)

# Sidebar logo (Streamlit >= 1.35): full lockup expanded, symbol-only collapsed.
# st.logo() has no built-in light/dark pair, so pick the variant ourselves via
# st.context.theme.type ("light"/"dark"/None on first render) -- the light SVGs
# fill #0F172A, nearly invisible against Streamlit's dark-theme background;
# assets/brand/README_BRAND.md's "_dark" variants (fill #F1F5F9) exist for this.
_theme_type = st.context.theme.type
if _theme_type == "dark":
    st.logo(
        str(BRAND_DIR / "qai_logo_dark.svg"),
        icon_image=str(BRAND_DIR / "qai_icon_dark.svg"),
    )
else:
    st.logo(
        str(BRAND_DIR / "qai_logo.svg"),
        icon_image=str(BRAND_DIR / "qai_icon.svg"),
    )

# ── Custom CSS ─────────────────────────────────────────────────────────────────
from theme import inject_theme_css

inject_theme_css()


# ── Session State Init ─────────────────────────────────────────────────────────
def init_session_state():
    if "agent" not in st.session_state:
        st.session_state.agent = None
    if "dialogue" not in st.session_state:
        st.session_state.dialogue = DialogueManager()
    if "answers" not in st.session_state:
        st.session_state.answers = {}
    if "strategy" not in st.session_state:
        st.session_state.strategy = None
    if "sources" not in st.session_state:
        st.session_state.sources = []
    if "output_path" not in st.session_state:
        st.session_state.output_path = None
    if "risk_register" not in st.session_state:
        st.session_state.risk_register = None
    if "risk_sources" not in st.session_state:
        st.session_state.risk_sources = []
    if "risk_path" not in st.session_state:
        st.session_state.risk_path = None
    if "effort_report" not in st.session_state:
        st.session_state.effort_report = None
    if "effort_path" not in st.session_state:
        st.session_state.effort_path = None
    if "effort_data" not in st.session_state:
        st.session_state.effort_data = None
    if "test_plan" not in st.session_state:
        st.session_state.test_plan = None
    if "test_plan_path" not in st.session_state:
        st.session_state.test_plan_path = None
    if "test_plan_sources" not in st.session_state:
        st.session_state.test_plan_sources = []
    if "risk_pdf_bytes" not in st.session_state:
        st.session_state.risk_pdf_bytes = None
    if "effort_pdf_bytes" not in st.session_state:
        st.session_state.effort_pdf_bytes = None
    if "strategy_pdf_bytes" not in st.session_state:
        st.session_state.strategy_pdf_bytes = None
    if "test_plan_pdf_bytes" not in st.session_state:
        st.session_state.test_plan_pdf_bytes = None
    if "current_step" not in st.session_state:
        st.session_state.current_step = "intro"  # intro | dialogue | review | strategy | doc_review
    if "run_count" not in st.session_state:
        st.session_state.run_count = 0
    if "review_input_text" not in st.session_state:
        st.session_state.review_input_text = None
    if "review_source_label" not in st.session_state:
        st.session_state.review_source_label = None
    if "review_result" not in st.session_state:
        st.session_state.review_result = None
    if "review_narrative" not in st.session_state:
        st.session_state.review_narrative = None
    if "review_narrative_sources" not in st.session_state:
        st.session_state.review_narrative_sources = []
    if "review_output_path" not in st.session_state:
        st.session_state.review_output_path = None
    if "review_pdf_bytes" not in st.session_state:
        st.session_state.review_pdf_bytes = None
    if "results_analysis" not in st.session_state:
        st.session_state.results_analysis = None


# Session-state keys owned by the "Review an existing document" (F1) mode —
# a single shared list so the two "clear everything" handlers (sidebar Start
# Over, "Generate Another Strategy") and the mode's own reset button can't
# silently drift apart (see CLAUDE.md's session-state cleanup gotcha).
REVIEW_MODE_STATE_KEYS = [
    "review_input_text", "review_source_label", "review_result",
    "review_narrative", "review_narrative_sources", "review_output_path",
    "review_pdf_bytes",
]


def _reset_review_mode_state():
    for key in REVIEW_MODE_STATE_KEYS:
        if key in st.session_state:
            del st.session_state[key]
    st.session_state.pop("review_doc_uploader", None)
    st.session_state.pop("review_doc_pasted_text", None)
    st.session_state.pop("review_doc_type_select", None)


# ── Load Agent ─────────────────────────────────────────────────────────────────
@st.cache_resource(show_spinner=False)
def load_agent():
    """
    Load QAIAgent once per Streamlit session.
    Returns (agent, error_message) tuple — error_message is None on success.
    """
    try:
        agent = QAIAgent()
        logger.info("QAIAgent loaded successfully in Streamlit")
        return agent, None
    except QAIKnowledgeBaseError as e:
        logger.error(f"KB error: {e}")
        return None, str(e)
    except QAIConnectionError as e:
        logger.error(f"LLM connection error: {e}")
        return None, str(e)
    except Exception as e:
        logger.exception(f"Unexpected error loading agent: {e}")
        return None, f"❌ Unexpected error: {e}"


# ── Changelog ──────────────────────────────────────────────────────────────────
CHANGELOG_PATH = Path(__file__).resolve().parent.parent / "CHANGELOG.md"


@st.cache_data(show_spinner=False)
def load_changelog() -> str:
    """
    Read CHANGELOG.md from the repo root once per session (cached — the file
    doesn't change while a session is running). Returns a graceful fallback
    string instead of crashing if the file is missing or unreadable.
    """
    try:
        return CHANGELOG_PATH.read_text(encoding="utf-8")
    except Exception as e:
        logger.warning(f"Could not read CHANGELOG.md: {e}")
        return "_Release notes unavailable._"


# ── Knowledge Base panel ──────────────────────────────────────────────────────
KNOWLEDGE_BASE_DIR = Path(__file__).resolve().parent.parent / "knowledge_base"


@st.cache_data(show_spinner=False)
def load_kb_sidebar_bullets() -> list[str]:
    """
    Build the "### Knowledge Base" bullet lines from KB_MANIFEST, keeping only
    entries whose declared paths actually exist on disk under knowledge_base/.
    Cached — the on-disk knowledge_base/ layout doesn't change while a
    session is running, and re-checking Path.exists() on every rerun would be
    wasted work (same convention as load_changelog() above).
    """
    bullets = []
    for entry in KB_MANIFEST:
        paths_exist = any(
            (KNOWLEDGE_BASE_DIR / rel_path).exists() for rel_path in entry["paths"]
        )
        if paths_exist:
            bullets.append(f"- {entry['emoji']} {entry['label']}")
    return bullets


# ── MCP announcement (v3.0) ──────────────────────────────────────────────────
MCP_ANNOUNCEMENT_BODY = """
QAI Consultant is also available as a local MCP server — call it directly from
Claude Code, Claude Desktop, or claude.ai, no API keys required:

```
uvx qai-consultant-mcp
```

It exposes standards-grounded knowledge retrieval (`retrieve_qa_knowledge`,
`list_kb_sources`) and deterministic PERT-based effort estimation
(`estimate_qa_effort`) as MCP tools, plus prompts for the project-intake
interview and Risk Register / Test Strategy / Test Plan structures — so your
own AI coding assistant can ground its QA planning in the same knowledge base
this app uses, fully offline and keyless.

See the [GitHub repo](https://github.com/gvasile29/qai-consultant) for setup
and client configuration.

Listed on the [official MCP registry](https://registry.modelcontextprotocol.io)
(`io.github.gvasile29/qai-consultant-mcp`), [Glama](https://glama.ai/mcp/servers/gvasile29/qai-consultant),
and [Awesome MCP Servers](https://github.com/punkpeye/awesome-mcp-servers).
"""


# ── Sidebar ────────────────────────────────────────────────────────────────────
def render_sidebar():
    with st.sidebar:
        st.markdown("## 🧪 QAI Consultant")
        st.markdown("AI-powered QA Architect")
        st.caption(f"v{__version__}")
        if st.session_state.get("visit_count") is not None:
            st.caption(f"👀 {st.session_state.visit_count:,} visits")
        _eu_icon_svg = (
            "eu_ai_generated_icon_dark.svg"
            if _theme_type == "dark"
            else "eu_ai_generated_icon.svg"
        )
        st.image(str(EU_AI_ICON_DIR / _eu_icon_svg), width=140)
        st.info(AI_INTERACTION_NOTICE)
        with st.expander("📋 Release Notes"):
            st.markdown(load_changelog())
        with st.expander("🔌 Use QAI in your AI tools (MCP)"):
            st.markdown(MCP_ANNOUNCEMENT_BODY)
        st.divider()

        st.markdown("### How it works")
        st.markdown("""
1. **Describe** your project
2. **Answer** clarifying questions
3. **Receive** a tailored Test Strategy
4. **Download** as Markdown or PDF
        """)

        st.divider()
        st.markdown("### Knowledge Base")
        st.markdown("\n".join(load_kb_sidebar_bullets()))

        st.divider()
        if st.button("🔄 Start Over", use_container_width=True):
            for key in ["dialogue", "answers", "strategy", "sources", "output_path",
                        "risk_register", "risk_sources", "risk_path",
                        "effort_report", "effort_path", "effort_data",
                        "test_plan", "test_plan_path", "test_plan_sources",
                        "risk_pdf_bytes", "effort_pdf_bytes", "strategy_pdf_bytes", "test_plan_pdf_bytes",
                        "feedback_submitted", "_feedback_partial",
                        "generation_started", "results_complete",
                        "results_analysis",
                        "run_count", "current_step"]:
                if key in st.session_state:
                    del st.session_state[key]
            _reset_review_mode_state()
            for q in QUESTIONS:
                st.session_state.pop(f"input_{q['key']}", None)
            st.session_state.pop("input_additional_context", None)
            st.session_state.pop("review_additional_context", None)
            st.session_state.pop("results_uploader", None)
            st.rerun()

        st.markdown("[⭐ Star on GitHub](https://github.com/gvasile29/qai-consultant)", unsafe_allow_html=True)


# ── Example output constants (used in render_intro expander) ──────────────────
EXAMPLE_RISK = """
### Risk Register — ShopFlow E-Commerce Platform

| ID | Risk | Likelihood | Impact | Severity | Mitigation |
|----|------|-----------|--------|----------|-----------|
| R01 | Payment gateway integration failure | Medium | Critical | **High** | Contract SLA, fallback provider |
| R02 | GDPR non-compliance in user data handling | Low | Critical | **High** | DPO review, data mapping, consent flows |
| R03 | Performance degradation under Black Friday load | High | High | **High** | Load testing with k6, autoscaling config |
| R04 | SQL injection via product search | Low | Critical | **High** | Parameterised queries, OWASP WSTG review |
| R05 | Third-party analytics SDK breaking changes | Medium | Medium | **Medium** | Pin SDK versions, integration tests |
"""

EXAMPLE_EFFORT = """
### Effort Estimation — ShopFlow E-Commerce Platform

| Phase | Optimistic | Most Likely | Pessimistic | PERT Estimate |
|-------|-----------|-------------|-------------|---------------|
| Test Planning & Strategy | 3d | 5d | 8d | **5.2d** |
| Functional Testing | 8d | 12d | 18d | **12.3d** |
| Security Testing (OWASP) | 3d | 5d | 7d | **5.0d** |
| Performance Testing | 2d | 4d | 6d | **4.0d** |
| Regression & UAT | 4d | 6d | 10d | **6.3d** |
| **Total** | **20d** | **32d** | **49d** | **32.8d** |

**Confidence Score: 72 / 100 (Medium-High)**
Risk buffer: +20% → **~39 person-days**
"""

EXAMPLE_STRATEGY = """
### Test Strategy — ShopFlow E-Commerce Platform

**Scope:** End-to-end testing of checkout flow, user authentication, product catalogue, and payment integration.

**Approach:** Risk-based testing (ISTQB CTAL-TM) prioritising payment and authentication flows. OWASP WSTG v4.2 for security coverage.

**Test Levels:**
- **Unit** — Jest (frontend), Mocha (backend services) — developer-owned
- **Integration** — API contract tests (Postman/Newman), payment gateway mocks
- **System** — Playwright E2E covering 15 critical user journeys
- **Performance** — k6 load tests simulating 500 concurrent users

**Exit Criteria:** 0 open Critical/High defects, >85% test coverage on payment module, all OWASP Top 10 checks passed.
"""

EXAMPLE_TEST_PLAN = """
### Test Plan — ShopFlow E-Commerce Platform

**Standard:** IEEE 829 | **Methodology:** Scrum

**Test Items:** Checkout flow, user authentication, product catalogue, payment gateway integration, GDPR consent flows.

**Features NOT Tested:** Third-party logistics API (out of scope), admin panel (separate release).

**Entry Criteria:** Build passes CI, test environment deployed, test data seeded, no open Critical defects from previous sprint.

**Exit Criteria:** 0 open Critical/High defects, >90% test cases executed, all OWASP Top 10 checks passed, performance baseline met (p95 < 2s).

**Schedule:**

| Phase | Duration | Owner |
|-------|----------|-------|
| Test Design | 3 days | QA Lead |
| Functional Execution | 8 days | QA Engineers |
| Security (OWASP) | 3 days | QA Lead |
| Performance (k6) | 2 days | QA Engineers |
| Regression & UAT | 4 days | QA + Dev |

**AI Tool Oversight:** Playwright AI used for E2E test generation → all AI-generated test cases reviewed by QA Lead before merge. Copilot suggestions for test data require manual validation against GDPR requirements.
"""


# ── Steps ──────────────────────────────────────────────────────────────────────
def render_intro():
    from landing_hero import build_landing_hero_html
    from theme import DARK_TOKENS, LIGHT_TOKENS

    _hero_tokens = DARK_TOKENS if st.context.theme.type == "dark" else LIGHT_TOKENS
    st.markdown(build_landing_hero_html(_hero_tokens), unsafe_allow_html=True)

    st.markdown("---")

    st.markdown("#### 🎯 What you get in ~2 minutes")
    d1, d2, d3 = st.columns(3)
    with d1:
        st.success(
            "⚠️ **Risk Register**\n\n"
            "Prioritized risks with likelihood, impact & mitigation — before a single line of code is written."
        )
    with d2:
        st.success(
            "📊 **Effort Estimation**\n\n"
            "PERT-based timeline with team capacity analysis and a confidence score (0–100)."
        )
    with d3:
        st.success(
            "📋 **Test Strategy**\n\n"
            "ISTQB-aligned approach tailored to your stack, methodology, and compliance requirements."
        )
    d4, = st.columns(1)
    with d4:
        st.success(
            "📝 **Test Plan**\n\n"
            "IEEE 829-aligned plan with test items, entry/exit criteria, schedule, and AI tool oversight."
        )

    e1, e2, e3, e4 = st.columns(4)
    e1.metric("⏱️ Time to results", "~2 min", "vs. hours of manual work")
    e2.metric("📚 Standards", "ISTQB · OWASP · ISO", "7,100+ knowledge vectors")
    e3.metric("📄 Deliverables", "4 documents", "Risk · Effort · Strategy · Plan")
    e4.metric("💰 Cost", "Free", "No sign-up required")

    st.markdown("---")

    st.info(
        "💡 **Best used at project kick-off** — when you don't yet have code, "
        "architecture docs, or detailed specs to hand an AI assistant. "
        "QAI Consultant generates a baseline **Risk Register**, **Effort Estimation**, and **Test Strategy** "
        "grounded in ISTQB, OWASP, and ISO standards. "
        "Then **feed those docs into Claude Code or your AI IDE** as project context "
        "to get much more tailored, project-specific output."
    )

    with st.expander("📊 How is this different from just prompting Claude or Gemini?"):
        st.markdown("""
|  | **QAI Consultant** (this app) | **Generic AI** (no tools) | **Claude + `qai-consultant-mcp`** |
|---|---|---|---|
| Knowledge base | ISTQB, OWASP, ISO 26262, A-SPICE, EU AI Act, 17 AI SDLC case studies | General training data only | Same curated knowledge base, retrieved live via `retrieve_qa_knowledge` |
| Structured output | 4 full documents auto-generated (Risk, Effort, Strategy, Plan) | Varies by prompt quality, ungrounded | Claude writes the narrative — grounded in real retrieved sources, with `[Source N]` citations |
| Project discovery | Guided 11-question dialogue in the browser | You write the full prompt yourself | Same 11-question interview, served as an MCP prompt inside Claude |
| Effort estimation | Deterministic PERT + multipliers + confidence score | None — numbers are guessed, not computed | Same deterministic PERT core via `estimate_qa_effort` — no LLM guesswork |
| Setup | None — open the browser | None | One-time install (`uvx qai-consultant-mcp` / `claude mcp add`) |
| Best for | Fastest kick-off, no IDE, shareable documents | Quick unstructured chat, accept generic output | Already working in Claude Code/Desktop/claude.ai, want grounded answers + real numbers without leaving it |

The MCP server (v3.0+) is built from the same knowledge base and the same deterministic estimation core as this app — it's not a lesser copy, it's the same grounding and math, just consumed as tools inside Claude instead of as generated documents. It deliberately never generates documents itself: Claude's own reasoning writes the narrative, this server only supplies retrieval and numbers. See the [MCP server on PyPI](https://pypi.org/project/qai-consultant-mcp/).

**Recommended workflow:**
1. **Use QAI Consultant at kick-off** → generates your baseline documents in minutes
2. **Feed those docs into Claude Code** (or Copilot / Cursor) as project context — or, if you're already there, **install `qai-consultant-mcp`** and skip straight to grounded retrieval + estimation as tools
3. **Ask your AI assistant to refine** the strategy against your specific codebase, tickets, and architecture
        """)

    with st.expander("📄 See an example of what QAI Consultant generates"):
        ex_tab1, ex_tab2, ex_tab3, ex_tab4 = st.tabs(["⚠️ Risk Register", "📊 Effort Estimation", "📋 Test Strategy", "📝 Test Plan"])
        with ex_tab1:
            st.markdown(EXAMPLE_RISK)
        with ex_tab2:
            st.markdown(EXAMPLE_EFFORT)
        with ex_tab3:
            st.markdown(EXAMPLE_STRATEGY)
        with ex_tab4:
            st.markdown(EXAMPLE_TEST_PLAN)

    st.markdown("###")
    if st.button("🚀 Start — Generate a Test Strategy", use_container_width=True, type="primary"):
        st.session_state.current_step = "dialogue"
        st.rerun()
    if st.button("📝 Review an existing QA document instead", use_container_width=True):
        st.session_state.current_step = "doc_review"
        st.rerun()


def render_dialogue():
    st.markdown("## 📋 Project Discovery")
    st.markdown("Answer the questions below to help QAI understand your project.")
    st.markdown("---")

    total = len(QUESTIONS)
    answered = sum(1 for v in st.session_state.answers.values() if v and v.strip())
    progress = answered / total
    st.progress(progress, text=f"Progress: {answered}/{total} questions answered")
    st.markdown("###")

    selected_template = st.selectbox(
        "⚡ Quick start with a template",
        options=[opt[1] for opt in TEMPLATE_OPTIONS],
        format_func=lambda k: next((label for label, key in TEMPLATE_OPTIONS if key == k), "— Unknown —"),
        index=0,
        key="template_selector",
    )
    if selected_template and st.button("Apply template", key="apply_template"):
        for field, value in TEMPLATES[selected_template].items():
            if field != "label":
                st.session_state.answers[field] = value
                st.session_state[f"input_{field}"] = value
        st.rerun()

    with st.form("dialogue_form"):
        for idx, question in enumerate(QUESTIONS, start=1):
            key = question["key"]
            st.markdown(
                f'<div class="ledger-card">'
                f'<div class="idx">{idx:02d} / {len(QUESTIONS):02d}</div>'
                f'<div class="qtitle">{question["question"]}</div>'
                f"</div>",
                unsafe_allow_html=True,
            )
            st.caption(f"💡 {question['hint']}")
            st.session_state.answers[key] = st.text_input(
                label=question["question"],
                value=st.session_state.answers.get(key, ""),
                key=f"input_{key}",
                label_visibility="collapsed",
            )
            st.markdown("###")

        # Optional free-text context — deliberately NOT in st.session_state.answers:
        # the progress bar divides by len(QUESTIONS) and this field must not count.
        st.markdown("**Anything else QAI should know? (optional)**")
        st.caption("💡 e.g., legacy constraints, third-party dependencies, team specifics — used to tailor all generated documents")
        st.text_area(
            label="Anything else QAI should know? (optional)",
            key="input_additional_context",
            max_chars=2000,
            height=120,
            label_visibility="collapsed",
        )
        st.markdown("###")

        submitted = st.form_submit_button("✅ Review & Generate Strategy", use_container_width=True, type="primary")

    if submitted:
        # Validate all answers using InputValidator
        validator = InputValidator()
        errors = []
        cleaned_answers = {}

        for question in QUESTIONS:
            key = question["key"]
            raw = st.session_state.answers.get(key, "")
            result = validator.validate(key, raw)
            if not result.valid:
                errors.append(f"**{question['question']}**: {result.error}")
            else:
                cleaned_answers[key] = result.cleaned

        extra_result = validator.validate_additional_context(
            st.session_state.get("input_additional_context", "")
        )
        if not extra_result.valid:
            errors.append(f"**Additional context**: {extra_result.error}")

        if errors:
            st.warning("⚠️ Please fix the following before continuing:")
            for err in errors:
                st.markdown(f"- {err}")
        else:
            # Populate dialogue context with cleaned answers
            dialogue = DialogueManager()
            for question in QUESTIONS:
                dialogue.submit_answer(cleaned_answers[question["key"]])
            dialogue.set_additional_context(extra_result.cleaned)
            # Refresh the review pre-fill — safe here because the review
            # widget is not instantiated during this rerun.
            st.session_state["review_additional_context"] = extra_result.cleaned
            st.session_state.dialogue = dialogue
            st.session_state.current_step = "review"
            st.rerun()


def render_review():
    st.markdown("## 🔍 Review Project Context")
    st.markdown("Please confirm the information before generating the strategy.")
    st.markdown("---")

    context = st.session_state.dialogue.get_context()

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Project Name**")
        st.code(context.project_name)
        st.markdown("**Project Type**")
        st.code(context.project_type)
        st.markdown("**Tech Stack**")
        st.code(context.tech_stack)
        st.markdown("**Methodology**")
        st.code(context.methodology)
        st.markdown("**Timeline**")
        st.code(context.timeline)

    with col2:
        st.markdown("**QA Team Size**")
        st.code(context.team_qa_size)
        st.markdown("**Dev Team Size**")
        st.code(context.team_dev_size)
        st.markdown("**Known Risks**")
        st.code(context.known_risks)
        st.markdown("**Existing Automation**")
        st.code(context.existing_automation)
        st.markdown("**Compliance**")
        st.code(context.compliance_requirements)

    st.markdown("**Project Description**")
    st.info(context.project_description)

    st.markdown("**Additional Context**")
    # Seed-if-absent: passing value= when the key already exists in session
    # state would trigger Streamlit's "default value + Session State" warning.
    if "review_additional_context" not in st.session_state:
        st.session_state["review_additional_context"] = context.additional_context
    st.text_area(
        label="Additional context (optional — edit, extend, or clear before generating)",
        key="review_additional_context",
        max_chars=2000,
        height=120,
    )

    with st.expander("📊 Attach test execution results (optional)"):
        st.caption(
            "Upload JUnit XML and/or CSV test execution reports to ground the "
            "Risk Register in real pass/fail data — each XML file counts as one run."
        )
        uploaded_results = st.file_uploader(
            "Upload JUnit XML or CSV files",
            type=["xml", "csv"],
            accept_multiple_files=True,
            key="results_uploader",
        )
        if uploaded_results:
            records = []
            for uploaded_file in uploaded_results:
                content = uploaded_file.read().decode("utf-8", errors="ignore")
                if uploaded_file.name.lower().endswith(".csv"):
                    records.extend(parse_results_csv(content))
                else:
                    records.extend(parse_junit_xml(content, run_id=Path(uploaded_file.name).stem))
            st.session_state.results_analysis = compute_results_analysis(records)

        analysis = st.session_state.get("results_analysis")
        if analysis is not None:
            from ledger_components import signal_ledger_html

            pass_rate_pct = round(analysis.overall_pass_rate * 100)
            m1, m2, m3, m4 = st.columns(4)
            with m1:
                st.markdown(signal_ledger_html("Runs", analysis.runs, tier="hold"), unsafe_allow_html=True)
            with m2:
                st.markdown(signal_ledger_html("Pass Rate", pass_rate_pct, sub="%"), unsafe_allow_html=True)
            with m3:
                flaky_count = len(analysis.flaky)
                st.markdown(
                    signal_ledger_html("Flaky Tests", flaky_count, tier="pass" if flaky_count == 0 else "fail"),
                    unsafe_allow_html=True,
                )
            with m4:
                failing_count = len(analysis.ever_failing)
                st.markdown(
                    signal_ledger_html("Ever-Failing", failing_count, tier="pass" if failing_count == 0 else "fail"),
                    unsafe_allow_html=True,
                )
            if analysis.failure_clusters:
                top_clusters = "; ".join(
                    f"{c['signature']} (x{c['count']})" for c in analysis.failure_clusters[:3]
                )
                st.caption(f"Top failure clusters: {top_clusters}")
            if st.button("🗑️ Remove attached results"):
                st.session_state.results_analysis = None
                st.session_state.pop("results_uploader", None)
                st.rerun()

    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("← Go Back & Edit", use_container_width=True):
            # Carry review edits back to the dialogue widget — safe here
            # because the dialogue widget is not instantiated during this rerun.
            st.session_state["input_additional_context"] = st.session_state.get(
                "review_additional_context", ""
            )
            st.session_state.current_step = "dialogue"
            st.rerun()
    with col2:
        if st.button("🤖 Generate Test Strategy", use_container_width=True, type="primary"):
            validator = InputValidator()
            result = validator.validate_additional_context(
                st.session_state.get("review_additional_context", "")
            )
            if not result.valid:
                st.error(f"⚠️ Additional context: {result.error}")
            else:
                st.session_state.dialogue.set_additional_context(result.cleaned)
                st.session_state["input_additional_context"] = result.cleaned
                st.session_state.current_step = "strategy"
                st.rerun()


def _save_feedback(feedback_value: str, extra_note: str):
    output_path = st.session_state.get("output_path")
    if not output_path:
        st.warning("No strategy file found — feedback cannot be saved.")
        return
    if not output_path.exists():
        st.warning("Strategy file was deleted — feedback cannot be saved.")
        return
    try:
        feedback_dir = Path(__file__).resolve().parent.parent / "knowledge_base" / "generated_strategies"
        feedback_dir.mkdir(exist_ok=True)
        original_text = output_path.read_text(encoding="utf-8")
        # Strip existing YAML front matter to avoid duplicate --- blocks on re-ingestion
        if original_text.startswith("---"):
            end = original_text.find("---", 3)
            body = original_text[end + 3:].lstrip("\n") if end != -1 else original_text
        else:
            body = original_text
        feedback_content = f"---\nfeedback: {feedback_value}\nnotes: {extra_note}\n---\n\n"
        feedback_path = feedback_dir / output_path.name
        feedback_path.write_text(feedback_content + body, encoding="utf-8")
        st.success("✅ Strategy saved! Thank you for your feedback.")
    except Exception as e:
        logger.error(f"Feedback save failed: {e}")
        st.error("❌ Could not save feedback. Please try again.")


def render_strategy():
    MAX_RUNS_PER_SESSION = 3

    # Gated on an explicit completion flag, not on any single stage's output
    # (e.g. "strategy") — the pipeline has 4 sequential stages plus a PDF-bytes
    # precompute after that, so a rerun landing between "strategy" finishing
    # and the LAST step (PDF bytes) finishing must still resume, not fall
    # through as "already done".
    needs_generation = not st.session_state.get("results_complete", False)
    generation_started = st.session_state.get("generation_started", False)

    # Only block a *new* generation attempt on the run cap. A rerun that
    # re-enters mid-generation (generation_started already True) must be
    # allowed to resume — it's the same logical run, not a new one.
    if needs_generation and not generation_started and st.session_state.get("run_count", 0) >= MAX_RUNS_PER_SESSION:
        st.warning(
            f"⚠️ You've used all {MAX_RUNS_PER_SESSION} free runs for this session. "
            "Refresh the page to start a new session."
        )
        st.stop()

    st.markdown("## 📄 Generated Test Strategy")
    st.markdown("---")

    agent = st.session_state.get("agent")
    if agent is None:
        st.error("❌ Agent not initialised — please refresh the page.")
        st.stop()

    if needs_generation:
        from concurrent.futures import ThreadPoolExecutor
        from agent import RAG_K_GENERATION
        from risk_analyzer import build_risk_prompt, RISK_SYSTEM_PROMPT

        # A Streamlit rerun during the multi-minute streamed pipeline below
        # (e.g. a websocket reconnect) re-enters this branch before `strategy`
        # is set. Charge exactly one run per logical "Generate" click — not
        # once per rerun — and resume below rather than restart, so an
        # interrupted attempt doesn't burn the user's quota or redo
        # already-completed steps.
        if not generation_started:
            st.session_state.generation_started = True
            st.session_state.run_count += 1

        context = st.session_state.dialogue.get_context()
        generator = StrategyGenerator(agent)
        risk_analyzer = RiskAnalyzer(agent)
        estimator = EffortEstimator(agent)
        test_plan_generator = TestPlanGenerator(agent)

        # Parallel RAG retrieval (read-only Pinecone, thread-safe)
        with st.spinner("⚡ Fetching knowledge base context..."):
            with ThreadPoolExecutor(max_workers=3) as executor:
                f_risk = executor.submit(
                    agent.retrieve_knowledge,
                    risk_analyzer._build_risk_query(context),
                    RAG_K_GENERATION,
                )
                f_strategy = executor.submit(
                    agent.retrieve_knowledge,
                    context.to_rag_query(),
                    RAG_K_GENERATION,
                )
                f_test_plan = executor.submit(
                    agent.retrieve_knowledge,
                    test_plan_generator._build_test_plan_query(context),
                    RAG_K_GENERATION,
                )
                try:
                    risk_chunks = f_risk.result()
                except Exception as exc:
                    logger.warning("Risk RAG prefetch failed: %s", exc)
                    risk_chunks = []
                try:
                    strategy_chunks = f_strategy.result()
                except Exception as exc:
                    logger.warning("Strategy RAG prefetch failed: %s", exc)
                    strategy_chunks = []
                try:
                    test_plan_chunks = f_test_plan.result()
                except Exception as exc:
                    logger.warning("Test Plan RAG prefetch failed: %s", exc)
                    test_plan_chunks = []

        risk_sources = list({
            f"[{(c.metadata or {}).get('category', 'N/A')}] {(c.metadata or {}).get('filename', 'N/A')}"
            for c in risk_chunks
        })
        sources = list({
            f"[{(c.metadata or {}).get('category', 'N/A')}] {(c.metadata or {}).get('filename', 'N/A')}"
            for c in strategy_chunks
        })
        test_plan_sources = list({
            f"[{(c.metadata or {}).get('category', 'N/A')}] {(c.metadata or {}).get('filename', 'N/A')}"
            for c in test_plan_chunks
        })

        # Risk Register (streaming) — save to session state immediately after
        # Each step below is isolated in its own try/except, mirroring
        # StrategyGenerator.generate_all()'s per-step isolation: a transient
        # LLM outage (both Mistral and OpenRouter unavailable — observed to
        # become non-negligible under concurrent load) must fail that one
        # step with a clear message, not crash the whole page with a raw
        # traceback and discard whatever already generated successfully.
        # Each step is also skipped if a prior (interrupted) rerun already
        # produced it, so a resumed run doesn't redo completed work.
        if st.session_state.get("risk_register") is None:
            st.markdown("#### ⚠️ Generating Risk Register...")
            results_analysis = st.session_state.get("results_analysis")
            results_summary = summarize_for_prompt(results_analysis) if results_analysis else None
            risk_prompt = build_risk_prompt(
                context, agent.format_knowledge_context(risk_chunks), results_summary=results_summary,
            )
            try:
                risk_register = clean_markdown_html(st.write_stream(
                    agent.ask_streaming(risk_prompt, system_prompt=RISK_SYSTEM_PROMPT)
                ))
                risk_register = append_execution_data_appendix(risk_register, results_summary)
                risk_path = risk_analyzer.save(risk_register, context)
            except (StopException, RerunException):
                # Streamlit's own control-flow signals (e.g. a session
                # disconnect/reconnect mid-stream) — never swallow these.
                # Letting them propagate is what makes the resume-skip
                # guards above actually work on the next run; catching them
                # here as a normal error previously masked a real rerun as
                # a fake "generation failed" and let execution barrel into
                # the remaining stages, which is what racked up all these
                # empty-message failures in a single burst.
                raise
            except Exception as exc:
                logger.error("Risk Register generation failed: %s", exc)
                st.error(f"❌ Risk Register generation failed: {exc}")
                risk_register, risk_path = "", None
            st.session_state.risk_register = risk_register
            st.session_state.risk_sources = risk_sources
            st.session_state.risk_path = risk_path
        else:
            risk_register = st.session_state.risk_register

        # Effort Estimation (deterministic + short LLM narrative)
        if st.session_state.get("effort_report") is None:
            effort_data = None
            try:
                with st.spinner("📊 Generating Effort Estimation..."):
                    effort_report, effort_data = estimator.estimate(context, risk_register)
                    effort_path = estimator.save(effort_report, context)
            except (StopException, RerunException):
                raise
            except Exception as exc:
                logger.error("Effort Estimation generation failed: %s", exc)
                st.error(f"❌ Effort Estimation generation failed: {exc}")
                effort_report, effort_path = "", None
            st.session_state.effort_report = effort_report
            st.session_state.effort_path = effort_path
            st.session_state.effort_data = effort_data
        else:
            effort_report = st.session_state.effort_report

        # Test Strategy (streaming)
        if st.session_state.get("strategy") is None:
            st.markdown("#### 📋 Generating Test Strategy...")
            strategy_prompt = build_strategy_prompt(context, agent.format_knowledge_context(strategy_chunks))
            try:
                strategy = clean_markdown_html(st.write_stream(
                    agent.ask_streaming(strategy_prompt, system_prompt=SYSTEM_PROMPT)
                ))
                output_path = generator.save(strategy, context)
            except (StopException, RerunException):
                raise
            except Exception as exc:
                logger.error("Test Strategy generation failed: %s", exc)
                st.error(f"❌ Test Strategy generation failed: {exc}")
                strategy, output_path = "", None
            st.markdown("---")
            st.session_state.strategy = strategy
            st.session_state.sources = sources
            st.session_state.output_path = output_path
        else:
            strategy = st.session_state.strategy

        # Test Plan (streaming)
        from test_plan_generator import build_test_plan_prompt, TEST_PLAN_SYSTEM_PROMPT
        if st.session_state.get("test_plan") is None:
            st.markdown("#### 📝 Generating Test Plan...")
            test_plan_prompt = build_test_plan_prompt(context, risk_register, agent.format_knowledge_context(test_plan_chunks))
            try:
                test_plan = clean_markdown_html(st.write_stream(
                    agent.ask_streaming(test_plan_prompt, system_prompt=TEST_PLAN_SYSTEM_PROMPT)
                ))
                test_plan_path = test_plan_generator.save(test_plan, context)
            except (StopException, RerunException):
                raise
            except Exception as exc:
                logger.error("Test Plan generation failed: %s", exc)
                st.error(f"❌ Test Plan generation failed: {exc}")
                test_plan, test_plan_path = "", None
            st.markdown("---")
            st.session_state.test_plan = test_plan
            st.session_state.test_plan_path = test_plan_path
            st.session_state.test_plan_sources = test_plan_sources
        else:
            test_plan = st.session_state.test_plan

        # Pre-compute PDF bytes once — avoids regenerating on every re-render
        if st.session_state.get("risk_pdf_bytes") is None:
            _ai_pdf_meta = pdf_meta_html(MISTRAL_MODEL)
            _ai_pdf_icon = pdf_icon_html()
            st.session_state.risk_pdf_bytes = markdown_to_pdf(with_ai_footer(risk_register), "Risk Register", _ai_pdf_meta, _ai_pdf_icon)
            st.session_state.effort_pdf_bytes = markdown_to_pdf(with_ai_footer(effort_report), "Effort Estimation", _ai_pdf_meta, _ai_pdf_icon)
            st.session_state.strategy_pdf_bytes = markdown_to_pdf(with_ai_footer(strategy), "Test Strategy", _ai_pdf_meta, _ai_pdf_icon)
            st.session_state.test_plan_pdf_bytes = markdown_to_pdf(with_ai_footer(test_plan), "Test Plan", _ai_pdf_meta, _ai_pdf_icon)

        # All 4 stages (and the PDF-bytes precompute) finished this pass —
        # only NOW is it safe to stop re-entering this block on a rerun.
        st.session_state.results_complete = True

    # ── Three Tabs ────────────────────────────────────────────────────────
    tab1, tab2, tab3, tab4 = st.tabs(["⚠️ Risk Register", "📊 Effort Estimation", "📋 Test Strategy", "📝 Test Plan"])

    project_name = st.session_state.dialogue.get_context().project_name

    with tab1:
        from risk_ledger import parse_risk_matrix
        from ledger_components import risk_ledger_table_html

        risk_rows = parse_risk_matrix(st.session_state.risk_register)
        if risk_rows:
            st.markdown(risk_ledger_table_html(risk_rows), unsafe_allow_html=True)
            st.markdown("###")
        st.markdown(st.session_state.risk_register)
        st.markdown("---")
        with st.expander("📚 Knowledge Sources Used"):
            for source in st.session_state.risk_sources:
                st.markdown(f'<div class="source-item">• {source}</div>', unsafe_allow_html=True)
        dl_col1, dl_col2 = st.columns(2)
        with dl_col1:
            st.download_button(
                label="⬇️ Download (.md)",
                data=with_ai_footer(st.session_state.risk_register),
                file_name=f"risk_register_{project_name}.md",
                mime="text/markdown",
                use_container_width=True,
            )
        with dl_col2:
            pdf_bytes = st.session_state.risk_pdf_bytes
            st.download_button(
                label="⬇️ Download (.pdf)",
                data=pdf_bytes or b"",
                file_name=f"risk_register_{project_name}.pdf",
                mime="application/pdf",
                use_container_width=True,
                disabled=pdf_bytes is None,
            )

    with tab2:
        from ledger_components import signal_ledger_html

        effort_data = st.session_state.get("effort_data")
        if effort_data is not None:
            st.markdown(
                signal_ledger_html(
                    "Confidence",
                    effort_data.confidence_score,
                    sub=f"{effort_data.confidence_level} confidence",
                ),
                unsafe_allow_html=True,
            )
            st.markdown("###")
        st.markdown(st.session_state.effort_report)
        st.markdown("---")
        dl_col1, dl_col2 = st.columns(2)
        with dl_col1:
            st.download_button(
                label="⬇️ Download (.md)",
                data=with_ai_footer(st.session_state.effort_report),
                file_name=f"effort_estimation_{project_name}.md",
                mime="text/markdown",
                use_container_width=True,
            )
        with dl_col2:
            pdf_bytes = st.session_state.effort_pdf_bytes
            st.download_button(
                label="⬇️ Download (.pdf)",
                data=pdf_bytes or b"",
                file_name=f"effort_estimation_{project_name}.pdf",
                mime="application/pdf",
                use_container_width=True,
                disabled=pdf_bytes is None,
            )

    with tab3:
        st.markdown(st.session_state.strategy)
        st.markdown("---")
        with st.expander("📚 Knowledge Sources Used"):
            for source in st.session_state.sources:
                st.markdown(f'<div class="source-item">• {source}</div>', unsafe_allow_html=True)
        dl_col1, dl_col2 = st.columns(2)
        with dl_col1:
            st.download_button(
                label="⬇️ Download (.md)",
                data=with_ai_footer(st.session_state.strategy),
                file_name=f"test_strategy_{project_name}.md",
                mime="text/markdown",
                use_container_width=True,
                type="primary",
            )
        with dl_col2:
            pdf_bytes = st.session_state.strategy_pdf_bytes
            st.download_button(
                label="⬇️ Download (.pdf)",
                data=pdf_bytes or b"",
                file_name=f"test_strategy_{project_name}.pdf",
                mime="application/pdf",
                use_container_width=True,
                disabled=pdf_bytes is None,
            )

    with tab4:
        st.markdown(st.session_state.test_plan)
        st.markdown("---")
        with st.expander("📚 Knowledge Sources Used"):
            for source in st.session_state.test_plan_sources:
                st.markdown(f'<div class="source-item">• {source}</div>', unsafe_allow_html=True)
        dl_col1, dl_col2 = st.columns(2)
        with dl_col1:
            st.download_button(
                label="⬇️ Download (.md)",
                data=with_ai_footer(st.session_state.test_plan),
                file_name=f"test_plan_{project_name}.md",
                mime="text/markdown",
                use_container_width=True,
                type="primary",
            )
        with dl_col2:
            pdf_bytes = st.session_state.test_plan_pdf_bytes
            st.download_button(
                label="⬇️ Download (.pdf)",
                data=pdf_bytes or b"",
                file_name=f"test_plan_{project_name}.pdf",
                mime="application/pdf",
                use_container_width=True,
                disabled=pdf_bytes is None,
            )

    # Generate Another button
    st.markdown("###")
    if st.button("🔄 Generate Another Strategy", use_container_width=True):
        for key in ["dialogue", "answers", "strategy", "sources", "output_path",
                    "risk_register", "risk_sources", "risk_path",
                    "effort_report", "effort_path", "effort_data",
                    "test_plan", "test_plan_path", "test_plan_sources",
                    "risk_pdf_bytes", "effort_pdf_bytes", "strategy_pdf_bytes", "test_plan_pdf_bytes",
                    "feedback_submitted", "_feedback_partial",
                    "generation_started", "results_complete",
                    "results_analysis"]:
            if key in st.session_state:
                del st.session_state[key]
        _reset_review_mode_state()
        for q in QUESTIONS:
            st.session_state.pop(f"input_{q['key']}", None)
        st.session_state.pop("input_additional_context", None)
        st.session_state.pop("review_additional_context", None)
        st.session_state.pop("results_uploader", None)
        st.session_state.current_step = "intro"
        st.rerun()

    # ── Feedback Loop ──────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 💬 Was this Test Strategy useful?")
    st.caption("Your feedback helps QAI Consultant improve over time.")

    if not st.session_state.get("feedback_submitted", False):
        col1, col2, col3 = st.columns(3)
        with col1:
            yes = st.button("✅ Yes, it was useful!", use_container_width=True, type="primary")
        with col2:
            partially = st.button("🟡 Partially useful", use_container_width=True)
        with col3:
            no = st.button("❌ Not useful", use_container_width=True)

        # Persist "partially" across reruns — Streamlit buttons reset to False each rerun,
        # so we can't rely on the button value when the user is typing in the text input.
        if partially:
            st.session_state["_feedback_partial"] = True

        if st.session_state.get("_feedback_partial"):
            extra_note = st.text_input("📝 What could be improved?", key="improvement_note")
            save_partial = st.button("💾 Save feedback", use_container_width=True, type="primary")
            if save_partial:
                if not extra_note.strip():
                    st.warning("Please describe what could be improved before saving.")
                else:
                    _save_feedback("partially", extra_note)
                    st.session_state["_feedback_partial"] = False
                    st.session_state.feedback_submitted = True
                    st.rerun()

        if yes:
            _save_feedback("yes", "")
            st.session_state.feedback_submitted = True
            st.rerun()

        if no:
            st.session_state.feedback_submitted = True
            st.info("👍 Ok, strategy not added to knowledge base. Thank you for the feedback!")
            st.rerun()

    else:
        st.success("✅ Feedback submitted — thank you for helping QAI Consultant improve!")


_REVIEW_DOC_TYPE_OPTIONS = [
    ("Auto-detect", "auto"),
    ("Test Plan", "test_plan"),
    ("Test Strategy", "test_strategy"),
    ("Test Case List", "test_cases"),
]
_REVIEW_SEVERITY_ICON = {"critical": "🔴", "major": "🟠", "minor": "🟡"}


def render_doc_review():
    """F1: QA Document Quality Review. Step 1 (deterministic, instant) scores
    an uploaded/pasted document via review_core.review_document() — no LLM
    call. Step 2 (button) writes an LLM narrative around those already-
    computed findings and saves an Article-50(2)-marked report, mirroring
    render_strategy()'s save/PDF conventions."""
    MAX_RUNS_PER_SESSION = 3  # mirrors render_strategy()'s per-session cap — narrative is an LLM call

    st.markdown("## 📝 Review an Existing QA Document")
    st.markdown(
        "Upload or paste a Test Plan, Test Strategy, or test case list for a "
        "deterministic, ISTQB/IEEE-grounded quality review."
    )
    st.markdown("---")

    if st.session_state.get("review_result") is None:
        label = st.selectbox(
            "Document type",
            options=[label for label, _ in _REVIEW_DOC_TYPE_OPTIONS],
            index=0,
            key="review_doc_type_select",
        )
        doc_type = dict(_REVIEW_DOC_TYPE_OPTIONS)[label]

        uploaded = st.file_uploader(
            "Upload a document (.md, .txt)", type=["md", "txt"], key="review_doc_uploader",
        )
        st.caption("...or paste the document text below")
        pasted = st.text_area(
            "Document text", key="review_doc_pasted_text", height=300, label_visibility="collapsed",
        )

        document_text = ""
        source_label = "Document"
        if uploaded is not None:
            document_text = uploaded.read().decode("utf-8", errors="ignore")
            source_label = Path(uploaded.name).stem
        elif pasted.strip():
            document_text = pasted

        if st.button(
            "🔍 Review Document", use_container_width=True, type="primary",
            disabled=not document_text.strip(),
        ):
            st.session_state.review_input_text = document_text
            st.session_state.review_source_label = source_label
            st.session_state.review_result = review_document(document_text, doc_type=doc_type)
            st.rerun()

        if not document_text.strip():
            st.info("Upload a file or paste text above, then click **Review Document**.")

        if st.button("← Back to Home", key="review_back_to_home_pre"):
            st.session_state.current_step = "intro"
            st.rerun()
        return

    result = st.session_state.review_result

    if result.doc_type == "insufficient_content":
        st.warning(
            f"⚠️ Document is too short to review ({result.stats.get('char_count', 0)} "
            f"characters after cleanup — need at least {REVIEW_MIN_CONTENT_CHARS})."
        )
        if st.button("← Try another document", use_container_width=True):
            _reset_review_mode_state()
            st.rerun()
        return

    from ledger_components import signal_ledger_html

    st.markdown(f"**Detected document type:** `{result.doc_type}`")
    st.markdown(
        signal_ledger_html("Overall Score", result.overall_score, sub=f"{result.doc_type} · 6-dimension rubric"),
        unsafe_allow_html=True,
    )

    dim_cols = st.columns(len(result.dimension_scores))
    for col, (dim, score) in zip(dim_cols, result.dimension_scores.items()):
        with col:
            st.markdown(
                signal_ledger_html(dim.replace("_", " ").title(), score),
                unsafe_allow_html=True,
            )

    st.markdown("### Findings")
    if not result.findings:
        st.success("No findings — the document satisfies every mechanical check in the rubric.")
    else:
        for finding in result.findings:
            icon = _REVIEW_SEVERITY_ICON.get(finding.severity, "⚪")
            title = f"{icon} [{finding.dimension.replace('_', ' ').title()}] {finding.message}"
            with st.expander(title):
                st.markdown(f"**Severity:** {finding.severity}")
                st.markdown(f"**Evidence:** {finding.evidence}")

    st.markdown("---")

    # Step 2: LLM narrative — an LLM call, so it consumes run_count like render_strategy().
    if st.session_state.get("review_narrative") is None:
        if st.session_state.get("run_count", 0) >= MAX_RUNS_PER_SESSION:
            st.warning(
                f"⚠️ You've used all {MAX_RUNS_PER_SESSION} free runs for this session. "
                "Refresh the page to start a new session."
            )
        elif st.button("🤖 Generate narrative review", use_container_width=True, type="primary"):
            st.session_state.run_count += 1
            agent = st.session_state.get("agent")

            queries = []
            seen_queries = set()
            for finding in result.findings:
                for q in finding.citation_queries:
                    if q not in seen_queries:
                        seen_queries.add(q)
                        queries.append(q)

            with st.spinner("⚡ Retrieving grounding sources..."):
                chunks = []
                for q in queries[:5]:
                    chunks.extend(agent.retrieve_knowledge(q, k=1))
                if not chunks:
                    chunks = agent.retrieve_knowledge(
                        f"{result.doc_type.replace('_', ' ')} quality review", k=5,
                    )
            knowledge_context = agent.format_knowledge_context(chunks)

            prompt = build_review_prompt(result, knowledge_context)
            try:
                narrative = clean_markdown_html(st.write_stream(
                    agent.ask_streaming(prompt, system_prompt=REVIEW_SYSTEM_PROMPT)
                ))
            except (StopException, RerunException):
                # Same rule as render_strategy()'s 4 stages — never swallow
                # Streamlit's own stop/rerun control-flow signals.
                raise
            except Exception as exc:
                logger.error("Quality review narrative generation failed: %s", exc)
                st.error(f"❌ Narrative generation failed: {exc}")
                narrative = ""

            st.session_state.review_narrative = narrative
            st.session_state.review_narrative_sources = list({
                f"[{(c.metadata or {}).get('category', 'N/A')}] {(c.metadata or {}).get('filename', 'N/A')}"
                for c in chunks
            })
            st.rerun()
    else:
        if st.session_state.review_narrative:
            st.markdown("### 🤖 Narrative Review")
            st.markdown(st.session_state.review_narrative)
            with st.expander("📚 Knowledge Sources Used"):
                for source in st.session_state.get("review_narrative_sources", []):
                    st.markdown(f'<div class="source-item">• {source}</div>', unsafe_allow_html=True)

        # Save + PDF bytes computed once, only after the narrative step has
        # resolved (success or error) — mirrors render_strategy()'s "PDF
        # bytes precomputed once, never inside the tab render block" rule.
        if st.session_state.get("review_pdf_bytes") is None:
            report_md = build_review_report_markdown(result, st.session_state.review_narrative or "")
            st.session_state.review_output_path = save_review_report(
                report_md, st.session_state.get("review_source_label") or "Document",
            )
            _ai_pdf_meta = pdf_meta_html(MISTRAL_MODEL)
            _ai_pdf_icon = pdf_icon_html()
            st.session_state.review_pdf_bytes = markdown_to_pdf(
                with_ai_footer(report_md), "QA Document Quality Review", _ai_pdf_meta, _ai_pdf_icon,
            )

        report_md = build_review_report_markdown(result, st.session_state.review_narrative or "")
        st.markdown("---")
        dl_col1, dl_col2 = st.columns(2)
        with dl_col1:
            st.download_button(
                label="⬇️ Download (.md)",
                data=with_ai_footer(report_md),
                file_name="quality_review.md",
                mime="text/markdown",
                use_container_width=True,
            )
        with dl_col2:
            pdf_bytes = st.session_state.review_pdf_bytes
            st.download_button(
                label="⬇️ Download (.pdf)",
                data=pdf_bytes or b"",
                file_name="quality_review.pdf",
                mime="application/pdf",
                use_container_width=True,
                disabled=pdf_bytes is None,
            )

    st.markdown("###")
    if st.button("🔄 Review Another Document", use_container_width=True):
        _reset_review_mode_state()
        st.rerun()
    if st.button("← Back to Home"):
        _reset_review_mode_state()
        st.session_state.current_step = "intro"
        st.rerun()


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    init_session_state()

    # Visit counter: once per browser session (not per rerun) — see the
    # "visit_counted" guard. Excluded from both "Start Over" and "Generate
    # Another Strategy" cleanup lists on purpose (a visit is per page load,
    # not per generation attempt).
    if "visit_counted" not in st.session_state:
        st.session_state.visit_count = get_and_increment_visit_count()
        st.session_state.visit_counted = True

    _logo_col1, _logo_col2, _logo_col3 = st.columns([1, 1, 1])
    with _logo_col2:
        with st.container(key="header-logo"):
            _header_logo = (
                "qai_logo_horizontal_dark_1680.png"
                if st.context.theme.type == "dark"
                else "qai_logo_horizontal_1680.png"
            )
            st.image(str(BRAND_DIR / _header_logo), width=280)

    # ── Load agent — show clear error if API keys not ready ──────────────────
    agent, error = load_agent()
    if error:
        st.error(error)
        st.markdown("---")
        st.markdown("### 🛠️ Troubleshooting")
        st.code(
            "# Set required environment variables in .env\n"
            "MISTRAL_API_KEY=your_key_here\n"
            "OPENROUTER_API_KEY=your_key_here\n"
            "PINECONE_API_KEY=your_key_here\n"
            "PINECONE_INDEX_NAME=qai-consultant\n\n"
            "# Then build the knowledge base\n"
            "python src/ingest.py",
            language="bash"
        )
        st.stop()

    # Store agent in session state for use across components
    if st.session_state.get("agent") is None:
        st.session_state.agent = agent

    if not st.session_state.get("release_notes_seen"):
        st.session_state.release_notes_seen = True
        st.info(f"✨ Updated to v{__version__} — see the sidebar's **Release Notes** for what's new.")

    if not st.session_state.get("mcp_announcement_seen"):
        st.session_state.mcp_announcement_seen = True
        st.info(
            "🔌 QAI Consultant is now also available as an MCP server for Claude Code, "
            "Claude Desktop, and claude.ai — see the sidebar's **Use QAI in your AI tools "
            "(MCP)** panel."
        )

    render_sidebar()

    step = st.session_state.get("current_step", "intro")

    if step == "intro":
        render_intro()
    elif step == "dialogue":
        render_dialogue()
    elif step == "review":
        render_review()
    elif step == "strategy":
        render_strategy()
    elif step == "doc_review":
        render_doc_review()


if __name__ == "__main__":
    main()
