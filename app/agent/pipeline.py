"""Orchestrates the four agent-loop steps plus the eval step, wrapping the
whole run with a RunTracker for observability. Plain Python - no framework,
per context.md."""

import time
from statistics import mean

from app.agent.eval import check_duplication, score_relevance
from app.agent.steps import (
    categorize_by_difficulty,
    dedupe_and_refine,
    generate_candidate_questions,
    plan_subtopics,
)
from app.observability.logging_utils import RunTracker, log_event
from app.rag.corpus import retrieve_reference_chunks
from app.schemas.pipeline import EvalReport, GenerateResult, RunMetrics

DEFAULT_TARGET_COUNT = 10
# Generate this many extra candidates - dedupe trims back down to target_count.
CANDIDATE_OVERGENERATION = 4


def run_pipeline(topic: str, target_count: int = DEFAULT_TARGET_COUNT) -> GenerateResult:
    tracker = RunTracker()
    overall_start = time.perf_counter()

    rag_start = time.perf_counter()
    reference_chunks = retrieve_reference_chunks(topic, k=4)
    tracker.record_step("rag_retrieve", (time.perf_counter() - rag_start) * 1000)

    subtopics = plan_subtopics(topic, tracker)
    candidates = generate_candidate_questions(
        topic, subtopics, reference_chunks, target_count + CANDIDATE_OVERGENERATION, tracker
    )
    deduped = dedupe_and_refine(topic, candidates, target_count, tracker)
    final_set = categorize_by_difficulty(topic, deduped, tracker)

    relevance_scores = score_relevance(topic, final_set.questions, tracker)
    max_similarity, duplication_flagged = check_duplication(final_set.questions, tracker)

    total_latency_ms = (time.perf_counter() - overall_start) * 1000

    eval_report = EvalReport(
        average_relevance=round(mean(relevance_scores), 2) if relevance_scores else 0.0,
        relevance_scores=relevance_scores,
        max_pairwise_similarity=round(max_similarity, 4),
        duplication_flagged=duplication_flagged,
    )
    metrics = RunMetrics(
        total_latency_ms=round(total_latency_ms, 1),
        step_latencies_ms=tracker.step_latencies_ms,
        total_input_tokens=tracker.total_input_tokens,
        total_output_tokens=tracker.total_output_tokens,
    )

    log_event(
        "run_completed",
        topic=topic,
        question_count=len(final_set.questions),
        eval=eval_report.model_dump(),
        metrics=metrics.model_dump(),
    )

    return GenerateResult(
        topic=final_set.topic,
        questions=final_set.questions,
        eval=eval_report,
        metrics=metrics,
    )
