# ISO 26262 — Functional Safety for Road Vehicles

Source: Compiled from public knowledge — ISO 26262:2018 second edition concepts, SOTIF (ISO 21448), and automotive industry best practices.
Note: Full standard available for purchase at iso.org

---

## Overview

ISO 26262 is the international standard for functional safety of electrical and electronic (E/E) systems in road vehicles. It defines requirements for the entire safety lifecycle of automotive software and hardware, from concept through decommissioning.

**Core Purpose:** Ensure that safety-critical automotive systems are developed, verified, and validated in a way that reduces the risk of hazards caused by malfunctioning E/E systems.

---

## Key Concepts

### Functional Safety
The absence of unreasonable risk due to hazards caused by malfunctioning behavior of E/E systems.

### ASIL — Automotive Safety Integrity Level
ASIL is the risk classification system defined by ISO 26262. It determines the rigor of safety measures required.

| ASIL Level | Risk Level | Example |
|---|---|---|
| QM (Quality Management) | No safety requirement | Infotainment display brightness |
| ASIL A | Lowest safety requirement | Windshield wiper speed |
| ASIL B | Low-medium safety requirement | Headlight control |
| ASIL C | Medium-high safety requirement | ABS braking system |
| ASIL D | Highest safety requirement | Airbag deployment, steering control |

### ASIL Determination
ASIL is determined by combining three factors:
- **Severity (S)** — how bad is the harm if the hazard occurs? (S0-S3)
- **Exposure (E)** — how often is the driver in the situation? (E0-E4)
- **Controllability (C)** — can the driver control and avoid the hazard? (C0-C3)

```
ASIL = f(Severity, Exposure, Controllability)
```

---

## ISO 26262 Safety Lifecycle Phases

### Phase 1 — Concept Phase
- Item definition
- Hazard Analysis and Risk Assessment (HARA)
- Functional Safety Concept

### Phase 2 — System Level
- Technical Safety Concept
- System design
- System integration and testing

### Phase 3 — Hardware Level
- Hardware design
- Hardware verification

### Phase 4 — Software Level (Most relevant for QA)
- Software requirements specification
- Software architecture design
- Software unit design and implementation
- **Software unit verification (SWE.4)**
- **Software integration and testing (SWE.5)**
- **Software qualification testing (SWE.6)**

### Phase 5 — Production and Operation
- Production planning
- Operation and maintenance

---

## Software Testing Requirements by ASIL

ISO 26262 defines specific testing requirements based on ASIL level:

### Unit Testing Requirements
| Technique | ASIL A | ASIL B | ASIL C | ASIL D |
|---|---|---|---|---|
| Requirements-based testing | Recommended | Recommended | Mandatory | Mandatory |
| Equivalence classes & boundary values | Recommended | Recommended | Mandatory | Mandatory |
| Statement coverage | Recommended | Mandatory | Mandatory | Mandatory |
| Branch coverage | — | Recommended | Mandatory | Mandatory |
| MC/DC coverage | — | — | Recommended | Mandatory |

### Integration Testing Requirements
- Interface testing between software units
- Back-to-back testing (model vs code)
- Resource usage testing (CPU, memory, stack)
- Timing behavior testing

### System Testing Requirements
- Requirements-based testing at system level
- Fault injection testing
- Regression testing after changes
- Random testing (for ASIL C/D)

---

## HARA — Hazard Analysis and Risk Assessment

HARA is the core safety analysis activity in ISO 26262:

1. **Situation Analysis** — identify operational situations and operating modes
2. **Hazard Identification** — identify hazards for each situation
3. **ASIL Determination** — rate each hazard by Severity, Exposure, Controllability
4. **Safety Goals** — define top-level safety requirements for each hazard

### Example HARA for Infotainment System

| Hazard | Situation | S | E | C | ASIL |
|---|---|---|---|---|---|
| Screen freezes blocking rearview camera | Reversing | S2 | E3 | C2 | ASIL B |
| Incorrect navigation causes wrong turn | Highway driving | S1 | E4 | C2 | ASIL A |
| Phone call audio interferes with ADAS alerts | Any driving | S3 | E4 | C1 | ASIL C |
| System reboot causes momentary loss of cluster display | Any driving | S2 | E3 | C1 | ASIL B |

---

## Verification & Validation in ISO 26262

### Verification
"Are we building the product right?"
- Code reviews
- Static analysis
- Unit testing
- Integration testing

### Validation
"Are we building the right product?"
- System testing against safety goals
- Vehicle-level testing
- Field testing

### Independence Requirements
ISO 26262 requires independence in verification activities based on ASIL:

| ASIL | Required Independence |
|---|---|
| ASIL A | Guidelines recommended |
| ASIL B | Independence recommended |
| ASIL C | Independence mandatory (different person) |
| ASIL D | Independence mandatory (different team/org) |

---

## Safety Analysis Techniques

### FMEA — Failure Mode and Effects Analysis
- Systematic analysis of potential failure modes
- Identifies effects of failures on system safety
- Used at hardware and software level

### FTA — Fault Tree Analysis
- Top-down deductive analysis
- Identifies combinations of failures that lead to a hazard
- Used to verify safety goals are met

### FMEDA — Failure Mode Effects and Diagnostic Analysis
- Extension of FMEA for hardware
- Calculates diagnostic coverage of safety mechanisms

---

## ISO 26262 and Agile / V-model

ISO 26262 was originally designed for waterfall/V-model processes, but can be adapted for Agile:

**V-model alignment:**
- Left side: Requirements → Architecture → Design → Implementation
- Right side: Unit Test → Integration Test → System Test → Acceptance Test
- Each left phase has a corresponding right phase

**Agile adaptation challenges:**
- Safety documentation must be maintained incrementally
- Regression testing must be comprehensive after each sprint
- Safety analysis must be updated when requirements change
- Independence requirements must be maintained in sprint teams

---

## QA Testing Implications for Automotive Projects

### Test Documentation Requirements
- Test plans must reference safety goals and ASIL levels
- Test cases must be traceable to safety requirements
- Test results must be formally recorded and reviewed
- Deviation reports required for any test failures

### Mandatory Test Coverage Metrics (by ASIL)
- ASIL A/B: Statement coverage + Branch coverage
- ASIL C: Branch coverage + MC/DC coverage
- ASIL D: MC/DC coverage mandatory

### Regression Testing
- Any change to safety-relevant code requires re-verification
- Impact analysis mandatory before any change
- Full regression required for ASIL C/D components

---

## QAI Consultant Application

When a project involves ISO 26262, QAI Consultant should:
1. Ask for the ASIL levels of the components being tested
2. Recommend test coverage metrics based on ASIL level
3. Include HARA references in the Test Strategy
4. Recommend independence requirements for verification activities
5. Suggest safety analysis techniques (FMEA, FTA) appropriate for the project
6. Flag that all test documentation must meet ISO 26262 traceability requirements
7. Recommend specific tools for safety-critical testing (e.g., LDRA, VectorCAST, Tessy)
