# Prompt — Lessons Learned Knowledge Extraction

Copy and paste this prompt into any AI tool (ChatGPT, Claude, Gemini, Grok, DeepSeek, etc.) to extract lessons learned from your QA experience. The output will be a markdown file ready to commit directly to the QAI Consultant knowledge base.

---

## The Prompt

```
You are helping me document QA expert knowledge for an open-source project called QAI Consultant.
Your job is to interview me about a lesson I learned from real QA experience and produce a structured markdown file at the end.

Start by asking me these questions ONE AT A TIME. Wait for my answer before moving to the next question.

1. Describe a situation where something went wrong in a project from a quality perspective. What happened?

2. What was the root cause? Was it a process issue, a communication issue, a technical issue, or something else?

3. What was the impact? (e.g., production bug, delayed release, client complaint, data loss)

4. What did the team do wrong — and what should they have done instead?

5. Is this something you've seen happen more than once, or was it unique to this project?

6. What is the single most important takeaway from this experience that a QA professional should know?

7. What should an AI agent do differently when helping a team plan testing, knowing this lesson?

Once I have answered all questions, produce a markdown file using EXACTLY this format:

---
# Lessons Learned — [title based on my answers]

**Contributor:** [ask me for my name or GitHub handle]
**Date:** [current month and year]
**Experience context:** [summarize my background based on my answers]

---

## What Happened

[Summary of the situation based on my answers]

---

## Root Cause

[Root cause based on my answers]

---

## Impact

[Impact based on my answers]

---

## What Should Have Been Done Instead

[Corrective action based on my answers]

---

## Is This Common?

[Based on my answer about recurrence]

---

## The Key Lesson

[The single most important takeaway]

---

## QAI Consultant Should...

[What the agent should do differently based on this lesson]

---

Start with question 1 now.
```

---

## How to Use This Prompt

1. Copy the text inside the code block above
2. Paste it into any AI tool of your choice
3. Answer each question naturally — no need to be formal
4. At the end, copy the generated markdown file
5. Save it in `knowledge_base/expert_knowledge/` with this naming convention:

```
Lessons_Learned_[ShortTopic].md
```

**Examples:**
- `Lessons_Learned_Late_Testing.md`
- `Lessons_Learned_Missing_Requirements.md`
- `Lessons_Learned_Integration_Failures.md`

6. Commit and push — done! 🚀

---

## Tips for a Good Session

- Be specific — vague answers produce generic knowledge
- Use real examples, even if anonymized
- Don't worry about grammar or formatting — the AI handles that
- If the AI asks a follow-up question outside the script, go with it — it means your answer opened something interesting
