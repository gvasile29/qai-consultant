# OWASP ASVS — Application Security Verification Standard

Source: Compiled from public knowledge — OWASP Application Security Verification Standard, versions 4.0.3 and 5.0.0 (released 2025), publicly available at owasp.org/www-project-application-security-verification-standard
License: Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0)

---

## Overview

The OWASP Application Security Verification Standard (ASVS) is a checklist-style framework for defining and verifying the security controls a web application or API must implement. Unlike a risk catalog or a testing guide, ASVS exists to answer one question: *does this application meet a defined, auditable bar of security assurance?* It organizes hundreds of granular, testable requirements into chapters (V1–V14 in version 4.0.3; 17 chapters in the 5.0.0 restructuring) and tags every requirement with the minimum verification level at which it applies. ASVS 5.0.0 was released at Global AppSec EU Barcelona in 2025 and reorganized the chapter set while keeping the three-level model intact.

---

## The Three Verification Levels

ASVS levels are cumulative — Level 2 requires everything in Level 1 plus its own controls, and Level 3 requires everything in Levels 1 and 2 plus its own controls. A level is not a difficulty rating; it is a statement about what class of application the standard is being applied to and how much assurance the business needs.

| Level | Name | Applies To | Verification Approach | Approx. Requirement Coverage |
|---|---|---|---|---|
| **L1** | Opportunistic | All software, with no exceptions — the floor for anything internet-facing | Fully black-box; testable from the outside without source access, using tools and manual probing | Defends against the vulnerability classes in the OWASP Top 10 that are "easy to discover" |
| **L2** | Standard | Applications handling sensitive data — PII, healthcare, financial transactions, credentials, most B2B/B2C SaaS | Requires access to documentation, architecture, and source; the default target for most commercial audit engagements | The substantial majority of real-world requirements (access control, authentication, session management, input validation, cryptography, business logic) |
| **L3** | Advanced | High-value transactions, critical infrastructure, safety-of-life systems, or any application where the business explicitly requires the highest assurance | Deepest verification — architecture review, threat modeling artifacts, defense-in-depth checks | The final layer: defense-in-depth mechanisms and controls that are useful but expensive to implement and verify |

A practical litmus test used by auditors: if a breach of the application would cause regulatory, financial, or safety consequences beyond simple reputational damage, it does not belong at L1.

---

## ASVS Chapters at a Glance

ASVS 4.0.3 organizes its 286 verification requirements into 14 chapters. ASVS 5.0.0 (2025) restructured this into 17 chapters — splitting and renaming several areas for clarity — but the underlying control intent is preserved. Auditors working against an older codebase or an older compliance contract may still be asked to verify against 4.0.3; new engagements should default to 5.0.0.

| # | ASVS 4.0.3 Chapter | Typical Focus |
|---|---|---|
| V1 | Architecture, Design and Threat Modeling | Secure SDLC evidence, threat models exist and are maintained |
| V2 | Authentication | Credential handling, MFA, password policy, anti-automation |
| V3 | Session Management | Token generation, expiry, invalidation on logout/privilege change |
| V4 | Access Control | Authorization enforcement, least privilege, deny-by-default |
| V5 | Validation, Sanitization and Encoding | Input validation, output encoding, injection prevention |
| V6 | Stored Cryptography | Key management, algorithm choice, secrets storage |
| V7 | Error Handling and Logging | Safe error messages, audit trails, log integrity |
| V8 | Data Protection | Data classification, sensitive data handling, client-side storage |
| V9 | Communication | TLS configuration, certificate validation |
| V10 | Malicious Code | Code integrity, anti-tampering, backdoor prevention |
| V11 | Business Logic | Business-rule enforcement, workflow abuse prevention |
| V12 | Files and Resources | Upload handling, path traversal, resource exhaustion |
| V13 | API and Web Service | REST/SOAP/GraphQL-specific controls |
| V14 | Configuration | Hardening, dependency management, build pipeline security |

ASVS 5.0.0 (released May 30, 2025) reorganizes these into 17 chapters (V1–V17) — for example, the old V5 "Validation, Sanitization and Encoding" splits into V1 "Encoding and Sanitization" and V2 "Validation and Business Logic," and the old V6 "Stored Cryptography" broadens into a single V11 "Cryptography" chapter. It also adds first-class chapters for areas that had outgrown a subsection, including V9 "Self-Contained Tokens," V10 "OAuth and OIDC," V3 "Web Frontend Security," and an entirely new V17 "WebRTC." For QAI Consultant's purposes, the chapter list matters less than the level tagging — every requirement, in either version, still resolves to L1, L2, or L3.

---

## How ASVS Complements the Top 10 and WSTG (Already in This KB)

QAI Consultant's knowledge base already contains the OWASP Top 10 (risk taxonomy) and the OWASP Web Security Testing Guide (WSTG, testing methodology). ASVS is not a third, redundant document — it occupies a distinct role in the security lifecycle:

| Document | Answers | Artifact It Produces | When It Is Used |
|---|---|---|---|
| **OWASP Top 10** | "What are the most common categories of risk?" | A prioritized risk list (A01–A10) | Early — risk identification and awareness |
| **OWASP WSTG** | "How do I test for a given vulnerability?" | Test cases / test procedures per vulnerability class | During test design and execution |
| **OWASP ASVS** | "Does this system meet a defined, sign-off-able bar of security controls?" | A pass/fail control checklist per requirement, tied to a target level (L1/L2/L3) | Audit / verification / compliance sign-off, before release or as a periodic assurance exercise |

In short: the Top 10 tells you *what could go wrong*, the WSTG tells you *how to check for it*, and ASVS tells you *what "good enough" looks like and whether you've actually reached it*. A mature program uses all three together — Top 10 to scope risk, WSTG to build the test plan, ASVS to define the acceptance bar and produce the audit evidence that a specific level was met.

---

## How a Security Audit Differs from a Security Test

This distinction matters because QAI Consultant currently frames most outputs around *testing* (Test Strategy, Test Plan), while ASVS belongs to a distinct discipline: *auditing*.

| Dimension | Security Test | Security Audit (ASVS-based) |
|---|---|---|
| **Goal** | Find vulnerabilities | Verify compliance against a defined standard |
| **Question answered** | "Can this be broken?" | "Does this meet the required control level?" |
| **Output** | Bug/defect list, exploit proof-of-concept | Compliance checklist with pass/fail per requirement, gap report, sign-off status |
| **Scope driver** | Attacker creativity, threat model, exploratory coverage | A fixed, versioned requirement list (ASVS L1/L2/L3) |
| **Repeatability** | Varies by tester skill and time-box | Standardized — same checklist, same level, comparable across audits and vendors |
| **Typical actor** | Penetration tester, security QA engineer | Auditor, compliance assessor, sometimes a third party for independence |
| **Cadence** | Ad hoc, per-sprint, per-release | Periodic (e.g., annual) or gate-based (e.g., before a compliance certification) |
| **Failure consequence** | Defect ticket, fix-and-retest | Non-conformance, may block certification, contractual, or regulatory sign-off |

A security test can exist without any audit (e.g., an exploratory pentest with no standard behind it). A security audit, by definition, requires a standard to audit against — ASVS is the most widely adopted such standard for web/API applications, playing a role analogous to what A-SPICE plays for automotive process capability or ISO 25010 plays for quality characteristics.

---

## Using ASVS in Practice: A Minimal Verification Checklist

1. **Determine the target level** — driven by data sensitivity and business/regulatory context, not by developer preference. Default to L2 for anything handling personal or transactional data.
2. **Select the applicable chapters** — not every chapter applies to every architecture (e.g., a pure API-only service may deem client-side chapters non-applicable; document and justify any exclusion).
3. **Map existing controls to requirements** — for each requirement at the target level, record: implemented / partially implemented / not implemented / not applicable (with justification).
4. **Gather verification evidence** — code review notes, config snapshots, test results, architecture diagrams; an ASVS audit is only credible with evidence, not attestation alone.
5. **Produce a gap report** — every "not implemented" or "partially implemented" item becomes a finding with a severity and an owner.
6. **Re-verify after remediation** — audits are not one-shot; re-check remediated items before declaring the target level achieved.
7. **Re-baseline periodically** — ASVS versions evolve (4.0.3 → 5.0.0 restructured from 14 to 17 chapters); a previously "L2-compliant" system should be re-mapped against the current version on a defined cadence, not assumed to remain compliant indefinitely.

---

## Evidence Expected at Each Level

Auditors reject a self-attested "we meet L2" claim without supporting evidence. The evidence bar rises with the level:

| Level | Minimum Evidence Expected | Who Typically Signs Off |
|---|---|---|
| L1 | Automated scan output (DAST/SAST), a completed OWASP Top 10 checklist, manual spot-check of the highest-risk flows | QA lead or internal security champion |
| L2 | L1 evidence, plus source-code review notes per chapter, architecture diagrams, authentication/session configuration exports, a documented data classification | Internal security team or external auditor |
| L3 | L2 evidence, plus a maintained threat model, defense-in-depth control mapping, independent third-party verification, and a re-verification record after each material architecture change | External/independent auditor, often required for formal certification |

A common audit failure mode is treating L2 as "run more scanners." Scanners (SAST/DAST) only ever produce L1-grade evidence — they detect the easy-to-discover classes of vulnerability the Top 10 already names. L2 and L3 requirements (business logic abuse, session invalidation edge cases, defense-in-depth architecture) are inherently manual and cannot be fully automated; a Test Strategy that promises "L2 compliance via CI security scanning alone" is understating the required effort.

---

## Common Pitfalls When Adopting ASVS

- **Treating ASVS as a testing checklist instead of an audit standard.** Running through ASVS requirements as ad hoc manual tests without recording pass/fail evidence produces a test report, not an audit artifact — it cannot be used for sign-off.
- **Picking a level without a stated reason.** "We target L2" without linking it to the data classification or regulatory driver is not defensible in a real audit; the target level should trace back to a specific answer in the project context (see Question 11 below).
- **Conflating ASVS coverage with Top 10 coverage.** Passing all OWASP Top 10 checks is roughly equivalent to partial L1, not full L1 — ASVS L1 is broader than the ten Top 10 categories.
- **Stale re-verification.** An application audited against ASVS a year ago, with no re-check after subsequent releases, should not be represented as currently compliant.
- **Ignoring "not applicable" documentation.** Marking a requirement "N/A" without a written justification is a common finding in ASVS-based audits and should not appear un-explained in any generated compliance summary.

---

## Where ASVS Sits Relative to Named Compliance Frameworks

Project stakeholders frequently name a regulatory framework (PCI-DSS, HIPAA, SOC 2, GDPR) rather than ASVS directly when describing compliance needs — because that is the framework their business is actually contractually or legally bound to. ASVS is not a replacement for these; it is a practical, application-layer control set that helps satisfy the *technical security* portion of most of them.

| Named Framework | What It Covers | How ASVS Helps |
|---|---|---|
| PCI-DSS | Payment card data handling | ASVS V2 (Authentication), V6 (Cryptography), V9 (Communication) map closely to PCI-DSS technical requirements for cardholder data environments |
| HIPAA | Protected health information (PHI) | ASVS V8 (Data Protection) and V7 (Logging) support HIPAA's access-control and audit-trail technical safeguards |
| SOC 2 | Trust service criteria (security, availability, confidentiality) | ASVS provides a concrete, testable control set that auditors can point to as evidence for the "Security" criterion |
| GDPR | Personal data protection | ASVS V8 (Data Protection) supports GDPR's "appropriate technical measures" requirement, though GDPR also has legal/process obligations ASVS does not cover |

The practical implication: when a project names one of these frameworks, ASVS is a reasonable technical control set to recommend, but the generated documents should be explicit that ASVS coverage is necessary, not sufficient — legal, contractual, and process obligations under the named framework still require separate review outside QAI Consultant's scope.

---

## QAI Consultant Application

When a project's context indicates it is a candidate for formal security audit (not just security testing), QAI Consultant should:

1. **Surface it via Question 11 (`compliance_requirements`)** — "Are there any compliance or regulatory requirements?" If the answer references PCI-DSS, HIPAA, SOC 2, GDPR, financial services, healthcare, or any explicit security certification, treat ASVS as directly applicable and retrieve this document during RAG for the Risk Register, Test Strategy, and Test Plan generation steps.
2. **Cross-check against Question 3 (`product_type`) and Question 4 (`tech_stack`)** — ASVS applies most directly to web applications and APIs; if the product type is a native mobile app, prefer MASTG (already in this KB) as the primary audit standard and cite ASVS only for shared backend/API components.
3. **Recommend a target verification level in the Test Strategy** — L1 as the floor for any internet-facing system with no stated compliance driver; L2 by default once `compliance_requirements` names sensitive data handling; L3 only when the project description or known risks indicate high-value transactions or safety-critical data.
4. **Add an "ASVS Compliance Gap" risk category to the Risk Register** — distinct from generic security risks sourced from the Top 10. Each gap should be framed as a specific unmet requirement (e.g., "session tokens not invalidated server-side on logout — L1 gap") rather than a generic "authentication risk," and should carry its own likelihood/impact scoring consistent with the rest of the Risk Register.
5. **Separate "security testing" from "security audit" as distinct workstreams in the Test Strategy** — the strategy document should explicitly state which OWASP artifact backs which activity: WSTG-based test cases for the testing workstream, ASVS-based checklist verification for the audit/sign-off workstream, so stakeholders do not conflate "we ran security tests" with "we are ASVS-compliant."
6. **Reflect audit effort in the Effort Estimation Report** — an ASVS-based audit (evidence gathering, control mapping, gap remediation, re-verification) is a materially different, typically larger effort line than exploratory or scripted security testing; when `compliance_requirements` triggers ASVS applicability, the effort estimator's narrative should call out audit effort as a separate activity rather than folding it into generic "security testing" hours.
7. **Recommend the target level explicitly in generated documents** — every mention of ASVS in output should state which level (L1/L2/L3) is being targeted and why, since an unqualified "ASVS compliance" claim is not actionable or auditable.
8. **Flag version currency** — if a project references an old ASVS version, or has not re-verified against the current version in over a year, the Risk Register should include a "standard currency" finding, since ASVS is a living, versioned standard (4.0.3 → 5.0.0) rather than a fixed document.
