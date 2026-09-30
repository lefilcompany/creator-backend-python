from typing import Literal

from pydantic import Field

from ..base import CreatorDTO


class SettingsUpdateRequest(CreatorDTO):
    brand_name: str | None = Field(default=None, max_length=255)
    segment: str | None = Field(default=None, max_length=255)
    tone: (
        Literal["professional", "friendly", "persuasive", "educational", "formal", "casual"] | None
    ) = None
    voice: str | None = Field(default=None, min_length=1, max_length=1_000)
    visual_style: Literal["photographic", "illustration", "product_render"] | None = None
    default_preferences: dict[str, object] | None = None
