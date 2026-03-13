from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.rule import Rule
from rich.text import Text

load_dotenv()

console = Console()


def print_banner():
    title = Text("⚖  LEGAL DUELIST  ⚖", style="bold white on dark_blue", justify="center")
    console.print(Panel(title, padding=(1, 4)))
    console.print(
        "[dim]A multi-agent legal argument simulator powered by Claude[/dim]\n",
        justify="center",
    )


def print_agent_output(label: str, content: str, style: str, border_style: str):
    console.print(Rule(f"[bold {style}]{label}[/bold {style}]", style=border_style))
    console.print(Panel(content, border_style=border_style, padding=(1, 2)))
    console.print()


def main():
    print_banner()

    case_facts = Prompt.ask(
        "[bold cyan]Describe the legal scenario[/bold cyan]",
        console=console,
    )

    if not case_facts.strip():
        console.print("[red]No scenario provided. Exiting.[/red]")
        return

    console.print()
    console.print("[dim]Building case arguments...[/dim]\n")

    from src.graph import build_graph

    graph = build_graph()

    with console.status("[bold yellow]Plaintiff is building their case...[/bold yellow]"):
        result = {}
        for step in graph.stream({"case_facts": case_facts}):
            node_name = list(step.keys())[0]
            result.update(step[node_name])

            if node_name == "research_cases":
                console.log("[blue]✓ Legal research complete (statutes + CourtListener precedents)[/blue]")
            elif node_name == "plaintiff":
                console.log("[green]✓ Plaintiff argument ready[/green]")
            elif node_name == "defense":
                console.log("[red]✓ Defense rebuttal ready[/red]")
            elif node_name == "judge":
                console.log("[yellow]✓ Judge's analysis ready[/yellow]")

    console.print()
    console.print(
        Panel(
            result.get("legal_context", ""),
            border_style="blue",
            title="[bold blue]Legal Research Context (Statutes + Precedents)[/bold blue]",
            padding=(1, 2),
        )
    )
    console.print()
    console.print(Rule("[bold]ARGUMENTS[/bold]", style="white"))
    console.print()

    print_agent_output(
        "PLAINTIFF",
        result.get("plaintiff_speech", ""),
        style="green",
        border_style="green",
    )

    print_agent_output(
        "DEFENSE",
        result.get("defense_rebuttal", ""),
        style="red",
        border_style="red",
    )

    console.print(Rule("[bold gold1]JUDGE'S RULING[/bold gold1]", style="gold1"))
    console.print(
        Panel(
            result.get("judge_analysis", ""),
            border_style="gold1",
            title="[bold gold1]IRAC Analysis[/bold gold1]",
            padding=(1, 2),
        )
    )
    console.print()


if __name__ == "__main__":
    main()
