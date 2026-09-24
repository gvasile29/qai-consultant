"""Regenerate docs/screenshots/cli_banner.svg and cli_dialogue.svg from the real CLI code.

Renders cli.print_banner()/print_intro() and a scripted run_dialogue() (answers from
templates.TEMPLATES["web_app"]) through a recording Rich console, so the README's CLI
images always show the current version and question set. No API keys or network needed.

    python scripts/generate_cli_screenshots.py
"""
import sys
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from rich.console import Console  # noqa: E402

import cli  # noqa: E402
from dialogue import DialogueManager  # noqa: E402
from templates import TEMPLATES  # noqa: E402

OUT = REPO / "docs" / "screenshots"
WIDTH = 110


def _recording_console() -> Console:
    return Console(record=True, width=WIDTH, force_terminal=True, color_system="truecolor")


def banner() -> None:
    cli.console = _recording_console()
    cli.print_banner()
    cli.print_intro()
    cli.console.print("[bold green]✅ Knowledge base ready![/bold green]\n")
    cli.console.save_svg(str(OUT / "cli_banner.svg"), title="QAI Consultant — CLI")


def dialogue() -> None:
    cli.console = _recording_console()
    dm = DialogueManager()
    template = TEMPLATES["web_app"]
    answers = []
    while dm.has_next_question():
        q = dm.get_next_question()
        answers.append(template[q["key"]])
        dm.submit_answer(template[q["key"]])
    answers.append("")  # skip the optional additional-context question
    dm.reset()
    fed = iter(answers)

    def fake_ask(prompt, **_kwargs):
        answer = next(fed)
        cli.console.print(f"{prompt}: {answer}", highlight=False)
        return answer

    with patch.object(cli.Prompt, "ask", side_effect=fake_ask):
        cli.run_dialogue(dm)
    cli.console.save_svg(str(OUT / "cli_dialogue.svg"), title="QAI Consultant — Project Discovery")


if __name__ == "__main__":
    banner()
    dialogue()
    print(f"Wrote {OUT / 'cli_banner.svg'} and {OUT / 'cli_dialogue.svg'}")
