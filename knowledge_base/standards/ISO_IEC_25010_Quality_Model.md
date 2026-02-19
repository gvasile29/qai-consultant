# ISO/IEC 25010 – Software Product Quality Model

Source: ISO/IEC 25010:2011 (public knowledge summary)
Note: Full standard available for purchase at iso.org

---

## Overview

ISO/IEC 25010 defines a quality model for software products and systems. It is part of the SQuaRE (System and Software Quality Requirements and Evaluation) series. The standard provides a framework for:

- Specifying software quality requirements
- Evaluating software quality
- Establishing quality metrics

This model is fundamental for any QA strategy because it defines **what quality means** for a software system.

---

## The Two Quality Models

### 1. Product Quality Model
Defines 8 main quality characteristics, each with sub-characteristics.

### 2. Quality in Use Model
Defines 5 characteristics related to the outcome of using the product in a specific context.

---

## Product Quality Model — 8 Characteristics

### 1. Functional Suitability
The degree to which the product provides functions that meet stated and implied needs.

**Sub-characteristics:**
- **Functional Completeness** — all specified functions are present
- **Functional Correctness** — functions produce correct results
- **Functional Appropriateness** — functions facilitate accomplishment of specified tasks

**QA Focus:** Functional testing, acceptance testing, requirements coverage

---

### 2. Performance Efficiency
Performance relative to the amount of resources used under stated conditions.

**Sub-characteristics:**
- **Time Behaviour** — response times, processing times, throughput
- **Resource Utilization** — CPU, memory, disk, network usage
- **Capacity** — maximum limits that meet requirements

**QA Focus:** Performance testing, load testing, stress testing, scalability testing

---

### 3. Compatibility
Degree to which the product can exchange information and perform required functions while sharing the same environment.

**Sub-characteristics:**
- **Co-existence** — operates alongside other products sharing resources
- **Interoperability** — can exchange and use information with other systems

**QA Focus:** Integration testing, API testing, compatibility testing across environments

---

### 4. Usability
Degree to which the product can be used by specified users to achieve specified goals with effectiveness, efficiency, and satisfaction.

**Sub-characteristics:**
- **Appropriateness Recognizability** — users can recognize if the product is appropriate
- **Learnability** — ease of learning to use the product
- **Operability** — ease of operation and control
- **User Error Protection** — protection against errors by users
- **User Interface Aesthetics** — pleasing and satisfying interface
- **Accessibility** — accessible to people with widest range of characteristics

**QA Focus:** UX testing, accessibility testing, usability testing sessions

---

### 5. Reliability
Degree to which the system performs specified functions under specified conditions for a specified period of time.

**Sub-characteristics:**
- **Maturity** — meets needs for reliability under normal operation
- **Availability** — system is operational and accessible when required
- **Fault Tolerance** — operates as intended despite hardware or software faults
- **Recoverability** — can recover data and re-establish desired state after failure

**QA Focus:** Reliability testing, failover testing, disaster recovery testing, chaos engineering

---

### 6. Security
Degree to which the product protects information and data so that persons or other products have the degree of data access appropriate to their types and levels of authorization.

**Sub-characteristics:**
- **Confidentiality** — data accessible only to those authorized
- **Integrity** — system prevents unauthorized access or modification
- **Non-repudiation** — actions can be proven to have occurred
- **Accountability** — actions traced to the entity that performed them
- **Authenticity** — identity of subject or resource can be proved

**QA Focus:** Security testing, penetration testing, OWASP compliance, vulnerability scanning

---

### 7. Maintainability
Degree of effectiveness and efficiency with which the product can be modified.

**Sub-characteristics:**
- **Modularity** — system is composed of discrete components
- **Reusability** — asset can be used in more than one system
- **Analysability** — ease of assessing impact of changes or diagnosing deficiencies
- **Modifiability** — product can be effectively and efficiently modified without defects
- **Testability** — effectiveness and efficiency of establishing test criteria and running tests

**QA Focus:** Code review, static analysis, test coverage metrics, technical debt assessment

---

### 8. Portability
Degree of effectiveness and efficiency with which the system can be transferred from one hardware, software, or other operational/usage environment to another.

**Sub-characteristics:**
- **Adaptability** — can be effectively and efficiently adapted to different environments
- **Installability** — can be effectively installed or uninstalled in a specified environment
- **Replaceability** — can replace another specified software product for the same purpose

**QA Focus:** Cross-platform testing, installation testing, migration testing

---

## Quality in Use Model — 5 Characteristics

| Characteristic | Description |
|---|---|
| **Effectiveness** | Accuracy and completeness with which users achieve goals |
| **Efficiency** | Resources expended in relation to accuracy and completeness |
| **Satisfaction** | Degree to which user needs are satisfied |
| **Freedom from Risk** | Degree to which product mitigates risk to economic status, human life, health, or environment |
| **Context Coverage** | Degree to which product can be used with effectiveness, efficiency, and satisfaction in both specified contexts and beyond |

---

## Applying ISO/IEC 25010 in Test Strategy

### Step 1 — Quality Requirements Identification
Map project requirements to ISO/IEC 25010 characteristics. Not all characteristics apply equally to every project.

### Step 2 — Risk-Based Prioritization
Determine which quality characteristics are most critical:
- **Safety-critical systems** → Reliability, Security, Fault Tolerance
- **Consumer apps** → Usability, Performance, Compatibility
- **Enterprise systems** → Security, Maintainability, Reliability
- **APIs / Microservices** → Compatibility, Performance, Security

### Step 3 — Test Type Mapping

| ISO/IEC 25010 Characteristic | Test Types |
|---|---|
| Functional Suitability | Functional, Acceptance, Regression |
| Performance Efficiency | Load, Stress, Performance, Scalability |
| Compatibility | Integration, API, Cross-browser, Cross-platform |
| Usability | UX, Accessibility, Exploratory |
| Reliability | Reliability, Failover, Chaos |
| Security | Security, Penetration, OWASP |
| Maintainability | Static Analysis, Code Review, Test Coverage |
| Portability | Installation, Migration, Cross-platform |

---

## QAI Consultant Usage

When generating a Test Strategy, QAI Consultant should:
1. Ask which ISO/IEC 25010 characteristics are in scope
2. Map test types to relevant characteristics
3. Recommend prioritization based on project type and risk profile
4. Use ISO/IEC 25010 terminology in generated Test Strategy documents
