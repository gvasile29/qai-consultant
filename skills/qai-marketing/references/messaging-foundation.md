# QAI Consultant - Messaging Foundation

This is the source of truth for *what QAI Consultant actually solves*. Every post pulls its angle from here. The rule: lead with the problem/gap, use the product as the resolution, use standards/speed/determinism as proof.

## The core problem QAI addresses

QA planning and evaluation are done inconsistently, slowly, and without a defensible basis. In practice:

- **Blank-page paralysis.** A team starts a project and nobody knows where to begin with testing. Strategy, risk analysis, and effort estimates get improvised or skipped.
- **Documents nobody trusts.** Teams produce impressive-looking test plans and strategies that got approved, but no one can honestly say whether they are actually good, or whether they'd survive an audit.
- **Risk by gut feeling.** Risk registers are written from intuition, not evidence. The CI dashboard full of green and red dots is glanced at and never truly read.
- **Estimates as black boxes.** Effort numbers are pulled from experience or pressure, not a transparent method, so nobody can defend or reproduce them.
- **Standards live in PDFs, not in the work.** ISTQB, OWASP, IEEE, ISO, and now the EU AI Act contain the answers, but they sit in hundreds of pages nobody has time to retrieve mid-task.

## The gap (how it was identified)

The senior QA knowledge to do all of this well exists, but it is trapped: in expensive consultants, in a few experts' heads, and in dense standards documents. Most teams cannot access it at the moment they need it. Meanwhile general-purpose AI assistants are great at *writing* but will confidently hallucinate QA specifics, invent risk scores, and cite standards they don't actually know. So you get either no expertise, or fluent-but-untrustworthy expertise.

**The gap:** there was no tool that gives you *grounded, reproducible, standards-backed* QA thinking, retrieval that cites real sources, math that is deterministic, and process templates that are validated, rather than an LLM improvising.

## Why QAI helps (the resolution)

QAI Consultant acts as a senior QA Architect that is available on demand and honest about its basis:

- **From a short interview to real artifacts.** Answer a few questions about your project and get a Test Strategy, Risk Register, Effort Estimation, and Test Plan in minutes, each grounded in recognized standards.
- **Judgment, not just generation.** It reviews existing documents: upload a Test Plan/Strategy/test cases and get a 0-to-100 score across six quality dimensions with specific, actionable findings, so you know before an audit does.
- **Evidence over gut.** Point it at JUnit XML or CSV results and it surfaces flaky tests, never-passed tests, never-run tests, failure clusters, and slow spots, then feeds that evidence straight into the Risk Register.
- **Deterministic where it counts.** Effort (PERT-based) and results analysis are deterministic: same input, same verdict, every time. No hallucinated numbers.
- **Grounded and cited.** Every answer is retrieved from a real knowledge base and you can see the sources.
- **Portable.** It is also an MCP server, so the same grounded retrieval, deterministic math, and validated templates plug directly into Claude Code, Claude Desktop, or claude.ai. Keyless, local, no cloud LLM calls.
- **Transparent by design.** Fully compliant with EU AI Act Article 50 transparency obligations: clear AI interaction notice, every generated document labeled and machine-readable-marked, the EU's official "Fully AI-Generated" icon. A quality tool that holds itself to the standard it asks of others.

## The design principle (great for dev/OSS audience)

The client LLM is already a strong writer, so the MCP server deliberately does **not** try to out-write it. It exposes only what an LLM cannot reliably do alone: trusted standards-grounded retrieval, deterministic estimation, and validated QA process templates. Generation stays in the app; the server exposes judgment and grounding. This restraint is the point, and it resonates with builders.

## Proof points (evidence, use AFTER the problem is set)

- Grounded in ISTQB, OWASP, IEEE, ISO/IEC 25010 & 26262, A-SPICE, and EU AI Act, plus process/audit maturity models (TMMi, CMMI) and real failure case studies (Knight Capital, Boeing 737 MAX MCAS, CrowdStrike 2024).
- Deterministic PERT effort math with a confidence score.
- Six-dimension document review rubric grounded in ISTQB/IEEE 829.
- Free, in-browser live app, no install to start.
- Open-source (Apache 2.0), on PyPI as `qai-consultant-mcp`, listed on the MCP registry, Glama, and awesome-mcp-servers.
- One command to connect: `claude mcp add qai-consultant -- uvx qai-consultant-mcp`.

## Hook bank (problem-first openers to adapt, never reuse verbatim)

- "Every QA team has that one document nobody's brave enough to reopen."
- "Your test suite has been trying to tell you something. Nobody's been reading."
- "A test plan getting approved and a test plan being good are two very different things."
- "Most risk registers are just fear, formatted nicely."
- "The QA expertise you need exists. It's just locked in a 300-page PDF you don't have time to read."
- "General AI will happily write you a test strategy. It will also happily make half of it up."

## Audience awareness: many readers don't know they have the problem

A large part of the audience is **problem-unaware**. They ship software, they "do QA", and they have never once thought critically about whether their test strategy, risk analysis, or estimation is any good. They are not searching for a solution because they don't perceive a gap. You cannot sell a resolution to someone who doesn't feel the tension yet.

So a core job of the content is not just to answer a known pain, but to **make an invisible problem visible**, to produce the "aha, I never thought about that" moment. This is the awareness ladder (Eugene Schwartz's 5 stages): unaware -> problem-aware -> solution-aware -> product-aware -> most-aware. Different posts target different rungs:

- **Unaware / problem-aware (the biggest, most neglected group):** content that reframes something they take for granted and reveals the hidden flaw. No product pitch, or the lightest possible one. The goal is the realization, not the click. Example seeds:
  - "Your test plan getting approved and your test plan being good are two completely different things, and almost no team checks the second one."
  - "A green CI dashboard doesn't mean your tests are good. It might mean they never fail because they never actually test anything."
  - "Most teams estimate QA effort by feeling. Then wonder why the number was wrong. The problem isn't the number, it's that nobody can reproduce how it was reached."
  - "Nobody writes a risk register expecting an audit. Then the audit comes, and 'we felt these were the risks' is the answer on the page."
- **Solution-aware and up:** the release/feature/comparison posts. These convert people who already feel the gap. Fewer of them exist, so don't spend all your content here.

### The "aha" technique (how to build the realization)

1. Start from something the reader is certain is fine (an approved doc, a green dashboard, a confident estimate).
2. Reveal the quiet assumption underneath it that doesn't hold.
3. Let them feel the gap themselves before you name QAI. The realization must feel like *their* thought, not your sales pitch.
4. Only then, softly: "this is exactly the blind spot QAI's [document review / results analysis] surfaces."

Rule of thumb: for problem-unaware content, spend ~80% making the problem real and ~20% (or less) on the product. If the reader finishes thinking "huh, I should look at my own test plan differently," the post won. The click is a bonus, the reframe is the goal.

## Anti-patterns (do not do)

- Opening with "QAI Consultant is a fast, standards-based tool that..."
- Feature dumps with no pain named.
- Vague benefit language ("boosts quality", "streamlines testing").
- Reusing the same hook across posts.
- Any em dash character.
