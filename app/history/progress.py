"""Per-user subtopic review progress - the checkbox state behind the
generate page's progress bar. Lives alongside search history (same "tied to
the user" nature) but is its own table since it tracks a different thing:
not "did they search this" but "did they mark this subtopic reviewed."
"""

from datetime import datetime

from sqlmodel import Session, select

from app.models.subtopic_progress import SubtopicProgress
from app.schemas.progress import ProgressResponse
from app.topic_key import normalize_topic


def get_progress(user_id: int, topic: str, session: Session) -> ProgressResponse:
    key = normalize_topic(topic)
    rows = session.exec(
        select(SubtopicProgress).where(SubtopicProgress.user_id == user_id, SubtopicProgress.topic_key == key)
    ).all()
    return ProgressResponse(progress={row.subtopic: row.checked for row in rows})


def set_progress(user_id: int, topic: str, subtopic: str, checked: bool, session: Session) -> ProgressResponse:
    key = normalize_topic(topic)
    existing = session.exec(
        select(SubtopicProgress).where(
            SubtopicProgress.user_id == user_id,
            SubtopicProgress.topic_key == key,
            SubtopicProgress.subtopic == subtopic,
        )
    ).first()

    if existing is not None:
        existing.checked = checked
        existing.updated_at = datetime.utcnow()
        session.add(existing)
    else:
        session.add(SubtopicProgress(user_id=user_id, topic_key=key, subtopic=subtopic, checked=checked))
    session.commit()

    return get_progress(user_id, topic, session)
