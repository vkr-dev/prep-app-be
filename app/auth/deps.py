from datetime import datetime

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import Session, select

from app.auth.security import decode_access_token
from app.db import get_session
from app.models.user import User, UserStatus

bearer_scheme = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    session: Session = Depends(get_session),
) -> User:
    """The guard: every protected route depends on this. A valid JWT only
    proves identity - it is the DB check below that actually grants access,
    which is what makes both exact 1-hour expiry and instant revoke possible
    (a pure stateless JWT could give neither)."""
    try:
        payload = decode_access_token(credentials.credentials)
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")

    user = session.exec(select(User).where(User.email == payload.get("sub"))).first()
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")

    if user.status == UserStatus.owner:
        return user  # permanent, all-time access - no expiry check

    if user.status != UserStatus.approved:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Access not approved")

    if user.access_expires_at is None or user.access_expires_at <= datetime.utcnow():
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Access expired")

    return user


def require_owner(user: User = Depends(get_current_user)) -> User:
    if user.status != UserStatus.owner:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Owner access required")
    return user
