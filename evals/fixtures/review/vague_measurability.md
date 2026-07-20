# Test Plan — Vague Measurability Example

## Scope
This document defines the scope of testing for the checkout service.

## Test Items
The checkout API and payment gateway integration are the items to be tested.

## Features to be Tested
The following will be tested: cart totals, tax calculation, discount codes.

## Features Not to be Tested
Out of scope: third-party fraud detection internals are excluded from this plan.

## Objectives
The objective of this test plan is to validate checkout correctness end-to-end.

## Test Levels
Testing includes unit test, integration test, system test, and regression test levels.

## Approach
A risk-based testing approach is used, with risk-based prioritization of test cases.

## Pass/Fail Criteria
A test case passes only when its documented criteria are fully met.

## Entry Criteria
Entry criteria: all REQ-101 and REQ-102 requirements are code-complete and deployed to QA.

## Exit Criteria
Exit criteria: 95% of test cases pass and code coverage of 80% is achieved.

## Suspension Criteria
Testing will be suspended if the build fails smoke tests; resumption criteria apply after a fix.

## Deliverables
Test deliverables include the traceability matrix and the final test summary report.

## Schedule
The testing schedule spans two weeks per the project milestones.

## Risks
### R01 — Payment gateway instability
- **Severity:** Critical
- **Likelihood:** High priority risk requiring mitigation.
- **Mitigation:** A contingency plan and mitigation strategy are documented for R01.

Expected result: the checkout flow works correctly for REQ-101.
Expected result: the discount code REQ-102 works as expected.
Expected result: totals functions properly per REQ-101.

## Approvals
Sign-off is required from the QA Lead and Project Manager before release.
