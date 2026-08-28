from anthropic import APIError
from fastapi import APIRouter, Depends, HTTPException, status

from app.agent.pipeline import run_pipeline
from app.auth.deps import get_current_user
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
def generate(payload: GenerateRequest, _: User = Depends(get_current_user)):
    try:
        return run_pipeline(payload.topic)
    except APIError as e:
        # Bad/missing key, rate limit, provider outage, etc. - surfaced as a
        # distinct status so the frontend can tell "the LLM provider failed"
        # apart from "this app has a bug" (a bare 500).
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"LLM provider error: {e.message}") from e
