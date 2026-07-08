# ISO 19011 — Guidelines for Auditing Management Systems

Source: Compiled from public knowledge — ISO 19011:2018, "Guidelines for auditing management systems," third edition, publicly summarized by ISO and accredited certification bodies.
License: Summary derived from publicly available standard descriptions; not a reproduction of the licensed ISO text.

---

## Overview

ISO 19011 is a guidance standard — not a certifiable requirements standard — that describes how to plan, manage, and conduct audits of any management system, whether quality (ISO 9001), environmental (ISO 14001), information security (ISO/IEC 27001), or a QA/software process framework audited the same way. It is deliberately generic: it applies equally to internal audits, supplier audits, and certification audits, and it treats "the audit" as a repeatable process rather than a one-off inspection. For QAI Consultant, ISO 19011 is the reference for *how the QA process itself gets checked* — as distinct from ISTQB (how testing is executed) or IEEE 829 (how testing is documented). It matters whenever a project's QA process, not just its product, is subject to audit — by a customer, a regulator, or an internal quality function.

---

## The Seven Audit Principles

ISO 19011:2018 Clause 4 defines seven principles that underpin the reliability of any audit conclusion. An audit that violates one of these principles produces findings that cannot be trusted, regardless of how thorough the checklist was.

| # | Principle | What it means in practice |
|---|---|---|
| 1 | **Integrity** | The foundation of professionalism: auditors act with honesty, diligence, and responsibility; observe applicable legal requirements; and remain unbiased even under organizational pressure. |
| 2 | **Fair presentation** | Findings, conclusions, and reports reflect audit activities truthfully and accurately — including significant disagreements between the audit team and the auditee, not just the convenient conclusion. |
| 3 | **Due professional care** | Auditors apply diligence and sound judgment, exercising the level of care an experienced professional would apply given the significance of the task and the confidence placed in them by stakeholders. |
| 4 | **Confidentiality** | Audit information is treated with discretion — auditors do not use information inappropriately for personal gain or in a way that harms the auditee's legitimate interests. |
| 5 | **Independence** | The auditor is free of bias and conflict of interest; wherever practicable, auditors are independent of the activity being audited (internal audits use auditors independent of the function under review). |
| 6 | **Evidence-based approach** | Conclusions rest on a rational method for arriving at reliable, reproducible results using a verifiable sample of available information — audit evidence must be verifiable, not anecdotal. |
| 7 | **Risk-based approach** | The audit approach itself is proportionate to the risks and opportunities of the audited process — added in the 2018 edition, formalizing what was implicit practice before. |

---

## Audit Types by Party

ISO 19011 recognizes three categories of audit, distinguished by the relationship between the auditor and the organization being audited. QAI Consultant should identify which type applies because it changes both the independence requirements and the appropriate output format.

| Type | Also called | Performed by | Typical purpose |
|---|---|---|---|
| **First-party** | Internal audit | The organization's own personnel or a mandated internal function | Self-assessment, continuous improvement, management review input |
| **Second-party** | Supplier/customer audit | A customer, or someone acting on the customer's behalf | Contract due diligence, supplier qualification, ongoing vendor oversight |
| **Third-party** | External/certification audit | An independent auditing organization (e.g., a certification body) | Certification, accreditation, or regulatory compliance attestation |

Combined audits (multiple management systems audited together, e.g., quality + information security) and joint audits (two or more auditing organizations auditing one auditee together) are also addressed by the standard but are edge cases QAI Consultant does not need to model explicitly.

---

## Managing an Audit Programme

An "audit programme" is the set of one or more audits planned for a specific time frame and directed toward a specific purpose — distinct from a single audit engagement. ISO 19011 Clause 5 describes the programme as a cycle:

1. **Establishing programme objectives** — tied to management system policy, business priorities, and stakeholder requirements.
2. **Determining and evaluating programme risks and opportunities** — availability of competent auditors, complexity of the auditee's processes, communication and language barriers, use of remote vs. on-site auditing, and the consequences of a poorly executed audit.
3. **Establishing the programme** — roles/responsibilities, competence requirements, scope, resources, and procedures.
4. **Implementing the programme** — scheduling individual audits, selecting audit teams, managing audit records.
5. **Monitoring the programme** — reviewing whether objectives are met, whether the programme itself is delivering value.
6. **Reviewing and improving the programme** — feeding lessons learned back into the next planning cycle.

This is the level at which an organization decides *how often* a given process gets audited, and it is where audit fatigue, resourcing gaps, and stale audit criteria are usually rooted.

---

## The Audit Process (Clause 6)

A single audit, once initiated under the programme, follows five phases:

1. **Initiating the audit** — appointing the audit team leader, defining objectives/scope/criteria, confirming feasibility, establishing initial contact with the auditee, and agreeing on logistics and dates.
2. **Preparing audit activities** — reviewing documented information, preparing the audit plan, assigning work within the audit team, and preparing working documents (checklists, sampling plans, evidence-collection forms).
3. **Conducting the audit** — holding the opening meeting, collecting and verifying evidence through interviews, observation, and document/record review; generating audit findings; and reviewing findings against audit criteria.
4. **Preparing and distributing the audit report** — holding the closing meeting, agreeing on findings and any disagreements, and issuing a report that fairly and accurately reflects the audit's conduct and conclusions.
5. **Completing the audit and conducting follow-up** — archiving records, and — where corrective actions were required — verifying that they were implemented and effective within an agreed timeframe. An audit is not "closed" until follow-up confirms remediation, not merely promised.

### Audit Evidence and Findings — Quick Checklist

- [ ] Audit criteria (which standard, procedure, or contractual requirement) are defined *before* evidence collection begins
- [ ] Evidence is verifiable — records, statements of fact, or other information relevant to the criteria
- [ ] Sampling method and rationale are documented (audits sample; they rarely inspect 100% of records)
- [ ] Findings are categorized (conformity / nonconformity / opportunity for improvement) against stated criteria, not auditor opinion
- [ ] Nonconformities are traceable to a specific criterion, with objective evidence cited
- [ ] The auditee has an opportunity to respond to findings before the report is finalized

---

## Auditor Competence and Evaluation (Clause 7)

ISO 19011 treats auditor competence as the product of personal behavior plus demonstrated knowledge and skills — not a certificate alone. The standard's competence-evaluation process has four steps:

1. **Determine competence criteria** — qualitative and quantitative, considering audit programme volume, scope, complexity, and the maturity of the management system.
2. **Establish evaluation methods** — e.g., review of records, feedback, interview, observation, testimonials.
3. **Conduct the evaluation** — against the established criteria, using two or more of the methods above for reliability.
4. **Maintain and improve competence** — through continual professional development, participation in audits, training, and periodic re-evaluation.

Personal behaviors the standard calls out explicitly include: ethical, open-minded, diplomatic, observant, perceptive, versatile, tenacious, decisive, self-reliant, acting with fortitude, being open to improvement, culturally sensitive, and collaborative. Knowledge/skill domains span audit principles and methods, the applicable management system standard(s) and reference documents, the organizational context, applicable legal/regulatory requirements, and (for audit team leaders) leadership and negotiation skill.

---

## QAI Consultant Application

When a project involves formal process audits (customer supplier audits, regulatory audits, or certification against a management system standard), QAI Consultant should:

1. **Surface it via Dialogue Question 3 (compliance/regulatory context) and Question 6 (project constraints)** — ask explicitly whether the project is subject to first-, second-, or third-party audits, and by whom, since this changes both deliverable format and independence expectations for the QA function itself.
2. **Risk Register — add an "Audit & Compliance Readiness" risk category** whenever an audit is disclosed: flag gaps such as undocumented audit criteria, no evidence trail for QA activities, or no defined nonconformity/CAPA process, using the risk-based approach principle (#7) to weight audit-readiness risks by the consequence of a failed audit (e.g., lost certification, contract breach).
3. **Test Strategy — include a short "Process Audit Traceability" subsection** describing how test evidence (test records, defect logs, review minutes) will be retained and indexed so it can serve as audit evidence per the evidence-based approach principle (#6) — this is distinct from IEEE 829 documentation completeness; ISO 19011 concerns *retrievability and traceability under audit*, not just document existence.
4. **Effort Report — add an explicit line item for audit preparation and follow-up** (evidence compilation, mock audit / internal audit dry-run, corrective-action verification) when a second- or third-party audit is disclosed; this is frequently omitted from QA effort estimates and becomes a late-project schedule risk.
5. **Recommend an internal (first-party) audit cadence** ahead of any known second/third-party audit date, using the audit-programme management guidance (Clause 5) — internal audits should be scheduled early enough that findings can be remediated before the external audit, not discovered by it.
6. **Distinguish audit findings from test defects in generated documents** — an "audit nonconformity" is a process-conformance gap against a stated criterion (e.g., a procedure, standard, or contract clause), not a product defect; QAI Consultant should never conflate the two in the Risk Register or Test Strategy.
7. **When the disclosed auditor relationship is second-party (a customer audits the supplier's QA process)**, recommend the Test Strategy explicitly reference which audit criteria (contract clauses, referenced standards) the QA process is designed to satisfy — this maps directly to the "fair presentation" and "evidence-based approach" principles the customer's auditor will apply.
8. **Flag auditor independence conflicts** if the dialogue reveals that the same individuals both execute testing and would sign off on the internal audit of that testing — recommend segregation consistent with the independence principle (#5), especially for CMMI/A-SPICE-adjacent process assessments layered on top of the QA workstream.
