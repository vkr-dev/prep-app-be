"""Shared topic cache: the first request for a topic runs the full LLM
pipeline and pays for it; every later request for the same topic (from any
user) is served straight from Postgres, at zero token cost.

Cache key is a normalized topic string - exact match only (case/whitespace
insensitive), not embedding-similarity fuzzy matching. "SQL" and "sql" hit
the same entry; "SQL" and "SQL joins" do not. That's a deliberate v1
simplification, not an oversight.
"""

import time

from sqlmodel import Session, select

from app.models.question_cache import QuestionSetCache
from app.schemas.pipeline import GenerateResult, RunMetrics
from app.topic_key import normalize_topic


def get_cached_result(topic: str, session: Session) -> GenerateResult | None:
    key = normalize_topic(topic)
    start = time.perf_counter()
    row = session.exec(select(QuestionSetCache).where(QuestionSetCache.topic_key == key)).first()
    latency_ms = round((time.perf_counter() - start) * 1000, 1)

    if row is None:
        return None

    # metrics reflect THIS request's real cost (a cheap DB lookup, zero
    # tokens) - never the original run's cost, which is irrelevant here.
    cache_metrics = RunMetrics(
        total_latency_ms=latency_ms,
        step_latencies_ms={"cache_lookup": latency_ms},
        total_input_tokens=0,
        total_output_tokens=0,
    )
    return GenerateResult.model_validate({**row.payload, "metrics": cache_metrics, "from_cache": True})


def save_to_cache(topic: str, result: GenerateResult, session: Session) -> None:
    key = normalize_topic(topic)
    payload = result.model_dump(mode="json", exclude={"metrics", "from_cache"})

    existing = session.exec(select(QuestionSetCache).where(QuestionSetCache.topic_key == key)).first()
    if existing:
        existing.payload = payload
        existing.topic = result.topic
    else:
        session.add(QuestionSetCache(topic_key=key, topic=result.topic, payload=payload))

    try:
        session.commit()
    except Exception:
        # Two concurrent first-time requests for the same new topic could
        # both miss the cache and both try to insert - fine either way,
        # whichever wins is just as good a cache entry.
        session.rollback()
