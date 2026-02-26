# QAI Consultant — Hosted Version Architecture (v1.0+)

## Overview

Versiunea hosted permite utilizatorilor să acceseze QAI Consultant direct din browser,
fără instalare locală. Toți utilizatorii împart același KB (shared KB), iar strategiile
validate cu feedback "yes" intră automat în KB după un quality gate automat.

---

## Arhitectura generală

```
Browser (User A)          Browser (User B)          Browser (User C)
      │                         │                         │
      └─────────────────────────┼─────────────────────────┘
                                │
                    ┌───────────▼───────────┐
                    │   QAI Consultant      │
                    │   Web Server          │
                    │   (FastAPI + Streamlit│
                    │    sau Next.js)       │
                    └───────────┬───────────┘
                                │
              ┌─────────────────┼─────────────────┐
              │                 │                 │
    ┌─────────▼──────┐ ┌────────▼───────┐ ┌──────▼──────────┐
    │  Ollama Server │ │  ChromaDB      │ │  Pending Pool   │
    │  (Mistral)     │ │  (Shared KB)   │ │  (PostgreSQL    │
    │                │ │                │ │   sau SQLite)   │
    └────────────────┘ └────────────────┘ └─────────────────┘
                                │
                    ┌───────────▼───────────┐
                    │  Quality Gate +       │
                    │  Auto-Ingest Worker   │
                    │  (background job)     │
                    └───────────────────────┘
```

---

## Shared KB — Model de Date

### Surse de cunoaștere (în ordinea priorității RAG)
1. **Core KB** — standards + methodologies (ISTQB, OWASP, ISO, etc.)
   - Read-only, actualizat doar de maintainer via GitHub Action
2. **Community KB** — strategii validate de useri cu feedback "yes"
   - Grows over time, auto-ingested după quality gate
   - Tagged cu metadata: `source: community`, `validated_by: user_feedback`

### ChromaDB Collections
```
Collection: qai_knowledge_base
  ├── category: "Standard"         ← Core KB
  ├── category: "Methodology"      ← Core KB
  ├── category: "Expert Knowledge" ← Core KB
  ├── category: "Article"          ← Core KB
  └── category: "Community"        ← Community KB (feedback-validated)
```

---

## Feedback Flow — De la "yes" la KB

```
User dă feedback "yes" pe o strategie generată
        │
        ▼
Strategie salvată în Pending Pool (PostgreSQL)
  metadata: user_session_id, timestamp, project_type, strategy_text
        │
        ▼
Quality Gate Worker (rulează la fiecare 5 minute)
        │
        ├── Check 1: Lungime minimă (>500 cuvinte) ?
        ├── Check 2: Secțiuni obligatorii prezente ?
        │   (Test Scope, Test Types, Risk Assessment, Entry/Exit Criteria)
        ├── Check 3: Nu e duplicat față de KB existent ?
        │   (cosine similarity < 0.95 față de cele mai apropiate chunks)
        └── Check 4: Nu conține PII sau date sensibile ?
              (regex patterns pentru email, phone, IP, credentials)
                │
        ┌───────┴───────┐
       PASS            FAIL
        │                │
        ▼                ▼
Ingestat în         Discarded
ChromaDB            silențios
category: Community (logat pentru debugging)
        │
        ▼
Notification (optional):
"Your strategy contributed to the
 QAI community knowledge base! 🎉"
```

---

## Quality Gate — Detalii

### Check 1: Lungime minimă
```python
MIN_WORDS = 500
word_count = len(strategy_text.split())
passes = word_count >= MIN_WORDS
```

### Check 2: Secțiuni obligatorii
```python
REQUIRED_SECTIONS = [
    "scope", "test type", "risk", "entry criteria", "exit criteria"
]
passes = all(section in strategy_text.lower() for section in REQUIRED_SECTIONS)
```

### Check 3: Duplicate detection
```python
# Embed strategy, query ChromaDB for nearest neighbors
results = chroma.query(query_texts=[strategy_text], n_results=3)
max_similarity = max(results["distances"][0])
passes = max_similarity < 0.95  # cosine similarity threshold
```

### Check 4: PII detection
```python
PII_PATTERNS = [
    r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',  # email
    r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',                          # phone
    r'\b(?:\d{1,3}\.){3}\d{1,3}\b',                            # IP
    r'(?i)(password|secret|token|api.?key)\s*[:=]\s*\S+',       # credentials
]
passes = not any(re.search(p, strategy_text) for p in PII_PATTERNS)
```

---

## Pending Pool — Schema

```sql
CREATE TABLE pending_strategies (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id    VARCHAR(64),
    project_type  VARCHAR(100),
    strategy_text TEXT NOT NULL,
    feedback      VARCHAR(20) DEFAULT 'yes',
    notes         TEXT,
    created_at    TIMESTAMP DEFAULT NOW(),
    status        VARCHAR(20) DEFAULT 'pending',  -- pending/passed/failed/ingested
    fail_reason   VARCHAR(200),
    ingested_at   TIMESTAMP
);
```

---

## Deployment Stack

| Component | Technology | Justification |
|---|---|---|
| Web framework | FastAPI + Streamlit | Streamlit pentru UI, FastAPI pentru API/workers |
| LLM | Ollama (self-hosted) | Same as local, no API costs |
| Vector DB | ChromaDB (persistent) | Same as local, no migration needed |
| Pending Pool | PostgreSQL | Reliable, ușor de hosted |
| Background worker | APScheduler sau Celery | Quality gate worker |
| Hosting | Hetzner VPS (€5-20/mo) | Cost-effective, full control |
| Reverse proxy | Nginx | SSL termination |

### De ce Hetzner VPS și nu Streamlit Cloud / HF Spaces?
- Ollama nu rulează pe Streamlit Cloud (no GPU, no custom processes)
- HF Spaces suportă Gradio nativ dar Streamlit e limitat
- VPS propriu = control complet, Ollama local, ChromaDB persistent
- Cost: ~€10-15/lună pentru un server cu 4GB RAM suficient pentru Mistral 7B

---

## Considerații de Securitate

### Rate Limiting
- Max 5 generări per sesiune per oră
- Max 10 feedback submissions per sesiune per zi
- Previne spam în pending pool

### Session Isolation
- Fiecare user are o sesiune izolată (UUID)
- Nu se stochează date personale
- Strategiile din pending pool nu conțin informații despre user

### Quality Gate ca Security Layer
- Check 4 (PII detection) previne ca date sensibile să ajungă în KB
- Threshold-ul de similaritate previne flooding cu conținut duplicat

---

## Diferențe față de versiunea locală

| Aspect | Local | Hosted |
|---|---|---|
| KB | Local ChromaDB | Shared ChromaDB pe server |
| Feedback → KB | Direct ingest via watcher | Pending pool → quality gate → ingest |
| KB updates | `download_kb.py --update` | Automat (shared, toți văd imediat) |
| Ollama | Local install | Server-side (user nu instalează nimic) |
| Privacy | 100% local | Strategiile generate trec prin server |
| Cost user | 0 (doar hardware) | 0 (free hosted tier) |

---

## Roadmap Integration

Aceasta este arhitectura pentru **v1.0**.

Pași necesari înainte de v1.0:
- **v0.7** ✅ (planificat) — HF integration pentru versiunea locală
- **v0.8** — Community knowledge (LinkedIn polls + expert sessions)
- **v1.0** — Hosted version cu shared KB + quality gate + VPS deployment

---

## Definition of Done pentru v1.0 (Hosted)

- [ ] FastAPI backend cu endpoint-uri pentru dialogue, generate, feedback
- [ ] Streamlit UI adaptată pentru hosted (no local paths, session-based)
- [ ] Shared ChromaDB persistent pe VPS
- [ ] Pending Pool (PostgreSQL) pentru strategii în așteptare
- [ ] Quality Gate Worker (4 checks) + APScheduler
- [ ] Rate limiting per sesiune
- [ ] PII detection în quality gate
- [ ] Duplicate detection via ChromaDB similarity
- [ ] Nginx + SSL + domain
- [ ] Monitoring de bază (uptime, error rate)
- [ ] Privacy policy simplă (ce date se stochează)
