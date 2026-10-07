from uuid import UUID

from pydantic import Field

from ..base import CreatorDTO


class NotificationUpdateRequest(CreatorDTO):
    title: str | None = Field(default=None, min_length=1, max_length=150)
    body: str | None = Field(default=None, min_length=1, max_length=2000)
    payload: dict[str, object] | None = None
    resource_type: str | None = Field(default=None, max_length=40)
    resource_id: UUID | None = None
