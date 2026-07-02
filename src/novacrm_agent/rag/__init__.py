"""Hand-built RAG pipeline for Project 4 (P4-D1, D2, D4).

Framework-free by deliberate choice (P4-D7 keeps the *pipeline* hand-built; ADK is used
only for the multi-agent layer later). The pieces:

  chunker   — parse the markdown corpus into semantic, heading-bounded chunks + metadata.
  embedder  — local sentence-transformers (all-MiniLM-L6-v2) embeddings.
  store     — thin wrapper over a persistent ChromaDB collection.
  ingest    — corpus → chunks → embeddings → store (CLI: python -m novacrm_agent.rag.ingest).
  retriever — query-time vector search (+ optional metadata filter, the second defense).
"""

from __future__ import annotations
