---
title: A Survey of Bugs in AI-Generated Code
source: https://arxiv.org/html/2512.05239v1
category: AI SDLC Adoption
tags: AI, SDLC, software development, testing, quality assurance
---

# A Survey of Bugs in AI-Generated Code

## Abstract

This systematic literature review analyzes 72 studies examining bugs in AI-generated code. The research establishes a comprehensive taxonomy of bug types and investigates how different models generate defects. The authors find that AI code generation models, trained on publicly available repositories containing buggy code, propagate quality issues. The survey synthesizes findings about bug patterns, model-specific tendencies, and remediation strategies to support future improvements in code generation reliability.

## 1. Introduction

AI-powered code generation tools have transformed software development through Large Language Models (LLMs) that learn from existing code examples. Recent developer surveys indicate widespread adoption of these tools for automating coding tasks, code completion, translation, debugging, and program repair.

However, significant challenges persist. The accuracy and correctness of AI-generated code remain concerning — such code often contains bugs and security vulnerabilities. These issues arise because models train on public repositories known to contain buggy code and security flaws. Bugs can cause runtime crashes, unexpected behavior, increased debugging workload, reduced productivity, delayed timelines, and higher costs.

Generated code frequently lacks readability and consistency, employing non-standard naming conventions and failing to conform to team coding standards, thereby damaging maintainability. Despite fragmented research addressing isolated aspects — specific model types, bug categories, or domain-specific cases — "a holistic and consolidated understanding of the types, patterns, and root causes of bugs" remains elusive.

**Main contributions:**
- In-depth review of 72 studies on AI-generated code bugs
- Comprehensive taxonomy of bug types
- Analysis of model tendencies generating buggy code
- Examination of bug-mitigation approaches

## 2. Background

### 2.1 Using AI for Coding Tasks

Multiple AI model families support code generation:

**Proprietary models:** GPT-3 introduced basic code generation; GPT-3.5 improved natural language understanding; GPT-4 handles complex scenarios. Codex utilizes GitHub projects for code generation, completion, and refactoring. Claude family emphasizes safety and reducing hallucinations. Gemini series evolved with extended context windows and reasoning capabilities. OpenAI o-series (o1, o3, o4-mini) focus on reasoning and complex problem-solving.

**Open-source models:** Code Llama optimizes for code-related tasks with local deployment options. DeepSeek-Coder surpasses some closed-source leaders on benchmarks.

**Development tools:** GitHub Copilot integrates with popular IDEs. Cursor provides AI-driven code editing with project understanding. Tabnine offers local deployment options. Codeium provides free completion and generation. Amazon CodeWhisperer suits AWS ecosystem developers.

### 2.2 Challenges of AI-Assisted Code Generation

Despite rapid adoption, AI tools offer no guarantees regarding code correctness or reliability. Empirical studies demonstrate that generated code contains functional bugs and security vulnerabilities stemming from flawed training data or inherent model limitations like hallucinations, insufficient semantic reasoning, and incomplete understanding of program intent.

**Quality issues include:**

- **Logical bugs:** Produce incorrect results despite running, usually from algorithm or data processing errors
- **Code duplication:** Writing identical logic multiple times increases modification complexity and bug risk
- **Inconsistent coding styles:** Reduce readability and increase maintenance difficulty
- **Performance issues:** Result from insufficient optimization, causing slowness or excessive resource consumption

Security concerns are particularly critical for sensitive data or services. Research shows approximately 40% of GitHub Copilot-generated code contains vulnerabilities. Even with security improvements, models frequently produce insecure code.

Additional challenges include:
- Generated code may not meet developer needs, requiring adjustment
- Developers spend time debugging logical and implementation bugs, reducing efficiency
- Lack of clear comments means developers may use code without full understanding
- Over-reliance on AI may degrade developer skills
- Traceability issues arise when auto-generated code is not clearly marked

## 3. Study Design

This systematic literature review follows Kitchenham and Charters guidelines plus Wohlin's snowballing strategy. The review addresses three research questions:

**RQ1:** What bug types and patterns exist in AI-generated code?

**RQ2:** Which models more frequently produce bugs and why?

**RQ3:** What mitigation and fixing methods address these bugs?

### 3.2 Search Strategy

Searches conducted across Google Scholar and Scopus using keywords combining:
- AI tools: LLM, AI, Artificial Intelligence, ChatGPT, Copilot
- Generation tasks: code generation, generated code
- Issue focus: bug, defects, fault, flaw

Initial search yielded 526 studies from Google Scholar and 200 from Scopus. After removing 33 duplicates, 660 studies remained (493 from Google Scholar, 167 from Scopus).

### 3.3 Selection Criteria

**Inclusion criteria:**
- Studies discussing bugs in AI-generated code
- Published in peer-reviewed journals, conferences, or workshops
- Published in English

**Exclusion criteria:**
- Studies using AI/LLMs for bug localization, reduction, or program repair (non-AI-generated code focus)
- Electronically inaccessible or unavailable full text
- Studies primarily focused on security issues in AI-generated code

### 3.4 Filtration Process

Two authors manually filtered studies in stages:

1. **Title filtration:** 382 studies selected based on relevant keywords
2. **Abstract filtration:** 178 studies retained for full-text review
3. **Full-text review:** 72 studies identified as relevant

Cross-validation used Cohen's Kappa; disagreements were discussed and resolved. After venue quality assessment using SJR and CORE rankings, 14 studies were excluded, leaving 80 studies. Qualitative assessment classified studies as "Focus" (40), "Discuss" (32), or "Mention" (8). Final removal of "Mention" studies yielded 72 studies.

### 3.5 Snowballing

Backward and forward snowballing identified 22 additional studies, bringing the total to 94 studies for analysis.

### 3.6 Data Extraction and Analysis

Two co-authors independently extracted data from 47 studies each using a predefined form capturing:
- Basic information
- Research objectives
- Methodology
- Bug types and patterns (RQ1)
- Models involved (RQ2)
- Bug mitigation/fixing methods (RQ3)
- Additional findings

Cross-validation of 10 randomly selected studies identified 5 discrepancies, resolved through discussion. Final dataset comprised 72 studies published in quality venues.

## 4. Results

### 4.1 Overview

#### 4.1.1 Venue Distribution

Selected studies appeared primarily in reputable venues:
- Top software engineering conferences: ICSE, ASE, MSR, SCAM
- Top AI/NLP conferences: NeurIPS, ACL
- Renowned journals: TOSEM, IEEE TSE, IEEE Access

#### 4.1.2 Programming Languages

Python dominates with 61% of studies, followed by Java (41%), C++ (12%), and JavaScript (11%). Python's prevalence reflects AI community preferences, its use in machine learning/data science, and established code generation benchmarks.

#### 4.1.3 Datasets

44% of studies used existing public datasets:
- HumanEval
- APPS
- DevGPT
- MBPP

Other approaches: 10% used programming competition platforms, 12.5% used community platforms, 10% used educational assignments, 12.5% developed custom datasets, 11% did not specify datasets.

**Dataset quality concerns:** HumanEval exhibits incorrect test cases, insufficient coverage, erroneous reference solutions, and imprecise definitions. MBPP shows poor syntax and uncaught bugs. Both rely heavily on Pass@k metrics while overlooking code quality and semantic nuances.

#### 4.1.4 Bug Detection Methods

Three main approaches:
- **Static analysis** (32%): PMD, Pylint, Bandit employed most frequently
- **Manual inspection** (22%)
- **Dynamic analysis** (20%)
- Unspecified methods (24%)

### 4.2 Categorization of Bugs in AI-Generated Code (RQ1)

#### 4.2.1 Taxonomy of Bugs

Eight major bug categories identified:

**I. Functional Bugs** (56 studies)

These violate functional requirements or design specifications, manifesting in six subcategories:

1. **Semantic bugs:** Syntactically correct code with incorrect meaning; does not express developer intent
2. **Logical bugs:** Algorithm or business logic errors producing incorrect output despite executing; misalignment between generated solutions and user intentions
3. **Function/Method-related bugs:** Issues with function names, parameters, bodies, or return values; includes simple statement bugs (SStuBs) like SWAP_ARGUMENTS, DIFFERENT_METHOD_SAME_ARGS, OVERLOAD_METHOD_MORE_ARGS; method call bugs prominent
4. **API/Package/Library-related bugs:** Incorrect usage of external software interfaces; includes conceptual, factual, coding, and terminological bugs
5. **Variable/Object/Parameter/Property bugs:** Issues with data storage and representation; includes KeyNotFoundException, InvalidAssignment
6. **Type errors:** Incompatible or incorrect data types; includes TypeError, type mismatches, numeric type bugs
7. **Other functional bugs:** Requirements-based issues lacking specific detail categorization

**II. Reliability Bugs** (21 studies)

Violate software reliability — the probability of operating without failures. Two subcategories:

1. **Performance bugs:** Code meeting functional requirements but failing performance standards; unnecessarily complex implementations, lack of optimization, slow response times, excessive resource consumption
2. **Stability bugs:** May crash, deadlock, or exhibit unpredictable behavior during operation; incomplete exception handling; affects continued availability

**III. Syntax Bugs** (32 studies)

Violate grammatical/writing rules of programming languages, preventing compilation/interpretation. Detected early in program development. Include spelling errors, incorrect operator usage, missing/extra punctuation. Four subtypes identified: syntax errors, reference errors, logic errors, multiple errors.

**IV. Code Style and Standards Issues**

Non-functional bugs affecting internal structure, readability, maintainability, scalability, and collaboration. Include naming convention violations, unnecessary imports, unused parameters, best practice violations (avoiding globals), readability issues (braces for if statements), error-prone patterns (trailing commas in array declarations).

**V. Hallucination**

Unique to AI-generated code. LLMs produce outputs appearing syntactically correct and stylistically appropriate but factually incorrect or inconsistent with real-world APIs, libraries, or intended semantics. Models "imagine" non-existent objects, functions, libraries, or behaviors causing code failures. A representative example involves Codex relying on non-existent methods when generating code.

**VI. System Bugs**

Problems at system level involving hardware, operating system, or network. Six subcategories:

1. **Memory bugs:** Incorrect memory access/management causing unexpected behavior, performance overhead, data corruption, crashes; includes out-of-bounds access, stack overflow from infinite recursion, strict aliasing violations, misaligned memory access
2. **I/O bugs:** Problems during input/output operations; EOFError common when reading at stream end
3. **Database bugs:** Issues during database interaction (connection, query, transaction); sqlite3.OperationalError examples
4. **Hardware bugs:** Physical component failures; robot programming examples include Physical Errors
5. **Configuration bugs:** System configuration errors, improper settings, conflicts; POM class file path errors
6. **Access/Permission bugs:** Access control violations; PermissionError examples

**VII. Test Bugs**

Bugs in test code rather than production code. Hinder testing effectiveness, cause false positives, flakiness. Include assertion-related bugs — dominant root cause of "silent horror bugs" where tests pass despite incorrect production code. Test smells include Magic Number Test smell lacking explanation for expected outputs.

**VIII. Others/Unspecified Bugs**

Cannot categorize within previous categories or lack detailed descriptions; too broad with multiple potential causes.

#### 4.2.2 Bug Distribution Across Studies

| Bug Category | Number of Studies |
|---|---|
| Functional Bugs | 56 |
| Syntax Bugs | 32 |
| Reliability Bugs | 21 |
| Code Style and Standards | (referenced across multiple studies) |
| Hallucination | (referenced across multiple studies) |
| System Bugs | (referenced across multiple studies) |
| Test Bugs | (referenced across multiple studies) |
| Unspecified | (referenced across multiple studies) |

### 4.3 Models' Tendency to Generate Buggy Code (RQ2)

#### Overview of Prominent LLM Families

The survey examined multiple model families' bug-generation patterns. Key models evaluated included the GPT family (GPT-3, GPT-3.5, GPT-4), Codex, Claude, Gemini, Code Llama, and DeepSeek-Coder. These represent both proprietary and open-source approaches to code generation.

#### Evolution of Bugs Across Models

Research revealed that "bug patterns evolve as models improve across successive versions." GPT-4 demonstrated reduced bug rates compared to earlier iterations, though not uniformly across all bug categories. The progression from GPT-3 through GPT-4 showed incremental quality improvements, but certain semantic and logical errors persisted.

#### Empirical Comparison of Different Code Generation Models

Different models exhibited varying susceptibilities to specific bug types:

- **Functional bugs** appeared most frequently across all models (56 studies documented these)
- **Syntax bugs** were identified in 32 studies
- **Reliability issues** were noted in 21 studies

Models specialized for code tasks (Code Llama, DeepSeek-Coder) generally outperformed general-purpose models on domain-specific benchmarks, though security vulnerabilities remained a concern across all models.

#### Root Causes of Bugs in Generated Code

The survey identified multiple root causes:

1. **Training data contamination:** Models trained on "publicly available code from GitHub, Stack Overflow, and other platforms" inherently absorb existing bugs present in those repositories
2. **Model limitations:** Issues include "hallucinations, lack of deep semantic reasoning, and incomplete understanding of program intent"
3. **Language-specific challenges:** Python dominated research (61% of studies), creating potential research bias and limiting insights into other languages
4. **Prompt engineering factors:** The quality of input prompts significantly influenced bug generation rates
5. **Architectural constraints:** Models struggled with "context window limitations, inability to perceive external resources, and gaps in semantic understanding"

### 4.4 Bug Mitigation Approaches (RQ3)

#### Prompt Engineering and Strategies

Studies documented several prompt-based mitigation techniques:

- **Chain-of-thought prompting:** Encouraging step-by-step reasoning improved correctness
- **Few-shot learning:** Providing examples enhanced model performance
- **Explicit instruction refinement:** Detailed specifications reduced misalignment bugs
- **Iterative prompting:** Requesting revisions and self-correction improved outcomes

Research indicated that "providing more information in the prompt often helped the LLM correct the bug," particularly for hallucination-related issues.

#### Code Enhancement Modules and Frameworks

Multiple frameworks were proposed to improve generated code quality:

- **Static analysis integration:** Tools like PMD, Pylint, and Bandit (used in 32% of studies) automatically detected quality issues
- **Automated repair systems:** Some approaches combined detection with automatic fix generation
- **Multi-stage pipelines:** Combining generation, analysis, and refinement improved reliability
- **Testing frameworks:** Integrated test generation and validation enhanced correctness verification

#### Autonomous Coding Agents

Emerging approaches leveraged autonomous agents that:

- Iteratively generate and test code
- Provide feedback loops for self-improvement
- Execute test suites and adjust implementations based on failures
- Maintain context across multiple generation cycles

These agents demonstrated improved bug detection and correction capabilities compared to single-pass generation.

#### Program Analysis-Based Techniques

Traditional software engineering tools proved valuable:

- **Dynamic analysis:** Testing generated code against comprehensive test suites (employed in 20% of studies)
- **Static analysis tools:** Detected style violations and potential runtime issues
- **Constraint-based repair:** Applied formal methods to guarantee correctness
- **Pattern-matching approaches:** Identified and fixed recurring bug patterns

#### Mitigation Approaches for Task-Specific Code Generation

Domain-specific strategies addressed particular challenges:

- **Smart contract generation:** Specialized validation for blockchain code correctness
- **API usage correction:** Targeted fixes for incorrect library/package usage
- **Type system enforcement:** Stronger typing reduced type-related errors
- **Exception handling augmentation:** Automatically added missing error handling

## 5. Discussion

### 5.1 Interpretation of Findings

The review revealed critical insights about AI-generated code quality:

1. **Bug prevalence remains significant:** Despite model improvements, "AI-generated code often contains bugs and security vulnerabilities" that create substantial quality concerns
2. **Python-centric bias limits generalizability:** With 61% of studies focusing on Python, findings may not transfer reliably to other languages like Java (41%), C++ (12%), or JavaScript (11%)
3. **Training data quality impacts output:** Since models learn from "publicly available code repositories known to contain buggy code," bug reproduction is nearly inevitable without additional safeguards
4. **Functional bugs dominate:** Logic and semantic errors represent the most prevalent and challenging bug category, requiring deeper semantic understanding than models currently demonstrate
5. **Manual review remains essential:** Studies showed developers spend "moderately difficult" effort fixing LLM-generated bugs, with "hard-to-diagnose patterns including misunderstandings, unconfirmed assumptions, and omitted edge cases"

### 5.2 Limitations

The survey acknowledged several constraints:

- **Dataset limitations:** "HumanEval suffers from inherent flaws including incorrect test cases, insufficient coverage, and imprecise problem definitions"; MBPP exhibits "poor syntax and uncaught bugs"
- **Metric inadequacies:** Reliance on "execution-based metrics like Pass@k overlooks code quality and semantic nuances"
- **Publication venue bias:** Emphasis on top-tier venues may underrepresent emerging problem areas
- **Language representation:** Overwhelming Python focus limits conclusions about other programming contexts
- **Temporal constraints:** Rapid model evolution may quickly outdate findings

### 5.3 Future Research Directions

Recommended directions include:

- Developing "more robust evaluation frameworks" accounting for code quality beyond functional correctness
- Creating "targeted mitigation strategies" for specific bug categories
- Designing "more reliable and robust models" addressing root causes
- Investigating "cross-cutting bug patterns" across model families
- Expanding studies beyond Python to validate generalizability
- Studying "long-term maintenance implications" of AI-generated code

## 8. Conclusions

This systematic literature review synthesized 72 studies on bugs in AI-generated code, establishing the first comprehensive understanding of the failure landscape in code generation. Key takeaways:

1. **Comprehensive taxonomy established:** Eight major bug categories (Functionality, Reliability, Syntax, Code Style, Hallucination, System, Test, and Unspecified) provide "a structured framework for future research and comparison"

2. **Model variations matter:** Different models exhibit "tendencies to generate buggy code" requiring "model-specific improvement strategies"

3. **Multiple mitigation pathways exist:** "Prompt engineering, code enhancement modules, autonomous agents, program analysis, and domain-specific techniques" collectively improve code quality

4. **Trust remains challenging:** The persistence of bugs "increases the debugging and repair workload for developers, reducing productivity, and potentially delaying project timelines and incurring additional costs"

5. **Reliability requires vigilance:** Developers cannot assume AI-generated code quality; "systematic quality assurance practices when integrating AI-generated code into software development workflows" remain essential

The review provides "actionable insights for both researchers and practitioners striving to improve the reliability of current and future code generation models," establishing a foundation for advancing AI code generation reliability across industry and academia.

---

**Key Statistics:**
- 72 empirical studies reviewed (plus 22 from snowballing = 94 total)
- 8 major bug categories identified (18 subcategories across the taxonomy)
- ~40% of GitHub Copilot-generated code contains vulnerabilities (referenced finding)
- 61% of studies focused on Python; 41% Java; 12% C++; 11% JavaScript
- 56 studies documented functional bugs (most prevalent category)
- 32% of studies used static analysis as primary detection method
- Models covered: GPT-3/3.5/4, Codex, Claude, Gemini, Code Llama, DeepSeek-Coder, GitHub Copilot, Cursor, Tabnine, Codeium, Amazon CodeWhisperer
