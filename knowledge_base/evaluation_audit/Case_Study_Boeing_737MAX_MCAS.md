# Case Study — Boeing 737 MAX MCAS: Process Failure Behind Two Fatal Crashes

Source: Compiled from public sources — NTSB investigation records, the FAA-commissioned Joint Authorities Technical Review (JATR) report (October 11, 2019), and the U.S. House Committee on Transportation and Infrastructure Final Committee Report (September 16, 2020)
License: Public government and public-domain records — no proprietary or non-public Boeing material is used

---

## What Happened

The Boeing 737 MAX introduced a new flight-control software function called MCAS (Maneuvering Characteristics Augmentation System), designed to automatically push the aircraft's nose down under certain flight conditions to compensate for aerodynamic changes caused by the plane's larger, repositioned engines. MCAS was triggered by a single input: the reading from one of the aircraft's two angle-of-attack (AOA) sensors.

Two fatal crashes followed within five months of each other:

- **Lion Air Flight 610** — On October 29, 2018, a nearly new 737 MAX 8 operated by Lion Air crashed into the Java Sea off Indonesia approximately 13 minutes after takeoff, killing all **189** passengers and crew on board.
- **Ethiopian Airlines Flight 302** — On March 10, 2019, a 737 MAX 8 operated by Ethiopian Airlines crashed shortly after takeoff from Addis Ababa, killing all **157** passengers and crew on board.

In both accidents, a faulty AOA sensor fed erroneous data to MCAS, which repeatedly commanded the aircraft's nose down. Investigators found the flight crews were not able to counteract the automated nose-down inputs in time, and both aircraft entered unrecoverable dives. The combined death toll across the two accidents is widely reported as **346** people.

Following the second crash, aviation authorities worldwide grounded the entire 737 MAX fleet beginning mid-March 2019 — a grounding that lasted approximately 20 months in most jurisdictions, until regulators approved a redesigned MCAS and revised pilot training. The grounding, along with related settlements, fines, and production slowdowns, is reported to have cost Boeing tens of billions of dollars and caused lasting reputational damage.

---

## Root Cause (Process Gap)

The two crashes were not the result of a single coding bug. Multiple independent investigations — the FAA-commissioned Joint Authorities Technical Review (JATR, October 2019), the U.S. House Committee on Transportation and Infrastructure's 18-month investigation (final report, September 2020), and the DOT Office of Inspector General — converged on the same underlying pattern: a **process failure** in how a safety-critical software system was analyzed, specified, and certified, not merely an implementation defect.

Key process gaps identified across these reports:

1. **Single-sensor dependency with no cross-check.** MCAS was designed to accept input from only one of the aircraft's two AOA sensors on any given flight, with no requirement to cross-check against the second sensor or to disagree-flag before acting. A single failed or miscalibrated sensor could therefore trigger repeated, large automatic control inputs with no redundancy check — a design decision that a rigorous hazard analysis should have flagged as a single point of failure for a flight-critical function.

2. **Inadequate hazard and functional hazard assessment (FHA)/FMEA.** The JATR team found that MCAS was not evaluated as a complete and integrated function during certification — it was analyzed piecemeal across different requirements documents and safety assessments rather than as one system-level hazard, and its authority (how far and how repeatedly it could move the horizontal stabilizer) was revised upward late in development without a full re-assessment of the failure modes this created.

3. **Understated failure severity classification.** Early safety assessments reportedly classified an uncommanded MCAS activation as a "major" failure condition rather than "hazardous" or "catastrophic." That classification drove weaker design mitigations and lighter certification scrutiny than the actual risk to the aircraft warranted.

4. **Pilots and airlines were not informed MCAS existed.** Because MCAS was treated as a minor extension of an existing system rather than a new safety-critical function, it was omitted from flight crew operating manuals and differences training. Flight crews facing an MCAS malfunction had no trained procedure specific to it and limited time to diagnose a fast-developing, repeating fault.

5. **Certification process and organizational pressure.** The House Committee report (238 pages, released September 16, 2020, by Chairs Peter DeFazio and Rick Larsen) documented production pressure, extensive delegation of certification tasks from the FAA to Boeing itself, and insufficient independent regulatory verification of the safety analysis and requirements Boeing submitted — meaning the process gap existed on both the developer side and the certifying-authority oversight side.

---

## What a Mature Process / Audit Would Have Caught

A disciplined safety-critical software assurance process — of the kind ISTQB, IEC 61508/DO-178C-style safety lifecycles, and structured hazard analysis practices call for — would have surfaced these gaps well before certification:

- **A completed, system-level FMEA/FHA covering MCAS as a whole function** (not fragmented across separate documents) would have explicitly modeled "single AOA sensor fails or is miscalibrated" as a credible failure mode and required either sensor redundancy/voting logic or a documented, justified risk acceptance — not a silent gap.
- **Independent verification of severity/criticality classification** against the actual consequence of an erroneous nose-down command at low altitude would have driven the failure condition to "hazardous" or "catastrophic," triggering the higher level of design assurance (and independent review) those classifications require.
- **Requirements traceability and re-verification on change** — when MCAS's control authority was increased late in development, a mature change-control process would have mandated the hazard analysis and test coverage be re-run against the new authority level, not carried forward unchanged.
- **Cross-functional review looping in flight operations and training**, not just engineering, would have caught that a system capable of large, repeated automatic control inputs was omitted from pilot documentation and training — a gap a basic "who needs to know about this system" checklist should catch.
- **An independent (non-self-certifying) audit gate** on safety-critical requirements and hazard analysis, rather than relying primarily on the manufacturer's own delegated sign-off, would have added a check less exposed to the schedule and cost pressures documented by the House Committee.

---

## Source

- NTSB, *Investigation of Lion Air Flight 610 and Ethiopian Airlines Flight 302* (assistance/observer role to KNKT and EAIB): https://www.ntsb.gov/investigations/Pages/DCA19RA017-DCA19RA101.aspx
- Joint Authorities Technical Review (JATR), *Boeing 737 MAX Flight Control System: Observations, Findings, and Recommendations*, submitted to the FAA, October 11, 2019: https://www.faa.gov/sites/faa.gov/files/2021-08/Final_JATR_Submittal_to_FAA_Oct_2019.pdf
- U.S. House Committee on Transportation and Infrastructure, *Final Committee Report: The Design, Development & Certification of the Boeing 737 MAX*, September 16, 2020: https://www.govinfo.gov/content/pkg/GOVPUB-Y4_T68_2-PURL-gpo144993/pdf/GOVPUB-Y4_T68_2-PURL-gpo144993.pdf
- DOT Office of Inspector General, *Weaknesses in FAA's Certification and Delegation Processes Hindered Its Oversight of the 737 MAX*, Final Report, February 2021: https://www.oig.dot.gov/sites/default/files/FAA%20Certification%20of%20737%20MAX%20Boeing%20II%20Final%20Report%5E2-23-2021.pdf
- FAA, *Summary of the FAA's Review of the Boeing 737 MAX*: https://www.faa.gov/sites/faa.gov/files/2022-08/737_RTS_Summary.pdf

---

## QAI Consultant Application

When a project involves flight-critical, safety-critical, or otherwise high-consequence embedded/control software (aerospace, automotive, medical devices, industrial control), QAI Consultant should:

1. **Flag single-sensor / single-source dependencies in safety-relevant control logic as a high-severity Risk Register item.** Any automated control decision driven by one unredundant input source without a disagree-check or voting logic should be surfaced explicitly, even if the project team did not raise it.
2. **Require a documented, system-level hazard analysis (FHA/FMEA) as an entry criterion for test planning** on safety-critical features — not a piecemeal or component-level analysis — and ask whether failure severity classifications were independently reviewed rather than self-assigned by the feature team.
3. **Add a Test Strategy check for "does the test plan re-verify hazard analysis and coverage after any change to a safety-critical function's authority/behavior,"** mirroring the MCAS late-stage authority increase that was not re-assessed.
4. **Recommend cross-functional review gates** (engineering + operations/end-user training + independent safety/quality) for any system capable of autonomous, repeated corrective actions — not engineering sign-off alone.
5. **Where the organization is both developer and (self-)certifier of a safety claim, recommend an independent audit/verification gate** in the Test Strategy, rather than relying solely on internal delegated sign-off — directly mirroring the certification-process gap documented in the House Committee report.
