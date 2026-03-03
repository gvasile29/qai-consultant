# Contributing to QAI Consultant

Thank you for helping improve QAI Consultant! The most impactful way to contribute
is by expanding the knowledge base with high-quality QA content.

---

## Ways to Contribute

1. **Add knowledge base files** — standards, methodologies, expert knowledge
2. **Report bugs** — open a GitHub issue
3. **Improve existing content** — fix errors, add examples, improve clarity
4. **Share validated strategies** — use the feedback loop in the app

---

## Contributing Knowledge Base Files

### Folder Structure

```
knowledge_base/
├── standards/          ← Official QA standards (ISTQB, OWASP, ISO, etc.)
├── methodologies/      ← Testing methodologies and approaches
├── articles/           ← QA articles, guides, case studies
└── expert_knowledge/   ← Domain-specific expert knowledge (automotive, fintech, etc.)
```

### File Format

All knowledge files should be **Markdown (`.md`)** or **PDF (`.pdf`)**.

For markdown files, follow this structure:

```markdown
# Document Title

## Overview
Brief description of what this document covers and why it's relevant to QA.

## Key Concepts
...

## Application to Testing
...

## References
- Source 1
- Source 2
```

### Naming Conventions

```
standards/    → STANDARD_NAME_Version.md       (e.g., ISTQB_CTFL_v4.md)
methodologies/ → Methodology_Name.md           (e.g., Risk_Based_Testing.md)
articles/     → Topic_Description.md           (e.g., API_Testing_Best_Practices.md)
expert_knowledge/ → Domain_Topic.md            (e.g., Automotive_SOTIF_Testing.md)
```

---

## Adding a New Methodology

1. Create a `.md` file in `knowledge_base/methodologies/`
2. Follow the naming convention: `Methodology_Name.md`
3. Include these sections:
   - **Overview** — what it is and when to use it
   - **Core Principles** — key concepts
   - **Process / Steps** — how to apply it
   - **When to Use** — project types and contexts
   - **Advantages & Limitations**
   - **References** — authoritative sources

**Example:** See `knowledge_base/methodologies/Risk_Based_Testing.md`

---

## Adding a New Standard

For publicly available standards (ISTQB, OWASP, IEEE):

**Option A — Summary MD file (preferred for copyright reasons)**
Create a `.md` summary with key concepts, not a verbatim copy.

**Option B — Official PDF**
If the standard is freely distributable (e.g., OWASP WSTG):
- Place PDF in `knowledge_base/standards/`
- Verify the license allows redistribution

> ⚠️ **Copyright notice:** Do not add copyrighted PDFs (e.g., ISO standards that
> require purchase). Create a summary MD file instead.

---

## Adding Expert Knowledge

Expert knowledge files capture domain-specific QA insights not covered by
standard references. Great examples:

- Automotive: SOTIF, AUTOSAR testing, HIL/SIL validation
- Fintech: PCI-DSS testing patterns, transaction validation
- Healthcare: HIPAA compliance testing, FDA 21 CFR Part 11
- IoT: firmware testing, protocol fuzzing
- Energy: IEC 61850, grid stability testing

Use the prompts in `knowledge_base/expert_knowledge/` as a guide.

---

## After Adding Files

```bash
# Re-ingest to update ChromaDB
python src/ingest.py

# Verify the new content was ingested
# Look for your file in the output:
# ✅ Ingested: your_file.md → N chunks
```

If the app is already running, the **auto re-ingest watcher** (v0.5) will
detect new files and ingest them automatically within 3 seconds.

---

## Using the Feedback Loop

The easiest way to contribute validated strategies:

1. Run QAI Consultant and generate a strategy for your project
2. If the strategy is good → answer **"yes"** when prompted for feedback
3. The strategy is saved to `knowledge_base/generated_strategies/`
4. It's automatically ingested and used to improve future generations

---

## Pull Request Guidelines

1. **Fork** the repository at https://github.com/gvasile29/qai-consultant
2. **Create a branch**: `git checkout -b add/automotive-testing-knowledge`
3. **Add your files** following the naming conventions above
4. **Run ingest** and verify your content is ingested correctly
5. **Test** that QAI generates better strategies with your content
6. **Submit a PR** with:
   - Description of what you added
   - What project types benefit from this knowledge
   - How you verified the content quality

---

## Code Contributions

If you want to contribute code:

1. Read `CLAUDE.md` for the full architecture overview
2. Follow the existing code style (type hints, docstrings, logger usage)
3. Write tests for any new functionality
4. Run the full test suite before submitting: `pytest tests/`
5. Update `CLAUDE.md` if you add new modules or change the architecture

---

## Questions?

Open a GitHub issue with the label `question` or `enhancement`.
