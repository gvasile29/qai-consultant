---
title: 2024 Accelerate State of DevOps Report (DORA)
source: https://dora.dev/research/2024/dora-report/
category: AI SDLC Adoption
tags: AI, SDLC, software development, testing, quality assurance
---

# 2024 Accelerate State of DevOps Report (DORA)

**Published:** October 23, 2024
**Publisher:** Google Cloud / DORA Research Program
**Edition:** 10th Annual Accelerate State of DevOps Report
**Survey Scope:** Approximately 3,000 software professionals globally (developers, managers, senior executives)

---

## Overview

The DORA (DevOps Research and Assessment) research program has been investigating the capabilities, practices, and measures of high-performing technology-driven teams and organizations for more than a decade. The 2024 report marks the tenth anniversary of DORA's four key metrics — deployment frequency, lead time for changes, change failure rate, and time to restore — which have become the industry standard for measuring software delivery performance.

The central theme of the 2024 report is the tension between emerging tools (especially AI) and the human element of software development. The research emphasizes that **succeeding in today's tech landscape requires balancing emerging tools with a steadfast focus on the human element of software development**.

---

## AI Adoption: The Productivity Paradox

### Adoption Rates

AI has achieved widespread penetration in the software development profession:

- **75.9% of respondents** use AI for at least one daily professional responsibility
- **75%** of respondents report productivity gains from using AI
- **More than one-third** experienced "moderate" to "extreme" productivity increases due to AI

The top five AI-assisted task categories, in order of prevalence:
1. Writing code
2. Summarizing information
3. Code explanation
4. Code optimization
5. Documentation

AI tools appear most commonly in integrated development environments (IDEs) and internal web interfaces. However, approximately half of respondents indicated they do not use AI as an automated part of their toolchain — meaning AI is primarily a manual, on-demand tool rather than a pipeline-integrated one.

### The Counterintuitive Finding: AI Hurts Delivery Performance

Despite widespread productivity gains at the individual level, the 2024 DORA research reveals a critical system-level finding: **AI adoption negatively impacts software delivery performance**.

As AI adoption increased, DORA measured:

| Metric | Impact per 25% increase in AI adoption |
|---|---|
| Deployment throughput (delivery throughput) | **-1.5% decrease** |
| Delivery stability | **-7.2% decrease** |
| Valuable work time | **-2.6% decrease** |
| Documentation quality | **+7.5% increase** |
| Code quality | **+3.4% increase** |
| Code review speed | **+3.1% increase** |

The data reveals a paradox: AI accelerates individual work and improves code and documentation quality, yet the system-level outcome — how reliably and frequently software ships to production — degrades.

As the report states: "Our data suggest that improving the development process does not automatically improve software delivery — at least not without proper adherence to the basics of successful software delivery, like small batch sizes and robust testing mechanisms. AI has positive impacts on many important individual and organizational factors which foster the conditions for high software delivery performance. But, AI does not appear to be a panacea."

---

## Root Cause Analysis: Batch Size and Code Review Discipline

The explanation for why AI adoption degrades delivery performance is not related to AI generating poor-quality code. The root cause is **behavioral and process-level**:

### Increased Batch Sizes

AI tools make it dramatically easier and faster to write large amounts of code. This creates a perverse incentive: developers generate larger changesets per deployment cycle. DORA's research has long established that larger batch sizes introduce greater risk. When AI is used in the coding process, batch sizes tend to increase, and bigger changesets are riskier.

Laura Tacho (CTO, DX) summarizes the dynamic: "AI introduces risk, but not because of garbage code — it's because batch size seems to increase when AI is used in the coding process. And bigger changesets are riskier, something that DORA's research has long supported."

### Code Generation Is Not the Bottleneck

A key theoretical insight from the report: **code generation was never the primary bottleneck in software delivery**. Individual developers becoming more productive at writing code does not translate to system-wide improvements when the real constraint lies elsewhere — specifically in integrating, reviewing, testing, and deploying that code reliably.

AI tools free up time from coding tasks but do not proportionally reduce time spent on toilsome tasks like meetings, busywork, and administrative work. The time savings accrue in coding, but the pipeline constraints remain unchanged or worsen due to larger changesets needing more review cycles.

### Reduced Code Review Discipline

With AI generating code faster, code review practices face pressure. The volume of code submitted for review increases while the cognitive discipline required to review AI-generated code thoroughly is often underestimated. The combination of higher batch sizes and reduced code review rigor degrades stability.

---

## Trust Gap in AI-Generated Code

Despite high adoption rates, developer trust in AI-generated code is surprisingly low:

- **39.2% of respondents reported little to no trust** in AI-generated code
- Only **24%** expressed high trust in AI-generated code
- A substantial portion expressed neutral or negative sentiments about organizational transparency in AI implementation

This trust deficit indicates that AI integration must be managed more thoughtfully. Teams must carefully evaluate AI's role in their development workflow to mitigate the downsides. Trust in AI tools tends to grow with hands-on experience — organizations should provide dedicated time for experimentation.

---

## Performance Cluster Distribution: A Concerning Shift

The 2024 report tracks developer teams across performance clusters (elite, high, medium, low). Significant distribution shifts occurred year-over-year:

| Cluster | 2023 | 2024 | Change |
|---|---|---|---|
| Elite | Stable | Stable | No significant change |
| High performance | 31% | 22% | **-9 percentage points** |
| Medium | — | — | Absorbed some high-performers |
| Low | 17% | 25% | **+8 percentage points** |

The shrinking of the high-performance cluster and growth of the low-performance cluster is a warning signal. Overall software delivery performance declined slightly from the prior year.

**A notable anomaly:** The medium performance cluster demonstrated a *lower* change failure rate than the high performance cluster — the first time this pattern has appeared. DORA prioritized more frequent deployments with higher failure rates for high performers, suggesting a trade-off between throughput and stability at the top of the performance spectrum.

---

## Platform Engineering

Platform engineering — building and operating internal developer platforms (IDPs) — was a major focus of the 2024 report. Key findings:

1. **Increased developer productivity:** Internal development platforms effectively increase productivity for individual developers.
2. **Prevalence in larger firms:** Platforms are more commonly found in larger organizations, suggesting their suitability for managing complex development environments at scale.
3. **Potential performance dip on implementation:** Implementing a platform engineering initiative may lead to a temporary decrease in performance before improvements manifest as the platform matures.
4. **User-centeredness is critical:** For optimal results, platform engineering efforts should prioritize user-centered design, developer independence, and a product-oriented approach.

The risk is that poorly implemented platforms obstruct rather than enhance developer experience. Platform engineering may reduce overall throughput even while boosting individual performance metrics.

---

## Developer Experience and Organizational Culture

### User-Centric Development Drives Better Outcomes

Organizations and developers that prioritize end-user experience demonstrate measurably better results:

- Higher productivity
- Greater job satisfaction
- Lower burnout rates
- Higher-quality products

### Priority Instability Is a Critical Threat

One of the sharpest findings in the 2024 report concerns organizational priority instability:

> "Unstable organizational priorities cause meaningful decreases in productivity and increase burnout substantially, resisting typical mitigation efforts."

The "move fast and constantly pivot" mentality negatively impacts developer well-being and overall performance. Even with strong leadership, comprehensive documentation, and a user-centered approach — all known to be beneficial — priority instability can significantly hinder progress. The effects are resistant to mitigation regardless of leadership quality.

### Transformational Leadership

Leaders who demonstrate a clear vision and actively support their teams significantly enhance:

- Developer productivity
- Job satisfaction
- Organizational performance
- Reduced burnout

The report emphasizes that creating a work environment where teams feel supported, valued, and empowered is fundamental to achieving high performance.

---

## Recommendations for Practitioners

Based on the 2024 findings, DORA issues three core recommendations for AI integration:

1. **Empower employees and reduce toil.** Orient AI adoption strategies toward empowering employees and alleviating the burden of undesirable tasks — not toward generating larger amounts of code faster.

2. **Establish clear guidelines and address procedural concerns.** Create explicit organizational guidelines for AI use; foster open communication about AI's impact on teams and workflows. Address the transparency deficit that is creating distrust.

3. **Encourage continuous exploration.** Provide dedicated time for experimentation with AI tools. Promote trust through hands-on experience, as developer confidence in AI grows with direct use.

### Additional Practitioner Insights

- **Preserve small batch sizes.** Regardless of AI-assisted velocity gains, maintain disciplined batch size limits in your CI/CD pipeline. The evidence is clear: larger changesets increase risk.
- **Invest in robust testing.** AI adoption without strengthening automated test coverage is a delivery stability liability.
- **Do not automate code review away.** The code review step is a quality gate. AI-assisted code review speed gains (+3.1%) are positive, but reducing review rigor to match AI coding speed is counterproductive.
- **Use AI for documentation first.** The strongest positive ROI from AI is in documentation quality (+7.5%), a traditionally under-resourced area with low risk from AI-generated content.

---

## Methodology

- **Survey respondents:** Approximately 3,000 software professionals
- **Roles covered:** Software developers, engineering managers, senior executives, and other technical roles
- **Scope:** Global; cross-industry
- **Methodology addition in 2024:** Qualitative interviews incorporated alongside quantitative survey data to provide richer context for findings
- **Performance measurement:** DORA's four key metrics (deployment frequency, lead time for changes, change failure rate, time to restore service)
- **Analysis approach:** Structural equation modeling; cluster analysis of performance groups; regression analysis of AI adoption against delivery outcomes
- **Report availability:** Published in 9 languages (English, Spanish, French, Portuguese, Simplified Chinese, Traditional Chinese, Japanese, Korean)

---

## Key Takeaways for QA and Test Architects

The 2024 DORA report carries specific implications for QA strategy in AI-assisted development environments:

1. **AI is accelerating code production without proportionally accelerating test coverage.** The gap between code generation speed and test authoring speed is widening batch sizes and degrading stability.

2. **Automated regression testing becomes more critical, not less.** As AI generates larger changesets faster, the safety net of a comprehensive automated test suite is essential to maintaining delivery stability.

3. **Code review is a quality gate that must be protected.** The 39.2% distrust figure for AI-generated code aligns with QA practitioners' concerns about AI-generated test scripts — both require disciplined human review.

4. **Platform engineering investments should include testing infrastructure.** The "platform as a product" approach should encompass test environments, test data management, and CI pipeline quality gates.

5. **Delivery stability metrics (change failure rate, MTTR) are the leading indicators to watch.** The 7.2% decline in delivery stability is the most actionable signal: it shows where AI adoption is creating quality risk in production.

---

## References

- Primary source: [DORA 2024 Accelerate State of DevOps Report](https://dora.dev/research/2024/dora-report/)
- Google Cloud blog announcement: [Announcing the 2024 DORA Report](https://cloud.google.com/blog/products/devops-sre/announcing-the-2024-dora-report)
- Analysis by Laura Tacho (DX): [Highlights from the 2024 DORA State of DevOps Report](https://getdx.com/blog/2024-dora-report/)
- RedMonk analysis: [DORA Report 2024 – A Look at Throughput and Stability](https://redmonk.com/rstephens/2024/11/26/dora2024/)
- InfoQ coverage: [2024 Accelerate State of DevOps Report Shows Pros and Cons of AI](https://www.infoq.com/news/2024/11/2024-dora-report/)
