# Fix: Case Citations Missing Hyperlinks in Generated Content

## Problem

In this Streamlit legal debate app, the plaintiff, defense, and judge outputs should contain clickable hyperlinks to CourtListener case pages, but they render as plain text instead.

**Root cause:** The pipeline passes case URLs through 2–3 chained LLM calls (Synthesizer → Plaintiff/Defense → Judge). Despite prompt instructions telling the LLM to preserve `[Case Name](URL)` markdown links, the LLM frequently drops the URL or reformats citations as plain text. By the time the text reaches the frontend `_render_links()` function (which correctly converts markdown links to `<a>` tags), the markdown links are already gone.

## Codebase Overview

```
app.py              — Streamlit frontend; _render_links() converts [text](url) → <a> tags
src/graph.py        — LangGraph pipeline: research → evidence → plaintiff → defense → judge
src/researcher.py   — Generates queries, fetches precedents, synthesizes legal_context via LLM
src/court_listener.py — CourtListener API client; Precedent dataclass with .format() method
src/prompts.py      — System prompts for plaintiff, defense, judge, evidence analyst
src/llm.py          — Model factory
src/database.py     — FAISS statute retrieval
```

## Data Flow

1. `CourtListenerClient.search_precedents()` returns `Precedent` objects with `.url` field
2. `Precedent.format()` outputs `[Case Name](URL)` markdown links
3. `format_precedents()` assembles these into a numbered block
4. `LegalResearcher._synthesize()` sends this block to the LLM with instructions to preserve links → outputs `legal_context` (links often lost here)
5. `legal_context` is passed to plaintiff/defense LLM nodes along with system prompts that instruct `[Case Name](URL)` format (links often lost again here)
6. `app.py`'s `_render_links()` tries to regex-match `[text](url)` but finds nothing to match

Meanwhile, `source_cases` (a list of dicts with `name`, `url`, `citations`, `court`, `date`, `snippet`) is stored separately in `LegalState` and `st.session_state` — this is the reliable source of truth for case URLs.

## Required Fix

**Add a deterministic post-processing step** that injects hyperlinks into LLM-generated text by matching case names from `source_cases` against the plain text output, replacing them with `[Case Name](URL)` markdown links. This way we don't rely on the LLM to preserve links.

### Implementation Plan

1. **Create a helper function** `inject_case_links(text: str, source_cases: list[dict]) -> str` that:
   - Takes the raw LLM output text and the `source_cases` list
   - For each case in `source_cases`, checks if the case name appears in the text as plain text (i.e., NOT already inside a markdown link)
   - Replaces plain-text case names with `[Case Name](URL)` markdown links
   - Handles partial matches (e.g., the LLM might write "Smith v. Jones" when the full name is "Smith v. Jones Corp.")
   - Avoids double-linking (if the LLM did output a proper link, don't break it)
   - Is case-insensitive for matching

2. **Apply this function** in `src/graph.py` to the outputs of:
   - `plaintiff_node` → `plaintiff_speech`
   - `defense_node` → `defense_rebuttal`
   - `judge_node` → `judge_analysis`

   Each of these nodes already has access to `state["source_cases"]` in `LegalState`.

3. **Also apply to `legal_context`** — in `research_cases_node`, after `researcher.research()` returns, run the same injection on `legal_context` using `source_cases`.

### Key Considerations

- **Avoid double-linking**: If the LLM already output `[Smith v. Jones](https://...)`, don't wrap it again. Check that a case name is not already inside `[...](...)`  before replacing.
- **Match flexibility**: The LLM might abbreviate case names. Consider matching the longest case names first to avoid partial replacements. Also consider matching common abbreviation patterns (e.g., dropping "et al.", "Inc.", or "Corp." suffixes).
- **Regex safety**: Case names may contain special regex characters like parentheses. Use `re.escape()`.
- **Order matters**: Replace longer names before shorter ones to prevent substring conflicts.

### Where NOT to Change

- Do NOT modify the LLM prompts in `prompts.py` or `researcher.py` — the current prompts are fine as aspirational instructions; we're just adding a deterministic safety net.
- Do NOT modify `_render_links()` in `app.py` — it already works correctly for converting markdown links to HTML anchors.
- Do NOT modify `court_listener.py` — the API client and data model are fine.

### Testing

After implementing, verify by:
1. Running the app with a test scenario
2. Checking that the plaintiff, defense, and judge cards contain clickable blue hyperlinks to CourtListener pages
3. Checking that the Legal Research Context section also has clickable links
4. Confirming that clicking a link opens the correct CourtListener opinion page
