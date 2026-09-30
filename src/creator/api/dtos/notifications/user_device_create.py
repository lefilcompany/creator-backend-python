from pydantic import Field

from ..base import CreatorDTO


class UserDeviceCreateRequest(CreatorDTO):
    platform: str = Field(min_length=1, max_length=10)
    fcm_token: str = Field(min_length=1, max_length=255)
