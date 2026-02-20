# QAI Consultant — Conversational Agent Implementation Plan

## Overview

The conversational agent is the core of QAI Consultant. It takes a product description as input, engages the user in a structured clarifying dialogue, and generates a tailored Test Strategy document backed by the knowledge base.

---

## Tech Stack

| Component | Technology | Why |
|---|---|---|
| LLM | Ollama (local) | Free, private, no API key needed |
| Recommended model | `mistral` or `llama3` | Good reasoning, runs on CPU |
| RAG | LangChain + ChromaDB | Already built in ingest.py |
| Embeddings | HuggingFace all-MiniLM-L6-v2 | Already built in ingest.py |
| CLI interface | Python (rich library) | Beautiful terminal output |
| Web UI | Streamlit | Simple, fast, no frontend skills needed |

---

## Agent Architecture

```
User Input (product description)
        │
        ▼
┌───────────────────┐
│  Clarifying       │  ← Asks structured questions to understand
│  Dialogue Module  │    the project before generating anything
└───────────────────┘
        │
        ▼
┌───────────────────┐
│  RAG Retrieval    │  ← Queries ChromaDB for relevant knowledge
│  Module           │    based on project context
└───────────────────┘
        │
        ▼
┌───────────────────┐
│  Strategy         │  ← Uses LLM + retrieved knowledge to
│  Generation Module│    generate the Test Strategy document
└───────────────────┘
        │
        ▼
  Test Strategy Output (markdown)
```

---

## Clarifying Dialogue — Questions Flow

The agent asks these questions ONE AT A TIME before generating the strategy:

1. **Project Type**
   > "What type of product are we testing? (web app, mobile app, API, embedded system, other)"

2. **Tech Stack**
   > "What is the main technology stack? (e.g., React + Node.js, Java Spring, Python Django)"

3. **Team Size**
   > "How many people are on the QA team? And how many developers?"

4. **Timeline**
   > "What is the project timeline or release deadline?"

5. **Methodology**
   > "Does the team follow Agile, Waterfall, or another methodology?"

6. **Known Risks**
   > "Are there any known high-risk areas or critical features? (e.g., payments, authentication, data migration)"

7. **Existing Testing**
   > "Does the project have any existing automated tests? If yes, what type?"

8. **Compliance / Regulatory**
   > "Are there any compliance or regulatory requirements? (e.g., GDPR, PCI-DSS, ISO, HIPAA)"

After all answers → RAG retrieval → Strategy generation.

---

## Output — Test Strategy Document Structure

```markdown
# Test Strategy — [Project Name]

## 1. Project Overview
## 2. Scope — What Will Be Tested
## 3. Scope — What Will NOT Be Tested
## 4. Risk Assessment
## 5. Test Types Recommended
## 6. Test Approach & Methodology
## 7. Entry & Exit Criteria
## 8. Resources & Man Power Estimation
## 9. Tools & Environment
## 10. Key Risks & Mitigations
## 11. References (ISTQB / OWASP / ISO standards used)
```

---

## File Structure in src/

```
src/
├── ingest.py              ← Already built ✅
├── agent.py               ← Core agent logic (RAG + LLM)
├── dialogue.py            ← Clarifying questions flow
├── strategy_generator.py  ← Test Strategy document builder
├── cli.py                 ← CLI interface
└── app.py                 ← Streamlit Web UI
```

---

## Implementation Order

### Phase 1 — Core Agent (agent.py)
- Connect to Ollama
- Connect to ChromaDB vector store
- Basic RAG query function — given a context, retrieve relevant knowledge

### Phase 2 — Dialogue Module (dialogue.py)
- Structured question flow
- Collect and store user answers
- Build project context object from answers

### Phase 3 — Strategy Generator (strategy_generator.py)
- Take project context + RAG results
- Build prompt for LLM
- Generate Test Strategy markdown document

### Phase 4 — CLI Interface (cli.py)
- Beautiful terminal experience using `rich` library
- Display questions, answers, and final strategy
- Option to save output as .md file

### Phase 5 — Web UI (app.py)
- Streamlit interface
- Same flow as CLI but in browser
- Download button for generated strategy

---

## Ollama Setup (prerequisite for users)

Users need Ollama installed before running QAI Consultant:

```bash
# Install Ollama (ollama.ai)
# Then pull the recommended model:
ollama pull mistral
```

QAI Consultant will check if Ollama is running at startup and give a clear error if not.

---

## New Dependencies to Add to requirements.txt

```
ollama==0.2.1
rich==13.7.1
streamlit==1.35.0
```

---

## Future Considerations

### Feedback Loop & Strategy Learning (v0.2)
After generating a strategy, ask the user for feedback and use validated strategies to grow the knowledge base:

1. After generation, user is asked: *"Was this strategy useful? (yes / partially / no)"*
2. If **yes** → strategy saved automatically to `knowledge_base/generated_strategies/`
3. If **partially** → user can add written feedback, saved alongside the strategy
4. If **no** → strategy discarded, optional feedback captured for improvement
5. On next `ingest.py` run, validated strategies are included in the knowledge base

**Why this matters:** The agent learns from real-world validated outputs, creating a feedback loop that improves quality over time. Only validated strategies enter the knowledge base to avoid degrading quality.

**Work products needed:**
- `feedback.py` — handles post-generation feedback collection
- `knowledge_base/generated_strategies/` — folder for validated strategies
- Update `ingest.py` to include `generated_strategies/` in ingestion
- Update CLI and Web UI to trigger feedback flow after generation

---

### Hosting & Web Accessibility (v2.0+)
Currently QAI Consultant runs locally. For future versions, consider hosting options so users can access it directly from a browser without any local installation:

- **Streamlit Cloud** — free tier available, direct GitHub integration, easiest option
- **Hugging Face Spaces** — free, great for open-source AI projects, built-in community visibility
- **Railway / Render** — simple deployment, free tier, good for small apps
- **Self-hosted VPS** — full control, cheapest long term (e.g., Hetzner, DigitalOcean)

Main challenge to solve for hosted version: Ollama runs locally, so a hosted version would need to switch to an API-based LLM (OpenAI, Claude, or a hosted open-source model via HuggingFace Inference API).

---

## Definition of Done for v0.2

- [ ] After strategy generation, user is asked: "Was this strategy useful? (yes / partially / no)"
- [ ] If yes → strategy saved automatically to `knowledge_base/generated_strategies/`
- [ ] If partially → user can add free-text feedback, saved alongside the strategy
- [ ] If no → strategy discarded, optionally user explains why
- [ ] Re-ingest script updated to include `generated_strategies/` folder
- [ ] Only validated strategies (yes/partially) enter the knowledge base

---

## Definition of Done for v0.1

- [ ] User can describe a project and get clarifying questions
- [ ] Agent retrieves relevant knowledge from ChromaDB
- [ ] Agent generates a complete Test Strategy document
- [ ] Output is saved as a markdown file
- [ ] Works via CLI
- [ ] Works via Streamlit Web UI
- [ ] README updated with how to run
