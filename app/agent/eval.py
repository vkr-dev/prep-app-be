"""Eval step: LLM-as-judge relevance scoring + embedding-based duplication
check. Runs after the pipeline's own steps finish - purely to report
quality metrics. Nothing here mutates the question set (that's the dedupe
step's job); this is observability, not enforcement.
"""

import time

from app.llm.client import call_structured
from app.observability.logging_utils import RunTracker, log_event
from app.rag.embeddings import cosine_similarity_matrix, embed_texts
from app.schemas.generate import Question
from app.schemas.pipeline import RelevanceScores

# Reported, not enforced - a run above this is flagged as likely having
# near-duplicate questions the dedupe step's threshold let slip through.
DUPLICATION_FLAG_THRESHOLD = 0.9


def score_relevance(topic: str, questions: list[Question], tracker: RunTracker) -> list[float]:
    system = (
        "You are grading a set of technical interview questions for relevance "
        "to the given topic. Score each question 1-5: 5 = highly relevant and "
        "well-targeted, 1 = off-topic or nonsensical."
    )
    questions_block = "\n".join(f"{i}. {q.question}" for i, q in enumerate(questions))
    user_message = f"Topic: {topic}\n\nQuestions:\n{questions_block}\n\nScore all {len(questions)} questions."

    result = call_structured(system, user_message, RelevanceScores)
    tracker.record_llm_call("eval_relevance", result.latency_ms, result.input_tokens, result.output_tokens)

    scores = result.parsed.scores
    if len(scores) != len(questions):
        # Judge miscounted - pad/truncate rather than fail the whole run
        # over a scoring quirk.
        scores = (scores + [3] * len(questions))[: len(questions)]
    return [float(s) for s in scores]


def check_duplication(questions: list[Question], tracker: RunTracker) -> tuple[float, bool]:
    """Pure function - no LLM call. Reuses the same embedding function as
    the agent's dedupe step (RAG use #2) to report the worst-case pairwise
    similarity across the final set. This is eval - a report, not
    enforcement - so an embedding failure degrades to "nothing flagged"
    rather than failing the whole generate request."""
    start = time.perf_counter()
    if len(questions) < 2:
        tracker.record_step("eval_duplication", (time.perf_counter() - start) * 1000)
        return 0.0, False

    try:
        vectors = embed_texts([q.question for q in questions])
    except Exception as e:
        log_event("eval_duplication_embedding_failed", error=str(e))
        tracker.record_step("eval_duplication", (time.perf_counter() - start) * 1000)
        return 0.0, False

    similarity = cosine_similarity_matrix(vectors)
    n = len(questions)
    max_similarity = max(similarity[i, j] for i in range(n) for j in range(n) if i != j)
    tracker.record_step("eval_duplication", (time.perf_counter() - start) * 1000)

    return float(max_similarity), bool(max_similarity > DUPLICATION_FLAG_THRESHOLD)
