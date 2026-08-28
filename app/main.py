from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select

from app.api.routes import router as api_router
from app.auth.routes import router as auth_router
from app.config import settings
from app.db import engine, init_db
from app.models.user import User, UserStatus
from app.observability.logging_utils import configure_json_logging
from app.rag.corpus import build_reference_index


def bootstrap_owner() -> None:
    """Seed the owner account from env on every startup. Idempotent - does
    nothing once the row exists. This is what makes the whole app testable
    behind login immediately, before any guest ever registers."""
    with Session(engine) as session:
        existing = session.exec(select(User).where(User.email == settings.owner_email)).first()
        if existing is None:
            owner = User(
                email=settings.owner_email,
                password_hash=settings.owner_password_hash,
                status=UserStatus.owner,
                access_expires_at=None,
            )
            session.add(owner)
            session.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_json_logging()
    init_db()
    bootstrap_owner()
    build_reference_index()  # Chroma is ephemeral - rebuild from the seed corpus every startup
    yield


app = FastAPI(title="Interview Prep Question Generator", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(api_router)
