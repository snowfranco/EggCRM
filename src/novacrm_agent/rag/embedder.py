"""Local embedding model (P4-D2).

`sentence-transformers/all-MiniLM-L6-v2` — 384-dim, CPU-fast, zero-cost, offline. We compute
embeddings in *our* code and hand them to Chroma explicitly (rather than letting Chroma call its
own default embedding function), so the embedding step stays inspectable and swappable: the
P4-D2 revisit gate ("switch to a hosted model only if Phase 3 retrieval quality is poor") is a
one-module change here.

The model is loaded lazily and cached — the first call pays the load cost, subsequent calls reuse it.
"""

from __future__ import annotations

from functools import lru_cache

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
EMBED_DIM = 384


@lru_cache(maxsize=1)
def _model():
    # Imported lazily so that importing this module (e.g. for the dataclass/constants) does not
    # pull in torch + the model until an embedding is actually needed.
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(MODEL_NAME)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts → list of 384-dim float vectors."""
    if not texts:
        return []
    vectors = _model().encode(
        texts,
        normalize_embeddings=True,  # unit vectors → cosine space behaves well
        convert_to_numpy=True,
        show_progress_bar=False,
    )
    return [v.tolist() for v in vectors]


def embed_query(text: str) -> list[float]:
    """Embed a single query string → one 384-dim float vector."""
    return embed_texts([text])[0]
