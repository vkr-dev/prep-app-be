from typing import Literal, Optional

from pydantic import BaseModel, Field


class RerankOrder(BaseModel):
    """LLM-rerank output shape (app/search/rerank.py) - only an ordering of
    indices, same pattern as the /api/generate pipeline's categorize step:
    the LLM never touches the actual result text, so it cannot rewrite or
    hallucinate content, only reorder what's already there."""

    ranked_indices: list[int] = Field(
        description="Indices into the given candidate list, reordered from most to least relevant to the query. Must include every index exactly once."
    )


class QuickSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=300)
    k: int = Field(default=5, ge=1, le=20)
    fusion_method: Literal["rrf", "weighted"] = "rrf"
    bm25_weight: float = Field(default=0.5, ge=0.0, le=1.0, description="Only used when fusion_method is 'weighted'.")
    vector_weight: float = Field(default=0.5, ge=0.0, le=1.0, description="Only used when fusion_method is 'weighted'.")
    use_llm_rerank: bool = False


class SearchResultItem(BaseModel):
    id: str
    snippet: str
    score: float
    methods: list[Literal["keyword", "vector"]]
    bm25_score: Optional[float] = None
    vector_score: Optional[float] = None


class QueryEvalMetrics(BaseModel):
    k: int
    ndcg_at_k: float
    precision_at_k: float
    recall_at_k: float


class QuickSearchMetrics(BaseModel):
    total_latency_ms: float
    bm25_hit_count: int
    vector_hit_count: int
    fusion_method: str
    reranked: bool
    # Only populated when the query exactly matches one of the small labeled
    # eval queries (app/search/eval_dataset.py) - most real queries won't
    # have ground truth to score against.
    eval: Optional[QueryEvalMetrics] = None


class QuickSearchResponse(BaseModel):
    results: list[SearchResultItem]
    metrics: QuickSearchMetrics


class LabeledQueryResult(BaseModel):
    query: str
    ndcg_at_k: float
    precision_at_k: float
    recall_at_k: float


class QuickSearchEvalResponse(BaseModel):
    k: int
    per_query: list[LabeledQueryResult]
    average_ndcg_at_k: float
    average_precision_at_k: float
    average_recall_at_k: float
