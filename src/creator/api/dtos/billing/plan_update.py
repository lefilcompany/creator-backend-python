from pydantic import Field

from ..base import CreatorDTO


class PlanUpdateRequest(CreatorDTO):
    type: str | None = Field(default=None, min_length=1, max_length=20)
    name: str | None = Field(default=None, min_length=1, max_length=64)
    description: str | None = None
    metadata: dict[str, object] | None = None
    is_active: bool | None = None
