"""
QAI Consultant — Streamlit Web UI
Browser-based interface for generating Test Strategy documents.
"""

import os
import sys


from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent))

import streamlit as st
from agent import QAIAgent
from dialogue import DialogueManager, QUESTIONS
from strategy_generator import StrategyGenerator, build_strategy_prompt, SYSTEM_PROMPT
from risk_analyzer import RiskAnalyzer
from effort_estimator import EffortEstimator
from agent import QAIConnectionError, QAIKnowledgeBaseError
from logger import setup_logging, get_logger
from version import __version__
from templates import TEMPLATES, TEMPLATE_OPTIONS
from pdf_export import markdown_to_pdf
from test_plan_generator import TestPlanGenerator

setup_logging()
logger = get_logger(__name__)


# ── Page Config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="QAI Consultant",
    page_icon="🧪",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #00b4d8;
        margin-bottom: 0;
    }
    .sub-header {
        font-size: 1rem;
        color: #888;
        margin-bottom: 2rem;
    }
    .question-card {
        background-color: #1e1e2e;
        border-left: 4px solid #00b4d8;
        padding: 1rem;
        border-radius: 4px;
        margin-bottom: 1rem;
    }
    .progress-text {
        color: #00b4d8;
        font-weight: bold;
    }
    .source-item {
        background-color: #1e1e2e;
        padding: 0.3rem 0.6rem;
        border-radius: 4px;
        margin: 0.2rem 0;
        font-size: 0.85rem;
        color: #aaa;
    }
</style>
""", unsafe_allow_html=True)


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
    if "test_plan" not in st.session_state:
        st.session_state.test_plan = None
    if "test_plan_path" not in st.session_state:
        st.session_state.test_plan_path = None
    if "test_plan_sources" not in st.session_state:
        st.session_state.test_plan_sources = []
    if "current_step" not in st.session_state:
        st.session_state.current_step = "intro"  # intro | dialogue | review | strategy
    if "run_count" not in st.session_state:
        st.session_state.run_count = 0


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



# ── Sidebar ────────────────────────────────────────────────────────────────────
def render_sidebar():
    with st.sidebar:
        st.markdown("## 🧪 QAI Consultant")
        st.markdown("AI-powered QA Architect")
        st.caption(f"v{__version__}")
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
        st.markdown("""
- 📘 ISTQB Syllabuses
- 🔒 OWASP Testing Guides
- 🚗 ISO 26262 & A-SPICE
- 📋 IEEE 829
- ⚙️ ISO/IEC 25010
- 🤖 AI SDLC Adoption (2024–2025)
- 🧠 Expert Knowledge
        """)

        st.divider()
        if st.button("🔄 Start Over", use_container_width=True):
            for key in ["dialogue", "answers", "strategy", "sources", "output_path",
                        "risk_register", "risk_sources", "risk_path",
                        "effort_report", "effort_path",
                        "test_plan", "test_plan_path", "test_plan_sources",
                        "feedback_submitted",
                        "current_step"]:
                if key in st.session_state:
                    del st.session_state[key]
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
    st.markdown('<p class="main-header">🧪 QAI Consultant</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Your AI-powered QA Architect — Test Strategy Generator</p>', unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.info("📋 **Answer** a few questions about your project")
    with col2:
        st.info("🧠 **AI analyzes** using QA methodologies & standards")
    with col3:
        st.info("📄 **Download** your tailored Test Strategy (Markdown & PDF)")

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
    e2.metric("📚 Standards", "ISTQB · OWASP · ISO", "7,000+ knowledge vectors")
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
|  | **QAI Consultant** | **General AI (Claude / Gemini)** |
|---|---|---|
| Knowledge base | ISTQB, OWASP, ISO 26262, A-SPICE, 17 AI SDLC case studies | General training data |
| Structured output | Risk Register + Effort Estimation + Test Strategy | Varies by prompt quality |
| Project discovery | Guided 11-question dialogue | You write the full prompt |
| RAG grounding | 7,000+ QA-specific vectors in Pinecone | None |
| Best for | Early-stage / kick-off, no codebase yet | When you already have project context |

**Recommended workflow:**
1. **Use QAI Consultant at kick-off** → generates your baseline documents in minutes
2. **Feed those docs into Claude Code** (or Copilot / Cursor) as project context
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
        format_func=lambda k: next(label for label, key in TEMPLATE_OPTIONS if key == k),
        index=0,
        key="template_selector",
    )
    if selected_template and st.button("Apply template", key="apply_template"):
        for field, value in TEMPLATES[selected_template].items():
            if field != "label":
                st.session_state.answers[field] = value
        st.rerun()

    with st.form("dialogue_form"):
        for question in QUESTIONS:
            key = question["key"]
            st.markdown(f"**{question['question']}**")
            st.caption(f"💡 {question['hint']}")
            st.session_state.answers[key] = st.text_input(
                label=question["question"],
                value=st.session_state.answers.get(key, ""),
                key=f"input_{key}",
                label_visibility="collapsed",
            )
            st.markdown("###")

        submitted = st.form_submit_button("✅ Review & Generate Strategy", use_container_width=True, type="primary")

    if submitted:
        # Validate all answers using InputValidator
        from dialogue import InputValidator
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

        if errors:
            st.warning("⚠️ Please fix the following before continuing:")
            for err in errors:
                st.markdown(f"- {err}")
        else:
            # Populate dialogue context with cleaned answers
            dialogue = DialogueManager()
            for question in QUESTIONS:
                dialogue.submit_answer(cleaned_answers[question["key"]])
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

    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("← Go Back & Edit", use_container_width=True):
            st.session_state.current_step = "dialogue"
            st.rerun()
    with col2:
        if st.button("🤖 Generate Test Strategy", use_container_width=True, type="primary"):
            st.session_state.current_step = "strategy"
            st.rerun()


def _save_feedback(feedback_value: str, extra_note: str):
    feedback_dir = Path(__file__).resolve().parent.parent / "knowledge_base" / "generated_strategies"
    feedback_dir.mkdir(exist_ok=True)
    feedback_content = f"---\nfeedback: {feedback_value}\nnotes: {extra_note}\n---\n\n"
    output_path = st.session_state.output_path
    feedback_path = feedback_dir / output_path.name
    feedback_path.write_text(
        feedback_content + output_path.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    st.success("✅ Strategy saved! Thank you for your feedback.")


def render_strategy():
    MAX_RUNS_PER_SESSION = 3

    if st.session_state.run_count >= MAX_RUNS_PER_SESSION:
        st.warning(
            f"⚠️ You've used all {MAX_RUNS_PER_SESSION} free runs for this session. "
            "Refresh the page to start a new session."
        )
        st.stop()

    st.markdown("## 📄 Generated Test Strategy")
    st.markdown("---")

    if st.session_state.strategy is None:
        from concurrent.futures import ThreadPoolExecutor
        from agent import RAG_K_GENERATION
        from risk_analyzer import build_risk_prompt, RISK_SYSTEM_PROMPT

        context = st.session_state.dialogue.get_context()
        agent = st.session_state.agent
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
                risk_chunks = f_risk.result()
                strategy_chunks = f_strategy.result()
                test_plan_chunks = f_test_plan.result()

        risk_sources = list({
            f"[{c.metadata.get('category', 'N/A')}] {c.metadata.get('filename', 'N/A')}"
            for c in risk_chunks
        })
        sources = list({
            f"[{c.metadata.get('category', 'N/A')}] {c.metadata.get('filename', 'N/A')}"
            for c in strategy_chunks
        })
        test_plan_sources = list({
            f"[{c.metadata.get('category', 'N/A')}] {c.metadata.get('filename', 'N/A')}"
            for c in test_plan_chunks
        })

        # Risk Register (streaming)
        st.markdown("#### ⚠️ Generating Risk Register...")
        risk_prompt = build_risk_prompt(context, agent.format_knowledge_context(risk_chunks))
        risk_register = st.write_stream(
            agent.ask_streaming(risk_prompt, system_prompt=RISK_SYSTEM_PROMPT)
        )
        risk_path = risk_analyzer.save(risk_register, context)

        # Effort Estimation (deterministic + short LLM narrative)
        with st.spinner("📊 Generating Effort Estimation..."):
            effort_report, effort_data = estimator.estimate(context, risk_register)
            effort_path = estimator.save(effort_report, context)

        # Test Strategy (streaming)
        st.markdown("#### 📋 Generating Test Strategy...")
        strategy_prompt = build_strategy_prompt(context, agent.format_knowledge_context(strategy_chunks))
        strategy = st.write_stream(
            agent.ask_streaming(strategy_prompt, system_prompt=SYSTEM_PROMPT)
        )
        output_path = generator.save(strategy, context)
        st.markdown("---")

        # Test Plan (streaming)
        from test_plan_generator import build_test_plan_prompt, TEST_PLAN_SYSTEM_PROMPT
        st.markdown("#### 📝 Generating Test Plan...")
        test_plan_prompt = build_test_plan_prompt(context, risk_register, agent.format_knowledge_context(test_plan_chunks))
        test_plan = st.write_stream(
            agent.ask_streaming(test_plan_prompt, system_prompt=TEST_PLAN_SYSTEM_PROMPT)
        )
        test_plan_path = test_plan_generator.save(test_plan, context)
        st.markdown("---")

        st.session_state.strategy = strategy
        st.session_state.run_count = st.session_state.get("run_count", 0) + 1
        st.session_state.sources = sources
        st.session_state.output_path = output_path
        st.session_state.risk_register = risk_register
        st.session_state.risk_sources = risk_sources
        st.session_state.risk_path = risk_path
        st.session_state.effort_report = effort_report
        st.session_state.effort_path = effort_path
        st.session_state.test_plan = test_plan
        st.session_state.test_plan_path = test_plan_path
        st.session_state.test_plan_sources = test_plan_sources

    # ── Three Tabs ────────────────────────────────────────────────────────
    tab1, tab2, tab3, tab4 = st.tabs(["⚠️ Risk Register", "📊 Effort Estimation", "📋 Test Strategy", "📝 Test Plan"])

    with tab1:
        st.markdown(st.session_state.risk_register)
        st.markdown("---")
        with st.expander("📚 Knowledge Sources Used"):
            for source in st.session_state.risk_sources:
                st.markdown(f'<div class="source-item">• {source}</div>', unsafe_allow_html=True)
        dl_col1, dl_col2 = st.columns(2)
        with dl_col1:
            st.download_button(
                label="⬇️ Download (.md)",
                data=st.session_state.risk_register,
                file_name=f"risk_register_{st.session_state.dialogue.get_context().project_name}.md",
                mime="text/markdown",
                use_container_width=True,
            )
        with dl_col2:
            pdf_bytes = markdown_to_pdf(st.session_state.risk_register, "Risk Register")
            st.download_button(
                label="⬇️ Download (.pdf)",
                data=pdf_bytes or b"",
                file_name=f"risk_register_{st.session_state.dialogue.get_context().project_name}.pdf",
                mime="application/pdf",
                use_container_width=True,
                disabled=pdf_bytes is None,
            )

    with tab2:
        st.markdown(st.session_state.effort_report)
        st.markdown("---")
        dl_col1, dl_col2 = st.columns(2)
        with dl_col1:
            st.download_button(
                label="⬇️ Download (.md)",
                data=st.session_state.effort_report,
                file_name=f"effort_estimation_{st.session_state.dialogue.get_context().project_name}.md",
                mime="text/markdown",
                use_container_width=True,
            )
        with dl_col2:
            pdf_bytes = markdown_to_pdf(st.session_state.effort_report, "Effort Estimation")
            st.download_button(
                label="⬇️ Download (.pdf)",
                data=pdf_bytes or b"",
                file_name=f"effort_estimation_{st.session_state.dialogue.get_context().project_name}.pdf",
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
                data=st.session_state.strategy,
                file_name=f"test_strategy_{st.session_state.dialogue.get_context().project_name}.md",
                mime="text/markdown",
                use_container_width=True,
                type="primary",
            )
        with dl_col2:
            pdf_bytes = markdown_to_pdf(st.session_state.strategy, "Test Strategy")
            st.download_button(
                label="⬇️ Download (.pdf)",
                data=pdf_bytes or b"",
                file_name=f"test_strategy_{st.session_state.dialogue.get_context().project_name}.pdf",
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
                data=st.session_state.test_plan,
                file_name=f"test_plan_{st.session_state.dialogue.get_context().project_name}.md",
                mime="text/markdown",
                use_container_width=True,
                type="primary",
            )
        with dl_col2:
            pdf_bytes = markdown_to_pdf(st.session_state.test_plan, "Test Plan")
            st.download_button(
                label="⬇️ Download (.pdf)",
                data=pdf_bytes or b"",
                file_name=f"test_plan_{st.session_state.dialogue.get_context().project_name}.pdf",
                mime="application/pdf",
                use_container_width=True,
                disabled=pdf_bytes is None,
            )

    # Generate Another button
    st.markdown("###")
    if st.button("🔄 Generate Another Strategy", use_container_width=True):
        for key in ["dialogue", "answers", "strategy", "sources", "output_path",
                    "risk_register", "risk_sources", "risk_path",
                    "effort_report", "effort_path",
                    "test_plan", "test_plan_path", "test_plan_sources",
                    "feedback_submitted"]:
            if key in st.session_state:
                del st.session_state[key]
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


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    init_session_state()

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
    if st.session_state.agent is None:
        st.session_state.agent = agent

    render_sidebar()

    step = st.session_state.current_step

    if step == "intro":
        render_intro()
    elif step == "dialogue":
        render_dialogue()
    elif step == "review":
        render_review()
    elif step == "strategy":
        render_strategy()


if __name__ == "__main__":
    main()
