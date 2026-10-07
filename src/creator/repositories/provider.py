from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class RefundRecord:
    id: UUID
    billing_account_id: UUID
    invoice_id: UUID | None
    amount_cents: int
    currency: str
    reason: str | None
    status: str
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


class RefundRepository(Protocol):
    def list_for_user(self, *, user_id: UUID) -> list[RefundRecord]: ...
    def get_for_user(self, *, user_id: UUID, refund_id: UUID) -> RefundRecord | None: ...
    def add(self, *, fields: dict[str, object]) -> RefundRecord: ...
    def update(self, *, refund_id: UUID, fields: dict[str, object]) -> RefundRecord: ...
    def soft_delete(self, *, refund_id: UUID) -> None: ...


@dataclass(frozen=True, slots=True)
class ProviderDisputeRecord:
    id: UUID
    billing_account_id: UUID
    charge_id: UUID | None
    code: str | None
    reason: str | None
    status: str
    opened_at: datetime | None
    deadline_at: datetime | None
    payload: dict[str, object]
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


class ProviderDisputeRepository(Protocol):
    def list_for_user(self, *, user_id: UUID) -> list[ProviderDisputeRecord]: ...
    def get_for_user(self, *, user_id: UUID, dispute_id: UUID) -> ProviderDisputeRecord | None: ...
    def add(self, *, fields: dict[str, object]) -> ProviderDisputeRecord: ...
    def update(self, *, dispute_id: UUID, fields: dict[str, object]) -> ProviderDisputeRecord: ...
    def soft_delete(self, *, dispute_id: UUID) -> None: ...
