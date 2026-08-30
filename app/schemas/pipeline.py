from pydantic import BaseModel, Field

from app.schemas.generate import Difficulty, Question


class SubtopicPlan(BaseModel):
    """Output of the plan step - agent loop step 1."""

    subtopics: list[str] = Field(description="4-6 concise, non-overlapping subtopics covering the topic")


class QuestionBatch(BaseModel):
    """Output of a plain question-generation call (candidate generation, or
    the dedupe step's top-up call) - no topic field, just the questions."""

    questions: list[Question]


class CategoryLabel(BaseModel):
    """One question's normalized labels - index-based so the categorize
    step can never alter question/answer text, only relabel it."""

    index: int
    category: str
    difficulty: Difficulty


class CategorizationResult(BaseModel):
    labels: list[CategoryLabel]


class RelevanceScores(BaseModel):
    """Output of the LLM-as-judge eval call. One score per question, same
    order as the input question list."""

    scores: list[int] = Field(description="Relevance score 1-5 per question, same order as input")


class EvalReport(BaseModel):
    average_relevance: float
    relevance_scores: list[float]
    max_pairwise_similarity: float
    duplication_flagged: bool


class RunMetrics(BaseModel):
    total_latency_ms: float
    step_latencies_ms: dict[str, float]
    total_input_tokens: int
    total_output_tokens: int


class SubtopicContent(BaseModel):
    """Reading content for one subtopic - shown above that subtopic's
    accordion of practice questions, so there's real explanatory material
    to read end-to-end before self-testing, not just an isolated Q&A list.
    Empty/absent for LLM-pipeline results for now (the agent loop doesn't
    generate this) - only populated for curated content, see
    scripts/seed_curated_topics.py. The frontend simply skips rendering the
    reading section when a subtopic has no matching entry here."""

    subtopic: str
    content: str


class GenerateResult(BaseModel):
    """The full response shape for POST /api/generate - the question set
    plus the eval and observability data the UI surfaces alongside it."""

    topic: str
    questions: list[Question]
    subtopic_content: list[SubtopicContent] = []
    eval: EvalReport
    metrics: RunMetrics
    # True when this response came from the shared topic cache instead of a
    # fresh pipeline run - metrics reflect the cheap cache lookup, not the
    # original run's real cost.
    from_cache: bool = False
    # True for hand-authored content seeded directly into the DB (see
    # scripts/seed_curated_topics.py) - never ran the LLM pipeline at all,
    # not even once. Distinct from from_cache, which just means "not paid
    # for on this particular request" - curated content was never paid for.
    curated: bool = False
