"""Structured JSON logging to stdout, plus a RunTracker that accumulates
per-step timing and token usage across one pipeline run.

Deliberately plain: one logger, one JSON-per-line format, no framework. Swap
in Langfuse later by adding a second sink inside log_event() - callers don't
change.
"""

import json
import logging
import sys
import time
from dataclasses import dataclass, field

logger = logging.getLogger("prep_app")


def configure_json_logging() -> None:
    """Call once at app startup."""
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if logger.handlers:
        return  # avoid duplicate handlers when --reload re-imports this module
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)


def log_event(event: str, **fields) -> None:
    record = {"event": event, "ts": round(time.time(), 3), **fields}
    logger.info(json.dumps(record, default=str))


@dataclass
class StepTiming:
    step: str
    latency_ms: float
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class RunTracker:
    """One instance per /api/generate call. Each pipeline step reports into
    it; the pipeline reads it back at the end to build RunMetrics for the
    API response and to log the final run_completed event."""

    steps: list[StepTiming] = field(default_factory=list)

    def record_step(self, step: str, latency_ms: float) -> None:
        """A pure-function step with no LLM call (e.g. dedupe, eval's
        duplication check)."""
        self.steps.append(StepTiming(step=step, latency_ms=latency_ms))
        log_event("step_completed", step=step, latency_ms=round(latency_ms, 1))

    def record_llm_call(self, step: str, latency_ms: float, input_tokens: int, output_tokens: int) -> None:
        self.steps.append(StepTiming(step, latency_ms, input_tokens, output_tokens))
        log_event(
            "step_completed",
            step=step,
            latency_ms=round(latency_ms, 1),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    @property
    def total_input_tokens(self) -> int:
        return sum(s.input_tokens for s in self.steps)

    @property
    def total_output_tokens(self) -> int:
        return sum(s.output_tokens for s in self.steps)

    @property
    def step_latencies_ms(self) -> dict[str, float]:
        return {s.step: round(s.latency_ms, 1) for s in self.steps}
