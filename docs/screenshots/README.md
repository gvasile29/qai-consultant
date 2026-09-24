# Screenshots

Images used by the root `README.md`. Regenerate them after any visible UI change instead of
editing them by hand.

## CLI (`cli_banner.svg`, `cli_dialogue.svg`)

```bash
python scripts/generate_cli_screenshots.py
```

Renders the real `cli.py` banner and a scripted Project Discovery dialogue (Web Application
template answers) through a recording Rich console. No API keys or network needed.

## Web UI (`streamlit_*.png`)

```bash
streamlit run src/app.py --server.port 8599 --server.headless true
python scripts/generate_streamlit_screenshots.py
```

Needs real API keys in `.env`: the results screenshots come from a full 4-stage generation
(~2-3 minutes). Captures a 1440x900 viewport per screen: landing page, MCP sidebar panel,
Project Discovery dialogue, Executive Readout, the four output tabs, QA Document Quality
Review, and QA Maturity Assessment.

## Architecture (`architecture.svg`)

Hand-authored SVG — edit the text directly (e.g. when the LLM models change).
