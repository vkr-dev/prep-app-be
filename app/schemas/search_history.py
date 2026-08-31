from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_serializer

from app.schemas.utc import serialize_naive_utc


class TopicLabelResult(BaseModel):
    """Output of the LLM categorization call - only made once per new topic
    (see app/history/labels.py)."""

    short_label: str = Field(description="2-3 word label for the topic, suitable for a button")
    category: str = Field(
        description=(
            "A short group name this topic belongs to. Reuse one of the provided "
            "existing categories if it genuinely fits; otherwise invent a new, concise one."
        )
    )


class SearchHistoryItem(BaseModel):
    topic: str
    short_label: str
    category: str
    last_searched_at: datetime

    # last_searched_at is a naive UTC datetime - see app/schemas/utc.py.
    @field_serializer("last_searched_at")
    def _serialize_last_searched_at(self, value: datetime) -> str:
        return serialize_naive_utc(value)


class SearchHistoryGroup(BaseModel):
    category: str
    items: list[SearchHistoryItem]


class SearchHistoryResponse(BaseModel):
    groups: list[SearchHistoryGroup]
