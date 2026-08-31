from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_serializer

from app.models.user import UserStatus
from app.schemas.utc import serialize_naive_utc


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserPublic(BaseModel):
    id: int
    email: str
    status: UserStatus
    access_expires_at: Optional[datetime]

    model_config = {"from_attributes": True}

    # access_expires_at is a naive UTC datetime (datetime.utcnow() + a
    # timedelta - see app/auth/routes.py's approve()) - see app/schemas/utc.py
    # for why this needs an explicit "Z" on the wire rather than serializing
    # the naive value as-is.
    @field_serializer("access_expires_at")
    def _serialize_access_expires_at(self, value: Optional[datetime]) -> Optional[str]:
        return serialize_naive_utc(value)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    status: UserStatus
    access_expires_at: Optional[datetime]

    @field_serializer("access_expires_at")
    def _serialize_access_expires_at(self, value: Optional[datetime]) -> Optional[str]:
        return serialize_naive_utc(value)
