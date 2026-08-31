"""Shared datetime-serialization helper for any Pydantic response schema
exposing a naive UTC timestamp (this app stores every timestamp via
datetime.utcnow(), never timezone-aware) - see app/schemas/auth.py for the
full story on why this is necessary: serialized as-is, a naive datetime has
no timezone marker on the wire, and a browser's JS Date parser silently
treats that as LOCAL time rather than UTC, shifting the interpreted instant
by the viewer's own UTC offset. Confirmed live on this exact bug (a 1-hour
guest access window displaying as expiring 4 hours later than intended on
a UTC-4 machine).
"""

from datetime import datetime
from typing import Optional


def serialize_naive_utc(value: Optional[datetime]) -> Optional[str]:
    return None if value is None else value.isoformat() + "Z"
