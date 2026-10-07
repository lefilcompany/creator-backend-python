from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class BrandColorRecord:
    id: UUID
    brand_id: UUID
    workspace_id: UUID
    created_by: UUID
    order: int
    color_name: str | None
    hex_code: str | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


class BrandColorRepository(Protocol):
    def list_for_user(
        self, *, user_id: UUID, brand_id: UUID | None = None
    ) -> list[BrandColorRecord]: ...
    def get_for_user(self, *, user_id: UUID, color_id: UUID) -> BrandColorRecord | None: ...
    def add(self, *, fields: dict[str, object]) -> BrandColorRecord: ...
    def update(self, *, color_id: UUID, fields: dict[str, object]) -> BrandColorRecord: ...
    def soft_delete(self, *, color_id: UUID) -> None: ...
