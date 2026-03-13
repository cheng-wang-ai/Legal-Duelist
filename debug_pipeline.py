"""
Debug script — run this to verify each step of the pipeline:
  1. Is COURT_LISTENER_TOKEN set?
  2. Can the CourtListener API return results?
  3. Does Precedent.format() produce [Name](URL) markdown links?
  4. Does the synthesizer LLM preserve the links? (likely NOT)
  5. Does inject_case_links() fix them?

Usage:
  python debug_pipeline.py
"""

import os
import re
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule

load_dotenv()
console = Console()

TEST_SCENARIO = (
    "A tenant slipped on an icy staircase in their apartment building. "
    "The landlord had been notified of the hazard three weeks prior but took no action. "
    "The tenant suffered a fractured wrist and missed two weeks of work."
)

MD_LINK_RE = re.compile(r'\[([^\]]+)\]\((https?://[^)]+)\)')


def count_links(text: str) -> list[tuple[str, str]]:
    """Return list of (label, url) found as markdown links in text."""
    return MD_LINK_RE.findall(text)


def main():
    console.print(Rule("[bold]STEP 1: Environment Check[/bold]"))

    token = os.getenv("COURT_LISTENER_TOKEN")
    api_key = os.getenv("LLM_API_KEY")
    provider = os.getenv("LLM_PROVIDER", "not set")

    console.print(f"  LLM_PROVIDER:         {provider}")
    console.print(f"  LLM_API_KEY:          {'✅ set (' + api_key[:8] + '...)' if api_key else '❌ MISSING'}")
    console.print(f"  COURT_LISTENER_TOKEN: {'✅ set (' + token[:8] + '...)' if token else '❌ MISSING'}")
    console.print()

    if not token:
        console.print("[red bold]COURT_LISTENER_TOKEN is not set![/red bold]")
        console.print("Without this token, the app cannot fetch real cases from CourtListener.")
        console.print("→ source_cases will be an empty list")
        console.print("→ inject_case_links() has nothing to inject")
        console.print("→ No hyperlinks in the output\n")
        console.print("[yellow]Fix: Get a free token at https://www.courtlistener.com/sign-in/[/yellow]")
        console.print("[yellow]     Then add it to your .env file[/yellow]")
        # Continue anyway to test remaining steps

    # ---------------------------------------------------------------
    console.print(Rule("[bold]STEP 2: CourtListener API Test[/bold]"))

    if not token:
        console.print("[dim]Skipped — no token[/dim]\n")
        precedents = []
    else:
        try:
            from src.court_listener import CourtListenerClient
            client = CourtListenerClient()
            precedents = client.search_precedents(
                "landlord negligence tenant slip fall injury duty of care",
                max_results=3,
            )
            console.print(f"  Results returned: [bold]{len(precedents)}[/bold]")
            for i, p in enumerate(precedents):
                console.print(f"\n  [{i+1}] {p.case_name}")
                console.print(f"      URL:  {p.url}")
                console.print(f"      Cite: {', '.join(p.citations) if p.citations else 'none'}")
        except Exception as e:
            console.print(f"[red]  API error: {e}[/red]")
            precedents = []
    console.print()

    # ---------------------------------------------------------------
    console.print(Rule("[bold]STEP 3: Precedent.format() Output[/bold]"))

    if not precedents:
        console.print("[dim]Skipped — no precedents to format[/dim]\n")
    else:
        for i, p in enumerate(precedents):
            formatted = p.format()
            links = count_links(formatted)
            console.print(f"  Precedent {i+1} format():")
            console.print(f"    {formatted.splitlines()[0]}")
            console.print(f"    Markdown links found: [bold]{'✅ ' + str(len(links)) if links else '❌ 0'}[/bold]")
    console.print()

    # ---------------------------------------------------------------
    console.print(Rule("[bold]STEP 4: Full Research Pipeline[/bold]"))

    if not api_key:
        console.print("[red]Skipped — no LLM_API_KEY[/red]\n")
        return

    try:
        from src.researcher import LegalResearcher
        researcher = LegalResearcher()
        legal_context, source_cases = researcher.research(TEST_SCENARIO)
    except Exception as e:
        console.print(f"[red]  Research failed: {e}[/red]\n")
        return

    console.print(f"  source_cases count: [bold]{len(source_cases)}[/bold]")
    for c in source_cases:
        console.print(f"    • {c['name']}  →  {c['url']}")

    links_in_context = count_links(legal_context)
    console.print(f"\n  Markdown links in legal_context (from LLM): [bold]{len(links_in_context)}[/bold]")
    if links_in_context:
        for label, url in links_in_context:
            console.print(f"    ✅ [{label}]({url[:60]}...)")
    else:
        console.print("    [yellow]⚠ The synthesizer LLM did NOT preserve any markdown links[/yellow]")

    console.print()

    # ---------------------------------------------------------------
    console.print(Rule("[bold]STEP 5: inject_case_links() Fix[/bold]"))

    from src.graph import inject_case_links
    fixed_context = inject_case_links(legal_context, source_cases)
    links_after_fix = count_links(fixed_context)

    console.print(f"  Markdown links after inject_case_links(): [bold]{len(links_after_fix)}[/bold]")
    if links_after_fix:
        for label, url in links_after_fix:
            console.print(f"    ✅ [{label}]({url[:60]}...)")
    else:
        console.print("    [red]❌ Still no links — check if case names appear in the text at all[/red]")

        # Extra debug: check if case names appear as plain text
        console.print("\n  [dim]Checking if case names appear as plain text in legal_context:[/dim]")
        for c in source_cases:
            name = c["name"]
            if name.lower() in legal_context.lower():
                console.print(f"    Found '{name}' as plain text — inject should have worked!")
            else:
                console.print(f"    '{name}' NOT found in text — LLM may have abbreviated it")

    console.print()

    # ---------------------------------------------------------------
    console.print(Rule("[bold]STEP 6: Sample Output Preview[/bold]"))
    # Show a short snippet of the fixed legal_context
    preview = fixed_context[:800] + ("..." if len(fixed_context) > 800 else "")
    console.print(Panel(preview, title="legal_context (first 800 chars)", border_style="blue"))


if __name__ == "__main__":
    main()
