"""
QAI Consultant — CLI Interface
Beautiful terminal experience using the rich library.
"""

import os
import sys
from pathlib import Path

# Disable ChromaDB telemetry
os.environ["ANONYMIZED_TELEMETRY"] = "False"
os.environ["CHROMA_TELEMETRY"] = "False"

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.markdown import Markdown
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich import print as rprint

from agent import QAIAgent
from dialogue import DialogueManager
from strategy_generator import StrategyGenerator
from knowledge_watcher import get_watcher

console = Console()


def print_banner():
    """Print the QAI Consultant banner."""
    console.print(Panel.fit(
        "[bold cyan]QAI Consultant[/bold cyan]\n"
        "[dim]AI-powered QA Architect — Test Strategy Generator[/dim]",
        border_style="cyan",
        padding=(1, 4),
    ))
    console.print()


def print_intro():
    """Print introduction message."""
    console.print(
        "[bold white]Welcome![/bold white] I'm your AI QA Architect.\n"
        "I'll ask you a few questions about your project and generate\n"
        "a tailored [bold cyan]Test Strategy[/bold cyan] based on established QA methodologies.\n"
    )
    console.print("[dim]Answer each question as specifically as possible for the best results.[/dim]")
    console.print()


def run_dialogue(dialogue: DialogueManager) -> bool:
    """Run the clarifying questions dialogue. Returns True if completed."""
    console.print(Panel(
        "[bold]Project Discovery[/bold]\n[dim]Let's understand your project before generating the strategy.[/dim]",
        border_style="blue",
    ))
    console.print()

    while dialogue.has_next_question():
        question = dialogue.get_next_question()
        current, total = dialogue.get_progress()

        # Question header
        console.print(f"[bold cyan][{current}/{total}][/bold cyan] [bold]{question['question']}[/bold]")
        console.print(f"[dim]  → {question['hint']}[/dim]")

        # Get answer
        answer = Prompt.ask("  [cyan]Your answer[/cyan]")

        if not answer.strip():
            console.print("[yellow]  ⚠️  Please provide an answer to continue.[/yellow]")
            continue

        dialogue.submit_answer(answer)
        console.print()

    return True


def show_context_summary(dialogue: DialogueManager):
    """Display the collected project context in a table."""
    context = dialogue.get_context()

    table = Table(title="Project Context Summary", border_style="cyan", show_header=True)
    table.add_column("Field", style="bold cyan", width=25)
    table.add_column("Value", style="white")

    table.add_row("Project Name", context.project_name)
    table.add_row("Description", context.project_description[:80] + "..." if len(context.project_description) > 80 else context.project_description)
    table.add_row("Type", context.project_type)
    table.add_row("Tech Stack", context.tech_stack)
    table.add_row("QA Team Size", context.team_qa_size)
    table.add_row("Dev Team Size", context.team_dev_size)
    table.add_row("Timeline", context.timeline)
    table.add_row("Methodology", context.methodology)
    table.add_row("Known Risks", context.known_risks[:80] + "..." if len(context.known_risks) > 80 else context.known_risks)
    table.add_row("Existing Automation", context.existing_automation)
    table.add_row("Compliance", context.compliance_requirements)

    console.print()
    console.print(table)
    console.print()


def generate_strategy(agent: QAIAgent, dialogue: DialogueManager) -> dict:
    """Generate Risk Register, Effort Estimation, and Test Strategy with progress spinner."""
    generator = StrategyGenerator(agent)
    context = dialogue.get_context()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("🔍 Analyzing project risks...", total=None)
        from risk_analyzer import RiskAnalyzer
        risk_analyzer = RiskAnalyzer(agent)
        risk_register, risk_sources = risk_analyzer.analyze(context)
        risk_path = risk_analyzer.save(risk_register, context)

        progress.add_task("📊 Generating Effort Estimation...", total=None)
        from effort_estimator import EffortEstimator
        estimator = EffortEstimator(agent)
        effort_report, effort_data = estimator.estimate(context, risk_register)
        effort_path = estimator.save(effort_report, context)

        progress.add_task("📋 Generating Test Strategy with Mistral...", total=None)
        strategy, sources = generator.generate(context)
        strategy_path = generator.save(strategy, context)

    return {
        "strategy": strategy,
        "strategy_path": strategy_path,
        "sources": sources,
        "risk_register": risk_register,
        "risk_path": risk_path,
        "risk_sources": risk_sources,
        "effort_report": effort_report,
        "effort_path": effort_path,
    }


def show_sources(sources: list):
    """Display knowledge sources used."""
    console.print("\n[bold]📚 Knowledge Sources Used:[/bold]")
    for source in sources:
        console.print(f"  [dim]• {source}[/dim]")


def main():
    print_banner()
    print_intro()

    # Load agent
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Loading QAI Consultant knowledge base...", total=None)
        try:
            agent = QAIAgent()
        except Exception as e:
            console.print(f"\n[bold red]❌ Error:[/bold red] {e}")
            sys.exit(1)

    console.print("[bold green]✅ Knowledge base ready![/bold green]\n")

    # Start knowledge base watcher
    def on_kb_update(message: str):
        console.print(f"\n[bold green]{message}[/bold green]\n")

    watcher = get_watcher()
    watcher.start(callback=on_kb_update)

    try:
      _run_main_loop(agent, watcher)
    finally:
        watcher.stop()


def _run_main_loop(agent: QAIAgent, watcher):
    """Main interaction loop — separated so watcher can be cleanly stopped."""
    while True:
        # Run dialogue
        dialogue = DialogueManager()
        completed = run_dialogue(dialogue)

        if not completed:
            break

        # Show summary
        show_context_summary(dialogue)

        # Confirm before generating
        confirm = Prompt.ask(
            "[bold]Generate Test Strategy for this project?[/bold]",
            choices=["yes", "no"],
            default="yes"
        )

        if confirm == "no":
            console.print("[yellow]Strategy generation cancelled.[/yellow]")
        else:
            # Generate strategy + risk register
            console.print()
            result = generate_strategy(agent, dialogue)

            # Display Risk Register
            console.print(Panel(
                "[bold yellow]⚠️  Risk Register[/bold yellow]",
                border_style="yellow",
            ))
            console.print(Markdown(result["risk_register"]))
            show_sources(result["risk_sources"])
            console.print(f"\n[bold green]💾 Risk Register saved to:[/bold green] [cyan]{result['risk_path']}[/cyan]")

            # Display Effort Estimation
            console.print()
            console.print(Panel(
                "[bold green]📊 Effort Estimation Report[/bold green]",
                border_style="green",
            ))
            console.print(Markdown(result["effort_report"]))
            console.print(f"\n[bold green]💾 Effort Report saved to:[/bold green] [cyan]{result['effort_path']}[/cyan]")

            # Display Test Strategy
            console.print()
            console.print(Panel(
                "[bold cyan]📋 Generated Test Strategy[/bold cyan]",
                border_style="cyan",
            ))
            console.print(Markdown(result["strategy"]))
            show_sources(result["sources"])
            console.print(f"\n[bold green]💾 Strategy saved to:[/bold green] [cyan]{result['strategy_path']}[/cyan]")

            output_path = result["strategy_path"]

            # Feedback loop
            console.print()
            console.print(Panel(
                "[bold]Was this Test Strategy useful?[/bold]\n"
                "[dim]Your feedback helps QAI Consultant improve over time.[/dim]",
                border_style="yellow",
            ))
            feedback = Prompt.ask(
                "  [yellow]Your feedback[/yellow]",
                choices=["yes", "partially", "no"],
                default="yes"
            )

            if feedback in ["yes", "partially"]:
                # Save to generated_strategies folder
                feedback_dir = Path(__file__).resolve().parent.parent / "knowledge_base" / "generated_strategies"
                feedback_dir.mkdir(exist_ok=True)

                extra_note = ""
                if feedback == "partially":
                    extra_note = Prompt.ask("  [yellow]What could be improved?[/yellow]")

                # Add feedback metadata to the strategy file
                feedback_content = f"""---
feedback: {feedback}
notes: {extra_note}
---

"""
                feedback_path = feedback_dir / output_path.name
                feedback_path.write_text(
                    feedback_content + output_path.read_text(encoding="utf-8"),
                    encoding="utf-8"
                )
                # Immediate ingest — don't wait for file watcher
                try:
                    chunks = watcher.ingest_manager.ingest_file(feedback_path)
                    if chunks > 0:
                        console.print(f"[bold green]✅ Strategy added to knowledge base! +{chunks} chunks ingested.[/bold green]")
                    else:
                        console.print(f"[bold green]✅ Strategy saved to knowledge base![/bold green] [dim]{feedback_path}[/dim]")
                except Exception:
                    console.print(f"[bold green]✅ Strategy saved to knowledge base![/bold green] [dim]{feedback_path}[/dim]")

            elif feedback == "no":
                console.print("[dim]Ok, strategy not added to knowledge base. Thank you for the feedback![/dim]")

        # Ask if user wants to generate another
        console.print()
        another = Prompt.ask(
            "Generate a strategy for another project?",
            choices=["yes", "no"],
            default="no"
        )

        if another == "no":
            break

    console.print()
    console.print(Panel.fit(
        "[bold cyan]Thank you for using QAI Consultant![/bold cyan]\n"
        "[dim]Star us on GitHub if you found it useful 🌟[/dim]",
        border_style="cyan",
        padding=(1, 4),
    ))


if __name__ == "__main__":
    main()
