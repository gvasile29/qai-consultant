# LinkedIn Poll Series — QAI Consultant Knowledge Collection

A series of 10 weekly LinkedIn polls designed to collect real QA expert knowledge from the community.
Each poll is paired with a caption that explains the context and encourages comments.

**Posting cadence:** 1 poll per week
**Goal:** Collect real-world QA insights to feed into QAI Consultant's expert knowledge base

---

## WEEK 1 — Testing Practices

**Caption:**
> Testing is more than executing test cases. But in reality, how do most teams approach it?
>
> I'm building an open-source AI QA Consultant and I want to understand real-world testing habits.
> Vote below and share your experience in the comments 👇
>
> #QA #SoftwareTesting #QualityAssurance #TestStrategy

**Poll:**
> 🗳️ When does testing actually start in your projects?
> - ☐ Before development (shift-left)
> - ☐ During development, in parallel
> - ☐ After development is done
> - ☐ Depends on the project

**Knowledge captured:** Shift-left adoption in real teams

---

## WEEK 2 — Testing Practices

**Caption:**
> Every QA professional has a "that one bug" story — the one that should have been caught earlier.
>
> Where do most critical bugs actually come from in your experience?
>
> Vote and drop a comment with your worst example 👇
>
> #QA #Bugs #SoftwareTesting #QualityAssurance

**Poll:**
> 🗳️ Where do most critical production bugs originate?
> - ☐ Missing or unclear requirements
> - ☐ Integration between systems
> - ☐ Edge cases never tested
> - ☐ Last-minute code changes

**Knowledge captured:** Root causes of production defects

---

## WEEK 3 — Testing Practices

**Caption:**
> Exploratory testing is one of the most powerful — and most misunderstood — testing techniques.
>
> How much of your testing time is truly exploratory vs scripted?
>
> #QA #ExploratoryTesting #SoftwareTesting #QualityAssurance

**Poll:**
> 🗳️ What percentage of your testing is exploratory (unscripted)?
> - ☐ Less than 10%
> - ☐ 10–30%
> - ☐ 30–60%
> - ☐ More than 60%

**Knowledge captured:** Exploratory vs scripted testing balance in real teams

---

## WEEK 4 — Tools & Automation

**Caption:**
> Test automation is supposed to save time. But building and maintaining it is a real investment.
>
> What's the biggest challenge your team faces with test automation?
>
> I'm collecting real insights for an open-source QA AI project. Your vote helps! 👇
>
> #TestAutomation #QA #SoftwareTesting #Automation

**Poll:**
> 🗳️ What's your biggest test automation challenge?
> - ☐ Flaky tests
> - ☐ High maintenance cost
> - ☐ Hard to get started
> - ☐ Low team adoption

**Knowledge captured:** Real automation pain points

---

## WEEK 5 — Tools & Automation

**Caption:**
> The test automation pyramid says: many unit tests, some integration tests, few E2E tests.
>
> But what does your pyramid actually look like in practice?
>
> #TestAutomation #QA #TestPyramid #SoftwareTesting

**Poll:**
> 🗳️ Where does most of your automated testing live?
> - ☐ Unit tests
> - ☐ Integration / API tests
> - ☐ E2E / UI tests
> - ☐ We don't have automation

**Knowledge captured:** Real-world test pyramid distribution

---

## WEEK 6 — Tools & Automation

**Caption:**
> AI is changing software development fast. But is it changing how we test?
>
> Are you already using AI tools in your QA work?
>
> #AI #QA #TestAutomation #ArtificialIntelligence #SoftwareTesting

**Poll:**
> 🗳️ How are you using AI in your QA process?
> - ☐ Generating test cases
> - ☐ Writing automation scripts
> - ☐ Analyzing test results
> - ☐ Not using AI yet

**Knowledge captured:** AI adoption in QA teams

---

## WEEK 7 — Estimation & Planning

**Caption:**
> QA effort estimation is one of the hardest things to get right.
>
> What's the most common reason QA estimates turn out to be wrong?
>
> Vote and share your experience below 👇
>
> #QA #Estimation #ProjectManagement #SoftwareTesting

**Poll:**
> 🗳️ Why do QA estimates usually go wrong?
> - ☐ Scope changes during the project
> - ☐ Environment and setup issues
> - ☐ Requirements were unclear upfront
> - ☐ Underestimating edge cases

**Knowledge captured:** Root causes of estimation failures

---

## WEEK 8 — Estimation & Planning

**Caption:**
> There's a common rule of thumb that QA effort should be roughly 25–30% of total project effort.
>
> Does that match your real experience?
>
> #QA #Estimation #SoftwareTesting #ProjectPlanning

**Poll:**
> 🗳️ In your projects, QA effort is typically...
> - ☐ Less than 15% of total effort
> - ☐ 15–25% of total effort
> - ☐ 25–40% of total effort
> - ☐ More than 40% of total effort

**Knowledge captured:** Real QA effort ratios by project

---

## WEEK 9 — Estimation & Planning

**Caption:**
> Testing always competes with deadlines. At some point, every QA professional faces the pressure to cut scope.
>
> What's the first thing you cut when time runs out?
>
> #QA #Testing #DeadlinePressure #SoftwareTesting #RiskBasedTesting

**Poll:**
> 🗳️ When deadline pressure hits, what gets cut first?
> - ☐ Regression testing
> - ☐ Non-functional testing (performance, security)
> - ☐ Edge cases and negative scenarios
> - ☐ We never cut — we push back on deadlines

**Knowledge captured:** Risk trade-offs under deadline pressure

---

## WEEK 10 — Testing Practices

**Caption:**
> A Test Strategy is supposed to guide the entire testing effort. But does it actually get written — and used?
>
> What's the reality in your teams?
>
> #QA #TestStrategy #SoftwareTesting #QualityAssurance

**Poll:**
> 🗳️ Does your team have a documented Test Strategy?
> - ☐ Yes, always — and we follow it
> - ☐ Yes, but nobody reads it
> - ☐ We have something informal
> - ☐ No, we just start testing

**Knowledge captured:** Test strategy adoption in real teams — directly relevant to QAI Consultant's core value proposition

---

## How to Use Poll Results

After each poll closes (LinkedIn polls run for up to 2 weeks):

1. Screenshot the results
2. Copy the most insightful comments
3. Use this prompt in any AI tool to convert results into knowledge:

```
I ran a LinkedIn poll for an open-source QA AI project called QAI Consultant.
Here are the results and comments:

Poll question: [paste question]
Results: [paste % for each option]
Notable comments: [paste best comments]

Please convert this into a structured markdown knowledge file with:
- A summary of what the community answered
- Key insights for a QA AI agent to learn from
- What QAI Consultant should do differently based on these results

Format it as a markdown file ready to save in a knowledge base.
```

4. Save the output as `Poll_Results_[Topic].md` in `knowledge_base/expert_knowledge/`
