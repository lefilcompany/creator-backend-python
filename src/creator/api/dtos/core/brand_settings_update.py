from ..base import CreatorDTO


class BrandSettingsUpdateRequest(CreatorDTO):
    voice_settings: dict[str, object] | None = None
    visual_settings: dict[str, object] | None = None
    generation_defaults: dict[str, object] | None = None
    metadata: dict[str, object] | None = None
