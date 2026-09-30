from uuid import UUID

from pydantic import Field

from ..base import CreatorDTO


class BrandAssetCreateRequest(CreatorDTO):
    brand_id: UUID
    type: str = Field(min_length=1, max_length=30)
    file_url: str = Field(min_length=1, max_length=2048)
    file_name: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=500)
