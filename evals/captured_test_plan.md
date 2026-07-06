<!--
The "2. Test Items" section produced by the CURRENT QAI Consultant Test Plan prompt
(src/test_plan_generator.py) for the golden project context (_RUN_INPUTS in
estimate_integrity.py), captured live against real Mistral + Pinecone credentials on
2026-07-06. The user supplied NO version numbers in any of the 11 answers; the prompt's
"version not specified" guard (added in 8094bd3, 2026-07-02) means the generator now
reports every component as unversioned instead of inventing one. This replaces the
2026-06-30 fixture, which predated that guard and still showed fabricated version
strings for every component — see issue #28. Used as a fixture for the
fabricated-version gate.
-->

# Test Plan — Acme Project Hub

## 2. Test Items

| **Component** | **Description** | **Version** |
|---|---|---|
| **Frontend (React)** | User interface for project/task management, file uploads, and notifications. | Not specified |
| **Backend (FastAPI)** | REST API handling authentication, project/task CRUD, file storage, and GDPR data requests. | Not specified |
| **Database (Postgres)** | Stores user data, projects, tasks, and file metadata. | Not specified |
| **API Endpoints** | `/projects`, `/tasks`, `/files`, `/users`, `/auth`, `/notifications`. | Not specified |
| **Third-Party Integrations** | File storage (e.g., AWS S3, local storage), email/SMS notifications. | Not specified |
