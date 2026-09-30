from typing import Literal
from uuid import UUID

from pydantic import Field

from ..base import CreatorDTO


class GenerateContentRequest(CreatorDTO):
    workspace_id: UUID
    topic: str = Field(min_length=1, max_length=255)
    audience: str = Field(min_length=1, max_length=255)
    tone: (
        Literal["professional", "friendly", "persuasive", "educational", "formal", "casual"] | None
    ) = None
    content_type: Literal[
        "social_post", "email", "ad_copy", "landing_page", "blog_post", "product_description"
    ]
    brand_voice: str | None = Field(default=None, min_length=1, max_length=1_000)
