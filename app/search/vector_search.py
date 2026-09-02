"""Vector retrieval leg of Quick Search - reuses the exact same Chroma
collection and embedding function the RAG pipeline already builds
(app/rag/corpus.py), so the "vector" leg of a hybrid search is over the
identical corpus the BM25 leg indexes (app/search/indexing.py). Raises if
the collection was never built (see app.rag.corpus.build_reference_index) -
the caller (app/search/service.py) is what decides how to degrade, unlike
the RAG pipeline's own use of this collection which always degrades to
empty since grounding is a nice-to-have there; here a failed vector leg is
user-visible search behavior, not silent grounding, so it's raised, not
swallowed."""

from app.rag.corpus import query_with_scores
from app.search.hit import Hit


def vector_search(query: str, k: int) -> list[Hit]:
    return [Hit(id=doc_id, text=text, vector_score=score) for doc_id, text, score in query_with_scores(query, k)]
