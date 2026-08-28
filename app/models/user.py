from datetime import datetime
from enum import Enum
from typing import Optional

from sqlmodel import Field, SQLModel


class UserStatus(str, Enum):
    owner = "owner"        # seeded from env, permanent, all-time access
    pending = "pending"    # registered, awaiting owner approval
    approved = "approved"  # inside a 1-hour access window (access_expires_at)
    revoked = "revoked"    # owner revoked; effective on next request


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    password_hash: str
    status: UserStatus = Field(default=UserStatus.pending)
    # None for owner (permanent) and for pending/revoked. Set to
    # approval_time + guest_access_window_hours when the owner approves.
    access_expires_at: Optional[datetime] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
