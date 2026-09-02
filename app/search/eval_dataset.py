"""A small, hand-labeled query -> relevant-chunk-ids set, judged by hand
against app/rag/seed_corpus.py's actual ids/text. This is what
app/search/metrics.py's NDCG@k/Precision@k/Recall@k are computed against -
either for one query typed by a user that happens to exactly match an entry
here (app/search/service.py's run_quick_search), or in aggregate across the
whole set (run_quality_eval, GET /api/quick-search/eval).

Kept intentionally small (a handful of queries) and covering a spread of
the corpus's real topic areas, not just one - this is a smoke-test-sized
labeled set for a personal project's evaluation harness, not a production
IR benchmark.
"""

EVAL_QUERIES: list[dict] = [
    {
        "query": "how do sql joins work",
        "relevant_ids": {"sql-joins"},
    },
    {
        "query": "why use a database index",
        "relevant_ids": {"sql-indexing"},
    },
    {
        "query": "python gil threading",
        "relevant_ids": {"python-gil"},
    },
    {
        "query": "big o notation runtime complexity",
        "relevant_ids": {"dsa-big-o"},
    },
    {
        "query": "hash table collisions",
        "relevant_ids": {"dsa-hash-tables"},
    },
    {
        "query": "load balancing strategies",
        "relevant_ids": {"sysdesign-load-balancing"},
    },
    {
        "query": "cap theorem consistency availability partition tolerance",
        "relevant_ids": {"sysdesign-cap-theorem"},
    },
    {
        "query": "tcp vs udp",
        "relevant_ids": {"networking-tcp-udp"},
    },
    {
        "query": "solid design principles",
        "relevant_ids": {"oop-solid"},
    },
    {
        "query": "how to store passwords securely",
        "relevant_ids": {"security-hashing"},
    },
]


def find_labeled_query(query: str) -> dict | None:
    """Exact match, case/whitespace-insensitive - deliberately not fuzzy, so
    eval metrics are only ever shown for a query that's actually labeled,
    never a guess."""
    normalized = query.strip().lower()
    for entry in EVAL_QUERIES:
        if entry["query"] == normalized:
            return entry
    return None
