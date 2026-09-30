from pydantic import Field

from ..base import CreatorDTO


class GenerateTextRequest(CreatorDTO):
    prompt: str = Field(min_length=1, max_length=20_000)
    temperature: float = Field(default=0.7, ge=0, le=2)
