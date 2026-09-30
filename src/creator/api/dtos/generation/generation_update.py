from pydantic import Field

from ..base import CreatorDTO


class GenerationUpdateRequest(CreatorDTO):
    model: str | None = Field(default=None, min_length=1, max_length=255)
    prompt: str | None = Field(default=None, min_length=1, max_length=20_000)
    parameters: dict[str, object] | None = None
