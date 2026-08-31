from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.auth.deps import require_owner
from app.auth.security import create_access_token, hash_password, verify_password
from app.config import settings
from app.db import get_session
from app.models.user import User, UserStatus
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserPublic

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, session: Session = Depends(get_session)):
    """No email verification by design - the owner approves everyone manually,
    so email is just a label. Registering only creates a pending account."""
    existing = session.exec(select(User).where(User.email == payload.email)).first()
    if existing is not None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Email already registered")

    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        status=UserStatus.pending,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, session: Session = Depends(get_session)):
    """Login always succeeds for a valid password, regardless of status - the
    token it returns just won't pass the guard until the owner approves."""
    user = session.exec(select(User).where(User.email == payload.email)).first()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")

    return TokenResponse(
        access_token=create_access_token(subject=user.email),
        status=user.status,
        access_expires_at=user.access_expires_at,
    )


@router.get("/pending", response_model=list[UserPublic])
def list_pending(_: User = Depends(require_owner), session: Session = Depends(get_session)):
    return session.exec(select(User).where(User.status == UserStatus.pending)).all()


@router.get("/users", response_model=list[UserPublic])
def list_users(_: User = Depends(require_owner), session: Session = Depends(get_session)):
    """Every account except the owner's own, newest-first - what the admin
    page's approve/revoke UI is actually built on. /pending above still
    exists as a narrower, single-purpose listing; this is the one the
    frontend uses so a single page can show pending AND already-approved
    accounts (needed to expose revoke, not just approve) in one place."""
    return session.exec(
        select(User).where(User.status != UserStatus.owner).order_by(User.created_at.desc())
    ).all()


@router.post("/approve/{user_id}", response_model=UserPublic)
def approve(user_id: int, _: User = Depends(require_owner), session: Session = Depends(get_session)):
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    # Clock starts at approval time, not first login.
    user.status = UserStatus.approved
    user.access_expires_at = datetime.utcnow() + timedelta(hours=settings.guest_access_window_hours)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@router.post("/revoke/{user_id}", response_model=UserPublic)
def revoke(user_id: int, _: User = Depends(require_owner), session: Session = Depends(get_session)):
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    # Effective on the user's very next request: the guard re-checks the DB
    # every time rather than trusting anything cached in the JWT.
    user.status = UserStatus.revoked
    user.access_expires_at = None
    session.add(user)
    session.commit()
    session.refresh(user)
    return user
