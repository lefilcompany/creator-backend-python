from pydantic import Field

from ..base import CreatorDTO


class UserDeviceUpdateRequest(CreatorDTO):
    platform: str | None = Field(default=None, min_length=1, max_length=10)
    fcm_token: str | None = Field(default=None, min_length=1, max_length=255)
    is_active: bool | None = None
