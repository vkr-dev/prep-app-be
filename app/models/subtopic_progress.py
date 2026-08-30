from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel, UniqueConstraint


class SubtopicProgress(SQLModel, table=True):
    """Per-user "I've reviewed this subtopic" checkbox state, driving the
    progress bar on the generate page. Tied to the user (like search
    history), keyed by topic + subtopic name (the Question.category field
    doubles as the subtopic name - see app/schemas/generate.py)."""

    __table_args__ = (UniqueConstraint("user_id", "topic_key", "subtopic", name="uq_subtopic_progress"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    topic_key: str = Field(index=True)
    subtopic: str
    checked: bool = Field(default=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
