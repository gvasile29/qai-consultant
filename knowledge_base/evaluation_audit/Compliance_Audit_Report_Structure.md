# Compliance Audit Report — Standard Structure

Source: Compiled from public knowledge — ISO 19011:2018 (Guidelines for auditing management systems), ISO/IEC 17021-1 (conformity assessment), and common industry audit-report conventions (SOC 2, ISO 27001, ISO 9001 second/third-party audits)
License: Synthesized summary — not a reproduction of any single copyrighted standard

---

## Overview

A compliance audit report is the formal record of an independent evaluation of whether a process, system, or organization meets defined criteria — a regulation, standard, contract, or internal policy. Unlike a test report, which documents whether a *product* behaves as specified, an audit report documents whether a *process* is being followed and is capable of consistently producing conformant results. This document defines the standard structure of a compliance/process audit report so that QAI Consultant can recognize when a project needs one and can scaffold its structure and terminology correctly.

---

## 1. Executive Summary

A one-page, non-technical synthesis intended for management/sponsor readership. Typically includes:

- **Audit objective** — why the audit was performed (certification, regulatory mandate, contractual obligation, internal governance)
- **Overall conclusion** — a single verdict: conformant / conformant with minor findings / non-conformant
- **Headline numbers** — count of findings by severity (e.g., 0 Critical, 2 Major, 5 Minor, 3 Observations)
- **Key risks** — the 2-3 findings with the greatest business or safety impact
- **Recommendation** — proceed to certification / remediate and re-audit / escalate

The executive summary is written **last**, after findings are finalized, but placed **first** in the document.

---

## 2. Scope and Criteria

Defines the boundaries of what was audited and against what it was measured. Ambiguity here is the single most common source of disputed audit findings.

| Element | Description | Example |
|---|---|---|
| Audit scope | Systems, processes, sites, or organizational units included | "Production payment-processing microservices; excludes staging/test environments" |
| Audit criteria | The normative reference(s) the auditee is measured against | ISO 27001:2022 Annex A, PCI-DSS v4.0, internal SDLC Policy v3.2 |
| Audit period | Time window the evidence covers | "1 Jan 2026 – 30 Jun 2026" |
| Exclusions | Explicitly out-of-scope items and why | "Third-party vendor systems audited separately under SOC 2 reliance" |
| Audit type | First-party (internal), second-party (customer/supplier), or third-party (certification body) | Second-party vendor audit |

Scope and criteria must be agreed with the auditee **before** fieldwork begins, not retrofitted afterward.

---

## 3. Methodology

Describes how evidence was gathered, so a reader can judge the reliability of the conclusions. Typically follows the ISO 19011 audit process:

1. **Audit planning** — audit program, criteria confirmation, resource/auditor assignment
2. **Document review** — policies, procedures, prior audit reports, process artifacts examined pre-fieldwork
3. **Fieldwork / evidence collection** — interviews, direct observation, sampling of records, system walkthroughs, tool-assisted evidence pulls
4. **Sampling approach** — population size, sample size, and sampling method (random, risk-based, judgmental) — must be stated explicitly since findings only generalize as far as the sample justifies
5. **Evidence evaluation** — comparing observed practice against the stated criteria
6. **Finding generation and review** — draft findings validated with auditee subject-matter experts before finalization (fact-check step to reduce disputed findings)

---

## 4. Findings

The evidentiary core of the report. Every finding follows a fixed template so findings are comparable, traceable, and actionable. Recommended fields:

| Field | Purpose |
|---|---|
| **Finding ID** | Unique identifier (e.g., `AUD-2026-014`) for tracking through remediation and follow-up |
| **Description** | Objective, factual statement of the gap — what was expected vs. what was observed |
| **Evidence** | The specific artifact(s) that support the finding — document reference, screenshot, log excerpt, interview note, sample record IDs |
| **Requirement / Clause referenced** | The exact criterion violated (e.g., "ISO 27001:2022 A.8.24", "PCI-DSS v4.0 Req. 6.3.1", "internal SDLC Policy §4.2") |
| **Severity** | See classification table below |
| **Root cause (if determined)** | Why the gap exists, not just that it exists |
| **Affected area / owner** | Team or system accountable for remediation |
| **Recommendation** | Auditor's suggested remediation direction (not prescriptive of implementation) |

### Severity Classification

| Severity | Definition | Typical Consequence |
|---|---|---|
| **Critical** | Direct, immediate risk to safety, security, legal compliance, or data integrity | Audit fails; certification withheld/suspended; may require immediate containment |
| **Major** | The process fails to achieve its intended result; a systemic gap, not an isolated slip | Must be remediated before certification/sign-off; re-audit of the specific area required |
| **Minor** | An isolated deviation that does not undermine the overall capability of the process | Remediation required but does not block sign-off; verified at next scheduled audit |
| **Observation** | No nonconformity against stated criteria, but a risk or improvement opportunity worth noting | No mandatory corrective action; tracked for continuous improvement |

ISO 19011:2018 §6.4.8 ("Generating audit findings") describes the general process of evaluating evidence against criteria to determine findings, but does not itself define a severity taxonomy. Certification-body audits against ISO 9001 and ISO 27001 (governed by ISO/IEC 17021-1) conventionally use a **two-tier** Major/Minor nonconformity classification, plus an informal "Observation" / Opportunity for Improvement (OFI) that carries no mandatory corrective action. The four-tier Critical/Major/Minor/Observation scheme above is the de facto convention in second-party vendor audits, PCI-DSS assessments, SOC 2 engagements, and most internal audit functions, where an explicit "Critical" tier is used to flag findings requiring immediate containment. When scaffolding output for a certification-track audit (ISO 9001/27001 under ISO/IEC 17021-1), QAI Consultant should default to Major/Minor/Observation rather than introducing a "Critical" tier unless the auditee's own audit program defines one.

---

## 5. Recommendations

Distinct from per-finding recommendations, this section aggregates **cross-cutting** guidance:

- Patterns across multiple findings (e.g., "3 of 5 Major findings trace back to absent change-approval evidence — recommend a single process fix rather than five point fixes")
- Prioritization guidance when remediation capacity is constrained
- Process or tooling investments that would prevent recurrence, not just fix the instance found

---

## 6. Corrective Action Plan (CAP)

The auditee's committed response to each finding requiring remediation. A CAP entry typically contains:

| Field | Description |
|---|---|
| Finding ID reference | Links back to Section 4 |
| Corrective action | Specific action(s) to be taken |
| Owner | Named individual or role accountable |
| Target completion date | Committed remediation date |
| Interim risk mitigation | Any compensating control while the fix is in progress (for Critical/Major findings) |
| Status | Open / In Progress / Implemented / Verified |

CAPs for **Critical** and **Major** findings are typically required within a fixed window (e.g., 30/60/90 days) with mandatory status reporting; **Minor** findings and **Observations** may be batched into the next planning cycle.

---

## 7. Follow-Up and Closure Audit

Audits are not closed by the CAP being *submitted* — they are closed by remediation being *verified*.

1. **Evidence submission** — auditee provides evidence that the corrective action was implemented (updated procedure, screenshot, config change, training record)
2. **Desk review or targeted re-audit** — auditor evaluates the evidence; Critical/Major findings usually require a targeted on-site or remote re-check rather than a desk review alone
3. **Finding disposition** — each finding is marked Verified Closed, Partially Closed (extension granted), or Not Effective (action taken but did not resolve the root cause — reopened)
4. **Closure report / certificate** — for certification audits, formal closure enables certificate issuance or maintenance; for internal/vendor audits, a closure memo suffices
5. **Trend tracking** — closed findings feed into a historical register so repeat findings across audit cycles are visible (a repeat finding is itself evidence of an ineffective corrective action and is typically escalated in severity)

---

## Contrast with IEEE 829 Test Documentation

IEEE 829 (see `IEEE_829_Test_Documentation.md`) and a compliance audit report answer different questions and are frequently confused when a project has both regulatory and QA obligations:

| | IEEE 829 Test Documentation | Compliance Audit Report |
|---|---|---|
| Question answered | Does the **product** behave as specified? | Does the **process** conform to a defined standard/policy? |
| Unit of evidence | Test cases, test logs, defect records | Interviews, sampled records, document review, observed practice |
| Primary artifact | Test Plan → Test Cases → Test Log → Test Summary Report | Scope/Criteria → Findings → CAP → Closure |
| "Finding" equivalent | Test Incident Report (a specific execution anomaly) | Audit Finding (a specific process nonconformity, graded by severity) |
| Owner | QA / Test team | Compliance, Internal Audit, or an external certification body |
| Cadence | Per release / per test cycle | Per audit cycle (often annual, with surveillance/closure audits between) |

In practice, a mature Test Strategy references IEEE 829-style documents as its **execution backbone**, while a compliance audit (if the project is regulated) references **this** structure to verify that the testing process itself — not just the product — is being run the way governance requires. Projects under frameworks like ISO 27001, PCI-DSS, HIPAA, or ISO 26262 often need both: IEEE 829 artifacts as evidence, consumed *by* an audit that follows the structure above.

---

## QAI Consultant Application

When a project involves compliance or regulatory obligations, QAI Consultant should:

1. **Trigger on Q11 (`compliance_requirements`)** — any answer other than "none" (e.g., GDPR, PCI-DSS, HIPAA, ISO 27001, ISO 26262, SOC 2) should surface this document via RAG for the Risk Register, Test Strategy, and Effort Report prompts.
2. **Test Strategy** — add a dedicated "Audit Readiness" subsection listing the applicable criteria/standard, and recommend which project artifacts (test plans, traceability matrices, sign-off records) will double as audit evidence, so testing produces reusable audit trail rather than disposable output.
3. **Risk Register** — represent audit exposure as its own risk category, with likelihood/impact informed by the severity classification above (a Critical/Major-finding risk should score materially higher than a generic functional defect of similar likelihood); reference the specific clause/requirement at risk where known (e.g., "PCI-DSS Req. 6.3.1 — insufficient evidence of pre-release security review").
4. **Effort Estimation Report** — add a line item for audit-preparation and evidence-gathering effort (document review, sample compilation, CAP drafting) when `compliance_requirements` is non-trivial; this is frequently underestimated because it is process work, not test-execution work, and is easy to omit from a testing-only estimate.
5. **Findings template propagation** — when the project is audit-relevant, encourage the same Finding ID / Evidence / Severity / Requirement-referenced structure defined in Section 4 for defect and risk tracking, so QA findings and future audit findings share a common taxonomy and are easy to cross-reference.
6. **Closure discipline** — where the project references ISO 26262 or A-SPICE (see `ASPICE_Process_Reference_Model.md`), note that those frameworks already impose their own assessment/closure cycles; QAI Consultant should avoid recommending a redundant parallel audit process and instead point to alignment between the two.
7. **Severity language consistency** — when compliance requirements are present, prefer the Critical/Major/Minor/Observation vocabulary from this document over ad hoc severity labels in generated Risk Registers, so outputs read consistently to auditors and QA stakeholders alike.
