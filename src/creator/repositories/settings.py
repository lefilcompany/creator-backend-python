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
    preferences: JsonObject
    created_at: datetime
    updated_at: datetime


class SettingsRepository(Protocol):
    def get_by_user_id(self, user_id: UUID) -> SettingsRecord | None: ...

    def create_for_user(
        self,
        user_id: UUID,
        *,
        preferences: JsonObject | None = None,
    ) -> SettingsRecord: ...

    def upsert_preferences(self, user_id: UUID, preferences: JsonObject) -> SettingsRecord: ...

    def update_preferences(self, user_id: UUID, preferences: JsonObject) -> SettingsRecord: ...
