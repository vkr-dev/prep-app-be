"""The one embedding primitive, shared by both of Chroma's jobs in this
project: retrieving reference chunks (corpus.py) and embedding generated
questions for near-duplicate detection (used by the agent's dedupe step and
the eval step).

Uses Google's embedding API rather than a locally-loaded model. A local
model (Chroma's default embedding function, an ONNX build of
all-MiniLM-L6-v2) needs onnxruntime plus the loaded model weights in
memory - comfortably 150-400MB - which alone blew past Render free tier's
512MB cap during startup (confirmed live: "Out of memory (used over
512Mi)" before the server could even bind a port). An API call trades a
little latency for a dramatically smaller memory footprint, the right
tradeoff for a free-tier deploy.

This makes GOOGLE_API_KEY required for RAG/dedup regardless of which
LLM_PROVIDER handles question generation - Anthropic has no first-party
embeddings endpoint, so Google is the only free API-based embedding option
in this stack either way.
"""

import numpy as np
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings
from google import genai

from app.config import settings

_client = genai.Client(api_key=settings.google_api_key)
_EMBED_MODEL = "gemini-embedding-2"


def embed_texts(texts: list[str]) -> np.ndarray:
    """One API call per text - gemini-embedding-2 aggregates multiple
    strings passed in a single call into one combined vector, which is not
    what retrieval/dedup need (one independent vector per text)."""
    vectors = [
        _client.models.embed_content(model=_EMBED_MODEL, contents=text).embeddings[0].values
        for text in texts
    ]
    return np.array(vectors)


class GoogleEmbeddingFunction(EmbeddingFunction[Documents]):
    """Chroma's EmbeddingFunction is a runtime-checkable Protocol, but it
    isn't just __call__ - Chroma also calls .name() (and, for persisted
    collections, .get_config()/.build_from_config()) to validate a
    collection's embedding function hasn't silently changed between calls.
    Subclassing the real base class gives us those for free where we don't
    need custom behavior."""

    def __init__(self) -> None:
        pass

    def __call__(self, input: Documents) -> Embeddings:
        return embed_texts(list(input)).tolist()

    @staticmethod
    def name() -> str:
        return "google-gemini-embedding"

    def get_config(self) -> dict:
        return {"model": _EMBED_MODEL}

    @staticmethod
    def build_from_config(config: dict) -> "GoogleEmbeddingFunction":
        return GoogleEmbeddingFunction()


embedding_fn = GoogleEmbeddingFunction()


def cosine_similarity_matrix(vectors: np.ndarray) -> np.ndarray:
    """Symmetric NxN matrix; entry [i, j] is cosine similarity of row i, j."""
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    normalized = vectors / np.clip(norms, 1e-8, None)
    return normalized @ normalized.T
