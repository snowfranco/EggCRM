"""RAG pipeline tests (Project 4 Phase 0).

Two layers:
- Chunker tests are fully offline/deterministic (no model, no store) — they pin the P4-D4
  semantic-by-heading + metadata contract.
- Retrieval tests exercise the real embedder + ChromaDB store. They require an ingested store
  (`python -m novacrm_agent.rag.ingest`); if it's empty they skip rather than fail, so the fast
  chunker contract still runs in any environment.
"""

import pytest

from novacrm_agent.rag import store
from novacrm_agent.rag.chunker import Chunk, chunk_document, load_corpus
from novacrm_agent.rag.embedder import EMBED_DIM


# --- Chunker (offline, deterministic) ---------------------------------------
def test_corpus_chunks_have_required_metadata():
    chunks = load_corpus()
    assert chunks, "corpus produced no chunks"
    valid_types = {"feature_guide", "api_reference", "troubleshooting"}
    for c in chunks:
        assert isinstance(c, Chunk)
        assert c.text.strip()
        assert c.doc_title and c.section and c.source
        assert c.doc_type in valid_types, f"{c.source}: bad doc_type {c.doc_type!r}"


def test_chunk_ids_are_unique():
    chunks = load_corpus()
    ids = [c.chunk_id for c in chunks]
    assert len(ids) == len(set(ids)), "duplicate chunk_id"


def test_h1_title_dropped_sections_split_on_h2(tmp_path):
    doc = tmp_path / "sample.md"
    doc.write_text(
        "---\ndoc_title: Sample Doc\ndoc_type: feature_guide\n---\n\n"
        "# Sample Doc\n\n## First Section\nAlpha body.\n\n## Second Section\nBeta body.\n",
        encoding="utf-8",
    )
    chunks = chunk_document(doc)
    assert len(chunks) == 2
    assert [c.section for c in chunks] == ["First Section", "Second Section"]
    # H1 title line is dropped from chunk bodies; doc_title is carried in metadata instead.
    assert "# Sample Doc" not in chunks[0].text
    assert chunks[0].doc_title == "Sample Doc"
    assert "Alpha body." in chunks[0].text


# --- Retrieval (requires ingested store) ------------------------------------
def _store_ready() -> bool:
    try:
        return store.count(store.get_collection()) > 0
    except Exception:
        return False


needs_store = pytest.mark.skipif(
    not _store_ready(),
    reason="vector store empty — run `python -m novacrm_agent.rag.ingest` first",
)


@needs_store
def test_embedding_dimension():
    from novacrm_agent.rag.embedder import embed_query

    assert len(embed_query("test")) == EMBED_DIM


@needs_store
@pytest.mark.parametrize(
    "query,expected_doc",
    [
        ("How do I set up workflow automation?", "Workflow Automation"),
        ("Why is my dashboard slow in the morning?", "Dashboard Performance Troubleshooting"),
        ("How do I authenticate with the API?", "API Overview & Authentication"),
        ("Can I get a refund?", "Billing & Plan Changes Troubleshooting"),
    ],
)
def test_retrieval_surfaces_expected_doc(query, expected_doc):
    from novacrm_agent.rag.retriever import retrieve_docs

    hits = retrieve_docs(query, top_k=3)
    titles = {h["metadata"]["doc_title"] for h in hits}
    assert expected_doc in titles, f"{query!r} → {titles}"


@needs_store
def test_metadata_filter_restricts_doc_type():
    from novacrm_agent.rag.retriever import search_by_metadata

    hits = search_by_metadata("generate an api key", doc_type="api_reference", top_k=5)
    assert hits
    assert all(h["metadata"]["doc_type"] == "api_reference" for h in hits)


@needs_store
def test_zapier_tier_question_grounds_on_enterprise_only():
    """The tier matrix must be retrievable so the agent can correctly answer 'no, Enterprise-only'."""
    from novacrm_agent.rag.retriever import retrieve_docs

    hits = retrieve_docs("Is Zapier available on the Professional plan?", top_k=4)
    blob = " ".join(h["text"].lower() for h in hits)
    assert "enterprise" in blob and "zapier" in blob
