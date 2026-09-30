from typing import Any, Literal
from uuid import UUID

from pydantic import Field, model_validator

from ..base import CreatorDTO


class ImproveContentRequest(CreatorDTO):
    workspace_id: UUID
    text: str | None = Field(default=None, min_length=1, max_length=20_000)
    content_id: UUID | None = None
    objective: Literal["shorten", "persuasive", "formal", "seo", "audience_adaptation"]
    context: dict[str, Any] = Field(default_factory=dict)
    audience: str | None = Field(default=None, min_length=1, max_length=255)

    @model_validator(mode="after")
    def validate_target_and_context(self) -> "ImproveContentRequest":
        if (self.text is None) == (self.content_id is None):
            raise ValueError("Provide exactly one of text or content_id")
        if self.objective == "audience_adaptation" and self.audience is None:
            raise ValueError("audience is required for audience_adaptation")
        return self
