# Brand and Visual Identity

Full source: `assets/brand/README_BRAND.md`. Always propose a specific asset or a described custom visual for every post.

## Concept

"Pixelul defect" (the defect pixel): a **Q built from pixels on a grid**, where a single pixel, the one in the Q's tail, is in the accent color. The story: **QA finds the pixel that's out of place.** The Q also reads as an inspection magnifier. Deliberately avoids AI cliches (hexagons, spirals, gradients) and the QA cliche (the checkmark).

## Palette "Ocean"

| Role | Light bg | Dark bg |
|---|---|---|
| Q pixels / wordmark | `#0F172A` | `#F1F5F9` |
| Defect pixel (accent) | `#14B8A6` | `#2DD4BF` |
| Dark brand background | `#0F172A` | - |
| Muted subtext (CONSULTANT) | `#475569` | `#94A3B8` |

## Asset files (in `assets/brand/`)

| File | Use |
|---|---|
| `qai_logo.svg` / `qai_logo_dark.svg` | Horizontal lockup (symbol + QAI), vector |
| `qai_icon.svg` / `qai_icon_dark.svg` | Symbol only, vector |
| `qai_logo_stacked.svg` | Square variant (symbol above QAI) |
| `qai_logo_1024.png` | Square, transparent - social profile pic |
| `qai_logo_social_1024.png` | Square, white bg - posts without transparency |
| `qai_logo_horizontal_1680.png` / `_dark_` | Horizontal banner - LinkedIn, README |
| `qai_logo_social_1024.png` | Instagram profile / square tiles |
| `qai_icon_512.png` | Large symbol, transparent |
| `qai_favicon_64.png` / `_32.png` | Favicon |

There is also an existing `marketing/qai_linkedin_image.svg` reference to reuse or adapt for LinkedIn image cards.

## Usage rules

- The defect pixel is always exactly one, always in the bottom-right corner. Never move it or recolor it.
- Light backgrounds: standard variants. Dark backgrounds (`#0F172A` or darker): `_dark` variants.
- Minimum clear space around the logo: one grid pixel.
- Below 48px use only the symbol (`qai_icon`) or favicon, not the text lockup.
- Do not alter grid proportions.

## Scroll-stopping visuals are mandatory, not optional

**Every post ships with a visual.** No post is complete as text alone. The image, screenshot, carousel, or reel is what stops the scroll and earns the "...more" click, on a feed, the visual is seen before a single word is read. A great hook with no visual underperforms a mediocre hook with a strong one. Treat the visual as a co-equal deliverable, not a nice-to-have footnote.

What "eye-catching" means here (specific, not decorative):
- **Legible at thumbnail size.** It competes in a small feed rectangle on a phone. If the key idea isn't readable at 1/3 size, it fails.
- **One idea, big.** A single bold statement, number, or before/after, not a busy collage. High contrast (Ocean ink `#0F172A` vs teal `#14B8A6`) with generous whitespace.
- **Curiosity or tension in the image itself.** The visual should carry the hook's pain or the "aha", not just show a logo. A before/after, a "wrong vs right", a shocking number, a red-flagged screenshot, these stop scrolls. A plain product screenshot or bare logo does not.
- **Text-on-image is allowed and encouraged** for the hook line (LinkedIn/Instagram), the reader reads the image before the caption.

Preferred visual types for QAI, in rough order of stopping power:
1. **Before/after** (old vs new, messy vs clean, gray wall of text vs color-coded signal). Strongest for redesign, review, and results content.
2. **A real screenshot with the key element highlighted** (a red "Critical" swatch, a low score, a flaky-test cluster). Proof plus specificity.
3. **A bold statement card** (the hook line in big type on an Ocean-palette background, defect-pixel motif in the corner).
4. **A carousel** (Instagram/LinkedIn) for educational or data breakdowns, slide 1 must stop the scroll on its own.
5. **A short reel** for motion (the app producing an artifact in seconds).

If no suitable asset exists, do not fall back to "attach the logo." Either describe the custom visual precisely enough to be produced (layout, exact text, colors, which brand asset, what to screenshot), or offer to generate it. A weak visual is a reason to hold the post, not ship it.

## Proposing visuals per channel

- **LinkedIn:** a designed image card (headline + accent, `#0F172A` bg, teal accent, logo bottom) or the horizontal banner. Name the file or describe the card.
- **Instagram:** a carousel (slides using Ocean palette, big type, one idea per slide, defect-pixel motif) or a reel (see scripts in `marketing/`).
- **Facebook:** the social banner or a simple branded image; can reuse the LinkedIn card.

When a custom image is needed and none exists, describe it precisely (layout, text, colors, which logo asset) so it can be produced, or offer to generate it.
