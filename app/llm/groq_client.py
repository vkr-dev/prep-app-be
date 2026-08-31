"""Groq implementation of call_structured() - a third free-tier swap-in slot
(explicitly named in context.md as a candidate). Selected when
LLM_PROVIDER=3 - see app/llm/client.py. Same interface as the other two
providers (same LlmCallResult, same LlmOutputError).

Groq's API is OpenAI-compatible: chat.completions.create() with a
response_format of {"type": "json_schema", "json_schema": {...}}. Its
strict JSON-schema mode requires two things Pydantic's model_json_schema()
doesn't set automatically, both injected here:

1. additionalProperties: false on every object in the schema, including
   nested $defs (confirmed live: without it, Groq returns a 400 naming the
   exact $defs path that's missing it).
2. Every property listed in that object's `required` array - including
   ones with a Python-side default value. Pydantic's default schema
   generation omits a field from `required` whenever it has a default
   (correctly, from a plain-JSON-Schema perspective), but Groq's strict
   mode rejects that outright: it demands every property be required, with
   no concept of "optional with a default" at the schema level (confirmed
   live: a schema with one defaulted field, like TopicSafetyResult's
   `reason: str = Field(default="")`, failed with "the following
   properties must be listed in required"). The Python-side default still
   works exactly as before for any other caller of that same model - this
   only affects the schema shown to Groq, not the model's own semantics.

Default model is qwen/qwen3.6-27b, not one of the openai/gpt-oss-* models
also available on this account - both gpt-oss-120b and gpt-oss-20b were
tried live and sometimes wrap a QuestionBatch response in an extra array
(Groq's own server-side schema validation correctly rejects it with a 400),
where qwen/qwen3.6-27b consistently returned the schema correctly across
the same test. If GROQ_MODEL is changed, re-verify against a real
multi-item nested schema, not just a trivial flat one - the failure mode
only showed up on QuestionBatch's list-of-objects shape.

The free tier's 8000 tokens/minute cap is a *rolling* window shared across
every call in a pipeline run, not a per-call budget - clamping max_tokens
per call (below) isn't enough on its own, since plan -> generate ->
categorize -> eval can cumulatively exceed it within the same run
(confirmed live: a run failed on its 3rd call, citing tokens already used
by the earlier two). A 429 here retries after the wait Groq itself reports
(via the Retry-After header), rather than failing the request outright.
"""

import time
from typing import Any, TypeVar

from groq import Groq, RateLimitError
from pydantic import BaseModel

from app.config import settings
from app.llm.types import LlmCallResult, LlmOutputError

_client = Groq(api_key=settings.groq_api_key)

T = TypeVar("T", bound=BaseModel)

MAX_ATTEMPTS = 2

# Blocked, not retryable - mirrors Anthropic's refusal / Google's blocked
# finish reasons.
BLOCKED_FINISH_REASONS = {"content_filter"}

# Free tier caps at 8000 tokens/minute (input + output combined) on every
# model tried (confirmed live: gpt-oss-120b, gpt-oss-20b, and qwen3.6-27b
# all report the same ceiling via the x-ratelimit-limit-tokens header) - not
# model-specific, so switching models doesn't raise it. Callers may pass a
# higher max_tokens (needed for other providers with real headroom, e.g.
# Anthropic) - it's clamped here rather than in shared pipeline code, since
# this constraint is specific to this provider.
MAX_SAFE_TOKENS = 6000

# Don't wait indefinitely on a rate-limit retry - if Groq reports a wait
# longer than this, fail fast instead (the caller/route surfaces a clean
# 502 either way; this just bounds how long a single request can hang).
MAX_RATE_LIMIT_WAIT_SECONDS = 30.0


def _enforce_additional_properties_false(schema: Any) -> Any:
    if isinstance(schema, dict):
        if schema.get("type") == "object" or "properties" in schema:
            schema["additionalProperties"] = False
        for value in schema.values():
            _enforce_additional_properties_false(value)
    elif isinstance(schema, list):
        for item in schema:
            _enforce_additional_properties_false(item)
    return schema


def _enforce_all_properties_required(schema: Any) -> Any:
    """Groq's strict mode has no concept of an optional/defaulted property -
    every key in `properties` must also appear in `required`, recursively,
    including nested $defs. See the module docstring for why this doesn't
    change the Pydantic model's own Python-side default semantics."""
    if isinstance(schema, dict):
        if "properties" in schema:
            schema["required"] = list(schema["properties"].keys())
        for value in schema.values():
            _enforce_all_properties_required(value)
    elif isinstance(schema, list):
        for item in schema:
            _enforce_all_properties_required(item)
    return schema


def _retry_after_seconds(error: RateLimitError) -> float | None:
    header = error.response.headers.get("retry-after")
    if header is None:
        return None
    try:
        return float(header)
    except ValueError:
        return None


def call_structured(system: str, user_message: str, output_format: type[T], max_tokens: int = 4096) -> LlmCallResult:
    schema = _enforce_all_properties_required(_enforce_additional_properties_false(output_format.model_json_schema()))
    safe_max_tokens = min(max_tokens, MAX_SAFE_TOKENS)
    start = time.perf_counter()
    last_error: Exception | None = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = _client.chat.completions.create(
                model=settings.groq_model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_message},
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {"name": output_format.__name__, "schema": schema, "strict": True},
                },
                max_tokens=safe_max_tokens,
            )
        except RateLimitError as e:
            wait = _retry_after_seconds(e)
            if wait is None or wait > MAX_RATE_LIMIT_WAIT_SECONDS or attempt == MAX_ATTEMPTS:
                raise
            time.sleep(wait)
            continue

        choice = response.choices[0]
        if choice.finish_reason in BLOCKED_FINISH_REASONS:
            raise LlmOutputError(f"Groq blocked the request (finish_reason={choice.finish_reason})")

        content = choice.message.content
        if content:
            try:
                parsed = output_format.model_validate_json(content)
                return LlmCallResult(
                    parsed=parsed,
                    input_tokens=response.usage.prompt_tokens,
                    output_tokens=response.usage.completion_tokens,
                    latency_ms=(time.perf_counter() - start) * 1000,
                )
            except Exception as e:
                last_error = LlmOutputError(
                    f"Groq response didn't parse into {output_format.__name__} "
                    f"(finish_reason={choice.finish_reason}, attempt {attempt}/{MAX_ATTEMPTS}): {e}"
                )
                continue

        last_error = LlmOutputError(
            f"Groq response had no content (finish_reason={choice.finish_reason}, attempt {attempt}/{MAX_ATTEMPTS})"
        )

    raise last_error
