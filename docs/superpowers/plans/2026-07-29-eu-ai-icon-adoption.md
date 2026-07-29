# EU AI-Generated Content Icon Adoption Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adopt the EU's official "Fully AI-Generated" Code of Practice icon (supporting AI Act Article 50(4)) as a visual reinforcement of QAI Consultant's existing text/metadata AI disclosure system (`src/ai_disclosure.py`, v2.5.2/v2.6), in the Streamlit sidebar and in every generated document's PDF export.

**Architecture:** Vendor the icon (SVG for Streamlit, PNG for PDF — xhtml2pdf can't render SVG) into a new `assets/eu_ai_icon/` directory. Add one new dependency-free function to `ai_disclosure.py` that base64-encodes the PNG into an `<img>` data URI; thread it through a new `extra_body_html` parameter on `pdf_export.py`'s `markdown_to_pdf()`. Add the SVG next to the existing sidebar disclosure notice in `app.py`, theme-aware, reusing the theme-detection variable already used for the header logo.

**Tech Stack:** Python (stdlib `base64`, `pathlib`), Streamlit `st.image`/`st.columns`/`st.container(key=...)`, xhtml2pdf (existing dependency, no version change), pytest.

## Global Constraints

- No new runtime dependencies. The icon PNGs are pre-resized and vendored as static files — no image-processing library (e.g. Pillow) is added to `requirements.txt`.
- `src/ai_disclosure.py` stays dependency-free (stdlib only), per its own docstring's requirement to remain importable from every code path including a hypothetical future MCP path.
- xhtml2pdf renders raster images via base64 data URIs but does not render SVG — any image embedded into a PDF must be PNG.
- The MCP server package surface is unaffected: `ai_disclosure.py` is not in `pyproject.toml`'s `[tool.setuptools] py-modules` list, and `assets/` is not part of the packaged wheel (`[tool.setuptools.packages.find]` only includes `knowledge_base*`) — no `pyproject.toml` packaging changes are needed for this feature.
- New functions fail soft (return `""` or `None`, never raise) — matches the existing never-crash philosophy of `with_ai_footer()` / `pdf_meta_html()` / the RAG-prefetch futures.
- Version bump target: `3.1.6` → `3.3.0` (the roadmap's open v3.3 slot). Full release checklist from `CLAUDE.md` applies.
- Markdown `.md` downloads, `src/cli.py`, and the MCP server get **no** changes — they keep the existing text-only `with_ai_footer()` disclosure (confirmed: `cli.py` has zero references to any `ai_disclosure` symbol; the disclosure is baked into the shared generator `save()` methods).

---

### Task 1: Vendor the EU AI-Generated Content icon assets

**Files:**
- Create: `assets/eu_ai_icon/eu_ai_generated_icon.svg`
- Create: `assets/eu_ai_icon/eu_ai_generated_icon_dark.svg`
- Create: `assets/eu_ai_icon/eu_ai_generated_icon.png`
- Create: `assets/eu_ai_icon/README_EU_AI_ICON.md`

**Interfaces:**
- Produces: three static asset files at fixed, predictable paths under `assets/eu_ai_icon/`, consumed by Task 2 (`EU_AI_ICON_DIR` in `ai_disclosure.py`) and Task 5 (`app.py`'s sidebar).

The source files were already downloaded and verified in this session from the EU's official redirect links (`https://ec.europa.eu/newsroom/dae/redirection/document/129546` for the SVG bundle, `.../129547` for the PNG bundle — both are zip archives). The bundle contains three label variants (Basic `LABEL_AI_*`, Fully-Generated `LABEL_AI GENERATED_*`, Partially-Modified `LABEL_AI MODIFIED_*`) — this task uses only the **Fully-Generated** variant, per the design spec's applicability assessment (QAI's document bodies are entirely LLM-produced).

The raw PNGs from the bundle are 7459×2363px (~145KB each) — far larger than needed for a footer badge and would bloat every generated PDF once base64-encoded. They must be downscaled to 240×76px before vendoring (already done once in this session with Pillow, a one-time asset-prep step — **not** a new project dependency, since only the resulting static PNG is committed).

- [ ] **Step 1: Re-fetch and extract the icon bundles**

```bash
mkdir -p /tmp/eu_ai_icon_dl && cd /tmp/eu_ai_icon_dl
curl -sL -o svg_bundle.zip "https://ec.europa.eu/newsroom/dae/redirection/document/129546"
curl -sL -o png_bundle.zip "https://ec.europa.eu/newsroom/dae/redirection/document/129547"
mkdir -p svg_extract png_extract
unzip -o -q svg_bundle.zip -d svg_extract
unzip -o -q png_bundle.zip -d png_extract
```

Expected: `svg_extract/` and `png_extract/` each contain 12 files, including
`LABEL_AI GENERATED_black transparent.svg`, `LABEL_AI GENERATED_white transparent.svg`,
and `LABEL_AI GENERATED_black transparent.png`.

- [ ] **Step 2: Downscale the PNG to a footer-badge size**

```bash
python -c "
from PIL import Image
im = Image.open('/tmp/eu_ai_icon_dl/png_extract/LABEL_AI GENERATED_black transparent.png')
target_w = 240
ratio = target_w / im.width
im2 = im.resize((target_w, round(im.height * ratio)), Image.LANCZOS)
im2.save('/tmp/eu_ai_icon_dl/eu_ai_generated_icon.png', optimize=True)
print(im2.size)
"
```

Expected output: `(240, 76)`. Resulting file should be roughly 6-7KB (verified in
session: 6633 bytes). If Pillow is unavailable in the environment doing this
step, any equivalent image tool (ImageMagick's `convert -resize 240x`, etc.)
produces the same result — the exact tool doesn't matter, only the committed
output file does.

- [ ] **Step 3: Copy the three files into the repo**

```bash
mkdir -p assets/eu_ai_icon
cp "/tmp/eu_ai_icon_dl/svg_extract/LABEL_AI GENERATED_black transparent.svg" \
   assets/eu_ai_icon/eu_ai_generated_icon.svg
cp "/tmp/eu_ai_icon_dl/svg_extract/LABEL_AI GENERATED_white transparent.svg" \
   assets/eu_ai_icon/eu_ai_generated_icon_dark.svg
cp /tmp/eu_ai_icon_dl/eu_ai_generated_icon.png assets/eu_ai_icon/eu_ai_generated_icon.png
```

- [ ] **Step 4: Write the provenance README**

Create `assets/eu_ai_icon/README_EU_AI_ICON.md`:

```markdown
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
| `eu_ai_generated_icon.png` | `LABEL_AI GENERATED_black transparent.png`, downscaled to 240x76px | PDF export (`src/ai_disclosure.py`'s `pdf_icon_html()`) — xhtml2pdf renders raster images, not SVG; PDF pages are always white background regardless of the app's Streamlit theme, so only the black variant is needed here |

Deepfake-labelling icon variants (image/audio/video) are not vendored here —
QAI Consultant produces only text documents.
```

- [ ] **Step 5: Verify the files are valid and non-trivial**

```bash
file assets/eu_ai_icon/eu_ai_generated_icon.svg assets/eu_ai_icon/eu_ai_generated_icon_dark.svg assets/eu_ai_icon/eu_ai_generated_icon.png
ls -la assets/eu_ai_icon/
```

Expected: the two `.svg` files report as `SVG Scalable Vector Graphics image`
(or `XML document text`), the `.png` reports as `PNG image data, 240 x 76`,
and none of the three files is 0 bytes.

- [ ] **Step 6: Commit**

```bash
git add assets/eu_ai_icon/
git commit -m "feat: vendor EU AI-generated content icon assets"
```

---

### Task 2: Add `pdf_icon_html()` to `src/ai_disclosure.py`

**Files:**
- Modify: `src/ai_disclosure.py`
- Test: `tests/test_ai_disclosure.py`

**Interfaces:**
- Consumes: `assets/eu_ai_icon/eu_ai_generated_icon.png` (Task 1).
- Produces: `pdf_icon_html(icon_filename: str = "eu_ai_generated_icon.png") -> str`
  — consumed by Task 3/4 (`pdf_export.py`'s new `extra_body_html` param, and
  `app.py`'s PDF call sites).

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_ai_disclosure.py` (update the import line and append these
functions, plus add them to the `__main__` list at the bottom):

```python
from ai_disclosure import (
    AI_INTERACTION_NOTICE,
    AI_GENERATED_FOOTER,
    EU_AI_ICON_DIR,
    pdf_icon_html,
    with_ai_footer,
)


def test_pdf_icon_html_returns_data_uri_img_tag():
    """pdf_icon_html() returns a base64 data-URI <img> tag for the vendored PNG."""
    html = pdf_icon_html()
    assert html.startswith("<img "), f"Expected an <img> tag, got: {html[:50]!r}"
    assert "data:image/png;base64," in html
    assert "alt=" in html, "Missing alt text for assistive technologies"
    print("  PASS: pdf_icon_html() returns a data-URI <img> tag")


def test_pdf_icon_html_missing_file_returns_empty_string():
    """A missing/renamed asset file fails soft — no exception, no broken PDF."""
    assert pdf_icon_html("does_not_exist.png") == ""
    print("  PASS: pdf_icon_html() with a missing file returns ''")


def test_vendored_icon_assets_exist():
    """Guards against accidental deletion/rename of the vendored icon files."""
    for fname in (
        "eu_ai_generated_icon.svg",
        "eu_ai_generated_icon_dark.svg",
        "eu_ai_generated_icon.png",
    ):
        path = EU_AI_ICON_DIR / fname
        assert path.is_file(), f"Missing vendored asset: {path}"
    print("  PASS: all three vendored EU AI icon assets exist")
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
python -m pytest tests/test_ai_disclosure.py -v -k "pdf_icon_html or vendored_icon"
```

Expected: `ImportError: cannot import name 'EU_AI_ICON_DIR'` (or `pdf_icon_html`)
— these names don't exist in `ai_disclosure.py` yet.

- [ ] **Step 3: Implement `EU_AI_ICON_DIR` and `pdf_icon_html()`**

In `src/ai_disclosure.py`, add the `base64` and `Path` imports and the new
constant/function. Insert after the existing `from version import __version__`
line:

```python
import base64
from pathlib import Path

EU_AI_ICON_DIR = Path(__file__).resolve().parent.parent / "assets" / "eu_ai_icon"
```

Append the new function at the end of the file (after `pdf_meta_html()`):

```python
def pdf_icon_html(icon_filename: str = "eu_ai_generated_icon.png") -> str:
    """Base64-embedded <img> tag for the EU AI-Generated Content icon (Code of
    Practice on Transparency of AI-Generated Content, supporting AI Act
    Article 50(4)) — for injection into a PDF export's <body>.

    xhtml2pdf renders raster data URIs but not SVG, hence PNG here (the
    Streamlit sidebar uses the SVG variants directly instead, via
    EU_AI_ICON_DIR). Returns "" if the icon asset is missing, never raises —
    same never-crash philosophy as with_ai_footer()/pdf_meta_html(), so a
    missing/renamed asset file degrades to no icon, not a broken PDF.
    """
    icon_path = EU_AI_ICON_DIR / icon_filename
    try:
        icon_bytes = icon_path.read_bytes()
    except OSError:
        return ""
    encoded = base64.b64encode(icon_bytes).decode("ascii")
    return (
        f'<img src="data:image/png;base64,{encoded}" '
        'alt="EU AI-Generated Content label" '
        'style="height:28pt;margin-bottom:6pt;" />'
    )
```

Also update the module docstring's four-responsibilities list to mention this
fifth one, and update the stale note about "MCP_PLAN.md section 12" (that
file was trimmed and no longer has a section 12 — replace the sentence with
a short note that the Code of Practice icon was adopted in v3.3, see
`docs/superpowers/specs/2026-07-29-eu-ai-icon-adoption-design.md`).

- [ ] **Step 4: Run the tests to verify they pass**

```bash
python -m pytest tests/test_ai_disclosure.py -v
```

Expected: all tests in the file PASS, including the pre-existing four from
v2.5.2.

- [ ] **Step 5: Commit**

```bash
git add src/ai_disclosure.py tests/test_ai_disclosure.py
git commit -m "feat: add pdf_icon_html() for EU AI-generated content icon"
```

---

### Task 3: Add `extra_body_html` parameter to `markdown_to_pdf()`

**Files:**
- Modify: `src/pdf_export.py`
- Test: `tests/test_pdf_export.py`

**Interfaces:**
- Consumes: `pdf_icon_html()` output (Task 2) — but only as an opaque string;
  this task doesn't import `ai_disclosure` directly, keeping `pdf_export.py`
  ignorant of what "extra body html" actually contains, same separation of
  concerns as the existing `extra_meta_html` parameter.
- Produces: `markdown_to_pdf(md_text, title="...", extra_meta_html="", extra_body_html="") -> bytes | None`
  — consumed by Task 4 (`app.py`'s five PDF call sites).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_pdf_export.py`:

```python
def test_extra_body_html_injected_into_generated_html():
    """extra_body_html's content reaches xhtml2pdf's actual HTML input."""
    captured = {}

    def fake_create_pdf(src, dest, encoding):
        captured["html"] = src.decode("utf-8") if isinstance(src, bytes) else src
        dest.write(b"%PDF-fake")

        class _Result:
            err = 0

        return _Result()

    with patch("xhtml2pdf.pisa.CreatePDF", side_effect=fake_create_pdf):
        result = markdown_to_pdf(
            _SIMPLE_MD,
            extra_body_html='<img src="data:image/png;base64,AAAA" alt="EU AI icon" />',
        )

    assert result == b"%PDF-fake"
    assert 'alt="EU AI icon"' in captured["html"], "extra_body_html did not reach the HTML body"


def test_extra_body_html_default_empty_does_not_raise():
    """Default (no icon passed) behaves exactly as before this change."""
    result = markdown_to_pdf(_SIMPLE_MD)
    assert result is None or isinstance(result, bytes)
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
python -m pytest tests/test_pdf_export.py -v -k extra_body_html
```

Expected: `TypeError: markdown_to_pdf() got an unexpected keyword argument 'extra_body_html'`.

- [ ] **Step 3: Implement the parameter**

In `src/pdf_export.py`, update the function signature and body:

```python
def markdown_to_pdf(
    md_text: str,
    title: str = "QAI Consultant Report",
    extra_meta_html: str = "",
    extra_body_html: str = "",
) -> bytes | None:
    """Convert a markdown string to a styled PDF and return the raw bytes.

    Parameters
    ----------
    md_text:
        The markdown source text to render.
    title:
        Document title injected as an <h1> at the top of the PDF, and mapped by
        xhtml2pdf onto the PDF's /Title metadata field via the HTML <title> tag.
    extra_meta_html:
        Additional raw HTML <meta> tag(s) to inject into <head> — e.g.
        ai_disclosure.pdf_meta_html() for the EU AI Act Article 50(2)
        machine-readable marking (mapped onto /Author, /Subject, /Keywords).
        Empty string (default) injects nothing.
    extra_body_html:
        Additional raw HTML to inject into <body>, right after the <h1>
        title — e.g. ai_disclosure.pdf_icon_html() for the EU AI-Generated
        Content icon (Article 50(4)). Unlike extra_meta_html, this is
        rendered, visible content. Empty string (default) injects nothing.

    Returns
    -------
    bytes | None
        PDF bytes on success, ``None`` on any error (silent fail so callers
        can skip the download button rather than crashing).
    """
```

Then update the HTML-building block:

```python
        safe_title = escape(title)
        meta_block = f"  {extra_meta_html}\n" if extra_meta_html else ""
        body_prefix = f"  {extra_body_html}\n" if extra_body_html else ""
        html = (
            f'<!DOCTYPE html>\n'
            f'<html>\n'
            f'<head>\n'
            f'  <meta charset="UTF-8" />\n'
            f'  <title>{safe_title}</title>\n'
            f'{meta_block}'
            f'  <style>{_CSS}</style>\n'
            f'</head>\n'
            f'<body>\n'
            f'  <h1>{safe_title}</h1>\n'
            f'{body_prefix}'
            f'  {body_html}\n'
            f'</body>\n'
            f'</html>\n'
        )
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
python -m pytest tests/test_pdf_export.py -v
```

Expected: all tests PASS, including the 8 pre-existing ones.

- [ ] **Step 5: Commit**

```bash
git add src/pdf_export.py tests/test_pdf_export.py
git commit -m "feat: add extra_body_html param to markdown_to_pdf() for the EU AI icon"
```

---

### Task 4: Wire the icon into all five PDF export call sites in `app.py`

**Files:**
- Modify: `src/app.py:16` (import), `src/app.py:929-933` (four-doc PDF precompute),
  `src/app.py:1277-1280` (QA Document Quality Review PDF)

**Interfaces:**
- Consumes: `pdf_icon_html()` (Task 2), `markdown_to_pdf(..., extra_body_html=...)`
  (Task 3).
- Produces: no new interface — this task is pure call-site wiring, verified by
  Task 6's manual check (no automated Streamlit-script test exists for these
  call sites today, matching the existing project convention of manual
  verification for `app.py` UI wiring).

- [ ] **Step 1: Update the import**

In `src/app.py:16`, change:

```python
from ai_disclosure import AI_INTERACTION_NOTICE, pdf_meta_html, with_ai_footer
```

to:

```python
from ai_disclosure import AI_INTERACTION_NOTICE, pdf_icon_html, pdf_meta_html, with_ai_footer
```

- [ ] **Step 2: Wire the four-document PDF precompute block**

At `src/app.py:928-933`, change:

```python
        if st.session_state.get("risk_pdf_bytes") is None:
            _ai_pdf_meta = pdf_meta_html(MISTRAL_MODEL)
            st.session_state.risk_pdf_bytes = markdown_to_pdf(with_ai_footer(risk_register), "Risk Register", _ai_pdf_meta)
            st.session_state.effort_pdf_bytes = markdown_to_pdf(with_ai_footer(effort_report), "Effort Estimation", _ai_pdf_meta)
            st.session_state.strategy_pdf_bytes = markdown_to_pdf(with_ai_footer(strategy), "Test Strategy", _ai_pdf_meta)
            st.session_state.test_plan_pdf_bytes = markdown_to_pdf(with_ai_footer(test_plan), "Test Plan", _ai_pdf_meta)
```

to:

```python
        if st.session_state.get("risk_pdf_bytes") is None:
            _ai_pdf_meta = pdf_meta_html(MISTRAL_MODEL)
            _ai_pdf_icon = pdf_icon_html()
            st.session_state.risk_pdf_bytes = markdown_to_pdf(with_ai_footer(risk_register), "Risk Register", _ai_pdf_meta, _ai_pdf_icon)
            st.session_state.effort_pdf_bytes = markdown_to_pdf(with_ai_footer(effort_report), "Effort Estimation", _ai_pdf_meta, _ai_pdf_icon)
            st.session_state.strategy_pdf_bytes = markdown_to_pdf(with_ai_footer(strategy), "Test Strategy", _ai_pdf_meta, _ai_pdf_icon)
            st.session_state.test_plan_pdf_bytes = markdown_to_pdf(with_ai_footer(test_plan), "Test Plan", _ai_pdf_meta, _ai_pdf_icon)
```

- [ ] **Step 3: Wire the QA Document Quality Review PDF export**

At `src/app.py:1277-1280`, change:

```python
            _ai_pdf_meta = pdf_meta_html(MISTRAL_MODEL)
            st.session_state.review_pdf_bytes = markdown_to_pdf(
                with_ai_footer(report_md), "QA Document Quality Review", _ai_pdf_meta,
            )
```

to:

```python
            _ai_pdf_meta = pdf_meta_html(MISTRAL_MODEL)
            _ai_pdf_icon = pdf_icon_html()
            st.session_state.review_pdf_bytes = markdown_to_pdf(
                with_ai_footer(report_md), "QA Document Quality Review", _ai_pdf_meta, _ai_pdf_icon,
            )
```

- [ ] **Step 4: Sanity-check the app imports without errors**

```bash
python -c "import sys; sys.path.insert(0, 'src'); import app"
```

Expected: no `ImportError`/`SyntaxError` (Streamlit's own runtime warnings
about missing `ScriptRunContext` on a bare `python -c` import are expected
and harmless — this is just an import-time syntax/name sanity check, not a
full run).

- [ ] **Step 5: Commit**

```bash
git add src/app.py
git commit -m "feat: embed EU AI icon in all generated document PDF exports"
```

---

### Task 5: Streamlit sidebar icon + CSS scoping fix

**Files:**
- Modify: `src/app.py:46` (new `EU_AI_ICON_DIR` constant near `BRAND_DIR`)
- Modify: `src/app.py:106-110` (CSS scoping)
- Modify: `src/app.py:280-292` (`render_sidebar()`)
- Modify: `src/app.py:1326-1333` (header logo, wrapped in a keyed container)

**Interfaces:**
- Consumes: `assets/eu_ai_icon/eu_ai_generated_icon.svg` /
  `eu_ai_generated_icon_dark.svg` (Task 1), the module-level `_theme_type`
  variable already set at `app.py:61`.
- Produces: no new interface — verified manually in Task 6 (Streamlit theme
  switching + visual layout aren't unit-testable without a browser).

- [ ] **Step 1: Add the `EU_AI_ICON_DIR` constant**

At `src/app.py:46`, right after `BRAND_DIR`, add:

```python
BRAND_DIR = Path(__file__).resolve().parent.parent / "assets" / "brand"
EU_AI_ICON_DIR = Path(__file__).resolve().parent.parent / "assets" / "eu_ai_icon"
```

- [ ] **Step 2: Scope the header-logo centering CSS to a keyed container**

At `src/app.py:1326-1333`, change:

```python
    _logo_col1, _logo_col2, _logo_col3 = st.columns([1, 1, 1])
    with _logo_col2:
        _header_logo = (
            "qai_logo_horizontal_dark_1680.png"
            if st.context.theme.type == "dark"
            else "qai_logo_horizontal_1680.png"
        )
        st.image(str(BRAND_DIR / _header_logo), width=280)
```

to:

```python
    _logo_col1, _logo_col2, _logo_col3 = st.columns([1, 1, 1])
    with _logo_col2:
        with st.container(key="header-logo"):
            _header_logo = (
                "qai_logo_horizontal_dark_1680.png"
                if st.context.theme.type == "dark"
                else "qai_logo_horizontal_1680.png"
            )
            st.image(str(BRAND_DIR / _header_logo), width=280)
```

(`st.container(key=...)` generates a wrapping element with CSS class
`st-key-header-logo` — a documented Streamlit mechanism for scoping custom
CSS to one specific widget instance rather than every widget of that type.)

Then, at `src/app.py:106-110`, change:

```python
    /* Centers the top-of-page logo (the only st.image in this app) within its column */
    [data-testid="stImage"] {
        display: flex;
        justify-content: center;
    }
```

to:

```python
    /* Centers the top-of-page logo within its column. Scoped to the keyed
       container (not a blanket [data-testid="stImage"] rule) so it doesn't
       also apply to the sidebar's EU AI-generated-content icon below. */
    .st-key-header-logo [data-testid="stImage"] {
        display: flex;
        justify-content: center;
    }
```

- [ ] **Step 3: Add the icon to `render_sidebar()`**

At `src/app.py:280-292`, change:

```python
def render_sidebar():
    with st.sidebar:
        st.markdown("## 🧪 QAI Consultant")
        st.markdown("AI-powered QA Architect")
        st.caption(f"v{__version__}")
        if st.session_state.get("visit_count") is not None:
            st.caption(f"👀 {st.session_state.visit_count:,} visits")
        st.info(AI_INTERACTION_NOTICE)
        with st.expander("📋 Release Notes"):
```

to:

```python
def render_sidebar():
    with st.sidebar:
        st.markdown("## 🧪 QAI Consultant")
        st.markdown("AI-powered QA Architect")
        st.caption(f"v{__version__}")
        if st.session_state.get("visit_count") is not None:
            st.caption(f"👀 {st.session_state.visit_count:,} visits")
        _eu_icon_svg = (
            "eu_ai_generated_icon_dark.svg"
            if _theme_type == "dark"
            else "eu_ai_generated_icon.svg"
        )
        st.image(str(EU_AI_ICON_DIR / _eu_icon_svg), width=140)
        st.info(AI_INTERACTION_NOTICE)
        with st.expander("📋 Release Notes"):
```

(`_theme_type` is the module-level variable already computed at `app.py:61`
for the header-logo/`st.logo()` theme selection — reused here rather than
recomputing theme detection a second way.)

**Revised during implementation:** the original design sketched a
`st.columns([1, 5])` layout (small icon beside the notice text). Manually
verified in-browser, this made the icon illegible — the vendored asset is a
wide text-badge ("AI GENERATED", ~3.16:1 aspect ratio), not a compact square
glyph, so a `width=40` column squeezed it into an unreadable ~13px-tall
sliver. Fixed to a full-width badge (`width=140`, no columns) stacked above
the notice box instead — confirmed legible in both light and dark themes via
a real browser check.

- [ ] **Step 4: Manual visual check (light theme)**

```bash
streamlit run src/app.py
```

Open the app in a browser (default Streamlit light theme). Confirm:
- The EU AI-generated-content icon (black variant) appears in the sidebar,
  immediately to the left of the "You are interacting with an AI system"
  notice box.
- The header logo (page center, above the dialogue) is still centered as
  before — the CSS scoping fix didn't break it.

- [ ] **Step 5: Manual visual check (dark theme)**

In the running app, switch to dark theme (Streamlit's Settings menu → Theme
→ Dark), or set it via `~/.streamlit/config.toml`'s `[theme] base = "dark"`
before starting. Confirm:
- The EU icon switches to the white variant and remains legible against the
  dark sidebar background.
- The header logo is still centered.

Stop the server (`Ctrl+C`) once both checks pass.

- [ ] **Step 6: Commit**

```bash
git add src/app.py
git commit -m "feat: add EU AI-generated content icon to the Streamlit sidebar"
```

---

### Task 6: Full regression test pass

**Files:** none (verification only)

**Interfaces:** none — this task consumes everything from Tasks 1-5 and
verifies no regression across the existing suite.

- [ ] **Step 1: Run the full test suite**

```bash
python -m pytest tests/ -v
```

Expected: same pass count as the pre-change baseline, plus the new tests
added in Tasks 2-3 (5 new tests total: 3 in `test_ai_disclosure.py`, 2 in
`test_pdf_export.py`). Zero new failures or errors.

- [ ] **Step 2: Run lint**

```bash
ruff check src/ tests/
```

Expected: no new violations introduced by this feature's changes (existing
violations, if any predate this work, are out of scope here).

- [ ] **Step 3: Run the deterministic eval gate**

```bash
python -m evals.run --det
```

Expected: all green — this feature doesn't touch `review_core.py`,
`results_core.py`, or the effort estimator, so this is a pure regression
check.

- [ ] **Step 4: Generate one real document end-to-end and inspect its PDF**

Using the CLI (fastest path to a real generated document without the full
Streamlit UI):

```bash
python src/cli.py
```

Answer the 11-question dialogue with any minimal test inputs, let it
generate, then separately confirm the **Streamlit** PDF path (the CLI
doesn't call `markdown_to_pdf()` at all — only `app.py` does) by running
`streamlit run src/app.py`, completing one generation, and downloading a
PDF. Open the downloaded PDF and confirm the EU AI icon appears near the
top, above or alongside the document title.

- [ ] **Step 5: Confirm the MCP package is unaffected**

```bash
python -m pytest tests/test_packaging.py -v
```

Expected: PASS, unchanged — confirms `assets/eu_ai_icon/` and the modified
`ai_disclosure.py`/`pdf_export.py`/`app.py` don't leak into (or break) the
`qai-consultant-mcp` wheel's file allowlist.

---

### Task 7: Release checklist (v3.3.0)

**Files:**
- Modify: `src/version.py`
- Modify: `pyproject.toml`
- Modify: `CHANGELOG.md`
- Modify: `README.md`
- Modify: `README_MCP.md`
- Modify: `CLAUDE.md`

**Interfaces:** none — documentation/metadata only.

- [ ] **Step 1: Bump `src/version.py`**

```python
__version__ = "3.3.0"
__release_date__ = "2026-07-29"
```

- [ ] **Step 2: Bump `pyproject.toml`**

At line 7, change `version = "3.1.6"` to `version = "3.3.0"`.

- [ ] **Step 3: Add the CHANGELOG entry**

At the top of `CHANGELOG.md`, right after the file's intro paragraph and
before `## [3.1.6] - 2026-07-29`, insert:

```markdown
## [3.3.0] - 2026-07-29

### Added
- Adopted the EU's official "Fully AI-Generated" icon from the Code of
  Practice on Transparency of AI-Generated Content (supporting AI Act
  Article 50(4)) as a visual reinforcement of the existing text/metadata AI
  disclosure (v2.5.2/v2.6). The icon now appears in the Streamlit sidebar
  (theme-aware, next to the existing "you are interacting with an AI
  system" notice) and in every generated document's PDF export (Risk
  Register, Effort Estimation, Test Strategy, Test Plan, QA Document
  Quality Review). Markdown `.md` downloads, the CLI, and the MCP server
  are unaffected — they keep the existing text-only disclosure, since none
  of those are rendered surfaces for an image. Design rationale:
  `docs/superpowers/specs/2026-07-29-eu-ai-icon-adoption-design.md`.
```

- [ ] **Step 4: Update `README.md`**

Update the version badge at line 21:

```markdown
![Version](https://img.shields.io/badge/version-3.3.0-green.svg)
```

Update the Roadmap section (lines 251-275). The current list is stale
relative to `CLAUDE.md`'s roadmap (it still shows the pre-2026-07-28
numbering, with "v3.2" labeled as unshipped "Remote MCP + distribution" —
that item was renumbered to v4.0, and the actual v3.2 CI-quality-gates work
already shipped without ever updating this file). Replace line 275
(`- **v3.2** Remote MCP + distribution...`) with:

```markdown
- **v3.2** ✅ CI quality gates completion — a separate, always-green-by-construction nightly workflow exercising real Pinecone/Mistral/OpenRouter contract tests, isolated from the blocking PR checks
- **v3.3** ✅ Adopted the EU's official AI-generated-content icon (Code of Practice, AI Act Article 50(4)) in the Streamlit sidebar and all generated-document PDF exports, reinforcing the existing text/metadata disclosure
- **v3.4** App visual redesign ("Calibration Bench") — token-based color/typography system and a reusable score/severity component
- **v4.0** Remote MCP + distribution — hosted server connectable from claude.ai, registry submissions
```

- [ ] **Step 5: Update `README_MCP.md`**

No MCP tool surface change — add a one-line note only if `README_MCP.md`
has a version/changelog-pointer line already; otherwise skip (confirmed in
this session that `README_MCP.md` has no version badge to update).

- [ ] **Step 6: Update `CLAUDE.md`**

In the architecture table (`### Source Files (\`src/\`)`), update the
`ai_disclosure.py` row to mention `pdf_icon_html()` alongside the existing
four responsibilities, and update `pdf_export.py`'s row (if one exists) to
mention the new `extra_body_html` parameter.

In the Roadmap section, add after the existing `v3.2` entry:

```markdown
- **v3.3** ✅ Adopted the EU's official "Fully AI-Generated" icon from the Code of Practice on Transparency of AI-Generated Content (AI Act Article 50(4)) as a visual reinforcement of the v2.5.2/v2.6 text/metadata disclosure: `assets/eu_ai_icon/` (vendored SVG + PNG, no attribution required per the EU's license), `ai_disclosure.py`'s new `pdf_icon_html()` (base64 data-URI `<img>` tag — xhtml2pdf renders raster images but not SVG, hence PNG here), `pdf_export.py`'s new `extra_body_html` param on `markdown_to_pdf()`, and a theme-aware icon next to the sidebar's `AI_INTERACTION_NOTICE` in `app.py` (required scoping the header-logo centering CSS from a blanket `[data-testid="stImage"]` rule to a keyed `st.container(key="header-logo")`, since this is the app's second `st.image()` call). Markdown `.md` downloads, the CLI, and the MCP server are unaffected — text-only channels where an image reference wouldn't render. Design spec: `docs/superpowers/specs/2026-07-29-eu-ai-icon-adoption-design.md`.
```

Add two new Gotchas entries:

```markdown
- **Streamlit CSS scoping via `st.container(key=...)`:** a blanket
  `[data-testid="stImage"]` CSS rule applies to *every* `st.image()` call in
  the app, not just the one it was written for. When adding a second
  `st.image()` call (the v3.3 EU AI icon, alongside the existing header
  logo), the original centering rule had to be scoped to
  `.st-key-header-logo [data-testid="stImage"]` by wrapping the header logo
  in `st.container(key="header-logo")` — Streamlit's `key=` parameter on
  `st.container` generates a `st-key-<key>` CSS class specifically for this
  kind of per-instance scoping. Any future second/third `st.image()` call
  needs the same treatment, or it will silently inherit styling meant for a
  different image.
- **xhtml2pdf renders raster images (PNG) via base64 data URIs but not
  SVG:** discovered vendoring the EU AI-generated-content icon (v3.3) —
  the Streamlit sidebar uses the icon's SVG variants directly (crisp at any
  size, and Streamlit's `st.image()` handles SVG natively), but the same
  icon in a PDF export required a separately-vendored PNG
  (`assets/eu_ai_icon/eu_ai_generated_icon.png`, downscaled from the EU's
  official ~7460x2360px source to a 240x76px footer-badge size to avoid
  bloating every generated PDF's base64 payload). Any future image added to
  a PDF export (`pdf_export.py`'s `extra_body_html`) needs a PNG (or other
  raster format), not SVG.
```

- [ ] **Step 7: Verify `test_changelog.py` still passes with the new version**

```bash
python -m pytest tests/test_changelog.py -v
```

Expected: PASS — confirms `version.py`'s `__version__` matches
`CHANGELOG.md`'s new top heading, and the new entry has real bullet content
under it.

- [ ] **Step 8: Final commit**

```bash
git add src/version.py pyproject.toml CHANGELOG.md README.md README_MCP.md CLAUDE.md
git commit -m "release: v3.3.0 -- adopt EU AI-generated content icon (Article 50(4))"
```
