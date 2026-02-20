# A-SPICE — Automotive SPICE Process Reference Model

Source: Compiled from public knowledge — Automotive SPICE Process Reference Model v3.1 and Process Assessment Model v3.1 (ASPICE PAM), publicly available at automotivespice.com
License: VDA QMC — publicly available document

---

## Overview

Automotive SPICE (Software Process Improvement and Capability Determination) is a framework for assessing and improving software development processes in the automotive industry. It is based on ISO/IEC 33000 and is widely used by OEMs (BMW, Volkswagen, Daimler, etc.) to assess the capability of their suppliers.

**Core Purpose:** Ensure that automotive software suppliers have mature, repeatable, and measurable development processes that reduce risk and improve quality.

---

## Capability Levels

A-SPICE defines 6 capability levels for each process:

| Level | Name | Description |
|---|---|---|
| 0 | Incomplete | Process not implemented or fails to achieve its purpose |
| 1 | Performed | Process achieves its purpose |
| 2 | Managed | Process is planned, monitored, and adjusted |
| 3 | Established | Process uses a defined process based on standards |
| 4 | Predictable | Process operates within defined limits (quantitative) |
| 5 | Optimizing | Process is continuously improved |

**Industry target:** Most OEMs require suppliers to achieve **ASIL Level 2 or 3** for safety-relevant projects.

---

## Process Groups

A-SPICE organizes processes into groups:

### ACQ — Acquisition Processes
Processes used by the acquirer (OEM) to manage suppliers.

### SPL — Supply Processes
Processes used by the supplier to deliver software.

### SYS — System Engineering Processes
- SYS.1 Requirements Elicitation
- SYS.2 System Requirements Analysis
- SYS.3 System Architectural Design
- SYS.4 System Integration and Integration Test
- SYS.5 System Qualification Test

### SWE — Software Engineering Processes *(Most relevant for QA)*
- SWE.1 Software Requirements Analysis
- SWE.2 Software Architectural Design
- SWE.3 Software Detailed Design and Unit Construction
- **SWE.4 Software Unit Verification**
- **SWE.5 Software Integration and Integration Test**
- **SWE.6 Software Qualification Test**

### SUP — Support Processes *(Critical for QA)*
- **SUP.1 Quality Assurance**
- SUP.2 Verification
- SUP.4 Joint Review
- SUP.5 Audit
- SUP.7 Documentation
- **SUP.8 Configuration Management**
- **SUP.9 Problem Resolution Management**
- SUP.10 Change Request Management

### MAN — Management Processes
- MAN.3 Project Management
- MAN.5 Risk Management
- MAN.6 Measurement

### PIM — Process Improvement
- PIM.3 Process Improvement

---

## Key QA-Relevant Processes in Detail

### SWE.4 — Software Unit Verification

**Purpose:** Verify that software units satisfy their requirements and are ready for integration.

**Base Practices:**
- BP1: Develop unit verification plan — specify approach, criteria, environment
- BP2: Develop unit test cases — derived from software detailed design
- BP3: Perform static verification — code reviews, static analysis
- BP4: Execute unit tests — execute and record results
- BP5: Establish bidirectional traceability — requirements ↔ test cases ↔ results
- BP6: Ensure consistency — between detailed design and test specification

**Key Work Products:**
- Unit Test Plan
- Unit Test Specification
- Unit Test Results
- Static Verification Results

---

### SWE.5 — Software Integration and Integration Test

**Purpose:** Integrate software units into larger software items and verify interfaces and interactions.

**Base Practices:**
- BP1: Develop integration test plan — define integration strategy (bottom-up, top-down)
- BP2: Develop integration test specification — test cases for interfaces
- BP3: Integrate software units — incrementally combine units
- BP4: Execute integration tests — verify interfaces and interactions
- BP5: Establish bidirectional traceability — architecture ↔ integration tests ↔ results
- BP6: Ensure consistency — between software architecture and integration tests

**Key Work Products:**
- Software Integration Test Plan
- Software Integration Test Specification
- Software Integration Test Results

---

### SWE.6 — Software Qualification Test

**Purpose:** Verify that the integrated software meets the software requirements and is ready for system integration.

**Base Practices:**
- BP1: Develop software qualification test plan
- BP2: Develop software qualification test specification — derived from software requirements
- BP3: Execute software qualification tests — on target hardware or representative environment
- BP4: Establish bidirectional traceability — requirements ↔ test cases ↔ results
- BP5: Ensure consistency — between software requirements and qualification tests

**Key Work Products:**
- Software Qualification Test Plan
- Software Qualification Test Specification
- Software Qualification Test Results
- Software Test Report

---

### SUP.1 — Quality Assurance

**Purpose:** Ensure that work products and processes comply with defined standards and plans.

**Base Practices:**
- BP1: Develop quality assurance plan
- BP2: Assure quality of project planning
- BP3: Assure quality of work products — reviews, audits
- BP4: Assure quality of process implementation
- BP5: Assure quality of supplier's deliverables
- BP6: Report quality assurance results

---

### SUP.9 — Problem Resolution Management

**Purpose:** Ensure that problems are identified, analyzed, managed, and controlled.

**Base Practices:**
- BP1: Identify and record problems — all defects, deviations, anomalies
- BP2: Analyze problems — root cause analysis
- BP3: Initiate problem resolution — assign owner, priority
- BP4: Track problems — monitor until closure
- BP5: Communicate problem status — report to stakeholders
- BP6: Close problems — verify resolution

---

## Traceability — The Golden Thread

A-SPICE requires **bidirectional traceability** across all levels:

```
Stakeholder Requirements
        ↕
System Requirements
        ↕
Software Requirements
        ↕
Software Architecture
        ↕
Software Detailed Design
        ↕
Test Cases
        ↕
Test Results
```

Every test case must trace up to a requirement.
Every requirement must trace down to at least one test case.
This is audited during A-SPICE assessments.

---

## A-SPICE Assessment Process

### Assessment Types
- **Internal Assessment** — performed by the organization itself
- **Third-party Assessment** — performed by an accredited assessor (required by most OEMs)
- **Supplier Assessment** — OEM assessing a Tier 1 or Tier 2 supplier

### What Assessors Look For in QA
1. **Documented processes** — are test plans, specs, and results available?
2. **Traceability** — can you trace every test case to a requirement?
3. **Coverage** — are all requirements covered by test cases?
4. **Results** — are test execution results formally recorded?
5. **Problem management** — are defects tracked to closure?
6. **Consistency** — do test specs match the actual architecture/design?

---

## A-SPICE and ISO 26262 Relationship

A-SPICE and ISO 26262 are complementary:

| Aspect | A-SPICE | ISO 26262 |
|---|---|---|
| Focus | Process maturity | Functional safety |
| Scope | All automotive software | Safety-critical E/E systems |
| Coverage metric | Process capability levels | ASIL levels |
| Test documentation | Work products and traceability | Safety case evidence |
| Assessment | Process assessment | Safety audit |

**In practice:** Projects typically need to satisfy both. A-SPICE ensures the process is mature; ISO 26262 ensures safety requirements are met.

---

## Common A-SPICE Findings in QA

1. **Missing bidirectional traceability** — most common finding, test cases not linked to requirements
2. **Incomplete test specifications** — test cases missing expected results or preconditions
3. **No regression strategy** — changes made without re-running related tests
4. **Poor problem management** — defects not formally tracked or closed
5. **Inconsistency between documents** — test specs don't reflect the current architecture
6. **No coverage analysis** — unable to demonstrate that all requirements are tested

---

## Recommended Tools for A-SPICE Compliance

| Activity | Tool |
|---|---|
| Requirements management | IBM DOORS, Polarion, Jama |
| Test management & traceability | IBM RQM, Polarion, X-Ray (Jira) |
| Static analysis | LDRA, Polyspace, SonarQube |
| Unit testing | VectorCAST, Tessy, GoogleTest |
| Coverage analysis | LDRA, BullseyeCoverage |
| Defect tracking | Jira, IBM RTC |

---

## QAI Consultant Application

When a project involves A-SPICE, QAI Consultant should:
1. Ask what capability level is required by the OEM (typically Level 2 or 3)
2. Recommend test documentation aligned with SWE.4, SWE.5, SWE.6 work products
3. Emphasize bidirectional traceability as a mandatory requirement
4. Include SUP.9 Problem Resolution Management in the test process
5. Recommend appropriate tools for requirements management and test traceability
6. Flag that all test work products will be subject to assessment by the OEM
7. Recommend coverage metrics aligned with both A-SPICE and ISO 26262 ASIL requirements
8. Suggest integration between defect tracking and requirements management tools
