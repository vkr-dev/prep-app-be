"""Quick Search - hybrid BM25 + vector search over the RAG seed corpus.
Entirely additive: a new router, included in app/main.py alongside the
existing ones, touching none of them. Requires OpenSearch running locally
(see docker-compose.yml) - if it isn't, these two endpoints fail with a 503
naming exactly what to do; every other route in the app is unaffected
either way, since nothing here runs at app startup.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from opensearchpy.exceptions import ConnectionError as OpenSearchConnectionError

from app.auth.deps import get_current_user
from app.models.user import User
from app.schemas.quick_search import QuickSearchEvalResponse, QuickSearchRequest, QuickSearchResponse
from app.search.service import run_quality_eval, run_quick_search

router = APIRouter(prefix="/api/quick-search", tags=["quick-search"])

_OPENSEARCH_DOWN_MESSAGE = (
    "OpenSearch is not reachable. Run `docker compose up -d` then "
    "`python scripts/index_opensearch.py` (see prep-app-be's README)."
)


@router.post("", response_model=QuickSearchResponse)
def quick_search(payload: QuickSearchRequest, _: User = Depends(get_current_user)):
    try:
        return run_quick_search(payload)
    except OpenSearchConnectionError:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, _OPENSEARCH_DOWN_MESSAGE)


@router.get("/eval", response_model=QuickSearchEvalResponse)
def quick_search_eval(
    k: int = 5,
    fusion_method: str = "rrf",
    bm25_weight: float = 0.5,
    vector_weight: float = 0.5,
    _: User = Depends(get_current_user),
):
    try:
        return run_quality_eval(k, fusion_method, bm25_weight, vector_weight)
    except OpenSearchConnectionError:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, _OPENSEARCH_DOWN_MESSAGE)
