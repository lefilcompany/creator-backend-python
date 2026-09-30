from uuid import UUID

from pydantic import Field

from ..base import CreatorDTO


class NotificationCreateRequest(CreatorDTO):
    workspace_id: UUID
    type: str = Field(min_length=1, max_length=30)
    title: str = Field(min_length=1, max_length=150)
    body: str = Field(min_length=1, max_length=2000)
    payload: dict[str, object] = Field(default_factory=dict)
    resource_type: str | None = Field(default=None, max_length=40)
    resource_id: UUID | None = None
