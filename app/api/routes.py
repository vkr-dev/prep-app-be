from anthropic import APIError
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.agent.cache import get_cached_result, save_to_cache
from app.agent.pipeline import run_pipeline
from app.auth.deps import get_current_user
from app.db import get_session
from app.models.user import User
from app.schemas.generate import GenerateRequest
from app.schemas.pipeline import GenerateResult

router = APIRouter(prefix="/api", tags=["generate"])


@router.get("/health")
def health():
    # Deliberately unauthenticated: Render health checks and a cron
    # keep-alive ping need to hit this without a token.
    return {"status": "ok"}


@router.post("/generate", response_model=GenerateResult)
def generate(
    payload: GenerateRequest,
    _: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    # Shared cache, not per-user: the first person to ask about a topic pays
    # the LLM cost; everyone after that (any user) gets it for free.
    cached = get_cached_result(payload.topic, session)
    if cached is not None:
        return cached

    try:
        result = run_pipeline(payload.topic)
    except APIError as e:
        # Bad/missing key, rate limit, provider outage, etc. - surfaced as a
        # distinct status so the frontend can tell "the LLM provider failed"
        # apart from "this app has a bug" (a bare 500).
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"LLM provider error: {e.message}") from e

    save_to_cache(payload.topic, result, session)
    return result
