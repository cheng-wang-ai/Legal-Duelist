"""
CourtListener API client for retrieving real legal precedents.

Docs: https://www.courtlistener.com/help/api/rest/
Auth: https://www.courtlistener.com/help/api/rest/#auth

Set COURT_LISTENER_TOKEN in your .env file.
Free tokens are available at https://www.courtlistener.com/sign-in/
"""

import os
import re
from dataclasses import dataclass, field

import requests
from dotenv import load_dotenv

load_dotenv()

_OPINION_SEARCH_URL = "https://www.courtlistener.com/api/v3/search/"
_BASE_URL = "https://www.courtlistener.com"

# ---------------------------------------------------------------------------
# Jurisdiction constants — pass these to search_precedents()
# ---------------------------------------------------------------------------

# Federal appellate — covers California and the Western U.S.
CA9 = "ca9"
# U.S. Supreme Court
SCOTUS = "scotus"
# California Supreme Court
CAL_SUPREME = "cal"
# California Court of Appeal
CAL_APPEAL = "calctapp"

# Sensible default for California civil/AV litigation
DEFAULT_JURISDICTIONS: list[str] = [CA9, SCOTUS, CAL_SUPREME, CAL_APPEAL]


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Precedent:
    case_name: str
    citations: list[str]
    court: str
    date_filed: str
    status: str          # e.g., "Precedential", "Unpublished"
    snippet: str         # highlighted excerpt from full text
    url: str             # full CourtListener page URL

    def format(self) -> str:
        """Return a formatted string suitable for injection into a prompt.
        The case name is already formatted as a markdown hyperlink so the
        synthesizer LLM can copy the [Name](URL) pattern verbatim.
        """
        cite_str = ", ".join(self.citations) if self.citations else "No citation"
        return (
            f"Case:    [{self.case_name}]({self.url})\n"
            f"Cite:    {cite_str}\n"
            f"Court:   {self.court}  |  Filed: {self.date_filed}  |  {self.status}\n"
            f"Excerpt: {self.snippet}"
        )


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class CourtListenerClient:
    """
    Thin wrapper around the CourtListener search API v3.

    Usage:
        client = CourtListenerClient()
        results = client.search_precedents("autonomous vehicle negligence California")
        for p in results:
            print(p.format())
    """

    def __init__(self, api_token: str | None = None):
        token = api_token or os.getenv("COURT_LISTENER_TOKEN")
        if not token:
            raise EnvironmentError(
                "COURT_LISTENER_TOKEN not set. "
                "Add it to your .env file. "
                "Free tokens: https://www.courtlistener.com/sign-in/"
            )
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Token {token}",
            "Accept": "application/json",
        })

    def search_precedents(
        self,
        query: str,
        jurisdictions: list[str] | None = None,
        max_results: int = 5,
        precedential_only: bool = True,
    ) -> list[Precedent]:
        """
        Search CourtListener for opinion precedents matching `query`.

        Args:
            query:             Full-text search string.
            jurisdictions:     List of CourtListener court IDs to filter by.
                               Defaults to [ca9, scotus, cal, calctapp].
            max_results:       Maximum number of results to return (1–20).
            precedential_only: When True, filter to Precedential opinions only.

        Returns:
            List of Precedent dataclass instances, sorted by relevance.
        """
        courts = " ".join(jurisdictions or DEFAULT_JURISDICTIONS)
        params: dict = {
            "q": query,
            "type": "o",           # 'o' = Opinions
            "court": courts,
            "order_by": "score desc",
            "page_size": min(max_results, 20),
        }
        if precedential_only:
            params["stat_Precedential"] = "on"

        try:
            response = self._session.get(
                _OPINION_SEARCH_URL,
                params=params,
                timeout=15,
            )
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            raise RuntimeError(
                f"CourtListener API error {e.response.status_code}: {e.response.text[:300]}"
            ) from e
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"CourtListener request failed: {e}") from e

        hits = response.json().get("results", [])
        return [_parse_hit(hit) for hit in hits[:max_results]]


def format_precedents(precedents: list[Precedent]) -> str:
    """
    Format a list of Precedent objects into a numbered block
    ready to be injected into a LangGraph agent prompt.
    """
    if not precedents:
        return "No relevant precedents found in CourtListener."
    sections = [f"PRECEDENT {i}:\n{p.format()}" for i, p in enumerate(precedents, 1)]
    return "\n\n" + "\n\n".join(sections)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _parse_hit(hit: dict) -> Precedent:
    return Precedent(
        case_name=hit.get("caseName") or "Unknown Case",
        citations=hit.get("citation") or [],
        court=hit.get("court") or "",
        date_filed=hit.get("dateFiled") or "",
        status=hit.get("status") or "Unknown",
        snippet=_best_snippet(hit),
        url=_BASE_URL + (hit.get("absolute_url") or ""),
    )


def _strip_html(text: str) -> str:
    """Remove HTML tags (CourtListener wraps matches in <mark> tags)."""
    return re.sub(r"<[^>]+>", "", text).strip()


def _best_snippet(hit: dict, limit: int = 280) -> str:
    """
    Return the most meaningful excerpt from a search hit.

    Priority:
      1. API `snippet` field — only populated when the query term appears
         in the highlighted window; use it if it contains actual prose.
      2. First substantial paragraph extracted from the full `text` field.
      3. Fallback message.
    """
    # 1 — try the highlighted snippet
    raw = _strip_html(hit.get("snippet") or "")
    if _is_prose(raw):
        return raw[:limit] + ("…" if len(raw) > limit else "")

    # 2 — walk the full text looking for the first real sentence
    full_text = _strip_html(hit.get("text") or "")
    for line in re.split(r"\n{2,}|\r\n", full_text):
        line = line.strip()
        if _is_prose(line):
            return line[:limit] + ("…" if len(line) > limit else "")

    return "No excerpt available."


def _is_prose(text: str) -> bool:
    """
    Return True when text looks like a genuine sentence rather than a
    case header, docket number, or formatting artefact.
    """
    if len(text) < 60:
        return False
    # Reject lines that are purely uppercase (court headers)
    if text == text.upper():
        return False
    # Reject lines that start with a docket-style number: "No. 12345" / "Case 1:23-cv"
    if re.match(r"^(No\.|Case\s+\d|Nos?\.\s*\d|\d{2}-\d)", text):
        return False
    # Must contain at least one verb-like word to be a real sentence
    if not re.search(r"\b(the|a|an|is|was|were|are|has|have|held|found|affirmed|reversed)\b", text, re.I):
        return False
    return True
