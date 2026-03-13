import base64
import html
import io
import re

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Page config (must be first Streamlit call)
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Legal Duelist",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Global CSS
# ---------------------------------------------------------------------------

st.markdown(
    """
    <style>
    .plaintiff-card {
        background: #f0fff4;
        border-left: 5px solid #28a745;
        border-radius: 6px;
        padding: 20px 22px;
        line-height: 1.7;
        white-space: pre-wrap;
        font-size: 0.95rem;
    }
    .defense-card {
        background: #fff5f5;
        border-left: 5px solid #dc3545;
        border-radius: 6px;
        padding: 20px 22px;
        line-height: 1.7;
        white-space: pre-wrap;
        font-size: 0.95rem;
    }
    .judge-card {
        background: #fffbf0;
        border: 2px solid #f0a500;
        border-radius: 8px;
        padding: 24px 28px;
        line-height: 1.8;
        white-space: pre-wrap;
        font-size: 0.95rem;
    }
    .evidence-card {
        background: #faf5ff;
        border-left: 5px solid #7c3aed;
        border-radius: 6px;
        padding: 18px 22px;
        line-height: 1.7;
        white-space: pre-wrap;
        font-size: 0.9rem;
    }
    .agent-label {
        font-size: 1.1rem;
        font-weight: 700;
        margin-bottom: 10px;
    }
    .label-plaintiff { color: #28a745; }
    .label-defense   { color: #dc3545; }
    .label-judge     { color: #d48806; }
    .label-evidence  { color: #7c3aed; }
    .law-block {
        background: #f0f8ff;
        border-left: 4px solid #1a73e8;
        border-radius: 4px;
        padding: 14px 18px;
        font-size: 0.85rem;
        white-space: pre-wrap;
        font-family: monospace;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

GEMINI_MODELS = [
    "gemini-2.5-pro",
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
]

SESSION_KEYS = (
    "legal_context",
    "source_cases",
    "evidence_summary",
    "plaintiff_speech",
    "defense_rebuttal",
    "judge_analysis",
)


def _safe(text: str) -> str:
    return html.escape(text)


_MD_LINK_RE = re.compile(r'\[([^\]]+)\]\((https?://[^)]+)\)')


def _render_links(text: str) -> str:
    """Escape text for HTML but convert markdown [label](url) links to real anchors."""
    # Split around markdown links, escape non-link parts, convert links to <a>
    parts = _MD_LINK_RE.split(text)
    # split() with a capturing group returns [before, label, url, before, label, url, ...]
    out = []
    i = 0
    while i < len(parts):
        if i % 3 == 0:
            out.append(html.escape(parts[i]))
        elif i % 3 == 1:
            label = html.escape(parts[i])
            url = html.escape(parts[i + 1])
            out.append(
                f'<a href="{url}" target="_blank" rel="noopener noreferrer">{label}</a>'
            )
            i += 1  # skip the url part (already consumed)
        i += 1
    return "".join(out)


def _card(content: str, css_class: str) -> None:
    st.markdown(
        f'<div class="{css_class}">{_render_links(content)}</div>',
        unsafe_allow_html=True,
    )


def _process_upload(uploaded_file) -> tuple[str, str]:
    """Return (evidence_raw, evidence_type) from an UploadedFile."""
    mime = uploaded_file.type
    raw_bytes = uploaded_file.read()

    if mime == "application/pdf":
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(raw_bytes))
        text = "\n\n".join(
            page.extract_text() for page in reader.pages if page.extract_text()
        )
        return text, "application/pdf"

    # Image — base64 encode
    return base64.b64encode(raw_bytes).decode("utf-8"), mime


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown("## ⚙️ Model Settings")
    selected_model = st.selectbox(
        "Gemini Model",
        options=GEMINI_MODELS,
        index=0,
        help="Larger models produce more rigorous legal reasoning; flash models are faster.",
    )
    st.caption(f"Using `{selected_model}` for all agents.")

    st.divider()

    st.markdown("## 📎 Evidence Upload")
    uploaded_file = st.file_uploader(
        "Upload evidence (optional)",
        type=["jpg", "jpeg", "png", "pdf"],
        help="Images or PDFs are analyzed by a forensic AI agent before the duel begins.",
    )
    if uploaded_file:
        st.caption(f"📄 `{uploaded_file.name}` — {uploaded_file.type}")

    st.divider()

    if st.button("🗑️ Clear Results", use_container_width=True):
        for key in SESSION_KEYS:
            st.session_state.pop(key, None)
        st.rerun()

    st.divider()
    st.markdown(
        "**How it works**\n\n"
        "1. RAG retrieves relevant California statutes\n"
        "2. Evidence Analyst examines uploaded file *(if any)*\n"
        "3. Plaintiff builds an opening argument\n"
        "4. Defense delivers a rebuttal\n"
        "5. Judge applies IRAC analysis\n"
    )

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

st.title("⚖️ Legal Duelist: Agentic AI Moot Court")
st.caption("Powered by Google Gemini · LangGraph · FAISS RAG · Multimodal Evidence")
st.divider()

# ---------------------------------------------------------------------------
# Input section
# ---------------------------------------------------------------------------

scenario = st.text_area(
    "📋 Describe the legal scenario",
    height=160,
    placeholder=(
        "Example: A tenant slipped on an icy staircase in their apartment building. "
        "The landlord had been notified of the hazard three weeks prior but took no action. "
        "The tenant suffered a fractured wrist and missed two weeks of work."
    ),
)

start_clicked = st.button(
    "⚔️ Start Legal Duel",
    type="primary",
    use_container_width=True,
    disabled=not scenario.strip(),
)

# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------

if start_clicked and scenario.strip():
    for key in SESSION_KEYS:
        st.session_state.pop(key, None)

    # Process uploaded evidence before running the graph
    evidence_raw, evidence_type, evidence_filename = None, None, None
    if uploaded_file:
        uploaded_file.seek(0)  # reset after sidebar read
        evidence_raw, evidence_type = _process_upload(uploaded_file)
        evidence_filename = uploaded_file.name

    from src.graph import build_graph

    graph = build_graph()
    result: dict = {}

    initial_state = {
        "case_facts": scenario,
        "model_name": selected_model,
    }
    if evidence_raw:
        initial_state["evidence_raw"] = evidence_raw
        initial_state["evidence_type"] = evidence_type
        initial_state["evidence_filename"] = evidence_filename

    with st.status("⚖️ Agents are deliberating…", expanded=True) as status:
        for step in graph.stream(initial_state):
            node_name = list(step.keys())[0]
            result.update(step[node_name])

            if node_name == "research_cases":
                st.write("🔍 **Researcher** — querying CourtListener & retrieving statutes…")
            elif node_name == "evidence_analyst":
                st.write(f"🔬 **Evidence Analyst** — `{evidence_filename}` analyzed")
            elif node_name == "plaintiff":
                st.write("🟢 **Plaintiff** — opening argument complete")
            elif node_name == "defense":
                st.write("🔴 **Defense** — rebuttal complete")
            elif node_name == "judge":
                st.write("⚖️ **Judge** — IRAC analysis complete")

        status.update(label="Duel complete!", state="complete", expanded=False)

    for key in SESSION_KEYS:
        if key in result:
            st.session_state[key] = result[key]

    # Persist evidence display data for the results section
    if uploaded_file:
        st.session_state["_evidence_filename"] = evidence_filename
        st.session_state["_evidence_type"] = evidence_type
        st.session_state["_evidence_raw_b64"] = (
            evidence_raw if evidence_type != "application/pdf" else None
        )

# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------

if "plaintiff_speech" in st.session_state:

    # -- Evidence panel (if any) --
    if st.session_state.get("evidence_summary"):
        fname = st.session_state.get("_evidence_filename", "evidence")
        etype = st.session_state.get("_evidence_type", "")
        raw_b64 = st.session_state.get("_evidence_raw_b64")

        with st.expander(f"🔬 Evidence: `{fname}`", expanded=True):
            if raw_b64 and etype.startswith("image/"):
                img_bytes = base64.b64decode(raw_b64)
                col_img, col_analysis = st.columns([1, 2], gap="large")
                with col_img:
                    st.image(img_bytes, caption=fname, use_container_width=True)
                with col_analysis:
                    st.markdown(
                        '<div class="agent-label label-evidence">🔬 Forensic Analysis</div>',
                        unsafe_allow_html=True,
                    )
                    _card(st.session_state["evidence_summary"], "evidence-card")
            else:
                # PDF
                st.markdown(
                    '<div class="agent-label label-evidence">🔬 Forensic Analysis</div>',
                    unsafe_allow_html=True,
                )
                _card(st.session_state["evidence_summary"], "evidence-card")

        st.divider()

    # -- Legal context (synthesized statutes + precedents) --
    with st.expander("🔍 Legal Research Context (Statutes + Precedents)", expanded=True):
        st.markdown(
            '<div class="agent-label" style="color:#1a73e8;">🔍 Research Summary</div>',
            unsafe_allow_html=True,
        )
        _card(st.session_state.get("legal_context", ""), "law-block")

    st.divider()

    # -- Two-column: Plaintiff vs Defense --
    col_p, col_d = st.columns(2, gap="large")

    with col_p:
        st.markdown(
            '<div class="agent-label label-plaintiff">🟢 Plaintiff\'s Argument</div>',
            unsafe_allow_html=True,
        )
        _card(st.session_state["plaintiff_speech"], "plaintiff-card")

    with col_d:
        st.markdown(
            '<div class="agent-label label-defense">🔴 Defense\'s Rebuttal</div>',
            unsafe_allow_html=True,
        )
        _card(st.session_state["defense_rebuttal"], "defense-card")

    # -- Full-width: Judge's verdict --
    st.divider()
    st.markdown(
        '<div class="agent-label label-judge">⚖️ Judge\'s Verdict — IRAC Analysis</div>',
        unsafe_allow_html=True,
    )
    _card(st.session_state["judge_analysis"], "judge-card")

    # -- Sources section --
    source_cases = st.session_state.get("source_cases") or []
    if source_cases:
        st.divider()
        with st.expander("📎 Sources — Retrieved Precedents", expanded=False):
            st.markdown(
                '<div class="agent-label" style="color:#555;">🔗 CourtListener Precedents</div>',
                unsafe_allow_html=True,
            )
            for case in source_cases:
                name = case.get("name", "Unknown Case")
                url = case.get("url", "")
                cite_str = ", ".join(case.get("citations") or []) or "No citation"
                court = case.get("court", "")
                date = case.get("date", "")
                snippet = case.get("snippet", "")

                meta = " · ".join(filter(None, [cite_str, court, date]))
                st.markdown(
                    f"**[{_safe(name)}]({url})**  \n"
                    f"<small style='color:#666;'>{_safe(meta)}</small>",
                    unsafe_allow_html=True,
                )
                if snippet and snippet != "No excerpt available.":
                    st.caption(f'"{snippet}"')
                st.write("")
