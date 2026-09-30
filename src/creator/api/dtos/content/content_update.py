from uuid import UUID

from pydantic import Field

from ..base import CreatorDTO


class ContentUpdateRequest(CreatorDTO):
    brand_id: UUID | None = None
    project_id: UUID | None = None
    title: str | None = Field(default=None, max_length=255)
    payload: dict[str, object] | None = None
