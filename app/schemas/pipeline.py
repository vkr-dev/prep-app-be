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


class GenerateResult(BaseModel):
    """The full response shape for POST /api/generate - the question set
    plus the eval and observability data the UI surfaces alongside it."""

    topic: str
    questions: list[Question]
    eval: EvalReport
    metrics: RunMetrics
    # True when this response came from the shared topic cache instead of a
    # fresh pipeline run - metrics reflect the cheap cache lookup, not the
    # original run's real cost.
    from_cache: bool = False
