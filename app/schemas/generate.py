from enum import Enum
from typing import List

from pydantic import BaseModel, Field, field_validator

MAX_TOPIC_WORDS = 50


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
    topic: str = Field(min_length=1, max_length=400)

    @field_validator("topic")
    @classmethod
    def limit_words(cls, v: str) -> str:
        # min_length=1 above only rejects a truly empty string - "   " has
        # length 3 and would otherwise pass straight through.
        if not v.strip():
            raise ValueError("Topic cannot be blank")
        word_count = len(v.split())
        if word_count > MAX_TOPIC_WORDS:
            raise ValueError(f"Topic must be {MAX_TOPIC_WORDS} words or fewer (got {word_count})")
        return v


class GeneratedQuestionSet(BaseModel):
    """Validated shape returned by the LLM step. This is also the schema handed
    to client.messages.parse() as output_format - Claude's JSON response is
    validated against it directly, no manual json.loads() needed."""

    topic: str
    questions: List[Question]
