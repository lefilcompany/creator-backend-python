from typing import Literal
from uuid import UUID

from pydantic import Field

from ..base import CreatorDTO


class ImageWorkflowRequest(CreatorDTO):
    brand_id: UUID
    campaign: str = Field(min_length=1, max_length=4_000)
    persona: str = Field(min_length=1, max_length=2_000)
    quantity: int = Field(default=1, ge=1, le=20)
    extra_instructions: str | None = Field(default=None, max_length=4_000)
    human_review: Literal["AUTO", "OPTIONAL"] = "AUTO"
    max_refinements: int | None = Field(default=None, ge=0, le=10)
    extensions: dict[str, object] = Field(default_factory=dict)
