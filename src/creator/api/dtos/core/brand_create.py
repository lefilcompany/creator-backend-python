from uuid import UUID

from pydantic import Field

from ..base import CreatorDTO


class BrandCreateRequest(CreatorDTO):
    workspace_id: UUID
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    brand_voice: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)
