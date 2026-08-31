from anthropic import APIError as AnthropicAPIError
from fastapi import APIRouter, Depends, HTTPException, status
from google.genai.errors import APIError as GoogleAPIError
from groq import APIError as GroqAPIError
from sqlmodel import Session

from app.agent.cache import get_cached_result, save_to_cache
from app.agent.pipeline import run_pipeline
from app.auth.deps import get_current_user
from app.db import get_session
from app.history.progress import get_progress, set_progress
from app.history.service import get_search_history, record_search
from app.llm.client import LlmOutputError
from app.models.user import User
from app.observability.logging_utils import log_event
from app.safety import REJECTION_MESSAGE, TopicUnsafeError, check_topic_safety
from app.schemas.generate import GenerateRequest
from app.schemas.pipeline import GenerateResult
from app.schemas.progress import ProgressResponse, ProgressUpdateRequest
from app.schemas.search_history import SearchHistoryResponse

router = APIRouter(prefix="/api", tags=["generate"])


@router.get("/health")
def health():
    # Deliberately unauthenticated: Render health checks and a cron
    # keep-alive ping need to hit this without a token.
    return {"status": "ok"}


@router.get("/search-history", response_model=SearchHistoryResponse)
def search_history(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    return get_search_history(current_user.id, session)


@router.get("/progress", response_model=ProgressResponse)
def progress(
    topic: str,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    return get_progress(current_user.id, topic, session)


@router.post("/progress", response_model=ProgressResponse)
def update_progress(
    payload: ProgressUpdateRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    return set_progress(current_user.id, payload.topic, payload.subtopic, payload.checked, session)


@router.post("/generate", response_model=GenerateResult)
def generate(
    payload: GenerateRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    # Safety guardrail runs first, before anything else - a rejected topic
    # must never be recorded in search history, never cached, and never
    # reach the pipeline. See app/safety.py for why this is the one step in
    # the whole app that fails closed instead of degrading gracefully.
    try:
        check_topic_safety(payload.topic)
    except TopicUnsafeError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, REJECTION_MESSAGE)

    # A search happened regardless of what follows - record it (and, only
    # for a genuinely new topic, categorize it via one small LLM call). This
    # is a nice-to-have side effect, not core to generating questions, so a
    # failure here (rate limit, provider hiccup) must never crash the whole
    # request - log it and move on.
    try:
        record_search(current_user.id, payload.topic, session)
    except Exception as e:
        log_event("search_history_record_failed", topic=payload.topic, error=str(e))

    # Shared cache, not per-user: the first person to ask about a topic pays
    # the LLM cost; everyone after that (any user) gets it for free.
    cached = get_cached_result(payload.topic, session)
    if cached is not None:
        return cached

    try:
        result = run_pipeline(payload.topic)
    except (AnthropicAPIError, GoogleAPIError) as e:
        # Bad/missing key, rate limit, provider outage, etc. - surfaced as a
        # distinct status so the frontend can tell "the LLM provider failed"
        # apart from "this app has a bug" (a bare 500).
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"LLM provider error: {e.message}") from e
    except GroqAPIError as e:
        # Groq's exceptions don't carry a .message attribute like the other
        # two SDKs - str(e) is what's available.
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"LLM provider error: {e}") from e
    except LlmOutputError as e:
        # The provider responded but never gave usable structured output
        # (refusal, or a parse failure that survived the wrapper's retry).
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"LLM output error: {e}") from e

    save_to_cache(payload.topic, result, session)
    return result
