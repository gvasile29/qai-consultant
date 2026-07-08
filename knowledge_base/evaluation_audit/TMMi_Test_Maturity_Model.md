# TMMi — Test Maturity Model integration

Source: Compiled from public knowledge — Test Maturity Model integration (TMMi), published by the TMMi Foundation, publicly available at tmmi.org
License: TMMi Foundation — publicly available reference model (non-normative summary)

---

## Overview

TMMi (Test Maturity Model integration) is a staged, five-level maturity model for assessing and improving the test process of an organization, structured as a companion to CMMI's process-maturity approach but scoped specifically to testing. Where CMMI asks "how mature is your engineering process as a whole?", TMMi asks the narrower question "how mature is your test process specifically?" — do you test because a plan says to, or because a lifecycle demands it, or because a measured, continuously-improving discipline drives it? Each level defines a set of **process areas**, and each process area defines **specific goals** achieved through **specific practices**, plus generic goals covering institutionalization (commitment, ability, measurement, verification). An organization cannot skip levels: TMMi Level 3 cannot be claimed without first satisfying every process area at Level 2.

---

## The Five Maturity Levels

| Level | Name | Character | Test Process Behavior |
|---|---|---|---|
| 1 | Initial | Ad hoc | Testing is chaotic, undefined, treated as debugging; no dedicated test phase, no metrics, high defect leakage to production |
| 2 | Managed | Project-managed | Testing becomes a managed activity with its own policy, plan, and monitoring — but still project-specific, not organization-wide |
| 3 | Defined | Organization-wide | A standard, tailorable test process is defined at the organizational level; testing is a professional discipline with training and lifecycle integration from the start of the project |
| 4 | Measured | Quantitatively controlled | Test process performance is measured against quantitative goals; product quality is evaluated systematically, not just functionally |
| 5 | Optimization | Continuously improving | Metrics drive continuous process optimization, statistical defect prevention, and control over quality across the organization |

**No level-skipping:** each level's process areas build on and require the ones below. A Level 4 claim without a satisfied Level 2 and Level 3 is not a valid TMMi assessment result.

---

## Level 2 — Managed: Process Areas

Level 2 is where testing first becomes a genuinely managed activity, separated conceptually from debugging.

| Process Area | Purpose |
|---|---|
| Test Policy and Strategy | Define organizational test objectives, and a strategy (e.g., risk classes, generic test approach) that projects tailor from |
| Test Planning | Produce a project-level test plan derived from the strategy: scope, estimates, risks, resources, schedule |
| Test Monitoring and Control | Track actual progress against the plan and take corrective action when deviations occur |
| Test Design and Execution | Move from ad hoc test cases to structured test design techniques with defined entry/exit criteria and traceability to requirements |
| Test Environment | Ensure the test environment is specified, controlled, and available when needed, and is representative of production |

**Typical Level 2 evidence an assessor looks for:** a documented test policy, project test plans with estimates and risk-based prioritization, defect logs used to track status against exit criteria, and a managed (not ad hoc) test environment.

---

## Level 3 — Defined: Process Areas

Level 3 moves testing from project-managed to organization-defined — a standard process exists and is tailored, not reinvented, per project.

| Process Area | Purpose |
|---|---|
| Test Organization | Establish an independent test function/group with a defined structure, roles, and career path |
| Test Training Program | Ensure staff have the skills to execute the defined test process (formal training program, not informal mentoring only) |
| Test Lifecycle and Integration | Integrate test activities into the full software lifecycle from the requirements phase onward (master test planning, level-specific test plans) |
| Non-functional Testing | Extend structured testing beyond functional correctness to performance, security, usability, reliability, and other quality characteristics |
| Peer Reviews | Apply structured static testing (inspections, walkthroughs, technical reviews) to requirements, design, and code — not just dynamic execution |

**Typical Level 3 evidence:** an organization-wide test process standard with a tailoring guide, a training curriculum with completion records, master test plans covering every lifecycle phase, non-functional test plans (not just functional), and review records with defect data from static testing.

---

## Level 4 — Measured: Process Areas

Level 4 introduces quantitative management: the test process is no longer just followed, it is measured against quantitative goals.

| Process Area | Purpose |
|---|---|
| Test Measurement | Establish an organization-wide test measurement program: defined metrics, data collection, baseline, and use of data for decisions |
| Product Quality Evaluation | Evaluate product quality quantitatively against defined quality goals, not only pass/fail test results |
| Advanced Reviews | Apply quantitative techniques (e.g., statistical sampling, weighting) to make review and inspection processes measurably more effective |

**Typical Level 4 evidence:** a metrics catalog (defect density, defect detection percentage, test coverage trends, review effectiveness) fed by tooling, quality goals stated in measurable terms per release, and evidence that review data is analyzed statistically, not just logged.

---

## Level 5 — Optimization: Process Areas

Level 5 is a continuous-improvement loop: the organization uses its own measurement data to prevent defects before they occur and to keep optimizing the process itself.

| Process Area | Purpose |
|---|---|
| Test Process Optimization | Establish a continuous improvement mechanism for the test process itself, using quantitative process performance data |
| Quality Control | Apply statistical process control techniques to keep quality within predictable, controlled limits release over release |
| Defect Prevention | Perform root-cause analysis on defects to identify and eliminate systemic causes before they can recur |

**Typical Level 5 evidence:** a documented process-improvement backlog driven by measured process data, statistical control charts on quality trends, and a defect root-cause database that feeds back into requirements/design/coding standards.

---

## Model Structure — How TMMi Is Organized

Each TMMi process area (at any level) is defined by the same internal structure, which is what an assessor actually checks item-by-item:

1. **Purpose** — why the process area exists
2. **Specific Goals (SG)** — the process-area-specific outcomes that must be achieved
3. **Specific Practices (SP)** — the actions that achieve each specific goal
4. **Generic Goals / Generic Practices** — institutionalization requirements common across process areas (is the practice planned, resourced, assigned, trained, monitored, reviewed with management, and verified — not just performed once)

A process area is only "satisfied" when both its specific goals AND the generic institutionalization goals are met — a practice performed once on one project does not count; it must be planned, resourced, and repeatable.

---

## Self-Assessment Approach

An organization does not need an external accredited assessor to get value from TMMi; a structured self-assessment is a valid and common first step before (or instead of) a formal appraisal.

1. **Scope the assessment** — decide the organizational unit (single project, department, whole company) and the target level to assess against
2. **Gather evidence per process area** — for each process area at the target level and below, collect artifacts: policies, plans, test cases, defect logs, review records, metrics dashboards, training records
3. **Interview practitioners** — cross-check documented process against what testers, developers, and test managers actually do day to day; documentation without practice does not satisfy a goal
4. **Score each specific goal** — typically Fully / Largely / Partially / Not achieved, based on evidence + interview consistency
5. **Identify gaps** — for every goal not fully achieved, record the specific missing practice or missing institutionalization element (not just "process area X failed")
6. **Prioritize an improvement plan** — because levels are cumulative, close Level 2 gaps before investing in Level 3 practices, even if some Level 3 activity already exists informally
7. **Re-assess periodically** — self-assessment is not a one-time snapshot; TMMi improvement is a repeat cycle, mirroring the Level 5 Test Process Optimization process area

A formal TMMi appraisal (analogous to a CMMI SCAMPI appraisal) follows the same evidence-and-interview logic but is conducted by an accredited lead assessor and produces a certifiable maturity rating.

---

## TMMi, CMMI, and ISO/IEC 33002 — How the Frameworks Relate

TMMi does not exist in isolation; it was explicitly designed as the testing-focused companion to the broader process-maturity ecosystem also covered in this knowledge base (see `CMMI_Process_Maturity.md` and `ISO_IEC_33002_Process_Assessment.md`).

| Aspect | TMMi | CMMI | ISO/IEC 33002 |
|---|---|---|---|
| Scope | Test process only | Whole engineering/organizational process | Generic process assessment methodology (successor to ISO 15504/SPICE) |
| Structure | Staged, 5 fixed levels | Staged or continuous representation | Continuous, per-process capability levels 0–5 |
| Origin | TMMi Foundation, built as a CMMI companion | SEI / CMMI Institute | ISO/IEC JTC1, generic assessment standard underlying A-SPICE too |
| Typical pairing | Used alongside CMMI to add testing depth CMMI treats only lightly | Provides the organizational maturity backdrop TMMi assumes | Provides the assessment method A-SPICE itself is built on |
| QAI Consultant relevance | Directly test-process focused — most applicable of the three to test strategy content | Signals overall process maturity risk context | Signals whether a formal, standards-based assessment method is already in use (common in automotive/A-SPICE contexts) |

**In practice:** an organization already running CMMI or A-SPICE (built on ISO/IEC 33002) rarely adopts TMMi as a replacement — it layers TMMi on top for testing-specific depth that the broader models under-specify.

---

## Common Findings by Maturity Level

1. **Level 1 → 2 gap:** no written test policy; test estimates are guesses with no traceability to a plan; environment issues discovered only at execution time
2. **Level 2 → 3 gap:** test process is documented per-project but not standardized organization-wide; testers are trained informally, with no tracked curriculum; non-functional requirements exist but have no corresponding test plan
3. **Level 3 → 4 gap:** review records exist but defect data from them is never aggregated or analyzed; "quality" is reported as pass/fail counts with no quantitative goal to compare against
4. **Level 4 → 5 gap:** metrics are collected but not used to change the process; defects are fixed individually but root cause is never traced back to a systemic, preventable source

---

## QAI Consultant Application

When a project's context indicates process maturity matters — most directly surfaced by the dialogue questions on **methodology** ("Does the team follow Agile, Waterfall, or another methodology?"), **existing automated tests** ("Does the project have any existing automated tests?"), and **compliance or regulatory requirements** — QAI Consultant should:

1. Treat the answers to those three questions as a rough, informal TMMi level signal: no test policy/plan mentioned and testing described as reactive → Level 1 behavior; a documented plan and monitored execution but no organization-wide standard → Level 2; a described organization-wide, trained, lifecycle-integrated process → Level 3+
2. In the generated **Risk Register**, add a process-maturity risk entry whenever the answers suggest Level 1–2 behavior (e.g., "no test policy referenced" or "no defect tracking process described") — this is a process gap risk, distinct from a product/technical risk
3. In the generated **Test Strategy**, recommend the TMMi process areas one level above the inferred current state as concrete next steps (e.g., a Level 1-looking project should be pointed at Test Policy and Strategy + Test Planning before anything else)
4. When the compliance/regulatory answer names an audited industry (automotive, medical, finance), cross-reference this document with `ISO_IEC_33002_Process_Assessment.md` and `CMMI_Process_Maturity.md` in the same retrieval pass, since audited industries typically expect a demonstrable process-maturity story, not just test coverage numbers
5. In the **Effort Estimation Report**, flag low inferred maturity (Level 1–2) as a factor that increases risk buffer/contingency — immature test processes correlate with higher rework and re-test cycles, which the effort multiplier should reflect
6. Never claim or imply a specific TMMi certification level for the user's organization — only reference which process areas are present or absent based on stated answers, since a real TMMi level requires formal appraisal evidence this dialogue cannot collect
7. When non-functional testing (performance, security, usability) is absent from the user's description of existing tests, flag it explicitly as a Level 3 process-area gap (Non-functional Testing) rather than folding it silently into general test scope
8. Surface the self-assessment checklist structure (goals achieved: Fully/Largely/Partially/Not) as an optional appendix suggestion in the Test Strategy for teams that describe wanting to formally track process maturity over time
