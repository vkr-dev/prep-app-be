"""Orchestrates one Quick Search request: BM25 leg + vector leg -> fusion ->
optional LLM rerank -> response, plus the separate whole-labeled-set quality
evaluation. This is the one module app/api/quick_search_routes.py calls
into - everything else in app/search/ is a building block this wires
together.
"""

import time

from app.schemas.quick_search import (
    LabeledQueryResult,
    QueryEvalMetrics,
    QuickSearchEvalResponse,
    QuickSearchMetrics,
    QuickSearchRequest,
    QuickSearchResponse,
    SearchResultItem,
)
from app.search.eval_dataset import EVAL_QUERIES, find_labeled_query
from app.search.fusion import reciprocal_rank_fusion, weighted_fusion
from app.search.hit import Hit
from app.search.keyword_search import bm25_search
from app.search.metrics import ndcg_at_k, precision_at_k, recall_at_k
from app.search.rerank import llm_rerank
from app.search.vector_search import vector_search

# Retrieve more candidates per leg than the final k requested, so fusion has
# real overlap/ranking signal to work with instead of two near-disjoint
# lists of exactly k each.
CANDIDATE_POOL_MULTIPLIER = 3


def _fuse(request: QuickSearchRequest, bm25_hits: list[Hit], vector_hits: list[Hit]) -> list[Hit]:
    if request.fusion_method == "weighted":
        return weighted_fusion(bm25_hits, vector_hits, request.bm25_weight, request.vector_weight)
    return reciprocal_rank_fusion(bm25_hits, vector_hits)


def _to_result_item(hit: Hit) -> SearchResultItem:
    methods: list[str] = []
    if hit.bm25_score is not None:
        methods.append("keyword")
    if hit.vector_score is not None:
        methods.append("vector")
    return SearchResultItem(
        id=hit.id,
        snippet=hit.text,
        score=round(hit.fused_score, 4),
        methods=methods,
        bm25_score=round(hit.bm25_score, 4) if hit.bm25_score is not None else None,
        vector_score=round(hit.vector_score, 4) if hit.vector_score is not None else None,
    )


def run_quick_search(request: QuickSearchRequest) -> QuickSearchResponse:
    start = time.perf_counter()
    pool_size = request.k * CANDIDATE_POOL_MULTIPLIER

    bm25_hits = bm25_search(request.query, pool_size)
    vector_hits = vector_search(request.query, pool_size)

    fused = _fuse(request, bm25_hits, vector_hits)
    top = fused[: request.k]

    if request.use_llm_rerank:
        top = llm_rerank(request.query, top)

    eval_metrics = None
    labeled = find_labeled_query(request.query)
    if labeled is not None:
        ranked_ids = [hit.id for hit in top]
        eval_metrics = QueryEvalMetrics(
            k=request.k,
            ndcg_at_k=round(ndcg_at_k(ranked_ids, labeled["relevant_ids"], request.k), 4),
            precision_at_k=round(precision_at_k(ranked_ids, labeled["relevant_ids"], request.k), 4),
            recall_at_k=round(recall_at_k(ranked_ids, labeled["relevant_ids"], request.k), 4),
        )

    total_latency_ms = (time.perf_counter() - start) * 1000

    return QuickSearchResponse(
        results=[_to_result_item(hit) for hit in top],
        metrics=QuickSearchMetrics(
            total_latency_ms=round(total_latency_ms, 1),
            bm25_hit_count=len(bm25_hits),
            vector_hit_count=len(vector_hits),
            fusion_method=request.fusion_method,
            reranked=request.use_llm_rerank,
            eval=eval_metrics,
        ),
    )


def run_quality_eval(k: int, fusion_method: str, bm25_weight: float, vector_weight: float) -> QuickSearchEvalResponse:
    """Runs every labeled query in EVAL_QUERIES through the same search path
    a real request takes (no LLM rerank - this measures the retrieval/fusion
    quality itself, not rerank's added latency/cost) and reports
    per-query plus averaged NDCG@k/Precision@k/Recall@k."""
    per_query: list[LabeledQueryResult] = []

    for entry in EVAL_QUERIES:
        request = QuickSearchRequest(
            query=entry["query"],
            k=k,
            fusion_method=fusion_method,
            bm25_weight=bm25_weight,
            vector_weight=vector_weight,
            use_llm_rerank=False,
        )
        result = run_quick_search(request)
        assert result.metrics.eval is not None  # every EVAL_QUERIES entry is, by definition, labeled
        per_query.append(
            LabeledQueryResult(
                query=entry["query"],
                ndcg_at_k=result.metrics.eval.ndcg_at_k,
                precision_at_k=result.metrics.eval.precision_at_k,
                recall_at_k=result.metrics.eval.recall_at_k,
            )
        )

    count = len(per_query) or 1
    return QuickSearchEvalResponse(
        k=k,
        per_query=per_query,
        average_ndcg_at_k=round(sum(q.ndcg_at_k for q in per_query) / count, 4),
        average_precision_at_k=round(sum(q.precision_at_k for q in per_query) / count, 4),
        average_recall_at_k=round(sum(q.recall_at_k for q in per_query) / count, 4),
    )
