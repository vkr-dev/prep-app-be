from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


class QuestionSetCache(SQLModel, table=True):
    """Shared, topic-keyed cache of generated question sets - not tied to
    any user. The first person to ask about a topic pays the LLM cost;
    everyone after that (any user) gets the stored result for free until the
    entry is manually cleared. Lives in the same Postgres/Neon instance as
    the User table - a plain JSON column, no separate store needed.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    # Normalized (lowercased, whitespace-collapsed) topic - the actual cache key.
    topic_key: str = Field(unique=True, index=True)
    # Original, as-typed topic from whichever request first created this entry.
    topic: str
    # topic/questions/eval from a GenerateResult - metrics are deliberately
    # excluded, since a cache hit's real cost is the lookup, not the
    # original generation.
    payload: dict = Field(sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow)
