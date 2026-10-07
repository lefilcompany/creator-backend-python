from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class OrderRecord:
    id: UUID
    billing_account_id: UUID
    workspace_id: UUID
    credit_package_id: UUID | None
    subtotal_cents: int
    discount_cents: int
    amount_cents: int
    currency: str
    status: str
    closed: bool
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


class OrderRepository(Protocol):
    def list_for_user(self, *, user_id: UUID) -> list[OrderRecord]: ...
    def get_for_user(self, *, user_id: UUID, order_id: UUID) -> OrderRecord | None: ...
    def add(self, *, fields: dict[str, object]) -> OrderRecord: ...
    def update(self, *, order_id: UUID, fields: dict[str, object]) -> OrderRecord: ...
    def soft_delete(self, *, order_id: UUID) -> None: ...


@dataclass(frozen=True, slots=True)
class CouponRedemptionRecord:
    id: UUID
    coupon_id: UUID
    billing_account_id: UUID
    order_id: UUID | None
    subscription_id: UUID | None
    discount_percent_applied: float | None
    discount_amount_cents: int | None
    credits_applied: int | None
    status: str
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


class CouponRedemptionRepository(Protocol):
    def list_for_user(self, *, user_id: UUID) -> list[CouponRedemptionRecord]: ...
    def get_for_user(
        self, *, user_id: UUID, redemption_id: UUID
    ) -> CouponRedemptionRecord | None: ...
    def add(self, *, fields: dict[str, object]) -> CouponRedemptionRecord: ...
    def update(
        self, *, redemption_id: UUID, fields: dict[str, object]
    ) -> CouponRedemptionRecord: ...
    def soft_delete(self, *, redemption_id: UUID) -> None: ...


@dataclass(frozen=True, slots=True)
class WorkspaceCreditTransactionRecord:
    id: UUID
    workspace_id: UUID
    amount: int
    transaction_type: str
    reference_type: str | None
    reference_id: UUID | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


class WorkspaceCreditTransactionRepository(Protocol):
    def list_for_user(
        self, *, user_id: UUID, workspace_id: UUID | None = None
    ) -> list[WorkspaceCreditTransactionRecord]: ...
    def get_for_user(
        self, *, user_id: UUID, transaction_id: UUID
    ) -> WorkspaceCreditTransactionRecord | None: ...
    def add(self, *, fields: dict[str, object]) -> WorkspaceCreditTransactionRecord: ...
    def soft_delete(self, *, transaction_id: UUID) -> None: ...
