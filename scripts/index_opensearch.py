"""One-time (re-runnable) indexing script for Quick Search's BM25 leg. Run
after `docker compose up -d` and any time app/rag/seed_corpus.py changes -
idempotent, safe to run repeatedly.

Usage:
    .venv/Scripts/python.exe scripts/index_opensearch.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.search.indexing import index_corpus  # noqa: E402

if __name__ == "__main__":
    count = index_corpus()
    print(f"Indexed {count} chunks into OpenSearch.")
