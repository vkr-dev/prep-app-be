from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel, UniqueConstraint


class SearchHistory(SQLModel, table=True):
    """One row per (user, topic) - tied to the user, unlike TopicLabel and
    the question cache which are shared. Re-searching the same topic bumps
    last_searched_at rather than creating a duplicate row, so the home
    page's past-searches list shows one button per topic, most-recent first.
    """

    __table_args__ = (UniqueConstraint("user_id", "topic_key", name="uq_search_history_user_topic"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    topic_key: str = Field(index=True)
    last_searched_at: datetime = Field(default_factory=datetime.utcnow)
