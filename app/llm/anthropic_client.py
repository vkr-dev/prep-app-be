"""Anthropic implementation of call_structured(). Selected when
LLM_PROVIDER=anthropic (the default) - see app/llm/client.py for how the
active provider is chosen. Every pipeline step imports call_structured from
app.llm.client, never from this module directly, so switching providers
never touches step code.
"""

import time
from typing import TypeVar

from anthropic import Anthropic
from pydantic import BaseModel

from app.config import settings
from app.llm.types import LlmCallResult, LlmOutputError

_client = Anthropic(api_key=settings.anthropic_api_key)

T = TypeVar("T", bound=BaseModel)

# One retry on a malformed/empty parse - observed live: messages.parse() can
# come back with parsed_output=None on a normal end_turn stop (no exception
# raised), not just on the truncated-JSON case that DOES raise. Rare, but
# real, so every step gets this for free rather than each needing its own
# try/except.
MAX_ATTEMPTS = 2


def call_structured(system: str, user_message: str, output_format: type[T], max_tokens: int = 4096) -> LlmCallResult:
    """One Anthropic call, structured JSON out via messages.parse() - Claude's
    response is validated straight into output_format, no manual json.loads().
    Also captures latency and token usage for the caller to feed into a
    RunTracker (see app/observability/logging_utils.py).
    """
    start = time.perf_counter()
    last_error: Exception | None = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        response = _client.messages.parse(
            model=settings.anthropic_model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user_message}],
            output_format=output_format,
        )

        # A refusal is a policy decision, not a transient glitch - retrying
        # the identical prompt won't help, so fail fast with the category
        # for debugging instead of burning the retry budget.
        if response.stop_reason == "refusal":
            category = getattr(response.stop_details, "category", None) if response.stop_details else None
            raise LlmOutputError(f"Claude refused the request (category={category})")

        if response.parsed_output is not None:
            return LlmCallResult(
                parsed=response.parsed_output,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                latency_ms=(time.perf_counter() - start) * 1000,
            )

        last_error = LlmOutputError(
            f"Claude response didn't parse into {output_format.__name__} "
            f"(stop_reason={response.stop_reason}, attempt {attempt}/{MAX_ATTEMPTS})"
        )

    raise last_error
