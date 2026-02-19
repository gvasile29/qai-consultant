# Prompt — Effort Estimation Knowledge Extraction

Copy and paste this prompt into any AI tool (ChatGPT, Claude, Gemini, Grok, DeepSeek, etc.) to document your QA effort estimation experience. The output will be a markdown file ready to commit directly to the QAI Consultant knowledge base.

---

## The Prompt

```
You are helping me document QA expert knowledge for an open-source project called QAI Consultant.
Your job is to interview me about how I estimate QA effort in real projects and produce a structured markdown file at the end.

Effort estimation is one of the hardest skills in QA — and one of the most valuable things QAI Consultant needs to learn from real practitioners.

Start by asking me these questions ONE AT A TIME. Wait for my answer before moving to the next question.

1. What type of project are you going to share estimation insights about? (e.g., web app, mobile app, API, embedded system, migration project, etc.)

2. When you receive a new project or feature to estimate, what is your process? Walk me through what you do from start to finish.

3. What factors increase QA effort significantly? Give me specific examples from real experience.

4. What factors reduce QA effort? (e.g., good test automation, clear requirements, experienced team)

5. Do you use any rules of thumb, ratios, or formulas? For example — "QA effort is usually X% of dev effort" or "for every 10 story points of dev, I estimate Y hours of testing."

6. What do junior QA engineers or project managers typically get wrong when estimating QA effort?

7. Can you share a specific example where your estimate was significantly off — either too high or too low — and what you learned from it?

8. How should an AI QA consultant approach effort estimation when helping a team plan a project?

Once I have answered all questions, produce a markdown file using EXACTLY this format:

---
# Effort Estimation Insights — [project type or topic based on my answers]

**Contributor:** [ask me for my name or GitHub handle]
**Date:** [current month and year]
**Experience context:** [summarize my background based on my answers]

---

## Project Type

[The type of project this estimation knowledge applies to]

---

## Estimation Process

[Step-by-step process for approaching estimation based on my answers]

---

## Factors That Increase QA Effort

[List with brief explanation for each factor]

---

## Factors That Reduce QA Effort

[List with brief explanation for each factor]

---

## Rules of Thumb and Ratios

[Any formulas, percentages, or ratios shared — clearly marked as approximations based on experience]

---

## Common Estimation Mistakes

[What juniors or PMs typically get wrong]

---

## Real Example — When the Estimate Was Off

[The specific example and lesson learned]

---

## Estimation Checklist

[A practical checklist derived from all answers — things to consider before finalizing an estimate]

---

## QAI Consultant Should...

[How the agent should approach effort estimation based on this knowledge]

---

Start with question 1 now.
```

---

## How to Use This Prompt

1. Copy the text inside the code block above
2. Paste it into any AI tool of your choice
3. Answer each question as specifically as possible — numbers and real examples are gold
4. At the end, copy the generated markdown file
5. Save it in `knowledge_base/expert_knowledge/` with this naming convention:

```
Estimation_[ProjectType].md
```

**Examples:**
- `Estimation_WebApplication.md`
- `Estimation_MobileApp.md`
- `Estimation_APIProject.md`
- `Estimation_LegacyMigration.md`
- `Estimation_FinancialSystems.md`

6. Commit and push — done! 🚀

---

## Tips for a Good Session

- Numbers are the most valuable thing here — specific percentages, ratios, and hour ranges
- Real examples where estimates were wrong are more valuable than examples where they were right
- If your estimation approach differs by project phase (discovery vs sprint vs release), mention that
- Don't worry if your rules of thumb sound "unscientific" — real estimation is always part art, part science
- The more context you give about WHY a factor increases or decreases effort, the more useful it is for QAI Consultant
