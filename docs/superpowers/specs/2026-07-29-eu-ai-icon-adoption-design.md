# EU AI-Generated Content Icon Adoption — Design

**Date:** 2026-07-29
**Status:** Approved by user, pending spec review

## Problem

The EU published a set of official icons for labelling AI-generated content
(https://digital-strategy.ec.europa.eu/en/policies/eu-icons-labelling-ai-generated-content),
part of the Code of Practice on Transparency of AI-Generated Content, which
supports compliance with AI Act Article 50(4). QAI Consultant already ships a
text/metadata-based disclosure system (`src/ai_disclosure.py`, v2.5.2/v2.6:
`AI_INTERACTION_NOTICE`, `with_ai_footer()`, `build_front_matter()`,
`pdf_meta_html()`) — `ai_disclosure.py`'s own docstring flagged re-reviewing
it once the Code of Practice's icon set was published. This spec is that
review: adopt the official icon graphic as a visual reinforcement of the
existing disclosure, without changing the disclosure's legal substance.

## Applicability assessment

The EU icon set covers two categories:

1. **Deepfakes** (AI-generated/manipulated image, audio, or video resembling
   real persons/places/events) — **not applicable**. QAI Consultant produces
   only text documents (Risk Register, Effort Estimation, Test Strategy, Test
   Plan, QA Document Review).
2. **AI-generated text published on matters of public interest, without human
   editorial review** — QAI Consultant's outputs are internal QA engineering
   artifacts, not published civic/journalistic content, so the strict legal
   trigger for Article 50(4) arguably doesn't apply. Decision (user-approved):
   adopt the icon anyway as a best-practice reinforcement of the Article
   50(2) disclosure already shipped, rather than relying on a narrow reading
   to skip it.

**Icon variant:** the EU set offers "Basic," "Fully AI-Generated," and
"Partially AI-Modified" variants, each in black/white/transparent. QAI
Consultant's document bodies are entirely LLM-produced (the user only
supplies structured interview inputs, never document text) — use the
**"Fully AI-Generated"** variant consistently across all five generators.

## Assets

Vendor the icon files (SVG + PNG) from the EU's redirect links
(`https://ec.europa.eu/newsroom/dae/redirection/document/129546` for SVG,
`.../129547` for PNG) into a new directory, `assets/eu_ai_icon/`, kept
separate from `assets/brand/` (QAI's own identity assets, documented in
`assets/brand/README_BRAND.md`) since these are third-party regulatory
assets, not QAI branding.

`assets/eu_ai_icon/README_EU_AI_ICON.md` records provenance: source URL,
fetch date, license ("made publicly available for everyone to use freely,
without the need for attribution," per the EU page), and which variant
("Fully AI-Generated") was selected from the downloaded bundle.

Expected files after inspecting the downloaded bundle (exact names TBD until
downloaded — the redirect links likely resolve to a zip/package containing
all variant/color combinations):

- An SVG, black-on-transparent — for the Streamlit sidebar, light theme.
- An SVG, white-on-transparent — for the Streamlit sidebar, dark theme.
- A PNG, black-on-transparent — for PDF embedding (xhtml2pdf/reportlab
  renders raster images, not SVG, so PDF export needs PNG regardless of
  theme; PDF background is always white).

## Streamlit sidebar integration

`render_sidebar()` (`app.py:280-292`) currently renders
`AI_INTERACTION_NOTICE` via a plain `st.info(...)` call at line 287, with no
`st.image()` in that function. Add the icon immediately alongside it using
`st.columns([1, 5])` — icon in the narrow column, the existing `st.info()`
text in the wide column — selecting the black/white SVG variant via the same
theme-detection mechanism `app.py` already uses to pick between
`qai_logo.svg` / `qai_logo_dark.svg` for the header logo.

The CSS rule at `app.py:106-110` currently applies to all
`[data-testid="stImage"]` elements and is commented "the only st.image in
this app" — since this adds a second `st.image()` call, that selector must
be scoped specifically to the header logo's container (e.g. via a wrapping
key/class) so the new sidebar icon isn't mis-styled by rules meant for the
centered header logo.

## PDF export integration

`markdown_to_pdf()` (`pdf_export.py:32-99`) builds a literal HTML string —
`<head>` currently only receives invisible `<meta>` tags via
`pdf_meta_html()` (metadata-only, by design — adding an image there would
have no visual effect). The icon must go in the `<body>` template instead
(`pdf_export.py:81-84`), which today has no images at all.

Add a new function to `ai_disclosure.py` (e.g. `pdf_icon_html(icon_path) ->
str`) that base64-encodes the vendored PNG into a data-URI `<img>` tag, and
thread it into `markdown_to_pdf()` as a new optional parameter (e.g.
`extra_body_html`), inserted once near the top of body content (e.g. right
after `<h1>{safe_title}</h1>`) so it renders on the first page, matching the
Code of Practice's "clearly perceivable... at the latest at the time of
first exposure" placement guidance.

All four document PDF exports (`app.py:930-933`) and the QA Document Quality
Review PDF export (`app.py:1279`) get this the same way, since they already
share `pdf_meta_html()` computed once (`app.py:929`) — the icon becomes a
second shared value computed alongside it.

## Explicitly out of scope

- **Deepfake icon variant** — not applicable (no image/audio/video output).
- **Markdown `.md` downloads** (`app.py:954/977/1003/1030/1288`) — stay
  text-only via the existing `with_ai_footer()` wording. A raw `.md` file
  with an embedded base64 image would bloat every saved document and isn't
  needed since the existing footer text already discloses AI generation.
- **CLI (`src/cli.py`)** — confirmed zero references to any of the four
  `ai_disclosure` symbols already (the disclosure is baked into the shared
  generator `save()` methods, not called directly by `cli.py`); a terminal
  can't render an image regardless.
- **MCP server** — no document-generation surface at all (per the "MCP
  lens": `ask()`/document generation stay in Streamlit/CLI, never exposed
  via MCP), so nothing to change there.
- **No change to `build_front_matter()` or `pdf_meta_html()`'s machine-readable
  marking** — that mechanism is separate and already compliant; this work
  only adds a visible graphic on top.

## Testing / verification

- Manual: run Streamlit locally, confirm the icon renders correctly in both
  light and dark sidebar themes, generate a document, download its PDF,
  confirm the icon appears on the first page, confirm no regression to the
  existing header-logo centering CSS.
- Check `tests/test_packaging.py`'s MCP wheel allowlist to confirm
  `assets/eu_ai_icon/` (Streamlit-only) doesn't need to be — and isn't
  accidentally — included in the `qai-consultant-mcp` PyPI package.
- New unit test(s) for the new `ai_disclosure.py` function (e.g. valid
  base64 data URI produced, doesn't raise if the asset file is missing —
  follow the project's existing never-crash philosophy for anything on the
  document-generation path).

## Timeline note

Requested target: before 2026-08-02 (AI Act Article 50's application date).
The underlying legal disclosure obligation is already met by the
v2.5.2/v2.6 machine-readable + visible-footer mechanism — this icon is an
enhancement, not a new compliance gap. If the timeline gets tight, the
sidebar icon is the higher-value/lower-risk piece (small, isolated Streamlit
change); the PDF embedding touches a shared export path used by five
document types and warrants more careful testing. The implementation plan
should sequence sidebar first, PDF as a fast-follow if time is short, rather
than treating both as a single all-or-nothing unit.

## Release

Version bump to **v3.3** (the roadmap's currently-open patch slot, ahead of
v3.4's larger visual redesign). Full release checklist applies: `version.py`,
`pyproject.toml`, `CHANGELOG.md`, `README.md`, `README_MCP.md` (no MCP
surface change — one-line note only), `CLAUDE.md` (new gotcha entries for
the CSS-scoping fix and the PNG-vs-SVG PDF constraint, plus the architecture
table row for the new `ai_disclosure.py` function and `assets/eu_ai_icon/`).
