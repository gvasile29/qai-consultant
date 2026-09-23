# Audit QAI Consultant

**Aplicație:** `https://quality-ai-consultant.streamlit.app/`  
**Repository:** `https://github.com/gvasile29/qai-consultant`  
**Data auditului:** 23 septembrie 2026

## Context

Aplicația este publică și searchable în Streamlit Community Cloud. URL-ul live nu a putut fi încărcat complet de mediul meu de browsing, astfel că auditul tehnic și de produs de mai jos se bazează în principal pe repository-ul public și pe codul inspectat; comportamentul vizual efectiv în browser nu a putut fi validat integral.

Repository-ul arată un proiect mult mai matur decât un simplu demo Streamlit: are teste, evaluări, RAG, mai multe moduri de lucru, export PDF și server MCP.

# Verdict

**Proiectul este matur tehnic, dar are nevoie de consolidare înainte de a fi tratat ca produs public-facing la scară mai mare.**

Cele mai importante 5 probleme identificate:

| Prioritate | Problemă | Impact |
|---|---|---|
| **P1** | Controlul costului/abuzului este doar per sesiune | API abuse / cost runaway |
| **P1** | Fallback-ul streaming poate duplica output-ul | Fiabilitate / încredere |
| **P1** | „Grounded by standards” nu înseamnă citation-level grounding | Risc de halucinații / trust |
| **P1** | Effort estimate folosește heuristici fragile pentru risk buffer | Poate altera numeric estimarea |
| **P2** | Fluxul pretinde „dialogue”, dar afișează toate cele 11 întrebări simultan | UX / cognitive load |

# 1. Cost control și abuse protection

Generatorul produce 4 documente:

1. Risk Register
2. Effort Estimation
3. Test Strategy
4. Test Plan

Pipeline-ul folosește retrieval RAG și mai multe generații LLM.

Există un cap de **3 runs per session** prin `st.session_state`.

Problema: acesta nu este un rate limiter real. Un utilizator public poate crea sesiuni noi și poate relua generarea, ceea ce poate duce la costuri LLM greu de controlat.

## Recomandare

Introdu un control server-side de tip:

```text
IP/session fingerprint → quota → generation lock → token/input cap → provider budget
```

și separat:

- maximum input chars;
- maximum generation count;
- maximum concurrent generations;
- timeout per provider;
- circuit breaker când providerul este indisponibil;
- limită globală zilnică.

# 2. Bug potențial în fallback-ul de streaming

`LLMClient._chat_stream()` începe să primească stream de la Mistral și deja livrează conținut către UI. Dacă apare ulterior o excepție, codul poate porni un nou stream de la OpenRouter.

Scenariul problematic:

```text
Mistral:
"## Test Strategy
...
[connection breaks]

OpenRouter:
"## Test Strategy
...
"
```

Poate duce la output duplicat:

```text
## Test Strategy
...
## Test Strategy
...
```

Este greu de reprodus, dar foarte vizibil atunci când apare.

## Recomandare

Fallback-ul ar trebui permis doar **înainte de primul token**.

```text
before first token:
    fallback allowed

after first token:
    do NOT restart from scratch
    surface partial-generation failure
```

Alternativ, este necesar un mecanism explicit de resume, nu regenerare completă.

**Prioritate: P1.**

# 3. RAG bun, dar grounding-ul nu este citation-level

Arhitectura este:

```text
user context
   ↓
embedding
   ↓
Pinecone top-k
   ↓
knowledge context
   ↓
LLM
```

Este folosit `TOP_K_RESULTS = 5` / `RAG_K_GENERATION = 5`.

Prompturile cer referențierea standardelor și contextul conține surse de forma `[Source N — category: filename]`.

Problema este că rezultatul final nu leagă mecanic fiecare afirmație importantă de o sursă precisă.

Ai:

```text
claim X
claim Y
claim Z

Knowledge Sources Used
- source1
- source2
- source3
```

dar nu neapărat:

```text
claim X → Source 3
claim Y → Source 1
```

Pentru QA / Security / Compliance această diferență contează.

## Recomandare

Pentru recomandări importante:

```text
Recommendation
Why
Evidence
[Specific source]
```

sau:

```text
R03 — Authentication
Evidence: [Source 2]
```

Asta ar crește semnificativ trasabilitatea și încrederea.

# 4. Effort Estimation: `risk_buffer()` este fragil

Separarea `effort_core.py` de LLM este foarte bună: calculul este determinist, iar LLM-ul este folosit pentru partea narativă.

Problema este că `risk_buffer()` numără textual apariții precum:

```python
critical_count = rr_lower.count("critical")
high_count = rr_lower.count("| high") + rr_lower.count("risk level: high")
medium_count = ...
```

Numărul de apariții ale cuvântului „critical” nu este neapărat numărul de riscuri critice.

De exemplu:

```text
Risk Level: Critical
Critical impact
Critical payment failure
```

poate fi interpretat drept mai mult de un risc.

Există un cap de 35%, dar estimarea poate fi totuși distorsionată.

## Recomandare

Parsează structura tabelară și numără rândurile:

```text
Risk ID | ... | Risk Level
R01     | ... | Critical
R02     | ... | High
```

nu cuvintele.

# 5. Confidence score: `none` nu este același lucru cu `unknown`

În `calculate_data_quality()`, valori ca:

```text
none
n/a
unknown
not sure
```

sunt tratate ca răspunsuri vagi.

Dar:

```text
Compliance requirements: none
Existing automation: none
```

pot fi răspunsuri foarte precise și utile.

## Recomandare

Separă semantic:

```text
ABSENT / NONE
UNKNOWN
VAGUE
SPECIFIC
EMPTY
```

de exemplu:

```text
none → 4
unknown → 2
maybe → 2
specific → 4
empty → 0
```

# 6. UX: „11-question dialogue” nu este, de fapt, un dialog

README-ul descrie produsul ca un:

**guided 11-question dialogue**

Dar implementarea Streamlit randă toate cele 11 întrebări în același formular.

Modelul actual este:

```text
scroll
scroll
scroll
scroll
11 inputs
Submit
```

nu:

```text
Question 1/11
→
Question 2/11
→
...
```

## De ce contează

Pentru un produs poziționat drept „AI consultant”, experiența ar trebui să pară că îți pune întrebări progresiv, nu că completezi un formular lung.

## Recomandare

Transformă flow-ul într-un wizard:

```text
01/11
What are we testing?

[ answer ]

Continue →
```

cu:

```text
← Back
Skip
Progress 4 / 11
```

Aș păstra stilul vizual actual, dar aș schimba interaction model-ul.

# 7. Homepage-ul are prea multe mesaje concurente

Din cod reiese un efort mare pe visual identity:

- IBM Plex;
- token-based theme;
- light/dark;
- Signal Ledger;
- animații;
- responsive behavior;
- reduced-motion.

Pe homepage apar simultan:

- hero;
- gauges;
- standards;
- how it works;
- 4 deliverables;
- 4 stats;
- diferențiere vs Claude/Gemini;
- exemple;
- primary CTA;
- secondary CTA;
- sidebar;
- release notes;
- MCP announcement;
- AI disclosure;
- maturity assessment.

Problema nu este lipsa de informație, ci abundența.

Primary CTA-ul este clar:

> Start — Generate a Test Strategy

dar produsul are mai multe use-case-uri:

```text
Generate new QA plan
Review existing QA document
Assess QA maturity
Analyze test results
```

## Recomandare

Homepage-ul poate fi simplificat la 3 carduri principale:

```text
PLAN A NEW PROJECT
Generate Risk + Effort + Strategy + Plan

REVIEW WHAT YOU HAVE
Score a Test Plan / Strategy / Test Cases

ASSESS YOUR QA PROCESS
Get maturity + improvement areas
```

„Analyze test results” poate deveni input opțional în primul flow sau poate fi păstrat ca modul secundar.

# 8. Output-ul este puternic pentru QA, dar îi lipsește un „so what?”

Cele 4 documente sunt bine definite și exportabile în Markdown/PDF:

```text
Risk Register
Effort
Strategy
Test Plan
```

Ce lipsește este un rezumat executiv care spune ce trebuie făcut mai întâi.

## Recomandare

Adaugă înaintea celor 4 documente:

### QAI Executive Readout

```text
Overall risk       HIGH
QA effort          42–51 person-days
Capacity           36 person-days
Main gap           Integration + security
Recommended first  3 actions
```

Apoi tab-urile detaliate.

Astfel:

- managerul vede imediat implicațiile;
- specialistul poate intra în documentele complete.

# 9. Ce ai făcut foarte bine tehnic

## Separarea deterministic / LLM

`review_core.py`, `results_core.py`, `maturity_core.py` și `effort_core.py` sunt independente de LLM și Streamlit.

Asta este o decizie arhitecturală foarte bună:

- rezultate repetabile;
- mai ușor de testat;
- cost redus;
- logică deterministă pentru calcule.

## Security hygiene

Se văd mai multe măsuri bune:

- `html.escape()` pentru text randat prin `unsafe_allow_html=True`;
- `defusedxml` pentru JUnit XML;
- limite de upload de 10 MB;
- sanitizare pentru front matter YAML;
- `.env` gitignored;
- Bandit + mypy + Ruff în CI.

## Robustness la rerun

Ai tratat explicit natura rerun-based a Streamlit prin:

```text
generation_started
results_complete
per-stage state
StopException / RerunException
```

și ai încercat să nu regenerezi documentele deja finalizate.

Este o zonă în care proiectul pare gândit serios.

## AI disclosure

Există disclosure atât în UI, cât și în output-uri, inclusiv metadata pentru documente și PDF.

## Test coverage și CI

CI are un gate de **60% coverage**, plus teste statice și security checks.

# 10. Ce aș schimba în următoarea versiune

## Sprint 1 — Reliability

### Fix streaming fallback

```text
retry only before first token
```

### Fix risk-buffer parser

```text
parse risk matrix rows, don't count words
```

### Fix confidence semantics

```text
none != unknown
```

### Add provider timeout + circuit breaker

---

## Sprint 2 — Public product protection

Implement:

```text
per-session limit
+
per-IP/day limit
+
global daily budget
+
max input size/tokens
+
concurrency limit
```

Aplicația publică este practic un endpoint LLM cu UI, deci cost control-ul trebuie tratat ca parte din produs, nu doar ca infrastructură.

---

## Sprint 3 — UX

Schimbă:

```text
11 questions on one page
```

în:

```text
11-step conversational wizard
```

și homepage-ul în:

```text
PLAN
REVIEW
ASSESS
```

---

## Sprint 4 — Output quality

Adaugă:

```text
Executive Readout
```

înaintea celor 4 documente.

Și:

```text
recommendation → evidence → source
```

în loc de doar:

```text
Knowledge Sources Used
```

# 11. Ce nu aș mai adăuga acum

Nu aș prioritiza încă funcționalități noi.

Proiectul are deja:

- Test Strategy;
- Risk Register;
- Effort Estimation;
- Test Plan;
- Document Review;
- Test Results Analysis;
- QA Maturity;
- MCP;
- RAG;
- PDF;
- feedback loop;
- telemetry;
- release notes.

Repository-ul are deja o suprafață funcțională mare.

În această etapă, **quality-of-experience, reliability și cost control** au mai multă valoare decât încă un feature.

# Concluzie

**Nucleul tehnic este bun.**

Problema principală nu este lipsa de tehnologie, ci faptul că produsul a crescut rapid și acum are nevoie de o etapă de consolidare.

Cele mai importante două schimbări de produs sunt:

1. transformarea celor 11 întrebări într-un wizard conversațional real;
2. introducerea unui Executive Readout înaintea celor 4 documente.

Asta ar muta experiența din zona de „generator QA sofisticat” spre un **AI QA consultant pe care îl înțelegi și îl folosești imediat**.

## Note despre acces și surse

Auditul a pornit de la aplicația live și de la repository-ul public:

- `https://quality-ai-consultant.streamlit.app/`
- `https://github.com/gvasile29/qai-consultant`

URL-ul live nu a putut fi încărcat complet de mediul meu de browsing, așa că afirmațiile despre UI-ul efectiv în browser trebuie considerate mai puțin certe decât cele bazate direct pe cod.

Pentru documentarea tehnică Streamlit au fost consultate materialele oficiale despre sharing/public apps, authentication, secrets și indexability.
