"""Shared internal hit type passed between keyword_search, vector_search,
fusion, and rerank - one shape, so fusion doesn't need to know which leg(s)
produced a candidate."""

from dataclasses import dataclass


@dataclass
class Hit:
    id: str
    text: str
    bm25_score: float | None = None
    vector_score: float | None = None
    fused_score: float = 0.0
