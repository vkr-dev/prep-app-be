"""Hybrid fusion: merges the BM25 and vector legs' hit lists into one
ranked list. Two methods, selectable per-request:

- Reciprocal Rank Fusion (RRF) - rank-based, not score-based, so it needs no
  normalization between BM25 scores (unbounded, corpus-frequency-dependent)
  and cosine-derived vector scores (bounded 0-1). The de facto standard for
  combining heterogeneous retrievers for exactly this reason.
- Weighted score fusion - normalizes each leg's scores to 0-1 within this
  result set, then combines by a tunable weight per leg. More directly
  "tunable" than RRF (whose only knob, k_const, has a much less intuitive
  effect), at the cost of being sensitive to how the scores were
  normalized.

Both take the same two Hit lists and produce one fused, deduplicated,
score-sorted list.
"""

from app.search.hit import Hit

RRF_K = 60  # standard default from the original RRF paper - dampens the impact of any single rank


def _merge(bm25_hits: list[Hit], vector_hits: list[Hit]) -> dict[str, Hit]:
    """Combines both lists into one dict keyed by id, carrying over
    whichever score(s) each leg actually contributed for that id."""
    merged: dict[str, Hit] = {}
    for hit in bm25_hits:
        merged[hit.id] = Hit(id=hit.id, text=hit.text, bm25_score=hit.bm25_score)
    for hit in vector_hits:
        if hit.id in merged:
            merged[hit.id].vector_score = hit.vector_score
        else:
            merged[hit.id] = Hit(id=hit.id, text=hit.text, vector_score=hit.vector_score)
    return merged


def reciprocal_rank_fusion(bm25_hits: list[Hit], vector_hits: list[Hit]) -> list[Hit]:
    merged = _merge(bm25_hits, vector_hits)
    bm25_rank = {hit.id: rank for rank, hit in enumerate(bm25_hits, start=1)}
    vector_rank = {hit.id: rank for rank, hit in enumerate(vector_hits, start=1)}

    for doc_id, hit in merged.items():
        score = 0.0
        if doc_id in bm25_rank:
            score += 1.0 / (RRF_K + bm25_rank[doc_id])
        if doc_id in vector_rank:
            score += 1.0 / (RRF_K + vector_rank[doc_id])
        hit.fused_score = score

    return sorted(merged.values(), key=lambda h: h.fused_score, reverse=True)


def weighted_fusion(bm25_hits: list[Hit], vector_hits: list[Hit], bm25_weight: float, vector_weight: float) -> list[Hit]:
    merged = _merge(bm25_hits, vector_hits)

    max_bm25 = max((h.bm25_score for h in bm25_hits), default=0.0) or 1.0
    max_vector = max((h.vector_score for h in vector_hits), default=0.0) or 1.0

    for hit in merged.values():
        normalized_bm25 = (hit.bm25_score / max_bm25) if hit.bm25_score is not None else 0.0
        normalized_vector = (hit.vector_score / max_vector) if hit.vector_score is not None else 0.0
        hit.fused_score = bm25_weight * normalized_bm25 + vector_weight * normalized_vector

    return sorted(merged.values(), key=lambda h: h.fused_score, reverse=True)
