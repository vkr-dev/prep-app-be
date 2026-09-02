"""BM25 keyword retrieval leg of Quick Search, via OpenSearch."""

from app.config import settings
from app.search.hit import Hit
from app.search.opensearch_client import get_client


def bm25_search(query: str, k: int) -> list[Hit]:
    client = get_client()
    response = client.search(
        index=settings.opensearch_index,
        body={"query": {"match": {"text": query}}, "size": k},
    )
    return [
        Hit(id=doc["_id"], text=doc["_source"]["text"], bm25_score=doc["_score"])
        for doc in response["hits"]["hits"]
    ]
