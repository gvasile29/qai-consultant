# EU AI Act – Regulation (EU) 2024/1689 Overview

Source: Regulation (EU) 2024/1689 ("EU AI Act", self-authored public-knowledge summary — not reproduced regulatory text)
Note: Full consolidated text at eur-lex.europa.eu (official guidance: EU AI Act Service Desk); provided for QA-planning grounding as of mid-2026, not as legal advice — verify current obligations against the official text before making compliance decisions.

---

## Risk Tiers & Classification

The Act regulates AI systems through a tiered, risk-based framework. Tier placement drives which obligations (if any) apply.

- **Unacceptable risk (Article 5) — prohibited.** AI practices banned outright: social scoring by public authorities, real-time remote biometric identification in publicly accessible spaces for law enforcement (narrow exceptions apply), manipulative or deceptive techniques that materially distort behavior and cause harm, exploitation of vulnerabilities (age, disability, socio-economic situation), biometric categorization inferring sensitive attributes (race, political opinions, sexual orientation, etc.), emotion recognition in workplace and education settings (limited medical/safety exceptions), untargeted scraping of facial images to build facial recognition databases, and predictive policing based solely on profiling of an individual.
- **High risk (Article 6, Annex III, Annex I).** Two routes into this tier: (a) **Annex III use-cases** — AI used in biometrics, management of critical infrastructure, education/vocational training, employment and worker management, access to essential private/public services (e.g., credit scoring, insurance pricing, emergency dispatch), law enforcement, migration/asylum/border control, and administration of justice or democratic processes; (b) **Annex I products** — AI that is a safety component of a product already regulated under EU product-safety legislation (machinery, medical devices, toys, lifts, etc.) and therefore subject to third-party conformity assessment under that legislation.
- **Limited risk (Article 50) — transparency obligations only.** Systems that interact with people, generate synthetic content, or perform emotion recognition/biometric categorization must disclose that fact — no pre-market conformity assessment required. See Section 3.
- **Minimal risk.** Everything else (the large majority of AI systems, including most productivity and internal tooling use-cases). No mandatory obligations under the Act; voluntary codes of conduct are encouraged.

**Terminology note:** unlike "high risk" (Article 6) and "unacceptable risk" (Article 5), which the Regulation's operative articles formally define, "limited risk" and "minimal risk" are not defined classification tiers in the statute itself — Article 50 never uses the phrase "limited risk," and there is no standalone "minimal risk" article. Both terms originate from the Commission's own explanatory/popularization materials (the informal four-tier "pyramid") and are widely used pedagogically, but the uniform "Article X" citation format above shouldn't be read as implying the same degree of legal codification across all four tiers.

Tier placement is determined by **intended purpose and context of use**, not the underlying technology — the same model/technique can sit in different tiers depending on how it is deployed (e.g., a general classification model used for spam filtering vs. the same technique used for credit scoring).

**QA Focus:** Tier classification is a QA/requirements-gathering deliverable, not just a legal one — it determines test rigor, documentation depth, and which of the obligations in Sections 3–5 apply. Capture the intended purpose and deployment context explicitly during project scoping (see this app's dialogue intake) so the correct tier — and therefore the correct test strategy depth — is identified before test planning begins.

---

## Provider & Deployer Obligations

The Act assigns obligations by role in the AI value chain, not by company size or sector. The two primary roles:

- **Provider (Article 3(3)).** The entity that develops an AI system (or GPAI model), or has one developed, and places it on the market or puts it into service under its own name or trademark — whether for payment or free of charge. Providers carry the heaviest obligations because they control system design.
- **Deployer (Article 3(4)).** The entity using an AI system under its own authority in a professional capacity (personal, non-professional use is excluded). Most organizations *using* third-party AI tools are deployers, not providers.
- Two secondary roles exist but carry lighter, mostly pass-through obligations: **importers** (place a non-EU provider's system on the EU market) and **distributors** (make a system available on the market without being the provider or importer). An entity can also become a provider by substantially modifying a high-risk system or rebranding it under its own name.

**Provider obligations for high-risk systems (Article 16 and related articles):**
- **Quality management system** — establish and maintain one covering the AI system's full lifecycle
- **Conformity assessment** — carry out the applicable procedure before market placement (Section 5)
- **Technical documentation** — draw up and keep current (Article 11 — see Section 4)
- **Logging** — build in automatic event logging (Article 12 — see Section 4)
- **Registration** — register the system in the EU database before placing it on the market or putting it into service (most Annex III cases)
- **Corrective action & incident reporting** — take corrective action on non-conforming systems and report serious incidents to market surveillance authorities
- **CE marking** — affix the CE mark to indicate conformity

**Deployer obligations (Article 26 and related articles):**
- Use the system in accordance with the provider's instructions for use
- Assign human oversight to competent, trained personnel (Article 14 — see Section 4)
- Monitor operation and inform the provider/authorities of risks or serious incidents
- Ensure input data under the deployer's control is relevant and sufficiently representative for the system's intended purpose
- Keep logs generated by the system for an appropriate period, where under the deployer's control
- Inform affected workers and their representatives before deploying a high-risk system in the workplace
- Conduct a **fundamental rights impact assessment (Article 27)** — applies to specific deployer categories (bodies governed by public law, and private operators providing certain public services, plus credit/insurance use-cases) before first use
- Cooperate with market surveillance authorities

**QA Focus:** Determine which role(s) the project's organization holds — provider, deployer, or both — as an explicit early test-planning input, since it determines which obligation set (and therefore which artifacts: technical documentation vs. usage/oversight records) the test strategy needs to produce evidence for.

---

## Article 50 Transparency Obligations

Article 50 imposes disclosure duties independent of risk tier — they apply even to systems that are otherwise "limited risk," and they layer on top of high-risk obligations where both apply.

- **Article 50(1) — direct interaction disclosure.** Providers of AI systems intended to interact directly with natural persons must ensure people are informed they are interacting with an AI system, unless this is obvious from the circumstances to a reasonably well-informed person.
- **Article 50(2) — synthetic content marking.** Providers of AI systems — including general-purpose AI *systems* — that generate synthetic audio, image, video, or text content must mark outputs in a machine-readable format as artificially generated or manipulated, and ensure detection is technically feasible, reliable, and interoperable. Note the distinction: this targets GPAI *systems* (an AI system built on top of a GPAI model), not GPAI *models* themselves (the foundation model, governed separately under Chapter V, Articles 51–56, with its own transparency/documentation duties under Article 53).
- **Article 50(3) — emotion recognition / biometric categorization disclosure.** Deployers of such systems must inform exposed individuals of the system's operation.
- **Article 50(4) — deepfake and public-interest text disclosure.** Deployers generating or manipulating deepfake content must disclose its artificial nature; deployers publishing AI-generated or -manipulated text on matters of public interest must disclose this unless the content has undergone human review with editorial responsibility.

**This app's own compliance posture:** QAI Consultant is itself a provider-side implementer of Article 50. The v2.5.2 patch (`src/ai_disclosure.py`) added a persistent sidebar notice (`AI_INTERACTION_NOTICE`, aligned with Article 50(1) — a standing disclosure, not a one-time dismissible banner, since the disclosure obligation does not lapse after first viewing) and a visible "AI-generated content" footer (`with_ai_footer()`) appended to every generated document — Risk Register, Effort Estimation Report, Test Strategy, and Test Plan — in both Markdown and PDF output, in the spirit of Article 50(2)'s output-marking intent. Machine-readable marking (structured YAML front matter / PDF metadata, as opposed to human-visible labeling) remains a later roadmap item, tracked separately.

**QA Focus:** When a project under evaluation involves a chatbot, virtual assistant, or any content-generation feature, explicitly test for the presence, visibility, and persistence of AI-interaction/AI-content disclosures as an acceptance criterion — not just as a legal checkbox, but as a testable UI/output requirement with its own pass/fail condition.

---

## Articles 9–15 — Testing Implications for High-Risk AI Systems

These articles are the Act's technical-requirements core for high-risk AI systems, and they map directly onto concrete QA activities. This is the most actionable section for grounding a generated Test Strategy.

- **Article 9 — Risk management system.** Requires a continuous, iterative process across the full lifecycle: identify and analyze known/foreseeable risks, estimate and evaluate risks arising from both intended use and reasonably foreseeable misuse, and adopt risk-mitigation measures, tested and validated before market placement and after substantial modification.
  **QA activity:** Maintain a living AI-specific risk register (bias, robustness, safety, misuse scenarios) as a first-class test-planning artifact; re-run risk-based test cycles after every substantial model or system update, not just at initial release.

- **Article 10 — Data and data governance.** Training, validation, and testing datasets must be relevant, sufficiently representative, and — to the best extent possible — free of errors and complete for the intended purpose; data must be examined for possible biases likely to affect health, safety, or fundamental rights.
  **QA activity:** Design explicit data-quality test cases (completeness, representativeness, error rates); run bias/fairness testing across protected attributes; verify data lineage and provenance documentation as part of test evidence.

- **Article 11 — Technical documentation.** Must be drawn up before the system is placed on the market, kept up to date, and contain the information specified in Annex IV — including design specifications, capabilities and limitations, and validation/testing results.
  **QA activity:** Produce and retain traceable verification & validation reports; ensure every test-coverage or accuracy claim in the documentation is backed by reproducible test evidence, since this documentation is what a conformity assessment or audit will inspect.

- **Article 12 — Record-keeping (logging).** High-risk systems must have automatic logging capabilities appropriate to their intended purpose, enabling traceability of the system's operation across its lifecycle.
  **QA activity:** Test logging completeness and integrity, log retention against required periods, tamper-resistance of audit trails, and reconstructability of a decision from logs alone.

- **Article 13 — Transparency and provision of information to deployers.** Providers must supply instructions for use covering the system's characteristics, capabilities, known limitations, and declared accuracy metrics, plus foreseeable misuse.
  **QA activity:** Validate that documented accuracy/performance figures match actual measured test results (no aspirational numbers in instructions); usability-test the instructions themselves against real deployer comprehension.

- **Article 14 — Human oversight.** Requires measures enabling assigned humans to understand system output, monitor operation, and intervene — including the ability to override or stop the system ("human-in-the-loop," "on-the-loop," or "in-command" designs).
  **QA activity:** Test override/stop mechanisms end-to-end, run usability testing on oversight interfaces, verify escalation paths, and design scenario tests specifically probing automation bias (does the human overseer actually catch and correct wrong AI output, or defer to it by default?).

- **Article 15 — Accuracy, robustness, and cybersecurity.** Systems must achieve an appropriate level of accuracy throughout their lifecycle, be resilient to errors and inconsistencies, and be resilient against attempts to manipulate their behavior (e.g., data poisoning, adversarial examples, model evasion) or exfiltrate model/data confidentiality; declared accuracy metrics must be stated in the instructions for use.
  **QA activity:** Run accuracy/performance benchmark testing against the declared metrics from Article 13's documentation; conduct adversarial robustness and security testing (including simulated data-poisoning and adversarial-input attacks); include model-drift monitoring as a recurring, not one-off, test cycle.

**QA Focus:** These seven articles form a natural checklist for scoping a Risk Register and Test Strategy on any project the intake dialogue flags as a high-risk AI system — each article should produce at least one traceable test activity in the generated Test Plan, and this maps naturally onto ISTQB CT-AI/CT-GenAI test-type guidance already in this knowledge base.

---

## Conformity Assessment

Before a high-risk system is placed on the market or put into service, the provider must complete a conformity assessment and be able to demonstrate compliance with Articles 9–15.

- **Self-assessment (internal control, Annex VI).** The default route for Annex III points 2–8 (critical infrastructure, education, employment, essential services, law enforcement, migration/border control, administration of justice) — the provider assesses conformity itself against the requirements, without third-party involvement, provided a quality management system (Article 17) is in place. For Annex III point 1 ("Biometrics" — covering biometric identification, biometric categorization, *and* emotion recognition, not narrowly "remote biometric identification"), Annex VI self-assessment is also an option, but only where the provider has applied harmonized standards or common specifications (Article 43(1)).
- **Notified body assessment (Annex VII).** Mandatory for Annex III point 1 ("Biometrics") systems specifically where harmonized standards or common specifications were not applied, were only partially applied, or are unavailable. Also required for any high-risk system that is a safety component of a product already subject to third-party assessment under existing EU product-safety legislation (Annex I products, e.g., medical devices, machinery).
- **EU declaration of conformity & CE marking.** On successful assessment, the provider draws up an EU declaration of conformity and affixes the CE marking before the system is placed on the market.
- **EU database registration.** Providers (and, for certain public-sector deployments, deployers) must register the high-risk system in the EU-wide public database before market placement or putting into service — the primary public transparency mechanism for high-risk AI systems.
- **Post-market monitoring (Article 72).** Conformity assessment is not a one-time gate — providers must maintain a post-market monitoring system proportionate to the system's risks, feeding back into the Article 9 risk-management process.

**QA Focus:** Conformity assessment route (self- vs. notified-body) determines how much external, independent evidence a test program needs to produce — self-assessed systems still need audit-ready test evidence even without an external assessor, since market surveillance authorities can request it post-market.

---

## Timeline & Deadlines

**Original Regulation (EU) 2024/1689 — as adopted:**

| Milestone | Date |
|---|---|
| Entry into force | 1 August 2024 |
| Prohibited practices (Article 5) become applicable | 2 February 2025 |
| GPAI model obligations, governance, and penalty provisions become applicable | 2 August 2025 |
| General applicability — most provisions, including high-risk Annex III obligations and Article 50 transparency | 2 August 2026 |
| High-risk AI as a safety component under Annex I product legislation | 2 August 2027 |

**Amended timeline — Digital Omnibus on AI (adopted 2026):**

The Commission's "Digital Omnibus" package, proposed in November 2025, amends several digital regulations (including the AI Act, GDPR, and the Data Act) to ease compliance burden. For the AI Act specifically, this package has now completed the EU's ordinary legislative procedure: the European Parliament adopted the text on 16 June 2026 (423 in favour, 57 against, 174 abstentions), and the Council gave its final adoption on 29 June 2026. As of this document's authoring it is a formally adopted amending act, pending publication in the Official Journal (expected before 2 August 2026) to enter into force — no longer an unresolved proposal.

Confirmed changes for the AI Act:
- **Annex III standalone high-risk systems.** Full Articles 9–15 compliance obligations move from 2 August 2026 to **2 December 2027**, reflecting the unavailability, at the time of the original deadline, of the harmonized standards and support tools (e.g., an EU-provided compliance toolkit) providers need to actually meet those requirements.
- **Annex I product-embedded high-risk systems.** Obligations move from the original 2 August 2027 to **2 August 2028** — a one-year deferral for the same underlying reason.
- **Article 50(2) machine-readable marking grace period.** Generative AI systems already placed on the market before 2 August 2026 have until **2 December 2026** (four months past the original deadline) to meet the machine-readable synthetic-content marking requirement specifically.
- A new prohibition was also added: AI systems designed to generate non-consensual intimate imagery ("nudification" tools) or CSAM.

**Remaining caveat.** These dates reflect the adopted co-legislator text as publicly reported; formal Official Journal publication — and with it the precise legal entry-into-force date — was still pending as of this document's authoring, so treat the exact statutory citation as provisional until confirmed against the published text. This project's own v2.5.2 release notes independently arrived at **2 December 2026** as a working assumption for the Article 50(2) grace period; that figure is now corroborated by the adopted package rather than being purely this project's own guess, but the same "verify before relying on it" discipline still applies until Official Journal publication.

**Practical guidance:** for any project where the exact compliance deadline materially affects test planning or release timing, verify the current status directly against the EU AI Act Service Desk (digital-strategy.ec.europa.eu) or the consolidated EUR-Lex text rather than relying on any single date cited here.

**QA Focus:** Do not hard-code a single compliance deadline into a generated Test Strategy for a high-risk AI project — instead, flag the applicable-date uncertainty explicitly as a project risk (schedule risk tied to regulatory timeline) and recommend the project team confirm the current applicable date before finalizing release-readiness criteria.
