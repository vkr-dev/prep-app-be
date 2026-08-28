"""The one embedding primitive, shared by both of Chroma's jobs in this
project: retrieving reference chunks (corpus.py) and embedding generated
questions for near-duplicate detection (used by the agent's dedupe step and
the eval step).
"""

import numpy as np
from chromadb.utils import embedding_functions

# Local, free, no API key: a small ONNX model (all-MiniLM-L6-v2) running on
# CPU. Downloaded once and cached under ~/.cache/chroma. This is the "free
# step" side of the swappable-model design - retrieval/dedup never touches
# the paid Anthropic API.
embedding_fn = embedding_functions.DefaultEmbeddingFunction()


def embed_texts(texts: list[str]) -> np.ndarray:
    return np.array(embedding_fn(texts))


def cosine_similarity_matrix(vectors: np.ndarray) -> np.ndarray:
    """Symmetric NxN matrix; entry [i, j] is cosine similarity of row i, j."""
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    normalized = vectors / np.clip(norms, 1e-8, None)
    return normalized @ normalized.T
