# ISO/IEC 33002 — Requirements for Performing Process Assessment

Source: Compiled from public knowledge — ISO/IEC 33002:2015 *Information technology — Process assessment — Requirements for performing process assessment*, part of the ISO/IEC 330xx family that superseded ISO/IEC 15504 (SPICE); companion standard ISO/IEC 33020 (process measurement framework for process capability) referenced where relevant, along with ISO/IEC TS 33061 (the generic software life cycle Process Assessment Model that succeeded ISO/IEC 15504-5). Automotive SPICE's own PAM is a domain-specific document published by VDA QMC/AutomotiveSIG — not itself an ISO/IEC-numbered standard — that conforms to ISO/IEC 33004's requirements for process assessment models.
License: ISO/IEC copyrighted document — this file summarizes publicly documented structure and terminology; it is not a reproduction of the standard's normative text.

---

## Overview

ISO/IEC 33002 is the normative core of the ISO/IEC 330xx family: it defines the minimum set of requirements an assessment must satisfy for its results to be objective, impartial, consistent, repeatable, and representative of the processes assessed. It replaced ISO/IEC 15504-2 as the international basis for process capability determination, and it is the direct ancestor of Automotive SPICE (A-SPICE) — the six capability levels and the process attribute rating scale used throughout A-SPICE originate here, not from the automotive standard itself. Where A-SPICE tells an organization *what* automotive software processes should look like, ISO/IEC 33002 tells an assessor *how* to run a valid, defensible assessment of any process against a Process Assessment Model (PAM).

---

## The Process Assessment Model (PAM) Structure

ISO/IEC 33002 assessments are always performed against a **Process Assessment Model** — a two-dimensional structure:

- **Process dimension** — a set of processes, each with a defined purpose and outcomes, drawn from a **Process Reference Model (PRM)** (ISO/IEC 33004 defines PRM requirements). A-SPICE's SWE/SYS/MAN/SUP process categories are one such PRM.
- **Capability dimension** — the six-level capability scale defined in ISO/IEC 33020, expressed through **process attributes (PAs)** that are rated using a defined evidence-based scale.

A PAM maps process-specific indicators (base practices, work products) at Level 1 and generic indicators (generic practices, generic resources) at Levels 2–5 onto this capability scale. A-SPICE's own PAM — published by VDA QMC/AutomotiveSIG, conformant to ISO/IEC 33004 but not itself an ISO/IEC-numbered standard — is a worked example of this structure applied to automotive engineering processes.

---

## The Six Capability Levels

This is the scale A-SPICE capability levels (0–5) are inherited from verbatim — the level names, the process attributes, and the rating logic all trace back to this framework.

| Level | Name | Process Attributes (PA) | What it demonstrates |
|---|---|---|---|
| 0 | Incomplete | — | The process is not implemented, or fails to achieve its purpose; little or no systematic evidence of outcomes. |
| 1 | Performed | PA 1.1 Process Performance | The process achieves its intended purpose; base practices are performed and work products exist. |
| 2 | Managed | PA 2.1 Performance Management, PA 2.2 Work Product Management | Performance is planned, monitored, and adjusted; work products are appropriately controlled. |
| 3 | Established | PA 3.1 Process Definition, PA 3.2 Process Deployment | A standard, tailorable process definition is deployed consistently across the organization. |
| 4 | Predictable | PA 4.1 Process Measurement, PA 4.2 Process Control | The process operates within defined limits using quantitative data to achieve predictable results. |
| 5 | Optimizing | PA 5.1 Process Innovation, PA 5.2 Process Optimization | The process is continually improved to meet current and projected business goals. |

**Rating scale per process attribute** (ISO/IEC 33020):

| Rating | Abbreviation | Achievement |
|---|---|---|
| Not achieved | N | 0–15% |
| Partially achieved | P | >15–50% |
| Largely achieved | L | >50–85% |
| Fully achieved | F | >85–100% |

A capability level is only achieved when all of its process attributes, and all attributes of every lower level, are rated Largely or Fully achieved. This is why A-SPICE assessors report "Level 2" or "Level 3" rather than a single blended score — capability is a floor, not an average.

---

## The Formal Assessment Process

ISO/IEC 33002 mandates five sequential activities. Skipping or informally compressing any of them invalidates the result as a conformant assessment.

1. **Plan the assessment**
   - Define assessment scope: organizational unit, process scope, capability level target, assessment class (as defined in ISO/IEC 33002, e.g. Class 1 = full evidence set, Class 3 = reduced/self-assessment)
   - Confirm assessor independence and the assessment purpose (self-improvement, supplier selection, contractual capability determination)
   - Identify roles: sponsor, competent (lead) assessor, assessment team, process owners/interviewees
   - Define the rating and aggregation method to be used before data collection starts

2. **Collect the data**
   - Gather objective evidence against the PAM's indicators — documents, work products, tool records, interviews, observation of practice
   - Evidence must be sufficient and traceable to specific process attribute indicators, not general impressions

3. **Validate the data**
   - Cross-check evidence for sufficiency, representativeness (does it cover the full assessed scope, not a cherry-picked project), and consistency between sources (interview claims vs. artifact evidence)
   - Resolve conflicting or ambiguous evidence before rating

4. **Determine the process attribute ratings**
   - Rate each in-scope process attribute N/P/L/F using the validated evidence and the defined rating method
   - Aggregate individual PA ratings into a capability level per process, applying the "all attributes at this level and below must be L or F" rule

5. **Report the assessment**
   - Produce a documented, traceable record: scope, ratings per process per attribute, supporting evidence summary, and any findings/observations
   - The report must allow the ratings to be reconstructed and audited independently — an un-traceable rating is a non-conformant assessment

---

## Assessor Competence Requirements

ISO/IEC 33002 requires assessors to meet documented competence criteria before they can lead or perform a conformant assessment:

- **Competent assessor** — demonstrated knowledge of the PRM/PAM in use, the ISO/IEC 330xx assessment process, and rating/evidence practices; typically evidenced by training plus supervised assessment experience
- **Lead assessor** — additional requirement of prior experience leading assessments, responsible for the overall conduct, consistency, and defensibility of the result
- Assessor competence itself is auditable: an assessment can be challenged on the basis that the team lacked the qualifications the standard requires, independent of whether the ratings look plausible

This competence requirement is why A-SPICE assessments are normally performed by intacs-certified (or equivalent) principal/competent assessors — the certification scheme exists specifically to satisfy this clause of ISO/IEC 33002.

---

## Assessment vs. Certification Audit — the Key Distinction

This distinction matters because clients and stakeholders routinely conflate the two, and QAI Consultant should not reinforce that confusion.

| Dimension | ISO/IEC 33002 Process Assessment | Certification Audit (e.g. ISO 9001) |
|---|---|---|
| Output | A capability profile (per-process ratings against a defined scale) | A binary pass/fail conformity decision |
| Basis | A Process Reference Model + Process Assessment Model with graded attributes | A management system standard's clause-by-clause requirements |
| Purpose | Process improvement, benchmarking, supplier capability determination | Formal certification/registration, often for contractual or regulatory proof |
| Who performs it | Competent/lead assessor per ISO/IEC 33002 competence rules | Accredited certification body auditor |
| Repeatability requirement | Explicit design goal — same evidence should yield same rating regardless of assessor | Conformance decision, not a graded/comparable score |
| Typical trigger in automotive | OEM requires supplier to reach A-SPICE Level 2/3 | Organization seeks/maintains ISO 9001 or IATF 16949 certificate |

A process assessment tells you *how good* a process is on a graded scale; a certification audit tells you *whether* a system meets a fixed bar. A supplier can be ISO 9001-certified and still assessed at A-SPICE Level 1 on SWE.5 — the two are not substitutes for each other, and a QAI Consultant output should never present one as satisfying the other.

---

## QAI Consultant Application

1. **Dialogue question surfacing** — the question capturing applicable standards/regulatory context (where A-SPICE, ISO 26262, or supplier-capability requirements are declared) should treat "A-SPICE capability level required" as a signal to pull this document, since the target level (e.g. "OEM requires Level 2 on SYS.2–SYS.5, SWE.1–SWE.6") is expressed entirely in ISO/IEC 33002's capability-level vocabulary.

2. **Risk Register** — when a project targets a specific capability level and current practice is unassessed or known to be informal, generate a risk entry such as: "Process capability gap — SWE.5 currently unmanaged (no PA 2.1/2.2 evidence); OEM contract requires Level 2 by milestone X," with likelihood tied to how far current practice diverges from the target level's process attributes.

3. **Test Strategy — process evidence requirements** — if a target capability level is in scope, the Test Strategy should explicitly list the work-product evidence needed to demonstrate the relevant process attributes (e.g. for Level 2: planned/tracked test activities and controlled test work products; for Level 3: a deployed, organization-standard test process), not just the test techniques themselves.

4. **Test Strategy — assessment readiness section** — where the project context indicates an upcoming formal or supplier assessment, the generated strategy should recommend evidence traceability (test plans, review records, defect data mapped to indicators) be organized so it can be presented to an assessor without reconstruction effort.

5. **Effort Estimation Report** — if the project must move from an unassessed/Level 0-1 state to a contractually required Level 2/3, add an explicit effort line for process-definition and process-deployment activities (PA 3.1/3.2 equivalents) distinct from product testing effort — these are commonly underestimated because they are organizational, not per-release, costs.

6. **Terminology guardrail** — the generated documents must not use "audit" and "assessment" interchangeably when ISO/IEC 33002 language is invoked; if the user's answers mention a "certification audit," the agent should recognize this is a different mechanism (see comparison table above) and avoid recommending capability-level ratings as if they were a certification outcome, or vice versa.

7. **Assessor/reviewer competence note** — where a project explicitly plans an A-SPICE or ISO/IEC 33002-style assessment, the Test Strategy's review/governance section should note that assessment results are only defensible if performed by assessors meeting the standard's competence requirements — informal self-scoring against the capability table is a useful internal health check but should not be represented as a conformant assessment result.

8. **Effort Report confidence factors** — projects reporting no prior formal process assessment should be flagged as lower data-quality inputs for capability-related risk and effort figures, since the deterministic estimator has no prior L/F-rated baseline to anchor against — this should reduce the confidence score rather than being silently ignored.
