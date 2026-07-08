# Changelog

All notable changes to QAI Consultant are documented in this file, in
end-user terms. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [2.5.1] - 2026-07-08

### Added
- Expanded the knowledge base with a new "audit & evaluation" collection: process/test maturity models, audit methodology, security and regulatory compliance audits, and real-world case studies of process failures — so generated strategies can better anticipate what an audit will actually check for.

### Fixed
- Fixed a knowledge-base loading bug on Windows where several documents either failed to load entirely or were loaded with corrupted text (garbled special characters) due to an incorrect text encoding. All knowledge-base content is now loaded and indexed correctly.

## [2.5.0] - 2026-07-07

### Added
- In-app Release Notes: a "📋 Release Notes" panel in the sidebar now shows the full history of changes without leaving the app.
- A one-time "what's new" banner appears the first time you open the app after an update, pointing you to the sidebar for details.

## [2.0.2] - 2026-07-06

### Added
- An automated release-quality check now runs before every release, verifying that estimates and generated documents stay accurate and trustworthy.

### Fixed
- Fixed several estimate and validation issues: duration ranges, team-size handling, project name display, confidence scoring, and fabricated version numbers appearing in generated Test Plans.
- Fixed a crash that could occur while navigating between steps in the web app.
- Fixed duplicated and cut-off text in generated narrative sections.
- Increased the generation length limit so longer Test Plans and Test Strategies no longer get cut off mid-sentence.
- Improved reliability so a temporary hiccup in one part of document generation no longer prevents the other parts from completing.

## [2.0.1] - 2026-06-28

### Fixed
- A major stability release: fixed 27 issues affecting effort estimates, PDF downloads, session handling, generated file names, and knowledge-base search reliability.
- Fixed an issue where reapplying a project template could silently fail to update the form.
- Fixed PDF export freezing for certain inputs.
- Fixed an issue where the per-session run limit could be bypassed.
- Improved handling so a temporary knowledge-base search failure no longer stops the whole strategy from generating.

## [2.0.0] - 2026-05-07

### Changed
- Moved to the cloud: QAI Consultant now runs on the Mistral API (with an automatic fallback provider) instead of a locally hosted model, and uses a cloud-hosted knowledge base.
- QAI Consultant is now deployed as a hosted web app — no local installation required to use it.

## [1.0.0] - 2026-02-27

### Added
- First stable release (MVP): hardened error handling and input validation, activity logging, a full automated test suite, and new setup (`INSTALL.md`) and contribution (`CONTRIBUTING.md`) guides.
- The app now displays its version number in both the CLI and the web UI.

## Early development (v0.1 – v0.6)

These releases predate formal version tracking and don't have exact recorded release dates.

### v0.6
- Added a confidence score (0–100) to every estimate, based on four underlying factors, so you can gauge at a glance how much to trust a given number.

### v0.5
- The knowledge base now keeps itself up to date automatically — new or changed reference material is picked up without a manual rebuild step.

### v0.4
- Added Effort Estimation Reports: a data-driven time/effort estimate with a realistic best-case-to-worst-case range, tailored to your team's size and capacity.

### v0.3
- Every Test Strategy now comes with an automatically generated Risk Register, identifying and prioritizing project risks alongside your test plan.

### v0.2
- Added a feedback loop: strategies you mark as useful are saved back into the knowledge base, helping future recommendations keep improving.

### v0.1
- First release: the core AI agent, a terminal (CLI) interface, and a browser-based Streamlit web app for generating Test Strategies.
