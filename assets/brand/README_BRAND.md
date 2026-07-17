# QAI Consultant - Brand Assets (v2, "Pixelul defect")

Concept: un Q construit din pixeli pe grid, in care un singur pixel, cel din coada Q-ului, este in culoarea de accent. Povestea: QA gaseste pixelul care nu e la locul lui. Constructia pe grid si estetica pixel sunt aliniate cu trendurile 2026 (neo-minimalism, monograme bold, grid ultra-crisp) si evita cliseele AI (hexagoane, spirale, gradiente) si cliseul QA (bifa).

Wordmark: "QAI" geometric monoline bold; Q-ul citeste si ca o lupa de inspectie. Sub el, "CONSULTANT" in majuscule monoline tracked, slate estompat (#475569 / #94A3B8 pe dark), pentru ierarhie.

## Paleta "Ocean"

| Rol | Fundal deschis | Fundal inchis |
|---|---|---|
| Pixeli Q / wordmark | `#0F172A` | `#F1F5F9` |
| Pixelul defect (accent) | `#14B8A6` | `#2DD4BF` |
| Fundal inchis brand | `#0F172A` | - |

## Fisiere

| Fisier | Utilizare |
|---|---|
| `qai_logo.svg` / `qai_logo_dark.svg` | Sursa vectoriala, lockup orizontal (simbol + QAI) |
| `qai_icon.svg` / `qai_icon_dark.svg` | Doar simbolul, vectorial |
| `qai_logo_stacked.svg` | Varianta patrata (simbol sus, QAI jos) |
| `qai_favicon.svg` | Simbol pe tile navy rotunjit |
| `qai_logo_1024.png` | Patrat, transparent - profil social media |
| `qai_logo_social_1024.png` | Patrat, fundal alb - postari fara transparenta |
| `qai_logo_horizontal_1680.png` / `_dark_` | Banner orizontal - postari, LinkedIn, README |
| `qai_icon_512.png` | Simbol mare, transparent |
| `qai_favicon_64.png`, `qai_favicon_32.png` | Favicon / page_icon Streamlit |

## Integrare Streamlit (`src/app.py`)

```python
st.set_page_config(
    page_title="QAI Consultant",
    page_icon="assets/brand/qai_favicon_32.png",
)

# Logo in sidebar (Streamlit >= 1.35):
st.logo(
    "assets/brand/qai_logo.svg",
    icon_image="assets/brand/qai_icon.svg",
)
```

## Reguli de utilizare

- Pixelul defect este intotdeauna unul singur si intotdeauna in coltul din dreapta-jos. Nu-i schimba pozitia sau culoarea.
- Pe fundal deschis: variantele standard. Pe fundal inchis (`#0F172A` sau mai inchis): variantele `_dark`.
- Spatiu liber minim in jurul logo-ului: dimensiunea unui pixel din grid.
- Sub 48px foloseste doar simbolul (`qai_icon`) sau favicon-ul, nu lockup-ul cu text. Randul "CONSULTANT" apare doar in lockup-urile mari (orizontal si stacked); nu il adauga separat si nu il mari fata de proportia din SVG.
- Nu modifica proportiile gridului (celula 12, spatiu 3).
