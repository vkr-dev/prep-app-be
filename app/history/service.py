"""Per-user search history, backed by a shared, DB-persisted topic
categorization: the LLM labels a topic (short button text + a group name)
only the first time anyone ever searches it; every later search of that
topic - by any user - reuses the stored label instead of calling the LLM
again. New topics are shown the full list of existing categories so the
LLM reuses one where it genuinely fits, instead of inventing near-duplicate
group names ("Java" vs "Java Programming") over time.
"""

from datetime import datetime

from sqlmodel import Session, select

from app.llm.client import call_structured
from app.models.search_history import SearchHistory
from app.models.topic_label import TopicLabel
from app.observability.logging_utils import log_event
from app.schemas.search_history import (
    SearchHistoryGroup,
    SearchHistoryItem,
    SearchHistoryResponse,
    TopicLabelResult,
)
from app.topic_key import normalize_topic

_FALLBACK_CATEGORY = "Uncategorized"


def _fallback_label(topic: str, key: str) -> TopicLabel:
    """A topic gets this heuristic label when the LLM categorization call
    fails, instead of losing the search entirely (see record_search) - a
    plain title-cased truncation of the topic itself, grouped into a
    catch-all category. Never touches the LLM, so it can't fail the way the
    real categorization call can."""
    words = topic.strip().split()
    short_label = " ".join(words[:3]).title()[:24] or topic[:24]
    return TopicLabel(topic_key=key, topic=topic, short_label=short_label, category=_FALLBACK_CATEGORY)


def get_or_create_topic_label(topic: str, session: Session) -> TopicLabel:
    key = normalize_topic(topic)
    existing = session.exec(select(TopicLabel).where(TopicLabel.topic_key == key)).first()
    if existing is not None:
        return existing

    existing_categories = sorted({row for row in session.exec(select(TopicLabel.category)).all()})
    system = (
        "You categorize technical interview-prep search topics. Given a topic, "
        "produce a short 2-3 word label suitable for a UI button, and assign it "
        "to a category (group name). Reuse one of the provided existing "
        "categories if the topic genuinely belongs there (match by meaning, not "
        "exact wording); only invent a new category if none fit."
    )
    categories_block = ", ".join(existing_categories) if existing_categories else "(none yet - this is the first topic)"
    user_message = f"Topic: {topic}\n\nExisting categories: {categories_block}"

    # This LLM call is a nice-to-have (a tidy button label + grouping), not
    # something the search itself should ever depend on - degrade to a
    # heuristic label rather than raise, so a flaky/rate-limited provider
    # can never prevent record_search() below from actually saving the
    # search. Confirmed live: this used to silently drop every new topic's
    # search history whenever categorization failed (Groq structured-output
    # errors), since the exception propagated out of record_search entirely
    # before the SearchHistory row was ever written.
    try:
        result = call_structured(system, user_message, TopicLabelResult, max_tokens=200)
        label = TopicLabel(
            topic_key=key,
            topic=topic,
            short_label=result.parsed.short_label,
            category=result.parsed.category,
        )
    except Exception as e:
        log_event("topic_label_generation_failed", topic=topic, error=str(e))
        label = _fallback_label(topic, key)

    session.add(label)
    try:
        session.commit()
    except Exception:
        # Two concurrent first-time searches of the same new topic - fine
        # either way, re-fetch whichever won.
        session.rollback()
        existing = session.exec(select(TopicLabel).where(TopicLabel.topic_key == key)).first()
        if existing is not None:
            return existing
        raise
    session.refresh(label)
    return label


def record_search(user_id: int, topic: str, session: Session) -> None:
    """Called on every /api/generate request, regardless of cache hit or
    pipeline outcome - a search happened, so it belongs in history."""
    label = get_or_create_topic_label(topic, session)

    existing = session.exec(
        select(SearchHistory).where(
            SearchHistory.user_id == user_id,
            SearchHistory.topic_key == label.topic_key,
        )
    ).first()

    if existing is not None:
        existing.last_searched_at = datetime.utcnow()
        session.add(existing)
    else:
        session.add(SearchHistory(user_id=user_id, topic_key=label.topic_key, last_searched_at=datetime.utcnow()))

    try:
        session.commit()
    except Exception:
        session.rollback()


def get_search_history(user_id: int, session: Session) -> SearchHistoryResponse:
    rows = session.exec(
        select(SearchHistory, TopicLabel)
        .where(SearchHistory.user_id == user_id, SearchHistory.topic_key == TopicLabel.topic_key)
        .order_by(SearchHistory.last_searched_at.desc())
    ).all()

    groups: dict[str, list[SearchHistoryItem]] = {}
    group_order: list[str] = []
    for history, label in rows:
        item = SearchHistoryItem(
            topic=label.topic,
            short_label=label.short_label,
            category=label.category,
            last_searched_at=history.last_searched_at,
        )
        if label.category not in groups:
            groups[label.category] = []
            group_order.append(label.category)
        groups[label.category].append(item)

    # Rows arrived most-recent-first, so both group_order (first appearance
    # of each category) and each group's items are already in the right
    # order - most recently active category first, most recent search
    # within it first.
    return SearchHistoryResponse(groups=[SearchHistoryGroup(category=c, items=groups[c]) for c in group_order])
