from enum import Enum
from typing import List

from pydantic import BaseModel, Field


class Difficulty(str, Enum):
    easy = "easy"
    medium = "medium"
    hard = "hard"


class Question(BaseModel):
    category: str = Field(description="Subtopic this question belongs to, e.g. 'Joins', 'Indexing'")
    difficulty: Difficulty
    question: str
    answer: str


class GenerateRequest(BaseModel):
    topic: str = Field(min_length=1, max_length=200)


class GeneratedQuestionSet(BaseModel):
    """Validated shape returned by the LLM step. This is also the schema handed
    to client.messages.parse() as output_format - Claude's JSON response is
    validated against it directly, no manual json.loads() needed."""

    topic: str
    questions: List[Question]
