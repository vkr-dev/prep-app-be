from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class TopicLabel(SQLModel, table=True):
    """AI-assigned short label + category for a topic - shared across all
    users, keyed by normalized topic, same pattern as QuestionSetCache.
    Computed once by the LLM the first time a topic is ever searched by
    anyone; every later search (any user, any casing/whitespace) reuses the
    stored row instead of asking the LLM again.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    topic_key: str = Field(unique=True, index=True)
    topic: str
    short_label: str  # 2-3 words, for a button
    category: str  # group name - reused across topics where the LLM judges they belong together
    created_at: datetime = Field(default_factory=datetime.utcnow)
