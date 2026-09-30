from pydantic import Field

from ..base import CreatorDTO


class AssetUpdateRequest(CreatorDTO):
    asset_type: str | None = Field(default=None, min_length=1, max_length=100)
    public_url: str | None = Field(default=None, max_length=2048)
    metadata: dict[str, object] | None = None
