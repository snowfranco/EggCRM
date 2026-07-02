"""ChromaDB vector store wrapper (P4-D1).

One thin module owns all Chroma contact so swapping to a production store later is a single-file
change (the P4-D1 trade-off rationale). The collection holds precomputed embeddings (from
rag.embedder) plus per-chunk metadata (from rag.chunker) and uses cosine distance.

Persisted to data/rag_store/ (gitignored — rebuilt by `python -m novacrm_agent.rag.ingest`).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

_STORE_DIR = Path(__file__).resolve().parents[3] / "data" / "rag_store"
_COLLECTION = "novacrm_docs"


def _client():
    import chromadb
    from chromadb.config import Settings

    _STORE_DIR.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(
        path=str(_STORE_DIR),
        settings=Settings(anonymized_telemetry=False, allow_reset=True),
    )


def get_collection():
    """Get-or-create the docs collection (cosine space)."""
    return _client().get_or_create_collection(
        name=_COLLECTION,
        metadata={"hnsw:space": "cosine"},
    )


def reset_collection():
    """Drop and recreate the collection — a clean slate for a fresh ingest."""
    client = _client()
    try:
        client.delete_collection(_COLLECTION)
    except Exception:
        pass  # not present yet — fine
    return client.get_or_create_collection(
        name=_COLLECTION,
        metadata={"hnsw:space": "cosine"},
    )


def add_chunks(
    collection,
    ids: list[str],
    embeddings: list[list[float]],
    documents: list[str],
    metadatas: list[dict[str, Any]],
) -> None:
    """Upsert chunks (id + embedding + text + metadata) into the collection."""
    if not ids:
        return
    collection.upsert(
        ids=ids,
        embeddings=embeddings,
        documents=documents,
        metadatas=metadatas,
    )


def query(
    collection,
    query_embedding: list[float],
    top_k: int = 5,
    where: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Vector search; optional `where` metadata filter (the P4-D4 second defense).

    Returns a list of {chunk_id, text, metadata, distance, score} ordered best-first.
    """
    result = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        where=where or None,
        include=["documents", "metadatas", "distances"],
    )
    ids = result.get("ids", [[]])[0]
    docs = result.get("documents", [[]])[0]
    metas = result.get("metadatas", [[]])[0]
    dists = result.get("distances", [[]])[0]

    hits: list[dict[str, Any]] = []
    for cid, doc, meta, dist in zip(ids, docs, metas, dists):
        hits.append(
            {
                "chunk_id": cid,
                "text": doc,
                "metadata": meta,
                "distance": dist,
                "score": 1.0 - dist,  # cosine distance → similarity
            }
        )
    return hits


def count(collection) -> int:
    return collection.count()
