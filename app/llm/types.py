"""Shared across every provider implementation (anthropic_client.py,
google_client.py, ...) so callers depend on one return type and one error
type regardless of which provider is active - see app/llm/client.py.
"""

from dataclasses import dataclass

from pydantic import BaseModel


@dataclass
class LlmCallResult:
    parsed: BaseModel
    input_tokens: int
    output_tokens: int
    latency_ms: float


class LlmOutputError(Exception):
    """The LLM responded but never gave us usable structured output - a
    safety refusal/block, or a parse failure that survived a retry."""
