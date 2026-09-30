from typing import Literal
from uuid import UUID

from pydantic import Field

from ..base import CreatorDTO


class ProjectCreateRequest(CreatorDTO):
    workspace_id: UUID
    brand_id: UUID | None = None
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    status: Literal["ACTIVE", "ARCHIVED"] = "ACTIVE"
    metadata: dict[str, object] = Field(default_factory=dict)
