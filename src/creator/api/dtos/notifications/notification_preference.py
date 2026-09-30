from pydantic import Field

from ..base import CreatorDTO


class NotificationPreferenceRequest(CreatorDTO):
    type: str = Field(min_length=1, max_length=30)
    channel: str = Field(min_length=1, max_length=10)
    is_enabled: bool = True
