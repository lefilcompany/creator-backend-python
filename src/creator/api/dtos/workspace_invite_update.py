from datetime import datetime

from pydantic import Field

from .base import CreatorDTO


class WorkspaceInviteUpdateRequest(CreatorDTO):
    role: str | None = Field(default=None, max_length=20)
    email: str | None = None
    max_uses: int | None = Field(default=None, ge=1)
    expires_at: datetime | None = None
    is_active: bool | None = None
