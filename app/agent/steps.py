"""The four typed steps of the agent loop: plan -> generate -> dedupe/refine
-> categorize. Each is its own function with its own prompt, and each is
Pydantic-validated at the boundary (call_structured() guarantees that via
messages.parse()).
"""

import time

from app.llm.client import call_structured
from app.observability.logging_utils import RunTracker, log_event
from app.rag.embeddings import cosine_similarity_matrix, embed_texts
from app.schemas.generate import GeneratedQuestionSet, Question
from app.schemas.pipeline import CategorizationResult, QuestionBatch, SubtopicContent, SubtopicContentBatch, SubtopicPlan

# Candidate questions whose cosine similarity to an already-kept question
# exceeds this are treated as near-duplicates and dropped. Tuned loosely -
# 1.0 is identical text, ~0.85+ is usually "same question, different words".
DEDUPE_SIMILARITY_THRESHOLD = 0.88


def plan_subtopics(topic: str, tracker: RunTracker, count: int = 5) -> list[str]:
    """Step 1: plan. Breaks the topic into subtopics so generation has an
    explicit outline to cover, instead of free-associating."""
    system = (
        "You are planning the structure of a technical interview question set. "
        "Given a topic, produce a list of concise, non-overlapping subtopics "
        "that together give comprehensive interview coverage of the topic."
    )
    user_message = f"Topic: {topic}\n\nProduce exactly {count} subtopics."

    result = call_structured(system, user_message, SubtopicPlan)
    tracker.record_llm_call("plan_subtopics", result.latency_ms, result.input_tokens, result.output_tokens)
    return result.parsed.subtopics


def generate_candidate_questions(
    topic: str,
    subtopics: list[str],
    reference_chunks: list[str],
    target_count: int,
    tracker: RunTracker,
) -> list[Question]:
    """Step 2: generate. RAG use #1 - reference_chunks (retrieved from the
    seed corpus by app.rag.corpus.retrieve_reference_chunks) ground the
    generation in accurate terminology. Over-generates relative to
    target_count since dedupe will remove some."""
    system = (
        "You are an expert technical interviewer. Generate interview questions "
        "with sample answers for the given topic, distributed across the given "
        "subtopics and spanning easy, medium, and hard difficulty. Ground your "
        "questions and answers in the provided reference material where "
        "relevant, but you are not limited to it."
    )
    reference_block = "\n".join(f"- {chunk}" for chunk in reference_chunks) or "(no reference material retrieved)"
    user_message = (
        f"Topic: {topic}\n"
        f"Subtopics to cover: {', '.join(subtopics)}\n\n"
        f"Reference material:\n{reference_block}\n\n"
        f"Generate {target_count} interview questions covering these subtopics."
    )

    # Generous headroom: answers run longer than expected in practice, and a
    # truncated JSON response fails Pydantic validation outright rather than
    # degrading gracefully - better to overpay a little than fail the run.
    result = call_structured(system, user_message, QuestionBatch, max_tokens=10000)
    tracker.record_llm_call("generate_candidates", result.latency_ms, result.input_tokens, result.output_tokens)
    return result.parsed.questions


def dedupe_and_refine(
    topic: str,
    candidates: list[Question],
    target_count: int,
    tracker: RunTracker,
) -> list[Question]:
    """Step 3: dedupe/refine. RAG use #2 - embeds each candidate question and
    greedily drops near-duplicates by cosine similarity (pure function, no
    LLM call). If dedup drops the count below target, one refine call tops
    it back up, explicitly told what's already covered so it doesn't just
    reintroduce the duplicates that were removed.

    If embedding fails (provider outage/quota, e.g. Google's separate
    embedding quota - see app/rag/embeddings.py), dedup is skipped rather
    than failing the whole generate request - a request should still
    return question, just without duplicate-filtering that one time,
    consistent with RAG retrieval's degrade-not-crash behavior."""
    start = time.perf_counter()
    try:
        vectors = embed_texts([q.question for q in candidates])
        similarity = cosine_similarity_matrix(vectors)
    except Exception as e:
        log_event("dedupe_embedding_failed", topic=topic, error=str(e))
        tracker.record_step("dedupe", (time.perf_counter() - start) * 1000)
        return candidates[:target_count]

    kept: list[Question] = []
    kept_indices: list[int] = []
    for i, question in enumerate(candidates):
        is_duplicate = any(similarity[i, j] > DEDUPE_SIMILARITY_THRESHOLD for j in kept_indices)
        if not is_duplicate:
            kept.append(question)
            kept_indices.append(i)
    tracker.record_step("dedupe", (time.perf_counter() - start) * 1000)

    if len(kept) >= target_count:
        return kept[:target_count]

    missing = target_count - len(kept)
    system = (
        "You are an expert technical interviewer refining a question set. "
        "Generate additional interview questions with sample answers for the "
        "given topic that do NOT overlap in substance with the questions "
        "already in the set."
    )
    existing_block = "\n".join(f"- {q.question}" for q in kept) or "(none yet)"
    user_message = (
        f"Topic: {topic}\n\nQuestions already in the set:\n{existing_block}\n\n"
        f"Generate {missing} new, distinct questions to add to the set."
    )

    result = call_structured(system, user_message, QuestionBatch, max_tokens=6000)
    tracker.record_llm_call("refine_topup", result.latency_ms, result.input_tokens, result.output_tokens)
    return (kept + result.parsed.questions)[:target_count]


def categorize_by_difficulty(topic: str, questions: list[Question], tracker: RunTracker) -> GeneratedQuestionSet:
    """Step 4: categorize. Normalizes category names into a small consistent
    taxonomy and re-verifies each question's difficulty against the whole
    set. The LLM only returns index + labels (CategorizationResult), never
    question/answer text, so it cannot accidentally rewrite content -
    labels are remapped onto the original Question objects locally."""
    system = (
        "You review a set of technical interview questions. Normalize the "
        "category labels into a small, consistent set of subtopic names "
        "(merge near-duplicate categories), and verify each question's "
        "difficulty (easy/medium/hard) is accurate relative to the whole set, "
        "adjusting where needed. Return one label per question, by index, in "
        "the same order as given."
    )
    questions_block = "\n".join(
        f"{i}. [{q.category} / {q.difficulty.value}] {q.question}" for i, q in enumerate(questions)
    )
    user_message = f"Topic: {topic}\n\nQuestions:\n{questions_block}"

    result = call_structured(system, user_message, CategorizationResult)
    tracker.record_llm_call("categorize", result.latency_ms, result.input_tokens, result.output_tokens)

    labels_by_index = {label.index: label for label in result.parsed.labels}
    relabeled = [
        question.model_copy(
            update={
                "category": labels_by_index[i].category,
                "difficulty": labels_by_index[i].difficulty,
            }
        )
        if i in labels_by_index
        else question
        for i, question in enumerate(questions)
    ]
    return GeneratedQuestionSet(topic=topic, questions=relabeled)


def explain_subtopics(
    topic: str,
    subtopics: list[str],
    reference_chunks: list[str],
    tracker: RunTracker,
) -> list[SubtopicContent]:
    """Step 5: explain. Runs after categorize, against the FINAL, normalized
    subtopic names (not the plan step's initial guess) so every content
    entry's key matches a real question category the frontend groups by -
    an LLM-backed search should read the same way a curated one does:
    explanatory content first, practice questions in the accordion after,
    not just an isolated Q&A list. Falls back to an empty list (never
    raises) on failure - a search should still return its questions even
    if the explanatory writeup couldn't be generated that one time; the
    frontend already tolerates a subtopic having no reading content."""
    system = (
        "You are an expert technical educator. For each of the given subtopics "
        "of the given technical topic, write a clear, thorough explanation "
        "(2 short paragraphs) suitable for someone learning the concept from "
        "scratch - as if it were the reading material in a study guide, read "
        "before attempting practice questions on that subtopic. Ground your "
        "explanation in the provided reference material where relevant, but "
        "you are not limited to it. Return exactly one entry per subtopic, in "
        "the same order given, with the subtopic field matching the given name "
        "exactly."
    )
    reference_block = "\n".join(f"- {chunk}" for chunk in reference_chunks) or "(no reference material retrieved)"
    user_message = (
        f"Topic: {topic}\n"
        f"Subtopics: {', '.join(subtopics)}\n\n"
        f"Reference material:\n{reference_block}"
    )

    try:
        result = call_structured(system, user_message, SubtopicContentBatch, max_tokens=4000)
    except Exception as e:
        log_event("explain_subtopics_failed", topic=topic, error=str(e))
        return []

    tracker.record_llm_call("explain_subtopics", result.latency_ms, result.input_tokens, result.output_tokens)
    return result.parsed.contents
