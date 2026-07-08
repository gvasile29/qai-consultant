# CMMI — Capability Maturity Model Integration

Source: Compiled from public knowledge — CMMI Institute / ISACA, CMMI for Development (CMMI-DEV) v1.3 and CMMI v2.0 Product Suite, publicly available at cmmiinstitute.com
License: CMMI Institute — publicly available model summary

---

## Overview

CMMI (Capability Maturity Model Integration) is a process-improvement framework, originally developed at the Software Engineering Institute (SEI, Carnegie Mellon University) and now stewarded by ISACA/CMMI Institute, that describes the practices an organization needs to reliably build and deliver products. Unlike A-SPICE, which assesses process **capability per discipline** for automotive suppliers, CMMI assesses either overall **organizational maturity** (staged representation) or per-process-area **capability** (continuous representation), and is used broadly across software, systems, services, and acquisition domains — not automotive-specific. For QA, CMMI matters because it formalizes *how* an organization plans, performs, and independently audits its verification and validation work, which is exactly the process backbone a Test Strategy has to fit inside.

---

> **Version note:** CMMI V3.0 (released April 2023) is now the only version accepted for official SCAMPI appraisals as of January 1, 2024. V3.0 restructured the practice areas referenced below: PPQA was renamed **PQA (Process Quality Assurance)** under a new "Ensuring Quality" capability area, **VER and VAL were merged** into a single Verification and Validation practice area, and **REQM and RD were merged** into **RDM (Requirements Development and Management)**. The five Maturity Level names and the staged/continuous distinction described in this document are unchanged in V3.0 — only the underlying process-area/practice-area names and groupings differ. The v1.3/v2.0 terminology (REQM, PPQA, VER, VAL) below remains widely used in practice and industry literature, but a client citing a fresh SCAMPI appraisal will be assessed against the V3.0 practice-area names.

---

## Staged vs. Continuous Representation

CMMI can be applied in two representations, which answer different questions:

| Representation | Question it answers | Unit of appraisal | Typical use |
|---|---|---|---|
| **Staged** | "How mature is the whole organization?" | A single Maturity Level (ML1–ML5) covering a required set of process areas | Executive benchmarking, contractual maturity requirements (e.g. "supplier must be CMMI ML3") |
| **Continuous** | "How capable is this specific process area?" | A Capability Level (CL0–CL3, CMMI v2.0) per individual process area | Targeted improvement, comparing specific practices (e.g. "our VER capability vs our REQM capability") |

**Practical implication for QA:** a staged ML3 rating tells a client "this vendor's whole SDLC is process-disciplined." A continuous CL2 rating on VER alone tells them "this vendor's testing practice specifically is managed," even if other areas are weaker. Contracts and RFPs almost always cite the staged Maturity Level.

---

## The Five Maturity Levels (Staged Representation)

| Level | Name | Characteristic | QA Signal |
|---|---|---|---|
| 1 | **Initial** | Processes are ad hoc, chaotic; success depends on individual heroics | No repeatable test process; testing is reactive, undocumented |
| 2 | **Managed** | Projects plan, perform, measure, and control their own work; basic project discipline exists | Test plans exist per-project but are not standardized org-wide; requirements are tracked |
| 3 | **Defined** | Processes are documented as an organizational standard, tailored per project | A common test strategy template, defined entry/exit criteria, org-wide QA standards |
| 4 | **Quantitatively Managed** | Processes are controlled using statistical and quantitative techniques; performance is predictable | Defect density, test coverage, and escape rates are tracked against statistical control limits |
| 5 | **Optimizing** | Continuous process improvement based on quantitative understanding of common causes of variation | Root-cause defect analysis feeds back into process change; predictive quality models |

**Key rule:** each level is a prerequisite for the next — an organization cannot claim ML4 without having satisfied all ML2 and ML3 process areas first. There is no "skipping" levels in the staged representation.

---

## Process Areas Most Relevant to QA

CMMI-DEV defines over 20 process areas; four are directly load-bearing for test strategy and quality assurance work:

### REQM — Requirements Management *(Maturity Level 2)*

**Purpose:** Manage requirements of the project's products and product components, and identify inconsistencies between those requirements and the project's plans and work products.

**Why it matters for QA:**
- Establishes the traceability baseline that test cases are derived from and measured against
- Requires bidirectional traceability: requirement → design → code → test case → result
- Any requirement change must trigger an impact analysis on affected test artifacts

**Typical QA artifacts:** Requirements Traceability Matrix (RTM), change-impact log, requirements baseline.

---

### PPQA — Process and Product Quality Assurance *(Maturity Level 2)*

**Purpose:** Provide staff and management with objective insight into processes and associated work products — i.e., an independent audit function that checks whether the team is actually following its own defined process.

**Why it matters for QA:**
- PPQA is explicitly an **independent** function — the person auditing compliance should not be the person doing the work being audited
- It audits *both* process adherence (was the test plan followed?) and product quality (does the work product meet its defined standard?)
- Non-compliance issues are logged, tracked, and escalated if unresolved — this is the audit trail an external assessor will request

**Typical QA artifacts:** Process/product audit checklists, non-compliance reports, escalation log.

---

### VER — Verification *(Maturity Level 3)*

**Purpose:** Ensure that selected work products meet their specified requirements — "are we building the product right?"

**Why it matters for QA:**
- Covers peer reviews, static analysis, unit and integration testing — verification against **specification**, not against user need
- Requires defined verification methods per work-product type and documented verification criteria
- Peer review data (defects found per review hour) is a standard VER metric feeding quantitative process control at ML4

**Typical QA artifacts:** Peer review records, unit/integration test specifications and results, static analysis reports.

---

### VAL — Validation *(Maturity Level 3)*

**Purpose:** Demonstrate that a product or product component fulfills its intended use when placed in its intended environment — "are we building the right product?"

**Why it matters for QA:**
- Distinct from VER: validation is checked against **user needs / operational context**, typically via system-level and acceptance testing, UAT, or beta programs
- Requires the environment used for validation to be representative of the real operating environment
- Validation results directly inform release-readiness decisions

**Typical QA artifacts:** System/acceptance test plans, UAT sign-off records, validation environment description.

---

## CMMI Appraisal Process (SCAMPI)

CMMI maturity/capability claims are confirmed through **SCAMPI** (Standard CMMI Appraisal Method for Process Improvement) appraisals, run by a certified Lead Appraiser:

1. **SCAMPI A** — the only appraisal type that can result in an official, benchmark-quality Maturity Level or Capability Level rating; requires objective evidence review, interviews, and document inspection across a representative project sample
2. **SCAMPI B** — a lighter-weight readiness check ahead of a full SCAMPI A; identifies gaps without issuing a formal rating
3. **SCAMPI C** — a quick, informal gap analysis, often used very early in an improvement initiative

**What an appraiser looks for in QA specifically:**
- Objective evidence that verification and validation activities actually happened (not just that a plan says they should)
- Independent PPQA audit records, including logged non-compliances and their resolution
- Requirements traceability that survives a spot-check from requirement to test result
- For ML4/ML5 claims: statistical evidence — control charts, defect trend data — not just anecdote

---

## CMMI vs. A-SPICE — Comparison

| Aspect | CMMI | A-SPICE |
|---|---|---|
| Origin / steward | SEI (Carnegie Mellon) → CMMI Institute / ISACA | VDA QMC (German Association of the Automotive Industry) |
| Primary domain | Software, systems, services, acquisition (industry-agnostic) | Automotive software/systems specifically |
| Rating unit | Maturity Level (staged, org-wide) or Capability Level (continuous, per process area) | Capability Level per process (continuous only) |
| Levels | 5 Maturity Levels (staged) | 6 Capability Levels (0–5) |
| Structural basis | Process Areas (e.g. REQM, PPQA, VER, VAL) | Process Reference Model — SYS, SWE, SUP, MAN, ACQ, SPL groups |
| QA-equivalent process | PPQA (independent process/product audit) | SUP.1 Quality Assurance |
| Verification-equivalent process | VER | SWE.4/SWE.5/SWE.6 (unit/integration/qualification test) |
| Assessment method | SCAMPI (A/B/C), certified Lead Appraiser | Formal Assessment per ISO/IEC 33002, certified Assessor |
| Typical mandate | Often contractual (RFPs, government/defense, offshoring vendors) | Mandatory for most OEM supplier contracts |
| Traceability requirement | Required via REQM, checked at VER/VAL | Required bidirectionally across all V-model levels, explicitly audited |

**In practice:** the two are not mutually exclusive. A Tier 1 automotive supplier can hold both a CMMI Maturity Level (as an org-wide quality credential, often required by non-automotive customers too) and an A-SPICE capability profile (required specifically by automotive OEMs). Where A-SPICE drills into automotive-specific software engineering work products, CMMI provides the broader organizational-process backbone — including the independent audit function (PPQA) that A-SPICE addresses only narrowly through SUP.1.

---

## Common CMMI-Related Findings in QA

1. **PPQA not independent** — the "auditor" is the same person who wrote the test plan being audited, invalidating objectivity
2. **REQM traceability gaps** — requirement changes made without updating the linked test cases, breaking the traceability chain
3. **VER/VAL conflated** — teams claim "we tested it" without distinguishing specification-conformance (VER) from fitness-for-use (VAL)
4. **No quantitative baseline at ML4 claims** — defect and coverage data collected but never plotted against control limits or used to predict outcomes
5. **Non-compliance issues logged but never closed** — PPQA findings pile up without resolution tracking, a common SCAMPI red flag
6. **Process defined but not followed** — organizational standard test process (ML3) exists on paper, but project teams silently deviate from it

---

## QAI Consultant Application

When a project cites CMMI (or a client explicitly requires a target Maturity Level), QAI Consultant should:

1. Surface this during the **compliance/regulatory question** (dialogue question 11, "Are there any compliance or regulatory requirements?") — capture the target Maturity Level (e.g. "CMMI ML3 required") and whether staged or continuous appraisal applies
2. Cross-check against the **methodology question** (dialogue question 8, Agile/Waterfall/other) — CMMI is representation-agnostic but higher maturity levels demand more documented, repeatable process discipline than a loosely-run Agile team may currently have; flag the gap
3. In the generated **Test Strategy**, include an explicit VER vs. VAL split — separate unit/integration/spec-conformance testing (VER) from system/acceptance/user-need testing (VAL) as distinct sections, since CMMI appraisers look for this distinction
4. In the generated **Risk Register**, add a process-maturity risk item whenever the target Maturity Level is ML3+ but the team's described QA practices (from the dialogue answers) suggest ML1–ML2 behavior — e.g., no requirements traceability tooling stated, no independent QA role
5. Recommend an explicit **PPQA-equivalent activity** (independent process/product audit, distinct from the test execution team) whenever team size and structure (dialogue questions 5–6, QA/dev headcount) make an independent audit function plausible
6. In the **Effort Estimation Report**, add a line item for traceability and audit-evidence overhead (RTM maintenance, review records, non-compliance tracking) when CMMI ML3+ or a formal SCAMPI appraisal is mentioned as a project driver
7. If the project also involves A-SPICE (automotive), recommend they be treated as complementary, not redundant — reference the comparison table above so the client understands which artifacts satisfy which framework
8. Flag in the Test Strategy that ML4/ML5 claims require quantitative defect and coverage trend data, not just pass/fail counts — recommend lightweight metrics capture (defect density, escape rate) even for teams not yet at that level, to build the evidence base early
