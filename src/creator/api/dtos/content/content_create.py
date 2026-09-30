from typing import Literal
from uuid import UUID

from pydantic import Field

from ..base import CreatorDTO


class ContentCreateRequest(CreatorDTO):
    workspace_id: UUID
    planning_id: UUID | None = None
    brand_id: UUID | None = None
    project_id: UUID | None = None
    type: Literal["IMAGE", "TEXT"] = "IMAGE"
    title: str | None = Field(default=None, max_length=255)
    payload: dict[str, object] = Field(default_factory=dict)
