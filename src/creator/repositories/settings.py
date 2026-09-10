from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from creator.repositories.common import JsonObject


@dataclass(frozen=True, slots=True)
class SettingsRecord:
    id: UUID
    user_id: UUID
    brand_name: str | None
    segment: str | None
    tone: str
    voice: str
    visual_style: str
    default_preferences: JsonObject
    created_at: datetime
    updated_at: datetime


class SettingsRepository(Protocol):
    def get_by_user_id(self, user_id: UUID) -> SettingsRecord | None: ...

    def get_or_create_for_user(self, user_id: UUID) -> SettingsRecord: ...

    def create_for_user(
        self,
        user_id: UUID,
        *,
        brand_name: str | None = None,
        segment: str | None = None,
        tone: str = "professional",
        voice: str = "Clear and useful",
        visual_style: str = "photographic",
        default_preferences: JsonObject | None = None,
    ) -> SettingsRecord: ...

    def update_partial(self, user_id: UUID, changes: JsonObject) -> SettingsRecord: ...
