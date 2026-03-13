"""
LegalResearcher — full research pipeline for a LangGraph agent node.

Pipeline:
  1. Generate 3 targeted CourtListener search queries via LLM
  2. Fetch precedents for each query (deduplicated by URL)
  3. Pull relevant statutes from the local FAISS knowledge base
  4. Synthesize everything into a single `legal_context` string via LLM
"""

import os
from langchain_core.messages import HumanMessage, SystemMessage

from src.llm import get_model
from src.database import search_laws, format_provided_context
from src.court_listener import CourtListenerClient, Precedent, format_precedents

# ---------------------------------------------------------------------------
# Prompts (kept here; only used by this module)
# ---------------------------------------------------------------------------

_MULTI_QUERY_PROMPT = """You are a legal research assistant preparing search queries for the CourtListener full-text case law database.

Given a legal scenario, generate exactly 3 professional search queries, each targeting a different legal angle or theory.

Rules:
- Each query must be 6–14 words
- Cover different theories (e.g., negligence, products liability, respondeat superior, statute violation)
- Use natural legal terminology — no party names, no jurisdiction names, no code numbers
- Output exactly 3 lines — one query per line — nothing else (no numbering, no bullets, no explanation)

Example output for a driverless car collision:
autonomous vehicle manufacturer defective software negligence duty of care
self-driving car product liability failure to warn consumer
employer vicarious liability autonomous vehicle deployment wrongful injury"""


_SYNTHESIZER_PROMPT = """You are a senior legal researcher preparing a pre-trial briefing for litigation attorneys.

Given case facts, relevant California statutes, and real court opinions retrieved from CourtListener, write a concise LEGAL CONTEXT document that attorneys can cite directly in argument.

Structure your output exactly as follows:

RELEVANT STATUTES
List the 2–3 most applicable statutes. For each: citation code, title, and one sentence on why it applies.

KEY PRECEDENTS
For each of the top 2 most on-point court cases:
  • Case name — IMPORTANT: the input already provides the case name as a markdown hyperlink [Case Name](URL).
    You MUST copy it exactly in that format. Example: [Smith v. Jones](https://www.courtlistener.com/opinion/123/)
  • Citation (copy exactly as provided)
  • The court's central holding in one sentence
  • How the facts of that case compare to the current scenario (one sentence each: similarities, differences)

STRATEGIC NOTES
One paragraph: the strongest available legal theory, and the most likely counter-argument to prepare for.

Critical rules:
- NEVER write a case name as plain text — always use the [Case Name](URL) hyperlink format from the input
- NEVER invent or modify URLs — copy them character-for-character from the input
- Do NOT invent case names, citations, or statute text not present in the input
- If no court cases were retrieved, omit the KEY PRECEDENTS section entirely and note the absence
- Be concise and attorney-ready — this will be read under time pressure"""


# ---------------------------------------------------------------------------
# LegalResearcher
# ---------------------------------------------------------------------------

class LegalResearcher:
    """
    Encapsulates the full research pipeline: query generation →
    CourtListener fetch → FAISS statute retrieval → LLM synthesis.

    Args:
        model_name: Optional Gemini model override (e.g. "gemini-2.5-flash").
                    Falls back to the LLM_PROVIDER default.
    """

    def __init__(self, model_name: str | None = None):
        self._model_name = model_name

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def research(self, case_facts: str) -> tuple[str, list[dict]]:
        """
        Run the full pipeline and return a tuple of:
          - legal_context: synthesized str ready for LangGraph state injection
          - source_cases: list of dicts (name, url, citations, court, date, snippet)
            for rendering clickable citations in the UI
        """
        queries = self._generate_queries(case_facts)
        precedents = self._fetch_precedents(queries)
        statutes = self._get_statutes(case_facts)
        legal_context = self._synthesize(case_facts, statutes, precedents)
        source_cases = [
            {
                "name": p.case_name,
                "url": p.url,
                "citations": p.citations,
                "court": p.court,
                "date": p.date_filed,
                "snippet": p.snippet,
            }
            for p in precedents
        ]
        return legal_context, source_cases

    # ------------------------------------------------------------------
    # Pipeline steps
    # ------------------------------------------------------------------

    def _generate_queries(self, case_facts: str) -> list[str]:
        """Ask the LLM for 3 targeted CourtListener search queries."""
        model = get_model(self._model_name)
        response = model.invoke([
            SystemMessage(content=_MULTI_QUERY_PROMPT),
            HumanMessage(content=f"Case facts:\n{case_facts}"),
        ])
        lines = [q.strip() for q in response.content.strip().splitlines() if q.strip()]
        return lines[:3]  # guard against over-generation

    def _fetch_precedents(self, queries: list[str], per_query: int = 3) -> list[Precedent]:
        """
        Search CourtListener for each query; return a deduplicated list
        ordered by the query that produced them (highest-priority first).
        Gracefully returns [] if the token is missing or the API fails.
        """
        try:
            client = CourtListenerClient()
        except EnvironmentError:
            return []

        seen_urls: set[str] = set()
        results: list[Precedent] = []

        for query in queries:
            try:
                hits = client.search_precedents(query, max_results=per_query)
            except RuntimeError:
                continue
            for hit in hits:
                if hit.url not in seen_urls:
                    seen_urls.add(hit.url)
                    results.append(hit)

        return results

    def _get_statutes(self, case_facts: str) -> str:
        """Retrieve the most relevant statutes from the local FAISS knowledge base."""
        docs = search_laws(case_facts)
        return format_provided_context(docs)

    def _synthesize(
        self,
        case_facts: str,
        statutes: str,
        precedents: list[Precedent],
    ) -> str:
        """Use the LLM to synthesize statutes + precedents into a single legal_context."""
        precedent_block = (
            format_precedents(precedents)
            if precedents
            else "\nNo court cases retrieved from CourtListener (token not configured or no matches found).\n"
        )

        model = get_model(self._model_name)
        response = model.invoke([
            SystemMessage(content=_SYNTHESIZER_PROMPT),
            HumanMessage(
                content=(
                    f"CASE FACTS:\n{case_facts}\n\n"
                    f"STATUTES FROM KNOWLEDGE BASE:\n{statutes}\n\n"
                    f"COURT OPINIONS FROM COURTLISTENER:{precedent_block}"
                )
            ),
        ])
        return response.content.strip()
