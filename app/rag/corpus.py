"""RAG use #1: retrieve reference chunks to ground question generation.

Chroma runs ephemeral (in-memory) here by design - see context.md. There's
nothing to persist: the index is small and cheap enough to rebuild from
SEED_CORPUS on every startup.
"""

import chromadb

from app.observability.logging_utils import log_event
from app.rag.embeddings import embedding_fn
from app.rag.seed_corpus import SEED_CORPUS

_COLLECTION_NAME = "reference_corpus"
_client = chromadb.EphemeralClient()


def build_reference_index() -> None:
    """Rebuild the reference collection from the seed corpus. Call once at
    app startup."""
    existing = {c.name for c in _client.list_collections()}
    if _COLLECTION_NAME in existing:
        _client.delete_collection(_COLLECTION_NAME)

    collection = _client.create_collection(_COLLECTION_NAME, embedding_function=embedding_fn)
    collection.add(
        ids=[chunk["id"] for chunk in SEED_CORPUS],
        documents=[chunk["text"] for chunk in SEED_CORPUS],
    )
    log_event("rag_index_built", chunk_count=len(SEED_CORPUS))


def retrieve_reference_chunks(topic: str, k: int = 4) -> list[str]:
    """Nearest-neighbor lookup by embedding similarity - no keyword
    matching, so loosely-phrased topics still surface relevant chunks."""
    collection = _client.get_collection(_COLLECTION_NAME, embedding_function=embedding_fn)
    result = collection.query(query_texts=[topic], n_results=k)
    documents = result.get("documents") or []
    return documents[0] if documents else []
