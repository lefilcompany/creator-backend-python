from uuid import UUID

from pydantic import Field

from ..base import CreatorDTO


class AssetCreateRequest(CreatorDTO):
    workspace_id: UUID
    brand_id: UUID | None = None
    project_id: UUID | None = None
    content_id: UUID | None = None
    asset_type: str = Field(min_length=1, max_length=100)
    storage_path: str = Field(min_length=1, max_length=1024)
    public_url: str | None = Field(default=None, max_length=2048)
    mime_type: str = Field(min_length=1, max_length=100)
    byte_size: int = Field(ge=0)
    checksum: str | None = Field(default=None, max_length=255)
    metadata: dict[str, object] = Field(default_factory=dict)
