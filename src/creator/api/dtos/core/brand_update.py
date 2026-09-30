from pydantic import Field

from ..base import CreatorDTO


class BrandUpdateRequest(CreatorDTO):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    brand_voice: str | None = None
    metadata: dict[str, object] | None = None
