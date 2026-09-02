"""Lazy OpenSearch connection for Quick Search's BM25 leg - see
docker-compose.yml. Deliberately not touched anywhere in app/main.py's
startup: connecting here happens only when a Quick Search request actually
comes in, so a stopped/missing OpenSearch container never affects app
startup or any other route (/api/generate, auth, etc. are all untouched by
this module existing).
"""

from opensearchpy import OpenSearch

from app.config import settings

_INDEX_MAPPING = {
    "mappings": {
        "properties": {
            "text": {"type": "text"},  # BM25 is OpenSearch's default similarity for a "text" field
        }
    }
}

_client: OpenSearch | None = None


def get_client() -> OpenSearch:
    global _client
    if _client is None:
        _client = OpenSearch(hosts=[settings.opensearch_url], use_ssl=False, verify_certs=False)
    return _client


def ensure_index() -> None:
    """Creates the index with an explicit mapping if it doesn't exist yet.
    Safe to call every time - a no-op once the index is there."""
    client = get_client()
    if not client.indices.exists(index=settings.opensearch_index):
        client.indices.create(index=settings.opensearch_index, body=_INDEX_MAPPING)
