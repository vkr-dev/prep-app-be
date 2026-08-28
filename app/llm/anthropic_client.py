"""The single point of contact with the LLM provider.

Swappable by design: every other module imports generate_questions() and the
GeneratedQuestionSet type, never the Anthropic SDK directly. To hand a cheap
step to a free-tier provider (Groq/Gemini) later, reimplement this function's
body against that SDK - callers don't change.
"""

from anthropic import Anthropic

from app.config import settings
from app.schemas.generate import GeneratedQuestionSet

_client = Anthropic(api_key=settings.anthropic_api_key)

SYSTEM_PROMPT = (
    "You are an expert technical interviewer. Given a topic, generate a "
    "structured set of interview questions with sample answers. Cover a "
    "range of difficulty (easy, medium, hard) and group questions into "
    "meaningful subtopic categories."
)


def generate_questions(topic: str, count: int = 10) -> GeneratedQuestionSet:
    """One Anthropic call, structured JSON out. No RAG/agent loop yet -
    Day 2 replaces this single call with the four-step pipeline (plan ->
    generate -> dedupe/refine -> categorize), each step reusing this same
    call-the-model pattern.
    """
    response = _client.messages.parse(
        model=settings.anthropic_model,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"Generate {count} interview questions for the topic: {topic}",
            }
        ],
        output_format=GeneratedQuestionSet,
    )
    return response.parsed_output
