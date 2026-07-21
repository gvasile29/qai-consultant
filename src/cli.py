"""
QAI Consultant — CLI Interface
Beautiful terminal experience using the rich library.
"""

import argparse
import os
import sys
from pathlib import Path
from typing import Optional


from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.prompt import Prompt
from rich.markdown import Markdown
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.text import Text
from rich import print as rprint

from agent import QAIAgent, QAIConnectionError, QAIModelError, QAIKnowledgeBaseError, clean_markdown_html
from dialogue import DialogueManager
from strategy_generator import StrategyGenerator
from logger import setup_logging, get_logger
from version import __version__

setup_logging()
logger = get_logger(__name__)

console = Console()


def print_banner():
    """Print the QAI Consultant banner."""
    console.print(Panel.fit(
        f"[bold cyan]QAI Consultant[/bold cyan] [dim]v{__version__}[/dim]\n"
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
        assert question is not None
        current, total = dialogue.get_progress()

        # Question header
        console.print(f"[bold cyan][{current}/{total}][/bold cyan] [bold]{question['question']}[/bold]")
        console.print(f"[dim]  → {question['hint']}[/dim]")

        # Get answer — retry loop until valid
        while True:
            answer = Prompt.ask("  [cyan]Your answer[/cyan]")
            result = dialogue.submit_answer(answer)
            if result.valid:
                break
            console.print(f"[yellow]  ⚠️  {result.error}[/yellow]")

        console.print()

    # Optional free-text context — Enter to skip
    console.print("[bold]Anything else QAI should know?[/bold] [dim](optional — Enter to skip)[/dim]")
    console.print("[dim]  → e.g., legacy constraints, third-party dependencies, team specifics[/dim]")
    while True:
        answer = Prompt.ask("  [cyan]Additional context[/cyan]", default="", show_default=False)
        result = dialogue.set_additional_context(answer)
        if result.valid:
            break
        console.print(f"[yellow]  ⚠️  {result.error}[/yellow]")
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
    table.add_row("Additional Context", (context.additional_context[:80] + "..." if len(context.additional_context) > 80 else context.additional_context) or "—")

    console.print()
    console.print(table)
    console.print()


def generate_strategy(agent: QAIAgent, dialogue: DialogueManager, results_summary: Optional[str] = None) -> dict:
    """Generate Risk Register, Effort Estimation, and Test Strategy with streaming output.

    results_summary: optional deterministic test-execution-data summary
    (results_core.summarize_for_prompt(), from --results) — grounds the Risk
    Register in real pass/fail data. Absence changes nothing.
    """
    from concurrent.futures import ThreadPoolExecutor
    from agent import RAG_K_GENERATION
    from risk_analyzer import RiskAnalyzer, append_execution_data_appendix, build_risk_prompt, RISK_SYSTEM_PROMPT
    from effort_estimator import EffortEstimator
    from strategy_generator import build_strategy_prompt, SYSTEM_PROMPT
    from test_plan_generator import TestPlanGenerator, build_test_plan_prompt, TEST_PLAN_SYSTEM_PROMPT

    generator = StrategyGenerator(agent)
    context = dialogue.get_context()
    risk_analyzer = RiskAnalyzer(agent)
    estimator = EffortEstimator(agent)
    test_plan_generator = TestPlanGenerator(agent)

    # === Parallel RAG retrieval (Pinecone reads, thread-safe, fast) ===
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
        progress.add_task("⚡ Fetching knowledge base context...", total=None)
        with ThreadPoolExecutor(max_workers=3) as executor:
            f_risk = executor.submit(
                agent.retrieve_knowledge, risk_analyzer._build_risk_query(context), RAG_K_GENERATION
            )
            f_strategy = executor.submit(
                agent.retrieve_knowledge, context.to_rag_query(), RAG_K_GENERATION
            )
            f_test_plan = executor.submit(
                agent.retrieve_knowledge, test_plan_generator._build_test_plan_query(context), RAG_K_GENERATION
            )
            try:
                risk_chunks = f_risk.result()
            except Exception as exc:
                logger.warning("Risk RAG prefetch failed: %s", exc)
                risk_chunks = []
            try:
                strategy_chunks = f_strategy.result()
            except Exception as exc:
                logger.warning("Strategy RAG prefetch failed: %s", exc)
                strategy_chunks = []
            try:
                test_plan_chunks = f_test_plan.result()
            except Exception as exc:
                logger.warning("Test Plan RAG prefetch failed: %s", exc)
                test_plan_chunks = []

    risk_knowledge = agent.format_knowledge_context(risk_chunks)
    strategy_knowledge = agent.format_knowledge_context(strategy_chunks)
    test_plan_knowledge = agent.format_knowledge_context(test_plan_chunks)
    test_plan_sources = list({
        f"[{(c.metadata or {}).get('category', 'N/A')}] {(c.metadata or {}).get('filename', 'N/A')}"
        for c in test_plan_chunks
    })
    risk_sources = list({
        f"[{(c.metadata or {}).get('category', 'N/A')}] {(c.metadata or {}).get('filename', 'N/A')}"
        for c in risk_chunks
    })
    sources = list({
        f"[{(c.metadata or {}).get('category', 'N/A')}] {(c.metadata or {}).get('filename', 'N/A')}"
        for c in strategy_chunks
    })

    # === Step 1/4: Risk Register (streaming) ===
    console.print(Panel("[bold yellow]⚠️  Generating Risk Register...[/bold yellow]", border_style="yellow"))
    risk_prompt = build_risk_prompt(context, risk_knowledge, results_summary=results_summary)
    risk_buffer = []
    with Live(console=console, refresh_per_second=8) as live:
        for chunk in agent.ask_streaming(risk_prompt, system_prompt=RISK_SYSTEM_PROMPT):
            risk_buffer.append(chunk)
            live.update(Text("".join(risk_buffer)))
    risk_register = clean_markdown_html("".join(risk_buffer))
    risk_register = append_execution_data_appendix(risk_register, results_summary)
    risk_path = risk_analyzer.save(risk_register, context)
    console.print(f"\n[bold green]✅ Risk Register generated[/bold green] ({len(risk_register)} chars)\n")

    # === Step 2/4: Effort Estimation (deterministic + short LLM narrative) ===
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
        progress.add_task("📊 Generating Effort Estimation...", total=None)
        effort_report, effort_data = estimator.estimate(context, risk_register)
        effort_path = estimator.save(effort_report, context)

    # === Step 3/4: Test Strategy (streaming) ===
    console.print(Panel("[bold cyan]📋 Generating Test Strategy...[/bold cyan]", border_style="cyan"))
    strategy_prompt = build_strategy_prompt(context, strategy_knowledge)
    strategy_buffer = []
    with Live(console=console, refresh_per_second=8) as live:
        for chunk in agent.ask_streaming(strategy_prompt, system_prompt=SYSTEM_PROMPT):
            strategy_buffer.append(chunk)
            live.update(Text("".join(strategy_buffer)))
    strategy = clean_markdown_html("".join(strategy_buffer))
    strategy_path = generator.save(strategy, context)
    console.print(f"\n[bold green]✅ Test Strategy generated[/bold green] ({len(strategy)} chars)\n")

    # === Step 4/4: Test Plan (streaming) ===
    console.print(Panel("[bold blue]📝 Generating Test Plan...[/bold blue]", border_style="blue"))
    test_plan_prompt = build_test_plan_prompt(context, risk_register, test_plan_knowledge)
    test_plan_buffer = []
    with Live(console=console, refresh_per_second=8) as live:
        for chunk in agent.ask_streaming(test_plan_prompt, system_prompt=TEST_PLAN_SYSTEM_PROMPT):
            test_plan_buffer.append(chunk)
            live.update(Text("".join(test_plan_buffer)))
    test_plan = clean_markdown_html("".join(test_plan_buffer))
    test_plan_path = test_plan_generator.save(test_plan, context)
    console.print(f"\n[bold green]✅ Test Plan generated[/bold green] ({len(test_plan)} chars)\n")

    return {
        "strategy": strategy,
        "strategy_path": strategy_path,
        "sources": sources,
        "risk_register": risk_register,
        "risk_path": risk_path,
        "risk_sources": risk_sources,
        "effort_report": effort_report,
        "effort_path": effort_path,
        "test_plan": test_plan,
        "test_plan_path": test_plan_path,
        "test_plan_sources": test_plan_sources,
    }


def show_sources(sources: list):
    """Display knowledge sources used."""
    console.print("\n[bold]📚 Knowledge Sources Used:[/bold]")
    for source in sources:
        console.print(f"  [dim]• {source}[/dim]")


def parse_args(argv: Optional[list] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="QAI Consultant — AI-powered QA Architect")
    parser.add_argument(
        "--review", metavar="PATH",
        help="Review an existing QA document (deterministic score + optional narrative), then exit.",
    )
    parser.add_argument(
        "--doc-type", choices=["auto", "test_plan", "test_strategy", "test_cases"], default="auto",
        help="Document type for --review (default: auto-detect).",
    )
    parser.add_argument(
        "--results", metavar="PATH", nargs="+",
        help="Attach JUnit XML/CSV test execution results to ground the Risk Register "
             "in the normal generation flow.",
    )
    return parser.parse_args(argv)


def _load_agent() -> QAIAgent:
    """Load QAIAgent with the same spinner + error handling used at every entry point."""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Loading QAI Consultant knowledge base...", total=None)
        try:
            return QAIAgent()
        except QAIKnowledgeBaseError as e:
            console.print(f"\n[bold red]{e}[/bold red]")
            logger.error(f"Startup failed - KB error: {e}")
            sys.exit(1)
        except QAIConnectionError as e:
            console.print(f"\n[bold red]{e}[/bold red]")
            logger.error(f"Startup failed - LLM connection: {e}")
            sys.exit(1)
        except QAIModelError as e:
            console.print(f"\n[bold red]{e}[/bold red]")
            logger.error(f"Startup failed - model error: {e}")
            sys.exit(1)
        except Exception as e:
            console.print(f"\n[bold red]❌ Unexpected error:[/bold red] {e}")
            logger.exception(f"Unexpected startup error: {e}")
            sys.exit(1)


def run_review_mode(agent: QAIAgent, path: str, doc_type: str) -> None:
    """`--review PATH [--doc-type ...]`: deterministic score + findings via a
    rich table (review_core.review_document(), no LLM), then an optional
    narrative review streamed and saved via review_generator.py's
    conventions — the same save path the interactive flow uses."""
    from review_core import review_document, MIN_CONTENT_CHARS
    from review_generator import (
        REVIEW_SYSTEM_PROMPT, build_review_prompt,
        build_review_report_markdown, save_review_report,
    )

    doc_path = Path(path)
    if not doc_path.exists():
        console.print(f"[bold red]❌ File not found:[/bold red] {path}")
        sys.exit(1)

    text = doc_path.read_text(encoding="utf-8", errors="ignore")
    result = review_document(text, doc_type=doc_type)

    if result.doc_type == "insufficient_content":
        console.print(
            f"[yellow]⚠️  Document is too short to review "
            f"({result.stats.get('char_count', 0)} characters after cleanup — "
            f"need at least {MIN_CONTENT_CHARS}).[/yellow]"
        )
        return

    console.print(Panel(
        f"[bold]QA Document Quality Review[/bold]\n[dim]{doc_path.name} — detected type: {result.doc_type}[/dim]",
        border_style="cyan",
    ))

    score_table = Table(title=f"Overall Score: {result.overall_score}/100", border_style="cyan", show_header=True)
    score_table.add_column("Dimension", style="bold cyan")
    score_table.add_column("Score", style="white")
    for dim, score in result.dimension_scores.items():
        score_table.add_row(dim.replace("_", " ").title(), f"{score}/100")
    console.print(score_table)

    if result.findings:
        severity_style = {"critical": "bold red", "major": "yellow", "minor": "dim"}
        findings_table = Table(title="Findings", border_style="yellow", show_header=True)
        findings_table.add_column("Severity", style="bold")
        findings_table.add_column("Dimension")
        findings_table.add_column("Message")
        for finding in result.findings:
            style = severity_style.get(finding.severity, "white")
            findings_table.add_row(
                f"[{style}]{finding.severity}[/{style}]",
                finding.dimension.replace("_", " ").title(),
                finding.message,
            )
        console.print(findings_table)
    else:
        console.print("[bold green]✅ No findings — every mechanical check in the rubric passed.[/bold green]")

    narrative = ""
    generate_narrative = Prompt.ask(
        "\n[bold]Generate a narrative review grounded in the QA knowledge base?[/bold]",
        choices=["yes", "no"], default="yes",
    )
    if generate_narrative == "yes":
        queries, seen = [], set()
        for finding in result.findings:
            for q in finding.citation_queries:
                if q not in seen:
                    seen.add(q)
                    queries.append(q)

        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
            progress.add_task("⚡ Retrieving grounding sources...", total=None)
            chunks = []
            for q in queries[:5]:
                chunks.extend(agent.retrieve_knowledge(q, k=1))
            if not chunks:
                chunks = agent.retrieve_knowledge(f"{result.doc_type.replace('_', ' ')} quality review", k=5)
        knowledge_context = agent.format_knowledge_context(chunks)
        prompt = build_review_prompt(result, knowledge_context)

        console.print(Panel("[bold cyan]🤖 Generating Narrative Review...[/bold cyan]", border_style="cyan"))
        buffer = []
        with Live(console=console, refresh_per_second=8) as live:
            for chunk in agent.ask_streaming(prompt, system_prompt=REVIEW_SYSTEM_PROMPT):
                buffer.append(chunk)
                live.update(Text("".join(buffer)))
        narrative = clean_markdown_html("".join(buffer))

    report_md = build_review_report_markdown(result, narrative)
    output_path = save_review_report(report_md, doc_path.stem)
    console.print(f"\n[bold green]💾 Quality Review saved to:[/bold green] [cyan]{output_path}[/cyan]")


def load_results_summary(paths: list):
    """`--results PATH [PATH ...]`: parse JUnit XML (run_id = filename stem)
    / CSV files into a results_core.ResultsAnalysis + its deterministic
    prompt summary. Returns (analysis, summary), or (None, None) if no file
    yielded any records — never raises on a missing/malformed file."""
    from results_core import analyze as compute_results_analysis, parse_junit_xml, parse_results_csv, summarize_for_prompt

    records = []
    for raw_path in paths:
        file_path = Path(raw_path)
        if not file_path.exists():
            console.print(f"[yellow]⚠️  Results file not found, skipping: {raw_path}[/yellow]")
            continue
        content = file_path.read_text(encoding="utf-8", errors="ignore")
        if file_path.suffix.lower() == ".csv":
            records.extend(parse_results_csv(content))
        else:
            records.extend(parse_junit_xml(content, run_id=file_path.stem))

    if not records:
        return None, None

    analysis = compute_results_analysis(records)
    return analysis, summarize_for_prompt(analysis)


def show_results_metrics(analysis) -> None:
    """Compact rich table for an attached ResultsAnalysis (--results)."""
    table = Table(title="Test Execution Results", border_style="cyan", show_header=True)
    table.add_column("Metric", style="bold cyan")
    table.add_column("Value", style="white")
    table.add_row("Runs", str(analysis.runs))
    table.add_row("Distinct Tests", str(analysis.total_tests))
    table.add_row("Overall Pass Rate", f"{analysis.overall_pass_rate:.0%}")
    table.add_row("Flaky Tests", str(len(analysis.flaky)))
    table.add_row("Ever-Failing Tests", str(len(analysis.ever_failing)))
    table.add_row("Failure Clusters", str(len(analysis.failure_clusters)))
    console.print(table)
    console.print()


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # emoji/markdown output; don't crash on cp1252/ascii

    args = parse_args()
    print_banner()

    if args.review:
        agent = _load_agent()
        console.print("[bold green]✅ Knowledge base ready![/bold green]\n")
        run_review_mode(agent, args.review, args.doc_type)
        return

    print_intro()
    agent = _load_agent()
    console.print("[bold green]✅ Knowledge base ready![/bold green]\n")

    _run_main_loop(agent, results_paths=args.results)


def _run_main_loop(agent: QAIAgent, results_paths: Optional[list] = None):
    """Main interaction loop — separated so watcher can be cleanly stopped."""
    results_summary = None
    if results_paths:
        results_analysis, results_summary = load_results_summary(results_paths)
        if results_analysis is not None:
            show_results_metrics(results_analysis)

    while True:
        # Run dialogue
        dialogue = DialogueManager()
        completed = run_dialogue(dialogue)

        if not completed:
            break

        # Show summary
        show_context_summary(dialogue)

        # Offer a second chance to edit the additional context before generating
        edit_extra = Prompt.ask(
            "[bold]Edit the additional context before generating?[/bold]",
            choices=["yes", "no"],
            default="no"
        )
        if edit_extra == "yes":
            current = dialogue.get_context().additional_context
            console.print(f"[dim]Current additional context:[/dim] {current or '—'}")
            console.print("[dim]Enter the full replacement text (empty input clears it).[/dim]")
            while True:
                answer = Prompt.ask("  [cyan]Additional context[/cyan]", default="", show_default=False)
                result = dialogue.set_additional_context(answer)
                if result.valid:
                    break
                console.print(f"[yellow]  ⚠️  {result.error}[/yellow]")
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
            strategy_result = generate_strategy(agent, dialogue, results_summary=results_summary)

            # Display Risk Register
            console.print(Panel(
                "[bold yellow]⚠️  Risk Register[/bold yellow]",
                border_style="yellow",
            ))
            console.print(Markdown(strategy_result["risk_register"]))
            show_sources(strategy_result["risk_sources"])
            console.print(f"\n[bold green]💾 Risk Register saved to:[/bold green] [cyan]{strategy_result['risk_path']}[/cyan]")

            # Display Effort Estimation
            console.print()
            console.print(Panel(
                "[bold green]📊 Effort Estimation Report[/bold green]",
                border_style="green",
            ))
            console.print(Markdown(strategy_result["effort_report"]))
            console.print(f"\n[bold green]💾 Effort Report saved to:[/bold green] [cyan]{strategy_result['effort_path']}[/cyan]")

            # Display Test Strategy
            console.print()
            console.print(Panel(
                "[bold cyan]📋 Generated Test Strategy[/bold cyan]",
                border_style="cyan",
            ))
            console.print(Markdown(strategy_result["strategy"]))
            show_sources(strategy_result["sources"])
            console.print(f"\n[bold green]💾 Strategy saved to:[/bold green] [cyan]{strategy_result['strategy_path']}[/cyan]")

            # Display Test Plan
            console.print()
            console.print(Panel(
                "[bold blue]📝 Test Plan[/bold blue]",
                border_style="blue",
            ))
            console.print(Markdown(strategy_result["test_plan"]))
            show_sources(strategy_result["test_plan_sources"])
            console.print(f"\n[bold green]💾 Test Plan saved to:[/bold green] [cyan]{strategy_result['test_plan_path']}[/cyan]")

            output_path = strategy_result["strategy_path"]

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

                # Strip existing YAML front matter before prepending feedback block
                original_text = output_path.read_text(encoding="utf-8")
                if original_text.startswith("---"):
                    end = original_text.find("---", 3)
                    body = original_text[end + 3:].lstrip("\n") if end != -1 else original_text
                else:
                    body = original_text
                feedback_content = f"---\nfeedback: {feedback}\nnotes: {extra_note}\n---\n\n"
                feedback_path = feedback_dir / output_path.name
                feedback_path.write_text(feedback_content + body, encoding="utf-8")
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
