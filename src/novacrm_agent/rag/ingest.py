"""Ingest: corpus → chunks → embeddings → ChromaDB (P4 Phase 0).

Run:  python -m novacrm_agent.rag.ingest          # rebuild the store from the corpus
      python -m novacrm_agent.rag.ingest --stats  # just print what's currently stored

By default it resets the collection (clean rebuild) so the store always matches the corpus on
disk — deterministic, no stale chunks. Measure-before-proceeding: it prints a chunk/doc summary
so the Phase 1 retrieval baseline starts from a known, inspected index.
"""

from __future__ import annotations

import argparse
from collections import Counter

from . import store
from .chunker import load_corpus
from .embedder import embed_texts


def ingest() -> dict[str, int]:
    """Rebuild the vector store from the corpus. Returns a small summary."""
    chunks = load_corpus()
    if not chunks:
        raise SystemExit("No corpus chunks found — is data/knowledge_base/docs/ populated?")

    print(f"Chunked corpus → {len(chunks)} chunks.")
    by_type = Counter(c.doc_type for c in chunks)
    by_doc = Counter(c.doc_title for c in chunks)
    print(f"  doc_types: {dict(by_type)}")
    print(f"  documents: {len(by_doc)}")

    print(f"Embedding {len(chunks)} chunks with the local model (first call loads the model)...")
    embeddings = embed_texts([c.text for c in chunks])

    collection = store.reset_collection()
    store.add_chunks(
        collection,
        ids=[c.chunk_id for c in chunks],
        embeddings=embeddings,
        documents=[c.text for c in chunks],
        metadatas=[c.metadata for c in chunks],
    )
    stored = store.count(collection)
    print(f"Stored {stored} chunks in ChromaDB collection 'novacrm_docs'.")
    return {"chunks": len(chunks), "stored": stored, "documents": len(by_doc)}


def stats() -> None:
    collection = store.get_collection()
    print(f"Collection 'novacrm_docs' holds {store.count(collection)} chunks.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest the EggCRM doc corpus into ChromaDB.")
    parser.add_argument("--stats", action="store_true", help="print store stats and exit")
    args = parser.parse_args()
    if args.stats:
        stats()
    else:
        ingest()


if __name__ == "__main__":
    main()
