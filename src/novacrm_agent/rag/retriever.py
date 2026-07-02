"""Query-time retrieval (P4-D4 — vector similarity + optional metadata filter).

This is the read side the RAG agent's tools will call in Phase 1. Two retrieval entry points,
the "both defenses" of P4-D4:

  retrieve_docs(query, top_k)                  — pure vector similarity.
  search_by_metadata(query, doc_type, top_k)   — vector similarity *within* a doc_type filter.

Both return plain dicts so the agent layer never imports Chroma.
"""

from __future__ import annotations

from typing import Any

from . import store
from .embedder import embed_query


def retrieve_docs(query: str, top_k: int = 5) -> list[dict[str, Any]]:
    """Top-k most similar chunks to `query` across the whole corpus."""
    if not query.strip():
        return []
    collection = store.get_collection()
    return store.query(collection, embed_query(query), top_k=top_k)


def search_by_metadata(
    query: str,
    doc_type: str | None = None,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """Top-k similar chunks restricted to a doc_type (feature_guide/api_reference/troubleshooting)."""
    if not query.strip():
        return []
    where = {"doc_type": doc_type} if doc_type else None
    collection = store.get_collection()
    return store.query(collection, embed_query(query), top_k=top_k, where=where)


def format_hits(hits: list[dict[str, Any]]) -> str:
    """Render hits as readable text for an agent prompt / CLI inspection."""
    if not hits:
        return "No matching documentation found."
    blocks = []
    for h in hits:
        meta = h["metadata"]
        blocks.append(
            f"[{meta['doc_title']} › {meta['section']}] (score {h['score']:.2f})\n{h['text']}"
        )
    return "\n\n".join(blocks)
