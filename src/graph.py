import re
from typing import TypedDict, NotRequired
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, START, END

from src.llm import get_model
from src.researcher import LegalResearcher
from src.prompts import (
    EVIDENCE_ANALYST_PROMPT,
    PLAINTIFF_SYSTEM_PROMPT,
    DEFENSE_SYSTEM_PROMPT,
    JUDGE_SYSTEM_PROMPT,
)

_IMAGE_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp", "image/gif"}

# Matches existing markdown links so we never double-link them.
_EXISTING_LINK_RE = re.compile(r'\[[^\]]+\]\([^)]+\)')


def inject_case_links(text: str, source_cases: list[dict]) -> str:
    """
    Deterministically inject [Case Name](URL) markdown hyperlinks into text.

    For each case in source_cases, replaces plain-text occurrences of the case
    name with a markdown link. Longer names are processed first to avoid
    substring conflicts. Names already inside a markdown link are never
    double-linked. Matching is case-insensitive.
    """
    if not source_cases or not text:
        return text

    # Only process cases that have both a name and a URL; longest names first
    cases = sorted(
        [c for c in source_cases if c.get("name") and c.get("url")],
        key=lambda c: len(c["name"]),
        reverse=True,
    )

    for case in cases:
        name = case["name"]
        url = case["url"]
        name_re = re.compile(re.escape(name), re.IGNORECASE)

        # Split around existing markdown links — never modify them
        segments = _EXISTING_LINK_RE.split(text)
        existing_links = _EXISTING_LINK_RE.findall(text)

        # Replace plain-text case name only in non-link segments
        new_segments = [name_re.sub(f'[{name}]({url})', seg) for seg in segments]

        # Reassemble: interleave processed segments with original links
        result: list[str] = []
        for i, seg in enumerate(new_segments):
            result.append(seg)
            if i < len(existing_links):
                result.append(existing_links[i])
        text = "".join(result)

    return text


class LegalState(TypedDict):
    case_facts: str
    model_name: NotRequired[str]        # optional model override
    evidence_raw: NotRequired[str]      # base64 for images; extracted text for PDFs
    evidence_type: NotRequired[str]     # MIME type or "application/pdf"
    evidence_filename: NotRequired[str] # original filename for display
    evidence_summary: NotRequired[str]  # AI-generated forensic description
    legal_context: str                  # synthesized statutes + precedents from researcher
    source_cases: NotRequired[list]     # raw list[dict] of retrieved precedents (name/url/etc.)
    plaintiff_speech: str
    defense_rebuttal: str
    judge_analysis: str


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

def research_cases_node(state: LegalState) -> LegalState:
    """
    Full research pipeline:
      1. LLM generates 3 professional CourtListener search queries
      2. CourtListener returns real precedents for each query (deduplicated)
      3. FAISS retrieves relevant statutes from the local knowledge base
      4. LLM synthesizes statutes + precedents into a single `legal_context`
    """
    researcher = LegalResearcher(model_name=state.get("model_name"))
    legal_context, source_cases = researcher.research(state["case_facts"])
    legal_context = inject_case_links(legal_context, source_cases)
    return {"legal_context": legal_context, "source_cases": source_cases}


def evidence_analyst_node(state: LegalState) -> LegalState:
    model = get_model(state.get("model_name"))
    evidence_type = state.get("evidence_type", "")
    evidence_raw = state.get("evidence_raw", "")

    if evidence_type in _IMAGE_TYPES:
        human_content = [
            {
                "type": "text",
                "text": (
                    f"Case facts: {state['case_facts']}\n\n"
                    f"File: {state.get('evidence_filename', 'evidence')}\n\n"
                    "Analyze the submitted image as evidence for this legal case."
                ),
            },
            {
                "type": "image_url",
                "image_url": {"url": f"data:{evidence_type};base64,{evidence_raw}"},
            },
        ]
    else:
        human_content = (
            f"Case facts: {state['case_facts']}\n\n"
            f"File: {state.get('evidence_filename', 'document.pdf')}\n\n"
            f"Document contents:\n{evidence_raw}\n\n"
            "Analyze the submitted document as evidence for this legal case."
        )

    messages = [
        SystemMessage(content=EVIDENCE_ANALYST_PROMPT),
        HumanMessage(content=human_content),
    ]
    response = model.invoke(messages)
    return {"evidence_summary": response.content}


def _build_advocate_context(state: LegalState) -> str:
    """Assemble the shared context block for plaintiff and defense."""
    parts = [
        f"CASE FACTS:\n{state['case_facts']}",
        f"LEGAL CONTEXT:\n{state['legal_context']}",
    ]
    if state.get("evidence_summary"):
        parts.append(f"EVIDENCE SUMMARY:\n{state['evidence_summary']}")
    return "\n\n".join(parts)


def plaintiff_node(state: LegalState) -> LegalState:
    model = get_model(state.get("model_name"))
    messages = [
        SystemMessage(content=PLAINTIFF_SYSTEM_PROMPT),
        HumanMessage(content=_build_advocate_context(state)),
    ]
    response = model.invoke(messages)
    speech = inject_case_links(response.content, state.get("source_cases") or [])
    return {"plaintiff_speech": speech}


def defense_node(state: LegalState) -> LegalState:
    model = get_model(state.get("model_name"))
    context = _build_advocate_context(state)
    messages = [
        SystemMessage(content=DEFENSE_SYSTEM_PROMPT),
        HumanMessage(
            content=f"{context}\n\nPLAINTIFF'S ARGUMENT:\n{state['plaintiff_speech']}"
        ),
    ]
    response = model.invoke(messages)
    rebuttal = inject_case_links(response.content, state.get("source_cases") or [])
    return {"defense_rebuttal": rebuttal}


def judge_node(state: LegalState) -> LegalState:
    model = get_model(state.get("model_name"))
    messages = [
        SystemMessage(content=JUDGE_SYSTEM_PROMPT),
        HumanMessage(
            content=(
                f"CASE FACTS:\n{state['case_facts']}\n\n"
                f"PLAINTIFF'S ARGUMENT:\n{state['plaintiff_speech']}\n\n"
                f"DEFENSE'S REBUTTAL:\n{state['defense_rebuttal']}"
            )
        ),
    ]
    response = model.invoke(messages)
    analysis = inject_case_links(response.content, state.get("source_cases") or [])
    return {"judge_analysis": analysis}


# ---------------------------------------------------------------------------
# Graph  —  START → research_cases → plaintiff → defense → judge → END
#           (evidence_analyst inserted conditionally between research_cases
#            and plaintiff when a file has been uploaded)
# ---------------------------------------------------------------------------

def _route_after_research(state: LegalState) -> str:
    return "evidence_analyst" if state.get("evidence_raw") else "plaintiff"


def build_graph() -> StateGraph:
    builder = StateGraph(LegalState)

    builder.add_node("research_cases", research_cases_node)
    builder.add_node("evidence_analyst", evidence_analyst_node)
    builder.add_node("plaintiff", plaintiff_node)
    builder.add_node("defense", defense_node)
    builder.add_node("judge", judge_node)

    builder.add_edge(START, "research_cases")
    builder.add_conditional_edges(
        "research_cases",
        _route_after_research,
        {"evidence_analyst": "evidence_analyst", "plaintiff": "plaintiff"},
    )
    builder.add_edge("evidence_analyst", "plaintiff")
    builder.add_edge("plaintiff", "defense")
    builder.add_edge("defense", "judge")
    builder.add_edge("judge", END)

    return builder.compile()
