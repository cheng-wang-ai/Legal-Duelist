"""
Standalone CourtListener API connection test.
Run with: .venv/bin/python test_court_listener.py
"""

import os
import re
import sys

import requests
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table

load_dotenv()

console = Console()

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

# Accept both naming conventions
TOKEN = os.getenv("COURT_LISTENER_TOKEN") or os.getenv("COURTLISTENER_TOKEN")

ENDPOINT = "https://www.courtlistener.com/api/rest/v3/search/"

DISPLAY_LIMIT = 3           # how many results to show
FETCH_SIZE = 10             # CourtListener enforces a minimum of 10; we slice below

PARAMS = {
    "q": "slip and fall negligence",
    "type": "o",            # 'o' = Opinions / case law
    "page_size": FETCH_SIZE,
    "order_by": "score desc",
    "stat_Precedential": "on",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "").strip()


def _is_prose(text: str) -> bool:
    if len(text) < 60:
        return False
    if text == text.upper():
        return False
    if re.match(r"^(No\.|Case\s+\d|Nos?\.\s*\d|\d{2}-\d)", text):
        return False
    if not re.search(r"\b(the|a|an|is|was|were|are|has|have|held|found|affirmed|reversed)\b", text, re.I):
        return False
    return True


def _best_snippet(hit: dict, limit: int = 260) -> str:
    """Return the most readable excerpt: highlighted snippet first, then first prose paragraph."""
    raw = _strip_html(hit.get("snippet") or "")
    if _is_prose(raw):
        return raw[:limit] + ("…" if len(raw) > limit else "")

    full_text = _strip_html(hit.get("text") or "")
    for line in re.split(r"\n{2,}|\r\n", full_text):
        line = line.strip()
        if _is_prose(line):
            return line[:limit] + ("…" if len(line) > limit else "")

    return "No excerpt available."

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

console.print()
console.print(Rule("[bold white]CourtListener API Connection Test[/bold white]"))
console.print()

# 1 ── Token check ──────────────────────────────────────────────────────────

if not TOKEN:
    console.print(
        Panel(
            "[bold red]No API token found.[/bold red]\n\n"
            "Add one of the following to your [bold].env[/bold] file:\n"
            "  [cyan]COURT_LISTENER_TOKEN=your-token-here[/cyan]\n\n"
            "Free tokens: [link=https://www.courtlistener.com/sign-in/]"
            "https://www.courtlistener.com/sign-in/[/link]",
            title="[red]Missing Token[/red]",
            border_style="red",
        )
    )
    sys.exit(1)

console.print(f"[green]✓[/green] Token loaded  [dim]({TOKEN[:6]}{'*' * (len(TOKEN) - 6)})[/dim]")
console.print(f"[green]✓[/green] Endpoint: [cyan]{ENDPOINT}[/cyan]")
console.print(f"[green]✓[/green] Query: [italic]\"{PARAMS['q']}\"[/italic]  ·  type=o  ·  precedential only  ·  showing top {DISPLAY_LIMIT}")
console.print()
console.print(
    "[dim]Note: API minimum page_size is 10. Fetching 10, displaying "
    f"top {DISPLAY_LIMIT} by relevance score.[/dim]"
)
console.print()

# 2 ── API request ──────────────────────────────────────────────────────────

console.print("[dim]Sending request…[/dim]")

try:
    response = requests.get(
        ENDPOINT,
        headers={"Authorization": f"Token {TOKEN}"},
        params=PARAMS,
        timeout=15,
    )
except requests.exceptions.ConnectionError:
    console.print(Panel("[bold red]Connection failed.[/bold red]\nCheck your internet connection.", border_style="red"))
    sys.exit(1)
except requests.exceptions.Timeout:
    console.print(Panel("[bold red]Request timed out after 15 seconds.[/bold red]", border_style="red"))
    sys.exit(1)

# 3 ── Error handling ────────────────────────────────────────────────────────

if response.status_code in (401, 403):
    console.print(
        Panel(
            f"[bold red]Authentication error — HTTP {response.status_code}.[/bold red]\n\n"
            "Your token was rejected. Please check:\n"
            "  1. The token is copied correctly (no extra spaces)\n"
            "  2. The token is still valid at "
            "[link=https://www.courtlistener.com/sign-in/]courtlistener.com[/link]\n"
            "  3. Your .env file uses [cyan]COURT_LISTENER_TOKEN[/cyan] "
            "or [cyan]COURTLISTENER_TOKEN[/cyan]",
            title=f"[red]HTTP {response.status_code}[/red]",
            border_style="red",
        )
    )
    sys.exit(1)

if not response.ok:
    console.print(
        Panel(
            f"[bold red]Unexpected error — HTTP {response.status_code}[/bold red]\n\n{response.text[:400]}",
            title="[red]API Error[/red]",
            border_style="red",
        )
    )
    sys.exit(1)

# 4 ── Parse and display ─────────────────────────────────────────────────────

data = response.json()
all_results = data.get("results", [])
total = data.get("count", 0)
shown = all_results[:DISPLAY_LIMIT]   # ← cap to requested display limit

console.print(
    f"[green]✓[/green] HTTP {response.status_code} OK  "
    f"[dim]— {total:,} total results in index, showing top {len(shown)} of {len(all_results)} fetched[/dim]"
)
console.print()
console.print(Rule("[bold]Top Results[/bold]"))
console.print()

if not shown:
    console.print("[yellow]No results returned for this query.[/yellow]")
    sys.exit(0)

for i, hit in enumerate(shown, 1):
    case_name  = hit.get("caseName") or "Unknown Case"
    date_filed = hit.get("dateFiled") or "—"
    court      = hit.get("court") or "—"
    citations  = ", ".join(hit.get("citation") or []) or "—"
    status     = hit.get("status") or "—"
    snippet    = _best_snippet(hit)
    url        = "https://www.courtlistener.com" + (hit.get("absolute_url") or "")

    table = Table.grid(padding=(0, 2))
    table.add_column(style="bold dim", width=14)
    table.add_column()
    table.add_row("Case Name",  f"[bold]{case_name}[/bold]")
    table.add_row("Citations",  f"[cyan]{citations}[/cyan]")
    table.add_row("Court",      court)
    table.add_row("Date Filed", date_filed)
    table.add_row("Status",     status)
    table.add_row("Excerpt",    f"[dim italic]{snippet}[/dim italic]")
    table.add_row("URL",        f"[link={url}]{url}[/link]")

    console.print(Panel(table, title=f"[bold white]#{i}[/bold white]", border_style="blue", padding=(0, 1)))
    console.print()

console.print(Rule("[green]Connection test passed[/green]"))
console.print()
