# IEEE 829 – Standard for Software and System Test Documentation

Source: IEEE Standard 829 (public knowledge summary)
Note: Full standard available for purchase at ieee.org

---

## Overview

IEEE 829 defines the format of a set of documents for use in software testing. It does not specify whether these documents should be produced, but establishes the content requirements for each document type. This standard is widely referenced in ISTQB and professional QA practice.

---

## Key Documents Defined by IEEE 829

### 1. Master Test Plan (MTP)
The top-level test planning document. Covers:
- **Scope** — what is and isn't being tested
- **Test approach** — overall strategy and methodology
- **Resources** — people, tools, environments
- **Schedule** — milestones and deadlines
- **Risks and contingencies**
- **Entry and exit criteria**

### 2. Level Test Plan (LTP)
A test plan for a specific test level (unit, integration, system, acceptance). Inherits from MTP but adds level-specific details:
- Features to be tested at this level
- Test design techniques to be used
- Pass/fail criteria specific to this level

### 3. Test Design Specification
Describes the approach for a specific set of test cases:
- Test conditions to be covered
- Relationships between test conditions
- Feature pass/fail criteria

### 4. Test Case Specification
Defines specific inputs, execution conditions, and expected results:
- Test case ID and description
- Inputs (data, commands)
- Expected outputs
- Environmental needs
- Dependencies

### 5. Test Procedure Specification
Step-by-step instructions for executing a set of test cases:
- Logging requirements
- Setup and teardown steps
- Execution sequence

### 6. Test Item Transmittal Report
Records what test items (software builds, documents) are being delivered for testing:
- Item identification
- Location
- Status

### 7. Test Log
A chronological record of relevant details about the execution of tests:
- Test items executed
- Results for each test case
- Environmental conditions

### 8. Test Incident Report
Describes any event that requires investigation during testing:
- Description of the incident
- Impact assessment
- Priority and severity

### 9. Test Summary Report
A summary of testing activities and results:
- Summary of activities
- Variances from plan
- Comprehensive assessment of testing
- Recommendations

---

## Relationship to QA Strategy

IEEE 829 provides the **documentation backbone** for any formal test process. When building a Test Strategy, QA teams should:

1. Decide which IEEE 829 documents are applicable for the project
2. Scale the formality based on project risk and compliance requirements
3. Use the document structure as templates, not rigid forms
4. Ensure traceability between requirements, test cases, and defects

---

## Practical Application in Test Strategy

| Project Type | Recommended Documents |
|---|---|
| Small Agile project | Test Plan (lightweight), Test Cases, Test Summary Report |
| Enterprise / regulated | All documents, formal sign-off required |
| Safety-critical systems | Full IEEE 829 compliance mandatory |
| Open-source / internal tools | Test Plan + Test Log minimum |

---

## Common Misconceptions

- IEEE 829 does **not** mandate a specific test process, only document formats
- Documents can be combined or simplified for smaller projects
- Agile teams often replace formal documents with lightweight equivalents (e.g., sprint test summaries instead of formal Test Summary Reports)
- The standard is complementary to ISTQB — ISTQB references IEEE 829 heavily

---

## QA Testing Implications for QAI Consultant

When generating Test Strategies and Test Plans, QAI Consultant should:
- Reference IEEE 829 document structure where appropriate
- Recommend which documents are needed based on project type and risk
- Scale documentation requirements based on regulatory context
- Use IEEE 829 terminology consistently in generated artifacts
