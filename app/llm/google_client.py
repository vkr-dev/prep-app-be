"""Google Gemini implementation of call_structured() - the free/cheap swap-in
slot from context.md. Selected when LLM_PROVIDER=google - see
app/llm/client.py for how the active provider is chosen. Same interface as
anthropic_client.py (same LlmCallResult, same LlmOutputError), so every
pipeline step works unchanged regardless of which provider is active.
"""

import time
from typing import TypeVar

from google import genai
from google.genai import types
from pydantic import BaseModel

from app.config import settings
from app.llm.types import LlmCallResult, LlmOutputError

_client = genai.Client(api_key=settings.google_api_key)

T = TypeVar("T", bound=BaseModel)

MAX_ATTEMPTS = 2

# finish_reasons that mean "blocked", not "ran out of room" - retrying the
# identical prompt won't change a safety/policy decision, so fail fast
# instead of burning the retry budget (mirrors Anthropic's "refusal").
BLOCKED_FINISH_REASONS = {"SAFETY", "PROHIBITED_CONTENT", "RECITATION", "BLOCKLIST", "SPII"}


def call_structured(system: str, user_message: str, output_format: type[T], max_tokens: int = 4096) -> LlmCallResult:
    start = time.perf_counter()
    last_error: Exception | None = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        response = _client.models.generate_content(
            model=settings.google_model,
            contents=user_message,
            config=types.GenerateContentConfig(
                system_instruction=system,
                response_mime_type="application/json",
                response_schema=output_format,
                max_output_tokens=max_tokens,
            ),
        )

        finish_reason = None
        if response.candidates:
            raw_reason = getattr(response.candidates[0], "finish_reason", None)
            finish_reason = getattr(raw_reason, "name", raw_reason)  # enum -> str if needed

        if finish_reason in BLOCKED_FINISH_REASONS:
            raise LlmOutputError(f"Gemini blocked the request (finish_reason={finish_reason})")

        if response.parsed is not None:
            usage = response.usage_metadata
            return LlmCallResult(
                parsed=response.parsed,
                input_tokens=usage.prompt_token_count or 0,
                output_tokens=usage.candidates_token_count or 0,
                latency_ms=(time.perf_counter() - start) * 1000,
            )

        last_error = LlmOutputError(
            f"Gemini response didn't parse into {output_format.__name__} "
            f"(finish_reason={finish_reason}, attempt {attempt}/{MAX_ATTEMPTS})"
        )

    raise last_error
