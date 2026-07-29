# EU AI-Generated Content Icon

Source: https://digital-strategy.ec.europa.eu/en/policies/eu-icons-labelling-ai-generated-content
(Code of Practice on Transparency of AI-Generated Content, supporting AI Act
Article 50(4)). Fetched 2026-07-29.

License: "made publicly available for everyone to use freely, without the
need for attribution" (per the EU page above).

Variant used: **Fully AI-Generated** ("LABEL_AI GENERATED_*" in the official
bundle) — QAI Consultant's document bodies (Risk Register, Effort
Estimation, Test Strategy, Test Plan, QA Document Quality Review) are
entirely LLM-produced; the user only supplies structured interview inputs,
never document text. The "Basic" and "Partially AI-Modified" variants in the
official bundle are not used here.

## Files

| File | Source (official bundle name) | Used by |
|---|---|---|
| `eu_ai_generated_icon.svg` | `LABEL_AI GENERATED_black transparent.svg` | Streamlit sidebar, light theme |
| `eu_ai_generated_icon_dark.svg` | `LABEL_AI GENERATED_white transparent.svg` | Streamlit sidebar, dark theme |
| `eu_ai_generated_icon.png` | `LABEL_AI GENERATED_black transparent.png`, downscaled from 7459x2363px to 240x76px | PDF export (`src/ai_disclosure.py`'s `pdf_icon_html()`) — xhtml2pdf renders raster images, not SVG; PDF pages are always white background regardless of the app's Streamlit theme, so only the black variant is needed here |

Deepfake-labelling icon variants (image/audio/video) are not vendored here —
QAI Consultant produces only text documents.
