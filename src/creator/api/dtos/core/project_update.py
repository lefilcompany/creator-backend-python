from typing import Literal

from pydantic import Field

from ..base import CreatorDTO


class ProjectUpdateRequest(CreatorDTO):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    status: Literal["ACTIVE", "ARCHIVED"] | None = None
    metadata: dict[str, object] | None = None
