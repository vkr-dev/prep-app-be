"""Standard IR ranking metrics, computed against a set of known-relevant
ids (app/search/eval_dataset.py). Pure functions, no I/O - given a ranked
list of ids and the set of ids that are actually relevant, score the top k.
"""

import math


def precision_at_k(ranked_ids: list[str], relevant_ids: set[str], k: int) -> float:
    top_k = ranked_ids[:k]
    if not top_k:
        return 0.0
    hits = sum(1 for doc_id in top_k if doc_id in relevant_ids)
    return hits / len(top_k)


def recall_at_k(ranked_ids: list[str], relevant_ids: set[str], k: int) -> float:
    if not relevant_ids:
        return 0.0
    top_k = ranked_ids[:k]
    hits = sum(1 for doc_id in top_k if doc_id in relevant_ids)
    return hits / len(relevant_ids)


def ndcg_at_k(ranked_ids: list[str], relevant_ids: set[str], k: int) -> float:
    """Binary relevance (in the labeled set or not) - gain is 1 for a
    relevant id at that rank, 0 otherwise, discounted by log2(rank + 1)."""
    top_k = ranked_ids[:k]

    dcg = sum(1.0 / math.log2(i + 2) for i, doc_id in enumerate(top_k) if doc_id in relevant_ids)

    ideal_hits = min(len(relevant_ids), k)
    idcg = sum(1.0 / math.log2(i + 2) for i in range(ideal_hits))

    return (dcg / idcg) if idcg > 0 else 0.0
