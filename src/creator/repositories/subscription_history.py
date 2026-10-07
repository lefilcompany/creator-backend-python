from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class SubscriptionHistoryRecord:
    id: UUID
    subscription_id: UUID
    change_type: str
    previous_plan_id: UUID | None
    plan_id: UUID | None
    previous_status: str | None
    status: str | None
    reason: str | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


class SubscriptionHistoryRepository(Protocol):
    def list_for_user(self, *, user_id: UUID) -> list[SubscriptionHistoryRecord]: ...
    def get_for_user(
        self, *, user_id: UUID, history_id: UUID
    ) -> SubscriptionHistoryRecord | None: ...
    def add(self, *, fields: dict[str, object]) -> SubscriptionHistoryRecord: ...
    def update(
        self, *, history_id: UUID, fields: dict[str, object]
    ) -> SubscriptionHistoryRecord: ...
    def soft_delete(self, *, history_id: UUID) -> None: ...
