from pydantic import BaseModel


class ProgressUpdateRequest(BaseModel):
    topic: str
    subtopic: str
    checked: bool


class ProgressResponse(BaseModel):
    # subtopic name -> checked. Absent keys mean "not yet marked" (false).
    progress: dict[str, bool]
