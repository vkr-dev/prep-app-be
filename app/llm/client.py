"""The one import point every pipeline step and route uses for LLM calls.
Picks the active provider from LLM_PROVIDER (see app/config.py) and
re-exports its call_structured() under one name. Switching providers is a
one-line env var change - "1" (Anthropic), "2" (Google), or "3" (Groq) -
never a code change.
"""

from app.config import settings
from app.llm.types import LlmCallResult, LlmOutputError  # noqa: F401 - re-exported for callers

if settings.llm_provider == "2":
    from app.llm.google_client import call_structured
elif settings.llm_provider == "3":
    from app.llm.groq_client import call_structured
else:
    # "1", unset, or anything else - Anthropic is the confirmed default stack.
    from app.llm.anthropic_client import call_structured

__all__ = ["call_structured", "LlmCallResult", "LlmOutputError"]
