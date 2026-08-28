"""The single point of contact with the LLM provider.

Swappable by design: every pipeline step calls call_structured() and never
imports the Anthropic SDK directly. To hand a step to a free-tier provider
(Groq/Gemini) later, reimplement this function's body against that SDK -
callers don't change.
"""

import time
from dataclasses import dataclass
from typing import TypeVar

from anthropic import Anthropic
from pydantic import BaseModel

from app.config import settings

_client = Anthropic(api_key=settings.anthropic_api_key)

T = TypeVar("T", bound=BaseModel)


@dataclass
class LlmCallResult:
    parsed: BaseModel
    input_tokens: int
    output_tokens: int
    latency_ms: float


def call_structured(system: str, user_message: str, output_format: type[T], max_tokens: int = 4096) -> LlmCallResult:
    """One Anthropic call, structured JSON out via messages.parse() - Claude's
    response is validated straight into output_format, no manual json.loads().
    Also captures latency and token usage for the caller to feed into a
    RunTracker (see app/observability/logging_utils.py).
    """
    start = time.perf_counter()
    response = _client.messages.parse(
        model=settings.anthropic_model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user_message}],
        output_format=output_format,
    )
    latency_ms = (time.perf_counter() - start) * 1000

    return LlmCallResult(
        parsed=response.parsed_output,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
        latency_ms=latency_ms,
    )
