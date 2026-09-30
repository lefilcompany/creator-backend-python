from pydantic import Field

from ..base import CreatorDTO


class PlanCreateRequest(CreatorDTO):
    code: str = Field(min_length=1, max_length=32)
    type: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=64)
    description: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)
    is_active: bool = True
