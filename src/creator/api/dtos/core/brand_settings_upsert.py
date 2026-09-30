from uuid import UUID

from pydantic import Field

from ..base import CreatorDTO


class BrandSettingsUpsertRequest(CreatorDTO):
    workspace_id: UUID
    voice_settings: dict[str, object] = Field(default_factory=dict)
    visual_settings: dict[str, object] = Field(default_factory=dict)
    generation_defaults: dict[str, object] = Field(default_factory=dict)
    metadata: dict[str, object] = Field(default_factory=dict)
