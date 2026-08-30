"""The one import point every pipeline step and route uses for LLM calls.
Picks the active provider from LLM_PROVIDER (see app/config.py) and
re-exports its call_structured() under one name. Switching providers is a
one-line env var change - "anthropic" or "google" - never a code change.
"""

from app.config import settings
from app.llm.types import LlmCallResult, LlmOutputError  # noqa: F401 - re-exported for callers

if settings.llm_provider == "google":
    from app.llm.google_client import call_structured
else:
    from app.llm.anthropic_client import call_structured

__all__ = ["call_structured", "LlmCallResult", "LlmOutputError"]
