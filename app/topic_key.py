"""Shared topic normalization - the cache key logic used by both the shared
question-set cache (app/agent/cache.py) and search history / topic labels
(app/history/). Kept in one place so a topic always maps to the same key
everywhere in the app.
"""

import re


def normalize_topic(topic: str) -> str:
    return re.sub(r"\s+", " ", topic.strip().lower())
