# OWASP Top 10 - 2021

Source: https://owasp.org/Top10/
License: CC BY-SA 4.0

## Overview

The OWASP Top 10 is a standard awareness document for developers and web application security. It represents a broad consensus about the most critical security risks to web applications.

---

## A01:2021 – Broken Access Control

**Description:**
Access control enforces policy such that users cannot act outside of their intended permissions. Failures typically lead to unauthorized information disclosure, modification, or destruction of all data or performing a business function outside the user's limits.

**Common Vulnerabilities:**
- Violation of the principle of least privilege
- Bypassing access control checks by modifying the URL or HTML page
- Insecure direct object references
- Missing access controls for POST, PUT, DELETE
- Elevation of privilege (acting as admin when logged in as user)
- CORS misconfiguration allowing unauthorized API access

**How to Prevent:**
- Deny by default
- Implement access control mechanisms once and reuse throughout the application
- Log access control failures and alert admins
- Rate limit API and controller access

---

## A02:2021 – Cryptographic Failures

**Description:**
Failures related to cryptography which often lead to exposure of sensitive data or system compromise. Focus is on failures related to cryptography (or lack thereof) which often leads to exposure of sensitive data.

**Common Vulnerabilities:**
- Data transmitted in clear text (HTTP, SMTP, FTP)
- Weak or outdated cryptographic algorithms
- Default crypto keys in use or weak keys generated
- Encryption not enforced (missing security headers)
- Deprecated hash functions (MD5, SHA1)

**How to Prevent:**
- Classify data processed, stored, or transmitted
- Encrypt all sensitive data at rest
- Ensure up-to-date and strong standard algorithms, protocols, and keys
- Disable caching for responses that contain sensitive data

---

## A03:2021 – Injection

**Description:**
Injection flaws occur when untrusted data is sent to an interpreter as part of a command or query. SQL, NoSQL, OS, and LDAP injection are common examples.

**Common Vulnerabilities:**
- SQL, NoSQL, OS, LDAP injection
- User-supplied data not validated, filtered, or sanitized
- Dynamic queries used without context-aware escaping
- Hostile data used within search parameters

**How to Prevent:**
- Use a safe API that avoids using the interpreter entirely
- Use positive server-side input validation
- Escape special characters using the specific escape syntax for the interpreter
- Use LIMIT and other SQL controls within queries

---

## A04:2021 – Insecure Design

**Description:**
A new category for 2021, focusing on risks related to design and architectural flaws. Insecure design is not the source for all other Top 10 risk categories.

**Common Vulnerabilities:**
- Missing or ineffective control design
- Lack of business risk profiling in software design
- No threat modeling during design phase

**How to Prevent:**
- Establish and use a secure development lifecycle
- Use threat modeling for critical authentication, access control, business logic, and key flows
- Write unit and integration tests to validate all critical flows are resistant to the threat model

---

## A05:2021 – Security Misconfiguration

**Description:**
The most commonly seen issue. Often results from insecure default configurations, incomplete or ad hoc configurations, open cloud storage, misconfigured HTTP headers, and verbose error messages containing sensitive information.

**Common Vulnerabilities:**
- Missing appropriate security hardening across the application stack
- Unnecessary features enabled (ports, services, accounts, privileges)
- Default accounts and passwords still enabled
- Error handling reveals stack traces or overly informative error messages
- Latest security features disabled or not configured securely

**How to Prevent:**
- Implement a repeatable hardening process
- Minimal platform — no unnecessary features, components, documentation
- Review and update configurations appropriate to all security notes, updates, and patches
- Segmented application architecture

---

## A06:2021 – Vulnerable and Outdated Components

**Description:**
Components such as libraries, frameworks, and other software modules run with the same privileges as the application. If a vulnerable component is exploited, such an attack can facilitate serious data loss or server takeover.

**Common Vulnerabilities:**
- Not knowing versions of all components used (both client-side and server-side)
- Software is vulnerable, unsupported, or out of date
- Not scanning for vulnerabilities regularly
- Not fixing or upgrading underlying platform, frameworks, and dependencies

**How to Prevent:**
- Remove unused dependencies, unnecessary features, components, files, and documentation
- Continuously inventory the versions of both client-side and server-side components
- Monitor sources like CVE and NVD for vulnerabilities in the components
- Only obtain components from official sources over secure links

---

## A07:2021 – Identification and Authentication Failures

**Description:**
Confirmation of the user's identity, authentication, and session management is critical to protect against authentication-related attacks.

**Common Vulnerabilities:**
- Permits brute force or other automated attacks
- Permits default, weak, or well-known passwords
- Uses weak or ineffective credential recovery processes
- Uses plain text, encrypted, or weakly hashed passwords
- Missing or ineffective multi-factor authentication
- Exposes session identifier in the URL

**How to Prevent:**
- Implement multi-factor authentication
- Do not ship or deploy with any default credentials
- Implement weak password checks
- Limit or increasingly delay failed login attempts
- Use a server-side, secure, built-in session manager

---

## A08:2021 – Software and Data Integrity Failures

**Description:**
A new category for 2021, focusing on making assumptions related to software updates, critical data, and CI/CD pipelines without verifying integrity.

**Common Vulnerabilities:**
- Application relies upon plugins, libraries, or modules from untrusted sources
- Insecure CI/CD pipeline that can introduce the potential for unauthorized access
- Auto-update functionality that downloads updates without sufficient integrity verification

**How to Prevent:**
- Use digital signatures to verify the software or data is from the expected source
- Ensure libraries and dependencies are consuming trusted repositories
- Ensure there is a review process for code and configuration changes
- Your CI/CD pipeline has proper segregation, configuration, and access control

---

## A09:2021 – Security Logging and Monitoring Failures

**Description:**
Without logging and monitoring, breaches cannot be detected. Insufficient logging, detection, monitoring, and active response occurs anytime.

**Common Vulnerabilities:**
- Auditable events not logged (logins, failed logins, high-value transactions)
- Warnings and errors generate no, inadequate, or unclear log messages
- Logs not monitored for suspicious activity
- Logs only stored locally
- No alerting thresholds and response escalation process

**How to Prevent:**
- Ensure all login, access control, and server-side input validation failures can be logged with sufficient user context
- Ensure logs are generated in a format that log management solutions can easily consume
- Ensure high-value transactions have an audit trail
- Establish or adopt an incident response and recovery plan

---

## A10:2021 – Server-Side Request Forgery (SSRF)

**Description:**
SSRF flaws occur whenever a web application is fetching a remote resource without validating the user-supplied URL. It allows an attacker to coerce the application to send a crafted request to an unexpected destination.

**Common Vulnerabilities:**
- Fetching a remote resource using a URL supplied by user input
- The application does not validate the user-supplied URL before fetching

**How to Prevent:**
- Sanitize and validate all client-supplied input data
- Enforce the URL schema, port, and destination with a positive allow list
- Do not send raw responses to clients
- Disable HTTP redirections

---

## QA Testing Implications

For each OWASP Top 10 category, QA teams should include:

1. **Security Test Cases** — verify that each vulnerability class is tested
2. **Penetration Testing Scope** — define which OWASP categories apply to the project
3. **Risk Assessment** — prioritize based on application type (web, mobile, API)
4. **Regression Testing** — ensure fixes don't reintroduce vulnerabilities
5. **Security in Definition of Done** — OWASP checks as acceptance criteria
