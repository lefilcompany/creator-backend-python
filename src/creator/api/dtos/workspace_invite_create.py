from datetime import datetime
from uuid import UUID

from pydantic import Field

from .base import CreatorDTO


class WorkspaceInviteCreateRequest(CreatorDTO):
    workspace_id: UUID
    type: str = Field(min_length=1, max_length=10)
    role: str = Field(min_length=1, max_length=20)
    email: str | None = None
    max_uses: int | None = Field(default=None, ge=1)
    expires_at: datetime | None = None
