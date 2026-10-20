"""Quick-start project templates that pre-fill the 11-question dialogue."""

TEMPLATES = {
    "web_app": {
        "label": "🌐 Web Application",
        "project_name": "SaaS Web Application",
        "project_description": (
            "B2C SaaS platform with user authentication, subscription billing, "
            "and a feature-rich dashboard served to end consumers via browser."
        ),
        "project_type": "Web Application",
        "tech_stack": "React, Node.js/Express, PostgreSQL, AWS (EC2, S3, RDS)",
        "methodology": "Agile/Scrum with 2-week sprints",
        "timeline": "6 months",
        "team_qa_size": "2",
        "team_dev_size": "6",
        "known_risks": (
            "Third-party payment and OAuth integrations, authentication/session security, "
            "GDPR data handling and right-to-erasure flows."
        ),
        "existing_automation": "Playwright E2E test suite, Jest unit and integration tests",
        "compliance_requirements": "GDPR, OWASP Top 10",
    },
    "mobile_app": {
        "label": "📱 Mobile Application",
        "project_name": "Mobile Application",
        "project_description": (
            "Cross-platform iOS and Android consumer app backed by a REST API, "
            "with offline-first data sync and push notifications via Firebase."
        ),
        "project_type": "Mobile Application",
        "tech_stack": "React Native (iOS + Android), REST API backend, Firebase (Auth + Firestore + FCM)",
        "methodology": "Agile/Kanban with continuous delivery",
        "timeline": "4 months",
        "team_qa_size": "1",
        "team_dev_size": "4",
        "known_risks": (
            "Device and OS fragmentation, offline mode data consistency, "
            "App Store and Play Store review/approval delays."
        ),
        "existing_automation": "Detox E2E automated tests for critical user flows",
        "compliance_requirements": "GDPR, Apple App Store guidelines, Google Play Store policies",
    },
    "microservices": {
        "label": "⚙️ Microservices / API",
        "project_name": "Microservices Platform",
        "project_description": (
            "Event-driven backend composed of Python FastAPI microservices communicating "
            "over RabbitMQ, deployed on Kubernetes with a PostgreSQL data tier."
        ),
        "project_type": "Microservices / API",
        "tech_stack": (
            "Python FastAPI, Docker, Kubernetes, PostgreSQL, RabbitMQ, AWS (EKS, RDS, SQS)"
        ),
        "methodology": "DevOps/CI-CD pipeline with Agile 2-week iterations",
        "timeline": "9 months",
        "team_qa_size": "3",
        "team_dev_size": "10",
        "known_risks": (
            "Service interdependencies and cascading failures, distributed transaction consistency, "
            "API versioning and backward compatibility."
        ),
        "existing_automation": (
            "pytest integration test suite, k6 load and stress testing, Postman/Newman API collections"
        ),
        "compliance_requirements": "SOC 2 Type II, PCI-DSS",
    },
    "automotive": {
        "label": "🚗 Embedded / Automotive",
        "project_name": "Automotive ECU Firmware",
        "project_description": (
            "Safety-critical C/C++ ECU firmware developed under AUTOSAR classic, "
            "communicating over CAN/LIN bus and validated with Hardware-in-the-Loop rigs."
        ),
        "project_type": "Embedded / Automotive",
        "tech_stack": (
            "C/C++, AUTOSAR Classic, CAN bus, LIN bus, Hardware-in-the-Loop (HiL) test bench, CANoe"
        ),
        "methodology": "V-Model with A-SPICE process framework",
        "timeline": "18 months",
        "team_qa_size": "4",
        "team_dev_size": "8",
        "known_risks": (
            "Safety-critical function failures, real-time timing constraint violations, "
            "ISO 26262 ASIL level verification and traceability gaps."
        ),
        "existing_automation": (
            "CANoe scripted test automation for bus communication, Google Test unit test framework"
        ),
        "compliance_requirements": "ISO 26262 (ASIL B/C), A-SPICE Level 2, MISRA C",
    },
}

TEMPLATE_OPTIONS = [("— Start from scratch —", None)] + [
    (t["label"], k) for k, t in TEMPLATES.items()
]
