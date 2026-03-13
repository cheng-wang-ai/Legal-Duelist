"""
Legal knowledge base: loads statutes from knowledge_base.json and indexes them
in a FAISS vector store for semantic retrieval.

The formatted output includes verbatim statutory text so agents can quote it
directly without hallucinating statute content.
"""

import json
import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_google_genai import GoogleGenerativeAIEmbeddings

load_dotenv()

_KB_PATH = Path(__file__).parent / "knowledge_base.json"


def _load_statutes() -> list[dict]:
    with open(_KB_PATH, encoding="utf-8") as f:
        return json.load(f)


def _build_documents(statutes: list[dict]) -> list[Document]:
    """
    Build LangChain Documents for FAISS indexing.
    page_content combines all fields so semantic search captures full meaning.
    metadata preserves the raw statute dict for formatted output.
    """
    docs = []
    for s in statutes:
        content = (
            f"{s['citation']} — {s['title']} [{s['code']}]\n"
            f"{s['verbatim_text']}\n"
            f"Scope: {s['scope']}"
        )
        docs.append(Document(page_content=content, metadata=s))
    return docs


@lru_cache(maxsize=1)
def get_vector_store() -> FAISS:
    statutes = _load_statutes()
    documents = _build_documents(statutes)
    embeddings = GoogleGenerativeAIEmbeddings(
        model="models/gemini-embedding-001",
        google_api_key=os.getenv("LLM_API_KEY"),
    )
    return FAISS.from_documents(documents, embeddings)


def search_laws(query: str, k: int = 4) -> list[Document]:
    """Semantic search over the knowledge base. Returns top-k relevant statutes."""
    store = get_vector_store()
    return store.similarity_search(query, k=k)


def format_provided_context(docs: list[Document]) -> str:
    """
    Format retrieved statutes into a strict reference block.
    Includes verbatim text clearly labelled so agents can quote it exactly.
    """
    if not docs:
        return "NO STATUTES RETRIEVED — argue on general legal principles only."

    sections = []
    for i, doc in enumerate(docs, 1):
        s = doc.metadata
        sections.append(
            f"[{i}] {s['citation']} — {s['title']} ({s['code']})\n"
            f"    VERBATIM TEXT: \"{s['verbatim_text']}\"\n"
            f"    SCOPE: {s['scope']}"
        )
    return "\n\n".join(sections)
