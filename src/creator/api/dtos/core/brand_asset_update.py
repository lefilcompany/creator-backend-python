from pydantic import Field

from ..base import CreatorDTO


class BrandAssetUpdateRequest(CreatorDTO):
    type: str | None = Field(default=None, min_length=1, max_length=30)
    file_url: str | None = Field(default=None, min_length=1, max_length=2048)
    file_name: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=500)
