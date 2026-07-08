# ISO 27001 and SOC 2 — Compliance Audit Frameworks for Software Delivery

Source: Compiled from public knowledge — ISO/IEC 27001:2022 (Information security management systems — Requirements), ISO/IEC 27002:2022 (Information security controls), and the AICPA Trust Services Criteria (SOC 2), all publicly documented frameworks
License: N/A — general knowledge synthesis; consult the official ISO and AICPA publications for authoritative, licensed text

---

## Overview

ISO 27001 and SOC 2 are the two compliance audit frameworks a QA function is most likely to encounter when a client sells software to enterprise, healthcare, or financial customers. Neither framework tests the *product* directly — both audit whether the *organization* runs a disciplined, evidenced process around security and delivery, and the SDLC is one of the process areas an auditor will sample. For QA, the practical consequence is the same in both frameworks: passing test results are necessary but not sufficient. An auditor wants proof that testing, review, and change control *happened as documented*, every time, for a sustained period — not just that the latest build is green.

---

## ISO 27001 — the Information Security Management System (ISMS)

ISO 27001 certifies an organization's **Information Security Management System (ISMS)** — the governance structure (policies, risk assessments, roles, controls, and continual-improvement cycle) that manages information security risk. It is certified by an accredited third-party body and reassessed via annual surveillance audits plus a full recertification every three years.

Core mechanics relevant to a delivery team:

1. **Risk-based, not checklist-based.** Clause 6.1.2 requires a documented information security risk assessment; controls are selected from Annex A (or elsewhere) based on that risk assessment, recorded in a **Statement of Applicability (SoA)** that states which controls apply, which are excluded, and why.
2. **PDCA cycle.** Plan (risk assessment, SoA) → Do (implement controls) → Check (internal audits, management review, metrics) → Act (corrective actions) — clauses 4 through 10 of the standard.
3. **Annex A is a control catalogue, not a mandate.** The 2022 revision restructured the annex from 14 domains / 114 controls (2013 edition) down to **4 themes / 93 controls**. A given software project only needs the controls its risk assessment and SoA actually select.

---

## ISO 27001 Annex A — Control Themes (2022 structure)

| Theme | Control count | Focus |
|---|---|---|
| Organizational | 37 | Policies, roles, supplier relationships, asset management, incident management |
| People | 8 | Screening, awareness training, disciplinary process, remote working |
| Physical | 14 | Secure areas, equipment, media handling, clear desk/screen |
| Technological | 34 | Access control, cryptography, logging, network security, **secure development** |

---

## Annex A Controls Most Relevant to SDLC/QA

These sit in the Technological theme and are the controls an auditor will ask a QA/engineering lead to produce evidence for:

| Control | Name | Relevance to QA |
|---|---|---|
| A.8.25 | Secure development life cycle | Requires security to be embedded at every SDLC stage — design, coding, testing, deployment — with documented rules, not ad hoc effort. This is the umbrella control the others sit under. |
| A.8.26 | Application security requirements | Security requirements must be identified and specified *before* development starts, and validated at acceptance — ties directly to acceptance criteria and the Test Strategy's requirements-traceability section. |
| A.8.27 | Secure system architecture and engineering principles | Secure-by-design principles applied consistently — relevant to architecture/design review gates in the test plan. |
| A.8.28 | Secure coding | Secure coding standards must be defined, applied, and — critically — **reviewed**; static analysis / code review evidence is the audit artifact. |
| A.8.29 | Security testing in development and acceptance | Explicit requirement for security testing (SAST/DAST, penetration testing) as a documented, repeatable process in dev and acceptance phases — not a one-off pentest. |
| A.8.31 | Separation of development, test, and production environments | Environment segregation with controlled promotion — a QA environment strategy question, not just an ops one. |
| A.8.32 | Change management | Every production-impacting change (including releases) must go through a documented approval and testing gate before deployment. |
| A.5.23 | Information security for use of cloud services | Relevant whenever the tech stack includes cloud/SaaS dependencies named in the dialogue's tech-stack answer. |
| A.5.1 | Policies for information security | The root policy Annex A controls trace back to; auditors expect QA process docs (test plans, defect-severity policy) to be consistent with it, not contradict it. |

---

## SOC 2 — Trust Service Criteria

SOC 2 is an **attestation report**, not a certification — issued by a licensed CPA firm under AICPA standards, addressed to the client's own customers rather than to a public registry. It evaluates controls against five **Trust Services Criteria (TSC)**:

| Criterion | Common name | Required in every SOC 2? |
|---|---|---|
| Security | Common Criteria (CC) | Yes — mandatory baseline for every SOC 2 report |
| Availability | — | Optional, selected per engagement |
| Processing Integrity | — | Optional — relevant to systems performing calculations, transactions, or data transformation |
| Confidentiality | — | Optional — relevant to systems handling confidential business data (not personal data specifically) |
| Privacy | — | Optional — relevant to systems processing personal information |

The **Security** criterion (the "Common Criteria") is the only one every SOC 2 report must include; the other four are scoped in based on what the service actually does. A B2B SaaS API handling customer transactions might scope in Security + Availability + Processing Integrity and leave Privacy out if it never touches personal data.

---

## SOC 2 Report Types — Type I vs Type II

| Aspect | Type I | Type II |
|---|---|---|
| What it assesses | Design of controls at a single point in time | Design **and** operating effectiveness over a period (typically 6–12 months) |
| Evidence style | "Here is our documented control" (a policy, a config screenshot) | "Here is our control operating on every occurrence across the period" (a sampled set of tickets/logs/approvals) |
| Typical use | First-time attestation, early-stage vendors, fills a gap while a Type II is being earned | Standard expectation for enterprise vendor due diligence |
| QA implication | Show the test plan and CI pipeline exist and are configured correctly | Show that every release in the audit window actually went through the documented test gate — sampled evidence, not just current state |

A Type II report is materially harder for a QA function to pass cold: it requires the testing and release process to have been followed *consistently*, with retained evidence, for the entire audit window — not tightened up right before the audit.

---

## Evidence-Based Audit Requirements — Beyond Passing Tests

Both frameworks convert "did testing happen" into "can you prove it happened, for whom, and when." A green CI pipeline on the day of the audit proves nothing about the prior eleven months. Auditors sample evidence artifacts, typically including:

- [ ] **Test execution records** — not just pass/fail counts, but who ran which test suite against which build, with a timestamp
- [ ] **Defect/ticket trail** — issue tracker records showing a defect was raised, triaged, fixed, retested, and closed (not just closed)
- [ ] **Code review sign-offs** — pull-request approvals showing a second reviewer, tied to the change that shipped
- [ ] **Change approval records** — a documented approver for each production release, separate from the person who implemented the change
- [ ] **Access logs** — who had permission to deploy or modify production, and evidence access was reviewed periodically
- [ ] **Security test artifacts** — SAST/DAST scan reports, dependency-vulnerability scan output, penetration test reports, retained and dated
- [ ] **Training records** — evidence the team completed secure-coding or security-awareness training (people controls)
- [ ] **Incident records** — for any security incident, evidence of detection, response, and root-cause follow-up
- [ ] **Risk assessment / SoA updates** — evidence the risk register and control scope were reviewed, not written once and forgotten

The common failure mode across both frameworks is not "tests didn't pass" — it's "the evidence trail has gaps": a defect closed with no linked retest, a release with no recorded approver, a test suite that ran but whose results were never archived.

---

## Comparing ISO 27001 and SOC 2

| Dimension | ISO 27001 | SOC 2 |
|---|---|---|
| Output | Certification (pass/fail, valid 3 years + annual surveillance) | Attestation report (narrative opinion, shared under NDA with customers) |
| Scope flexibility | Controls selected via risk assessment + SoA | Criteria selected per engagement (Security mandatory, others optional) |
| Primary audience | Regulators, international customers, public registries | Direct B2B customers doing vendor due diligence (common in US SaaS) |
| Geography | Globally recognized | Predominantly US/North America convention, increasingly requested globally |
| Renewal cadence | 3-year cycle + annual surveillance audits | Typically re-issued annually (especially Type II) |

They are not mutually exclusive — many vendors selling into both US enterprise and EU/international markets pursue both, and a well-run SDLC evidence trail (tickets, reviews, test records, change approvals) largely satisfies both frameworks' auditors simultaneously.

---

## Typical Audit Lifecycle — Where QA Evidence Gets Sampled

Both frameworks follow a similar audit rhythm; understanding it clarifies *when* evidence gets checked, not just what evidence to keep:

1. **Readiness / gap assessment.** The organization (or a consultant) compares current practice against the target controls (Annex A / SoA, or the relevant TSC) and lists gaps — this is the point where a missing test-evidence process is usually first caught.
2. **Remediation.** Gaps are closed — policies written, tooling added (e.g., a test-management system that retains execution history), process changes rolled out to engineering and QA teams.
3. **Observation window (SOC 2 Type II only; ISO 27001 surveillance is continuous).** The organization operates its controls for the full period (6–12 months) while evidence accumulates naturally as a byproduct of normal work — not backfilled afterward.
4. **Fieldwork / audit.** The external auditor samples a subset of changes, releases, or tickets from the window and requests the underlying evidence for each sampled item — a QA team that can pull up the test record, the reviewer, and the ticket link for any sampled release passes; a team that has to reconstruct it after the fact usually cannot.
5. **Report issuance.** ISO 27001 issues a certificate (valid ~3 years, with annual surveillance audits); SOC 2 issues an attestation report shared directly with the client's customers under NDA, typically re-issued annually.
6. **Continual monitoring.** Both frameworks expect controls to keep operating between audits, not just be demonstrated once — internal audits (ISO 27001 clause 9.2) or ongoing control monitoring (SOC 2) catch drift early.

The engineering implication is that evidence-generation has to be a **byproduct of the normal test/release workflow** (tickets link to test runs automatically, approvals are captured in the tool, retention is automatic) — a process that only produces audit-ready evidence when someone remembers to document it manually will fail sampling sooner or later.

---

## QAI Consultant Application

When a project's `compliance_requirements` answer mentions ISO 27001, SOC 2, "enterprise customers," "vendor security questionnaire," or "due diligence," QAI Consultant should:

1. **Surface this at dialogue intake.** The `compliance_requirements` question (question 11) is the direct trigger — any mention of ISO 27001, SOC 2, "SOC2," "Type II," or generic "security audit"/"enterprise compliance" language should route this document into the RAG retrieval for Risk Register and Test Strategy generation via `to_rag_query()`.
2. **Add an "Audit Evidence Gap" risk category to the Risk Register.** Beyond the usual functional/security/performance risk categories, flag the *absence of a retained evidence trail* — e.g., "Defect closures are not linked to retest evidence," "No documented approver on record for production releases" — as its own risk class, since this is the specific failure mode both frameworks penalize.
3. **Add an "Evidence & Traceability" section to the Test Strategy** whenever compliance is in scope: require the test plan to specify what artifact each test activity produces (execution log, sign-off record, ticket link) and where it is retained, not just what the test activity is.
4. **Distinguish Type I vs Type II readiness in the Test Strategy** if SOC 2 is named: a Type I bar only requires the process to be documented and demonstrably correct today; a Type II bar requires showing the process operated consistently across the full audit window, which should shape recommended test-cycle cadence and record-retention duration.
5. **Reflect audit overhead in the Effort Estimation Report.** Evidence capture, retention, and sign-off workflows are real, recurring QA effort — add an explicit multiplier or line item (e.g., "compliance evidence overhead") rather than folding it silently into general test execution time, consistent with how other multipliers are itemized before PERT normalization.
6. **Recommend the specific Annex A / TSC controls that map to the project's test scope** in the generated Test Plan — e.g., recommend A.8.29-aligned security testing cadence when `existing_automation` shows no security scanning, or an A.8.32-aligned change-approval gate when the release process described has no documented sign-off step.
7. **Flag environment segregation (A.8.31) as a Risk Register item** whenever `tech_stack` or `project_description` suggests shared dev/test/prod environments — a common finding in both ISO 27001 and SOC 2 audits.
8. **Do not conflate certification and attestation in generated language.** Documents should describe ISO 27001 as something the organization "is certified against" and SOC 2 as a report the organization "receives" or "is issued" — this distinction affects how a client's compliance team will read the generated Test Strategy.
