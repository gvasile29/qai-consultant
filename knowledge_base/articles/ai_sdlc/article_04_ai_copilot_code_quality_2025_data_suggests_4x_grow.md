---
title: AI Copilot Code Quality: 2025 Data Suggests 4x Growth in Code Clones — GitClear
source: https://www.gitclear.com/ai_assistant_code_quality_2025_research
category: AI SDLC Adoption
tags: AI, SDLC, software development, testing, quality assurance
---

# AI Copilot Code Quality: 2025 Data Suggests 4x Growth in Code Clones

**Subtitle:** Emerging trends: 4x more code cloning, 'copy/paste' exceeds 'moved' code for first time in history. Includes 2025 projections.

**Published:** January 2026 (analyzing 2020–2024 data)
**Source:** GitClear — https://www.gitclear.com/ai_assistant_code_quality_2025_research

---

## Overview

GitClear released research examining how AI assistants influence code quality across major technology companies. The study analyzes 211 million changed lines of code from repositories owned by Google, Microsoft, Meta, and enterprise corporations, spanning five years from January 2020 to December 2024.

The research investigates measurable differences in code quality metrics between AI-assisted and non-AI-assisted code blocks, focusing on what technical leaders should monitor as AI adoption scales in 2025 and beyond.

---

## Key Research Questions

- Which code quality metrics are threatened by the proliferation of AI coding tools?
- What should Technical Leaders monitor in 2025?
- How can teams measure AI's impact on their own code quality?

---

## Dataset and Methodology

The research employs analysis of the "largest known database of highly structured code change data," spanning January 2020 to December 2024. The dataset comprises **211 million changed lines of code** from major technology organizations including Google, Microsoft, and Meta, as well as enterprise C-Corps. Metrics are assessed using quantifiable code quality indicators tracked longitudinally across the five-year window.

---

## AI Adoption Context

According to the Stack Overflow 2024 Developer Survey:

- **63%** of professional developers currently use AI in their development process
- **14%** plan to begin using AI soon
- **36,894 developers** cited "Increased productivity" as the primary benefit they seek from AI coding tools

---

## Core Findings

### 1. Code Clone Growth: ~4x Increase

The prevalence of cloned (duplicate) code blocks rose approximately **4x** by 2025 compared to the pre-AI baseline. Cloned code was detected in approximately **10% of AI-assisted commits** analyzed.

Specific metric: lines classified as "copy/pasted" (cloned) rose from **8.3% to 12.3%** of changed lines between 2021 and 2024.

### 2. Refactoring in Steep Decline

The percentage of changed code lines associated with refactoring **sunk from 25% of changed lines in 2021 to less than 10% in 2024** — a reduction of more than 60% in relative terms. This is one of the most significant signals the research surfaces: AI-assisted development is reducing the proportion of code that actively improves the existing codebase structure.

### 3. Copy/Paste Exceeds Moved Code — A First

For the first time in the history of the dataset, **"copy/paste" code exceeded "moved" code** (i.e., genuine code reuse and reorganization). This inversion is significant because "moved" lines typically indicate intentional refactoring, while "copy/paste" lines indicate duplication without consolidation.

### 4. Productivity vs. Maintainability Trade-off

While AI assistants demonstrably increase raw line output — developers produce more lines of code faster with AI assistance — the research shows that code maintainability appears to be compromised. The shift toward duplication and away from refactoring suggests AI-generated code prioritizes immediate output over long-term system health.

The report states: "AI assistants do beget more lines," but warns that sustaining quality requires a "DRY (Don't Repeat Yourself), modular approach to building."

---

## Year-by-Year Trend Summary (2020–2024)

| Metric | 2021 Baseline | 2024 Value | Change |
|--------|--------------|------------|--------|
| Refactored lines (% of changed lines) | ~25% | <10% | −60%+ decline |
| Copy/pasted (cloned) lines (% of changed lines) | ~8.3% | ~12.3% | ~+48% absolute; ~4x relative to pre-AI baseline |
| Copy/paste vs. moved code relationship | Moved > Copy/paste | Copy/paste > Moved | First inversion in dataset history |

---

## Named Metrics and KPIs Tracked

- **Diff Delta™** — GitClear's correlation research metric for software effort measurement
- **DORA metrics** — referenced as relevant benchmarks for engineering performance
- **Changed lines percentage** — refactoring proportion tracker across time
- **Code clone prevalence** — duplicate code block measurement by commit
- **Code churn** — short-term modification tracking (edits reverted within two weeks)

---

## Conclusions and Recommendations

The research identifies a consistent pattern: as AI adoption increased dramatically from 2022 onward, developers produced substantially more duplicate and cloned code while refactoring activities decreased significantly. The correlation between AI tool adoption timelines and these metric shifts is strong across the dataset.

Key recommendations for technical leaders:

1. **Monitor clone rates actively.** Code duplication metrics should be part of any engineering health dashboard, not just test coverage and defect counts.
2. **Measure refactoring velocity separately.** Track what proportion of commits improve existing code structure versus add new code, as AI tools tend to deprioritize the former.
3. **Audit AI-generated code blocks for DRY violations.** Code reviews should specifically check whether AI-generated additions introduce or propagate duplicated logic.
4. **Balance velocity metrics with maintainability metrics.** Commit velocity alone, if used as the primary productivity indicator, will mask accumulating technical debt introduced by AI-generated duplication.
5. **Track "moved" vs. "copy/pasted" lines over time.** This ratio is an early indicator of codebase health and refactoring culture.

---

## Associated Research

A January 2026 companion piece is titled: **"AI Coding Tools Attract Top Performers — But Do They Create Them?"**, examining whether AI tools develop or atrophy developer skill over time.

---

## Relevance to QA and Test Strategy

This research has direct implications for QA architects and test strategists:

- **Increased clone rates inflate test surface area.** Duplicated code means duplicated logic paths that may each need separate test cases, expanding regression scope.
- **Reduced refactoring increases coupling.** Less-refactored codebases tend to have higher coupling, making unit testing harder and integration testing more fragile.
- **Technical debt accumulation accelerates defect rates.** Code that is not maintained through refactoring accumulates hidden defects over time; test strategies must account for this by weighting risk-based testing toward legacy and AI-generated modules.
- **DRY violations in production code often mirror DRY violations in test code.** Teams using AI to write tests alongside production code may inadvertently generate duplicated, brittle test suites.
- **Monitoring code quality metrics should be a QA responsibility.** QA architects should advocate for clone detection and refactoring trend metrics as part of the Definition of Done and sprint health reviews.
