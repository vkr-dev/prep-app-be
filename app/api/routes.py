from fastapi import APIRouter, Depends

from app.auth.deps import get_current_user
from app.llm.anthropic_client import generate_questions
from app.models.user import User
from app.schemas.generate import GenerateRequest, GeneratedQuestionSet

router = APIRouter(prefix="/api", tags=["generate"])


@router.get("/health")
def health():
    # Deliberately unauthenticated: Render health checks and a cron
    # keep-alive ping need to hit this without a token.
    return {"status": "ok"}


@router.post("/generate", response_model=GeneratedQuestionSet)
def generate(payload: GenerateRequest, _: User = Depends(get_current_user)):
    return generate_questions(payload.topic)
