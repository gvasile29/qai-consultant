# Prompt — Real Scenario Knowledge Extraction

Copy and paste this prompt into any AI tool (ChatGPT, Claude, Gemini, Grok, DeepSeek, etc.) to document how you handle real QA scenarios. The output will be a markdown file ready to commit directly to the QAI Consultant knowledge base.

---

## The Prompt

```
You are helping me document QA expert knowledge for an open-source project called QAI Consultant.
Your job is to interview me about a real scenario I have faced as a QA professional and produce a structured markdown file at the end.

A "scenario" is a challenging situation a QA engineer or manager faces — for example:
- Being asked to skip testing to meet a deadline
- Joining a project with no documentation
- Dealing with a team that doesn't care about quality
- Discovering a critical bug one day before release
- Managing QA with no budget for tools

Start by asking me these questions ONE AT A TIME. Wait for my answer before moving to the next question.

1. Describe a challenging situation you have faced as a QA professional. Set the scene — what was the project, who was involved, and what was the problem?

2. What was your first reaction or instinct when you faced this situation?

3. What did you actually do? Walk me through your approach step by step.

4. What worked well in how you handled it?

5. What would you do differently if you faced this situation again?

6. What is the key insight someone should take away from this scenario?

7. How should an AI QA consultant respond when it detects this situation in a project?

Once I have answered all questions, produce a markdown file using EXACTLY this format:

---
# Real Scenario — [title based on my answers]

**Contributor:** [ask me for my name or GitHub handle]
**Date:** [current month and year]
**Experience context:** [summarize my background based on my answers]

---

## The Scenario

[Description of the situation based on my answers]

---

## First Instinct

[Initial reaction — useful to show the human side of QA decision making]

---

## What I Did — Step by Step

[The actual approach taken]

---

## What Worked

[What was effective]

---

## What I Would Do Differently

[Retrospective improvement]

---

## The Key Insight

[Main takeaway for any QA professional facing this situation]

---

## How to Recognize This Scenario

[Signs and signals that this situation is developing, so it can be caught early]

---

## QAI Consultant Should...

[How the agent should respond when it detects this scenario in a project context]

---

Start with question 1 now.
```

---

## How to Use This Prompt

1. Copy the text inside the code block above
2. Paste it into any AI tool of your choice
3. Answer each question naturally — tell it like a story
4. At the end, copy the generated markdown file
5. Save it in `knowledge_base/expert_knowledge/` with this naming convention:

```
Scenario_[ShortTopic].md
```

**Examples:**
- `Scenario_Deadline_Pressure.md`
- `Scenario_No_Documentation.md`
- `Scenario_Critical_Bug_Before_Release.md`
- `Scenario_Team_Ignores_Quality.md`

6. Commit and push — done! 🚀

---

## Tips for a Good Session

- Tell it like a story — the more specific and human, the more valuable
- Don't sanitize the experience — mistakes and bad decisions are the most valuable lessons
- Anonymize client or company names if needed, but keep the details real
- One scenario per file — if you have multiple, run the prompt multiple times
- If you remember more details during the conversation, add them — don't hold back
