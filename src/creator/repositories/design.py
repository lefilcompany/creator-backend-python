from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class DesignStructureRecord:
    id: UUID
    post_structure_id: UUID
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


class DesignStructureRepository(Protocol):
    def list_for_user(self, *, user_id: UUID) -> list[DesignStructureRecord]: ...
    def get_for_user(self, *, user_id: UUID, design_id: UUID) -> DesignStructureRecord | None: ...
    def add(self, *, post_structure_id: UUID) -> DesignStructureRecord: ...
    def update(self, *, design_id: UUID, fields: dict[str, object]) -> DesignStructureRecord: ...
    def soft_delete(self, *, design_id: UUID) -> None: ...
