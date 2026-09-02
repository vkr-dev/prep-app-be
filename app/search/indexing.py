"""Indexing pipeline for Quick Search's BM25 leg: pushes the exact same
SEED_CORPUS the RAG pipeline already embeds into Chroma (app/rag/corpus.py)
into OpenSearch too - one corpus, two retrieval methods, so a hybrid search
result's "keyword" and "vector" contributions are always over the same
underlying documents. Run via scripts/index_opensearch.py, not on app
startup (see opensearch_client.py's docstring)."""

from opensearchpy.helpers import bulk

from app.config import settings
from app.observability.logging_utils import log_event
from app.rag.seed_corpus import SEED_CORPUS
from app.search.opensearch_client import ensure_index, get_client


def index_corpus() -> int:
    """Bulk-indexes every seed chunk, keyed by its existing id - idempotent,
    re-running just overwrites the same documents. Returns the count
    indexed."""
    ensure_index()
    client = get_client()

    actions = [
        {
            "_index": settings.opensearch_index,
            "_id": chunk["id"],
            "_source": {"text": chunk["text"]},
        }
        for chunk in SEED_CORPUS
    ]
    success_count, errors = bulk(client, actions, refresh=True)
    if errors:
        log_event("opensearch_index_errors", error_count=len(errors))
    log_event("opensearch_index_built", chunk_count=success_count)
    return success_count
